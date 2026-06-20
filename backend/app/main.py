import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import auth, datasets, forecast, export # , policy
from app.config import settings
from app.services.forecast_client import close_client #, verify_model_service_connectivity


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    
    # Programmatic override to silence SQL logging if configured
    if not settings.LOG_SQL:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        
    # Optional: Verify model service is up on startup
    # await verify_model_service_connectivity()
    
    try:
        yield
    finally:
        # This block runs when the application is shutting down
        logging.info("Shutting down: Closing HTTPX forecast client...")
        await close_client()
        logging.info("HTTPX client closed successfully.")


app = FastAPI(title="FMCG Sales Forecast API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], # Permission granted here
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# app.include_router(auth.router)
# app.include_router(datasets.router)
# app.include_router(forecast.router)
# app.include_router(export.router)

# Centralized API Router to handle common prefixes
api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(datasets.router)
api_router.include_router(forecast.router)
api_router.include_router(export.router)
# api_router.include_router(policy.router)

app.include_router(api_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
