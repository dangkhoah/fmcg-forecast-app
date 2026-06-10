import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, ForeignKey, Float, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ForecastResult(Base):
    __tablename__ = "forecast_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # u_id: Mapped[str] = mapped_column("user_id", String, ForeignKey("users.id")) # "user_id" tells SQLAlchemy the actual name of the column in the table, while your Python code would use .u_id
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    dataset_id: Mapped[str] = mapped_column(String, ForeignKey("datasets.id"))
    parameters_json: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ForecastScenario(Base):
    __tablename__ = "forecast_scenarios"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    dataset_id: Mapped[str] = mapped_column(String, ForeignKey("datasets.id"))
    name: Mapped[str] = mapped_column(String)
    parameters_json: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
