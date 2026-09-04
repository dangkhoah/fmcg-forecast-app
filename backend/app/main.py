import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db, async_session
from app.routers import auth, datasets, forecast, export, train, training_history, schedules, versions
from app.config import settings
from app.services.forecast_client import close_client

async def run_due_schedules():
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.models.schedule import ScheduleConfig
    from app.models.training import TrainingHistory

    now = datetime.now(timezone.utc)
    async with async_session() as db:
        try:
            result = await db.execute(
                select(ScheduleConfig).where(
                    ScheduleConfig.is_active == True,
                    ScheduleConfig.next_run_at <= now,
                )
            )
            due = result.scalars().all()
        except Exception as e:
            logging.error(f"Schedule check query failed: {e}")
            return

        for schedule in due:
            logging.info(f"Running schedule: {schedule.name}")
            schedule.last_run_at = now
            schedule.next_run_at = _compute_next_run(schedule)
            await db.commit()

            try:
                import httpx
                import json as _json
                from app.config import settings as _settings

                models = _json.loads(schedule.models_json)
                params = _json.loads(schedule.hyper_params_json)

                async with httpx.AsyncClient(timeout=None) as client:
                    for model_name in models:
                        payload = {
                            "dataset_id": schedule.dataset_id,
                            "model_name": model_name,
                            "hyper_params": params,
                            "seasonality_period": schedule.seasonality_period,
                            "date_format": schedule.date_format,
                        }
                        try:
                            resp = await client.post(
                                f"{_settings.MODEL_SERVICE_URL}/train",
                                json=payload,
                                headers={"Accept": "text/event-stream"},
                            )
                            resp.raise_for_status()
                            line_buffer = ""
                            mape_val = None
                            training_time_val = None
                            async for chunk in resp.aiter_bytes():
                                line_buffer += chunk.decode()
                                lines = line_buffer.split("\n")
                                line_buffer = lines.pop() if lines else ""
                                for ln in lines:
                                    if ln.startswith("data: "):
                                        try:
                                            evt = _json.loads(ln[6:])
                                            if evt.get("done"):
                                                mape_val = evt.get("mape")
                                                training_time_val = evt.get("training_time")
                                        except _json.JSONDecodeError:
                                            pass
                            record = TrainingHistory(
                                user_id=schedule.user_id,
                                dataset_id=schedule.dataset_id,
                                dataset_name=schedule.dataset_name,
                                model_name=model_name,
                                hyper_params_json=_json.dumps(params),
                                mape=mape_val,
                                training_time=training_time_val,
                                status="completed" if mape_val is not None else "failed",
                            )
                            db.add(record)
                            await db.commit()
                        except Exception as e:
                            logging.error(f"Schedule model {model_name} failed: {e}")
            except Exception as e:
                logging.error(f"Schedule run failed: {e}")


def _compute_next_run(schedule):
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    base = now.replace(hour=schedule.hour, minute=schedule.minute, second=0, microsecond=0)
    if base <= now:
        base += timedelta(days=1)
    if schedule.schedule_type == "daily":
        return base
    elif schedule.schedule_type == "weekly" and schedule.day_of_week is not None:
        days_ahead = (schedule.day_of_week - base.weekday()) % 7
        return base + timedelta(days=days_ahead)
    elif schedule.schedule_type == "monthly" and schedule.day_of_month is not None:
        try:
            if base.day > schedule.day_of_month:
                if base.month == 12:
                    base = base.replace(year=base.year + 1, month=1, day=schedule.day_of_month)
                else:
                    base = base.replace(month=base.month + 1, day=schedule.day_of_month)
            else:
                base = base.replace(day=schedule.day_of_month)
        except ValueError:
            base = base.replace(day=28)
        return base
    return base + timedelta(days=1)


scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    if not settings.LOG_SQL:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    global scheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            run_due_schedules,
            trigger="interval",
            minutes=1,
            id="check_schedules",
            replace_existing=True,
        )
        scheduler.start()
        logging.info("Scheduler started.")
    except ImportError:
        logging.warning("APScheduler not installed; scheduled training disabled.")

    try:
        yield
    finally:
        if scheduler and scheduler.running:
            scheduler.shutdown(wait=False)
            logging.info("Scheduler shut down.")
        logging.info("Shutting down: Closing HTTPX forecast client...")
        await close_client()
        logging.info("HTTPX client closed successfully.")


app = FastAPI(title="FMCG Sales Forecast API", lifespan=lifespan)

origins = [o.strip() for o in settings.CORS_ORIGINS.split(",")] if settings.CORS_ORIGINS else ["*"]
if "http://localhost:3000" not in origins and "*" not in origins:
    origins.extend(["http://localhost:3000", "http://127.0.0.1:3000"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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
api_router.include_router(train.router)
api_router.include_router(training_history.router)
api_router.include_router(schedules.router)
api_router.include_router(versions.router)
# api_router.include_router(policy.router)

app.include_router(api_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
