import os
import pandas as pd
from model_service.app.models import ForecastEngine

# Initialize engine and load reference data
engine = ForecastEngine()
engine.load_reference_data()

# Path to sample dataset (adjust if needed)
file_path = os.path.join(os.getcwd(), "test_data_small.csv")

# Run prediction (force retrain for demonstration)
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

# Print the list of detailed records (the loop you asked about)
print(result.get("detailed_records", []))
