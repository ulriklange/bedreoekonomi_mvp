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

Beløb gemmes med bankens fortegn: negative beløb er udgifter, positive beløb er indtægter. Månedsopsummeringen viser udgifter, indtægter og netto separat.

Brug `GET /categories` til at hente bankens underkategorier og `GET /category-hierarchy` til at hente underkategorier grupperet under deres hovedkategori. `POST /transactions` gemmer en transaktion ved at angive dens underkategori i feltet `category`; API'et sætter den tilhørende hovedkategori. Lakebase og transaktionssvar indeholder både `main_category` og `category`.

Importen omfatter også bankens `Ingen kategori` under `Indgår ikke i budget og forbrug` samt `Anden indtægt` under `Indtægter`.

`GET /transactions/summary?year=2026&month=11` returnerer udgifter, indtægter og netto samlet, under `main_categories` grupperet på hovedkategori med underkategorier indlejret, samt `categories` som en flad liste over underkategorier. Hovedkategorien `Indgår ikke i budget og forbrug` returneres særskilt som `excluded_from_budget` og medregnes ikke i de samlede beløb. `GET /transactions` henter alle transaktioner, `GET /transactions?category=Dagligvarer` henter transaktioner i én underkategori, `GET /transactions/{id}` henter én transaktion, `PUT /transactions/{id}` retter en transaktion og `DELETE /transactions/{id}` sletter en transaktion. Data bliver i Lakebase efter genstart af appen.

## Import af bankens CSV

CSV-filen læses lokalt. Importen bruger `Dato`, `Tekst`, `Beløb`, `Hovedkategori` og `Kategori`; saldo og kontooplysninger gemmes ikke. Start altid med en forhåndsvisning fra projektets rodmappe:

```powershell
python -m scripts.import_bank_csv "C:\Users\ulrik\Downloads\din-fil.csv" --preview
```

Når forhåndsvisningen melder, at alle rækker er gyldige, kan filen synkroniseres med `--apply`. Importen opretter et fingeraftryk ud fra kontonummer, dato, tekst, beløb og saldo. Kun fingeraftrykket gemmes; kontonummer og saldo gemmes ikke. Første synkronisering matcher de eksisterende rækker fra den oprindelige import og tilføjer fingeraftryk til dem. Senere synkroniseringer springer uændrede rækker over, tilføjer nye og opdaterer hoved- og underkategori, hvis banken har ændret kategoriseringen. Kategoriskift vises også i terminalen. En manuel kategorirettelse i appen bliver derfor overskrevet næste gang CSV'en synkroniseres med bankens kategori.
