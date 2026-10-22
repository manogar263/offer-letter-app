from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR, UPLOAD_DIR
from .database import Base, engine, migrate_sqlite_schema
from .routers import companies, letters

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
Base.metadata.create_all(bind=engine)
migrate_sqlite_schema(engine)

app = FastAPI(title="Offer Letter Generator")

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

app.include_router(companies.router)
app.include_router(letters.router)
