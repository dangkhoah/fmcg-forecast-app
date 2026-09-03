import os
import pandas as pd
from model_service.app.models import ForecastEngine

# Initialise engine and load reference data
engine = ForecastEngine()
engine.load_reference_data()

# Path to sample CSV (adjust if needed)
file_path = os.path.join(os.getcwd(), "test_data_small.csv")

# Run the full prediction pipeline (force retrain for demo)
result = engine.predict(
    file_path=file_path,
    forecast_periods=4,
    seasonality_period=52,
    confidence_level=0.95,
    aggregation="mean",
    model_type="ExtraTrees",
    frequency=None,
    force_retrain=True,
    date_format=None,
)

# Print the detailed records produced by the loop inside predict()
print(result.get("detailed_records", []))
