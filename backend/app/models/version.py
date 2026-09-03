import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.custom_types import UTCDateTime


class PredictionVersion(Base):
    __tablename__ = "prediction_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    forecast_id: Mapped[str] = mapped_column(String, ForeignKey("forecast_results.id"))
    dataset_id: Mapped[str] = mapped_column(String, ForeignKey("datasets.id"))
    dataset_name: Mapped[str] = mapped_column(String)
    version_label: Mapped[str] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    parameters_json: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
