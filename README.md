# Bedre Økonomi MVP

FastAPI API til Bedre Økonomi. Transaktioner gemmes i Databricks Lakebase Postgres.

## Krav

- Python 3.10 eller nyere
- Databricks Lakebase-projekt med en Postgres-rolle til appen

## Lokal opsætning

Opret en lokal `user.env` i projektets rodmappe med disse værdier:

```env
DB_HOST=din-lakebase-host
DB_NAME=databricks_postgres
DB_USER=forbrug_api
DB_PASSWORD=din-adgangskode
DB_SSLMODE=require
```

`user.env` indeholder en hemmelighed. Git ignorerer den; commit eller del den aldrig.

Åbn en terminal i VS Code fra projektets rodmappe, aktivér dit virtuelle miljø, og kør:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Ved opstart opretter appen tabellen `transactions`, hvis den ikke findes.

Databaseforbindelsen ligger i `app/database.py`, Pydantic-modeller til datavalidering i `app/schemas.py`, SQL-operationer i `app/transactions_repository.py` og HTTP-ruterne i `app/main.py`.

- Health check: http://127.0.0.1:8000/health
- Interaktiv API-dokumentation: http://127.0.0.1:8000/docs
- Alternativ dokumentation: http://127.0.0.1:8000/redoc
- Første økonomioversigt: http://127.0.0.1:8000/

Den første webside leveres af FastAPI selv. Den viser faktiske indtægter, udgifter, netto og kategoriopdeling for indeværende eller tidligere måneder fra `GET /transactions/summary`. Vælges en fremtidig måned, bruger siden `GET /forecast/monthly` og viser et gennemsnit baseret på afsluttede måneder i indeværende dataår.

For indeværende måned viser dashboardet også et estimeret rådighedsbeløb: månedens netto til dato minus de registrerede faste betalinger, der forventes senere samme måned. Det er et budgetestimat, ikke kontosaldoen. Prognosen for fremtidige måneder vises separat og påvirker ikke rådighedsbeløbet; rådighedsbeløbskortet skjules ved visning af andre måneder.

Beløb gemmes med bankens fortegn: negative beløb er udgifter, positive beløb er indtægter. Månedsopsummeringen viser udgifter, indtægter og netto separat.

Brug `GET /categories` til at hente bankens underkategorier og `GET /category-hierarchy` til at hente underkategorier grupperet under deres hovedkategori. `POST /transactions` gemmer en transaktion ved at angive dens underkategori i feltet `category`; API'et sætter den tilhørende hovedkategori. Lakebase og transaktionssvar indeholder både `main_category` og `category`.

Importen omfatter bankens indtægtskategorier `Anden indtægt`, `Løn, dagpenge og pension`, `Offentlige ydelser` og `Indtægter (Andet)`. Ukategoriserede overførsler registreres også. Kontonavn og en hash-baseret kontoidentifikation følger med hver importeret postering; råt kontonummer gemmes ikke.

`GET /transactions/summary?year=2026&month=11` returnerer udgifter, indtægter og netto for én måned. `GET /transactions/history?from_date=2026-01-01&to_date=2026-11-12` returnerer månedlige summer for et datointerval og markerer delvise måneder. Løn i kategorien `Løn, dagpenge og pension`, hvis bogføringsdato falder på månedens sidste fem kalenderdage, henføres i rapporterne til den efterfølgende måned. Rå postering og bogføringsdato i Lakebase ændres ikke. I begge rapporter grupperes `main_categories` på hovedkategori med underkategorier indlejret. Hovedkategorien `Indgår ikke i budget og forbrug` returneres særskilt som `excluded_from_budget` og medregnes ikke i de samlede beløb. Kategorierne `Andet (Overførsel)` og `Ingen kategori (Overførsel)` gemmes som posteringer, men udelades fra rapporternes totaler. `GET /transactions` henter alle transaktioner, `GET /transactions?category=Dagligvarer` henter transaktioner i én underkategori, `GET /transactions/{id}` henter én transaktion, `PUT /transactions/{id}` retter en transaktion og `DELETE /transactions/{id}` sletter en transaktion. Data bliver i Lakebase efter genstart af appen.

## Første månedsprognose

