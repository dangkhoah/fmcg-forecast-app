import uuid
from datetime import datetime
from sqlalchemy import String, Float, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.custom_types import UTCDateTime


class TrainingHistory(Base):
    __tablename__ = "training_history"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    dataset_id: Mapped[str] = mapped_column(String, ForeignKey("datasets.id"))
    dataset_name: Mapped[str] = mapped_column(String)
    dataset_row_count: Mapped[int | None] = mapped_column(nullable=True)
    model_name: Mapped[str] = mapped_column(String)
    model_key: Mapped[str | None] = mapped_column(String, nullable=True)
    hyper_params_json: Mapped[str] = mapped_column(Text, default="{}")
    mape: Mapped[float | None] = mapped_column(Float, nullable=True)
    training_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, default="completed")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
