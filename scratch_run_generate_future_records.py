import os
import sys
import pandas as pd

# Add model-service to python path
sys.path.append(os.path.join(os.getcwd(), "model-service"))

from app.models import ForecastEngine

# Instantiate engine
engine = ForecastEngine()

# Load reference data
engine.load_reference_data()

# Load small training data
file_path = "test_data_small.csv"
if not os.path.exists(file_path):
    file_path = os.path.join("model-service", "reference", "test_data_small.csv")

print(f"Loading data from: {file_path}")

# Run data preparation to populate max_date, detected_freq, product_outlet_map, label_encoders
df_features = engine._prepare_training_data(file_path)

# Generate future records
future_df = engine._generate_future_records(num_periods=3, seasonality_period=12)

print("\n--- Columns in future_df ---")
print(future_df.columns.tolist())

print("\n--- Shape of future_df ---")
print(future_df.shape)

print("\n--- First 10 rows of future_df ---")
print(future_df.head(10).to_string())

print("\n--- Last 10 rows of future_df ---")
print(future_df.tail(10).to_string())