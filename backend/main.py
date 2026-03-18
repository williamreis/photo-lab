from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from config import FRONTEND_DIR, UPLOADS_DIR
from routes import api_router

app = FastAPI(
    title="Photo Auto Retoucher API",
    description="API para retoque automático de fotos",
    version="0.1.0",
)

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

app.include_router(api_router)


@app.get("/api", include_in_schema=True)
def api_info():
    """Metadados da API (JSON)."""
    return {"message": "Photo Auto Retoucher API", "status": "ok", "ui": "/"}


@app.get("/health")
def health():
    """Health check para monitoramento."""
    return {"status": "healthy"}
