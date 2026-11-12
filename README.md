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

Brug `POST /transactions` til at gemme en udgift, `GET /transactions` til at hente alle udgifter, `GET /transactions?category=Mad` til at hente udgifter i én kategori, `GET /transactions/summary?year=2026&month=11` til at hente en månedsopsummering med kategori-fordeling, `GET /transactions/{id}` til at hente én udgift, `PUT /transactions/{id}` til at rette en udgift og `DELETE /transactions/{id}` til at slette en udgift. Data bliver i Lakebase efter genstart af appen.
