from fastapi import FastAPI

app = FastAPI(
    title="Bedre Økonomi API",
    description="API til Bedre Økonomi MVP.",
    version="0.1.0",
)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Return basic service status for local checks and monitoring."""
    return {"status": "ok"}