`GET /forecast/monthly?forecast_year=2026&forecast_month=12&history_from=2024-01-01&history_to=2026-10-31` beregner først gennemsnittet for samme kalendermåned i de tidligere år, så fx et decemberforecast bygger på tidligere decembermåneder. Hvis historikken ikke indeholder den valgte kalendermåned, falder beregningen tilbage på gennemsnittet af hele historikperioden. I weboversigten bruges de seneste tre kalenderår frem til seneste afsluttede måned. Historikken skal bestå af mindst tre hele kalendermåneder. Første historikmåned udelades fra indtægtsgennemsnittet, da der kan mangle løn bogført sidst i måneden før historikperioden. Indtægter summeres først pr. rapportmåned på tværs af konti, og kun kategorierne `Offentlige ydelser` og `Løn, dagpenge og pension` indgår. Måneder uden posteringer tæller med som nul. Store enkeltudgifter kan udelades, hvis de ligger markant over kategorihistorien; hvis en underkategori har færre end fem udgifter, bruges hovedkategoriens udgifter som sammenligningsgrundlag. De udeladte poster returneres som `excluded_one_off_expenses` med beløbsgrænsen; de faktiske månedsrapporter og posteringer ændres ikke. Prognosen tager ikke højde for kendte fremtidige regninger.

`GET /forecast/upcoming-bills` leder i de seneste 365 dage efter mindst tre betalinger på samme konto og med samme modtagernavn, hvor alle intervaller er 25–35 dage. Mønstret skal også have en postering i indeværende eller foregående kalendermåned. Den viser et forventet beløb (gennemsnittet af de seneste tre beløb), forventet dato og betalingerne bag estimatet. Som standard vises de næste 45 dage; `days_ahead` kan sættes til 1–120. Det er et mønsterestimat, ikke en bekræftelse på en kommende regning, og første version finder kun månedlige betalinger.

## Cloudflare-deploy

Cloudflare Containers kan køre den eksisterende FastAPI-app med dens PostgreSQL-driver. Containeren bruger fortsat Lakebase som datalager; den lokale `user.env` er ikke en del af Docker-imaget. CSV-importen køres fortsat lokalt fra din egen computer.

Cloudflare Containers kræver Workers Paid, som starter ved 5 USD pr. måned; containerforbrug over planens inkluderede mængder kan koste ekstra. Første besøg starter containeren, og den går i dvale efter 10 minutters inaktivitet. Worker-koden afviser forespørgsler, der ikke er godkendt af Cloudflare Access, så økonomiappen ikke kan tilgås, før Access er slået til for Workeren.

Den nemmeste deployment er via **Workers Builds** fra dit GitHub-repo. Når deployfilerne er committed og pushed:

1. I Cloudflare: gå til **Workers & Pages** → **Create application** → vælg **GitHub**, og forbind repoet.
2. Vælg den branch, der indeholder deployfilerne, og brug repoets rodmappe. Navnet på Workeren skal være `bedre-oekonomi`.
3. Lad build-kommandoen være tom, og brug `npm run deploy` som deploy-kommando. Slå previews fra for denne første opsætning.
4. Når Workeren er oprettet, gå til **Settings → Variables & Secrets**. Tilføj `DB_HOST`, `DB_NAME`, `DB_USER` og `DB_PASSWORD` som **Secrets** med værdierne fra din lokale `user.env`.
5. Gå til Workeren → **Access** → **Protect this Worker behind Access**, vælg **All traffic**, og tillad kun de e-mailadresser, der skal kunne se budgettet. Cloudflare Access kan sende en engangskode på e-mail.

Før Access er slået til, afviser Workeren alle forespørgsler med `403` og videresender ikke trafik til økonomiappen. Du behøver ikke at sætte `DB_SSLMODE`; appen bruger automatisk `require`. CSV-importen køres fortsat lokalt.

## Import af bankens CSV

CSV-filen læses lokalt. Importen bruger `Dato`, `Tekst`, `Beløb`, `Kontonummer`, `Kontonavn`, `Hovedkategori` og `Kategori`. Kontonavnet og en hash-baseret kontoidentifikation gemmes; råt kontonummer og saldo gemmes ikke. Start altid med en forhåndsvisning fra projektets rodmappe:

```powershell
python -m scripts.import_bank_csv "C:\Users\ulrik\Downloads\din-fil.csv" --preview
```

Når forhåndsvisningen melder, at alle rækker er gyldige, kan filen synkroniseres med `--apply`. Importen opretter et fingeraftryk ud fra kontonummer, dato, tekst, beløb og saldo, men råt kontonummer og saldo gemmes ikke. Første synkronisering matcher de eksisterende rækker fra den oprindelige import og tilføjer fingeraftryk og konto-oplysninger til dem. Senere synkroniseringer springer uændrede rækker over, tilføjer nye og opdaterer kontooplysninger og hoved- og underkategori, hvis banken har ændret kategoriseringen. Kategoriskift vises også i terminalen. En manuel kategorirettelse i appen bliver derfor overskrevet næste gang CSV'en synkroniseres med bankens kategori.
