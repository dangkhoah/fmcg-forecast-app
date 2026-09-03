import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.custom_types import UTCDateTime


class ScheduleConfig(Base):
    __tablename__ = "schedule_configs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String)
    dataset_id: Mapped[str] = mapped_column(String, ForeignKey("datasets.id"))
    dataset_name: Mapped[str] = mapped_column(String)
    models_json: Mapped[str] = mapped_column(Text)
    hyper_params_json: Mapped[str] = mapped_column(Text, default="{}")
    seasonality_period: Mapped[int] = mapped_column(Integer, default=52)
    date_format: Mapped[str | None] = mapped_column(String, nullable=True)
    schedule_type: Mapped[str] = mapped_column(String)
    day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hour: Mapped[int] = mapped_column(Integer, default=0)
    minute: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
