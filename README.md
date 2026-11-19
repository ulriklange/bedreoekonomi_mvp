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

Den første webside leveres af FastAPI selv. Den viser den valgte måneds indtægter, udgifter, netto og kategoriopdeling fra `GET /transactions/summary`. Vælg en anden måned i månedsvælgeren for at hente en ny rapport.

Beløb gemmes med bankens fortegn: negative beløb er udgifter, positive beløb er indtægter. Månedsopsummeringen viser udgifter, indtægter og netto separat.

Brug `GET /categories` til at hente bankens underkategorier og `GET /category-hierarchy` til at hente underkategorier grupperet under deres hovedkategori. `POST /transactions` gemmer en transaktion ved at angive dens underkategori i feltet `category`; API'et sætter den tilhørende hovedkategori. Lakebase og transaktionssvar indeholder både `main_category` og `category`.

Importen omfatter bankens indtægtskategorier `Anden indtægt`, `Løn, dagpenge og pension`, `Offentlige ydelser` og `Indtægter (Andet)`. Ukategoriserede overførsler registreres også. Kontonavn og en hash-baseret kontoidentifikation følger med hver importeret postering; råt kontonummer gemmes ikke.

`GET /transactions/summary?year=2026&month=11` returnerer udgifter, indtægter og netto for én måned. `GET /transactions/history?from_date=2026-01-01&to_date=2026-11-12` returnerer månedlige summer for et datointerval og markerer delvise måneder. I begge rapporter grupperes `main_categories` på hovedkategori med underkategorier indlejret. Hovedkategorien `Indgår ikke i budget og forbrug` returneres særskilt som `excluded_from_budget` og medregnes ikke i de samlede beløb. Kategorierne `Andet (Overførsel)` og `Ingen kategori (Overførsel)` gemmes som posteringer, men udelades fra rapporternes totaler. `GET /transactions` henter alle transaktioner, `GET /transactions?category=Dagligvarer` henter transaktioner i én underkategori, `GET /transactions/{id}` henter én transaktion, `PUT /transactions/{id}` retter en transaktion og `DELETE /transactions/{id}` sletter en transaktion. Data bliver i Lakebase efter genstart af appen.

## Første månedsprognose

`GET /forecast/monthly?forecast_year=2026&forecast_month=12&history_from=2026-01-01&history_to=2026-10-31` beregner en enkel baseline ved at tage gennemsnittet pr. måned over hele historikperioden. Historikken skal bestå af mindst tre hele kalendermåneder. Udgifter, indtægter og netto beregnes pr. hoved- og underkategori; poster uden for budgettet holdes ude. Prognosen tager ikke højde for sæsonudsving eller kendte fremtidige regninger.

## Import af bankens CSV

CSV-filen læses lokalt. Importen bruger `Dato`, `Tekst`, `Beløb`, `Kontonummer`, `Kontonavn`, `Hovedkategori` og `Kategori`. Kontonavnet og en hash-baseret kontoidentifikation gemmes; råt kontonummer og saldo gemmes ikke. Start altid med en forhåndsvisning fra projektets rodmappe:

```powershell
python -m scripts.import_bank_csv "C:\Users\ulrik\Downloads\din-fil.csv" --preview
```

Når forhåndsvisningen melder, at alle rækker er gyldige, kan filen synkroniseres med `--apply`. Importen opretter et fingeraftryk ud fra kontonummer, dato, tekst, beløb og saldo, men råt kontonummer og saldo gemmes ikke. Første synkronisering matcher de eksisterende rækker fra den oprindelige import og tilføjer fingeraftryk og konto-oplysninger til dem. Senere synkroniseringer springer uændrede rækker over, tilføjer nye og opdaterer kontooplysninger og hoved- og underkategori, hvis banken har ændret kategoriseringen. Kategoriskift vises også i terminalen. En manuel kategorirettelse i appen bliver derfor overskrevet næste gang CSV'en synkroniseres med bankens kategori.
