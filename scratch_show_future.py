import os, sys
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
import argparse
# Parse command-line arguments
parser = argparse.ArgumentParser(description="Run ForecastEngine with configurable inputs")
parser.add_argument("--model_service_dir", default="model-service",
                    help="Relative path to the model-service directory")
parser.add_argument("--data_file", default="test_data_small.csv",
                    help="CSV file containing training data")
parser.add_argument("--seasonality", type=int, default=52,
                    help="Seasonality period for future generation")
parser.add_argument("--num_periods_to_predict", type=int, default=3,
                    help="Number of future periods to generate")
parser.add_argument("--aggregation", type=str, default="mean",
                    help="Aggregation method for future generation")
parser.add_argument("--confidence_level", type=float, default=0.95,
                    help="Confidence level for future generation")
parser.add_argument("--model_type", type=str, default="ExtraTrees",
                    help="Model type for future generation")
parser.add_argument("--force_retrain", type=bool, default=False,
                    help="Force retrain the model")
parser.add_argument("--date_format", type=str, default=None,
                    help="Date format for future generation")
parser.add_argument("--original_filename", type=str, default=None,
                    help="Original filename for future generation")
parser.add_argument("--additional_params", type=dict, default=None,
                    help="Additional parameters for future generation")
parser.add_argument("--columns_to_keep", nargs="+",
                    default=[
                        'date', 'product_identifier', 'sell_price', 'outlet', 
                        'department_identifier', 'category_of_product', 'state', 'sales_prediction'
                    ],
                    help="List of columns to keep in the future dataframe")
parser.add_argument("--preview_rows", type=int, default=20,
                    help="Number of head/tail rows to preview in the console output")
args = parser.parse_args()

# Add model-service to python path using the provided argument
sys.path.append(os.path.join(os.getcwd(), args.model_service_dir))
from app.models import ForecastEngine

# Initialise engine and load reference data
engine = ForecastEngine()
engine.load_reference_data()

# Path to the sample CSV (adjust via --data-file argument)
file_path = os.path.join(os.getcwd(), args.data_file)

# ------------------------------------------------------------------
# 1. Train the model (force retrain) and obtain training matrices
# ------------------------------------------------------------------
# train() returns (is_trained, (X, y))
_is_trained, (X, y) = engine.train(
    file_path=file_path,
    force_retrain=args.force_retrain,
    date_format=args.date_format,
    seasonality_period=args.seasonality,
)

# Ensure the model is instantiated and fitted (train() does NOT fit the model yet)
if engine.model is None:
    engine.model = ExtraTreesRegressor(
        n_estimators=100, max_features=None, verbose=0, n_jobs=-1
    )
    engine.model.fit(X, y)

print(X.head(args.preview_rows).to_string())
print(y.head(args.preview_rows).to_string())

# ------------------------------------------------------------------
# 2. Generate future skeleton and attach predictions
# ------------------------------------------------------------------
future = engine._generate_future_records(num_periods=args.num_periods_to_predict, seasonality_period=args.seasonality)

# Align future columns with the training feature columns
X_future = future.reindex(columns=engine.feature_columns, fill_value=0)

# Predict sales for the future periods
future["sales_prediction"] = engine.model.predict(X_future)

# Filter the future DataFrame to include only the requested columns
columns_to_keep = []
for col in args.columns_to_keep:
    columns_to_keep.extend([c.strip() for c in col.split(',') if c.strip()])
future = future[[col for col in columns_to_keep if col in future.columns]]


print(f'---feature columns ({len(engine.feature_columns)}): {engine.feature_columns}')
print(f'---future columns ({len(future.columns)}): {future.columns.tolist()}')

# ------------------------------------------------------------------
# 3. Show the resulting DataFrame
# ------------------------------------------------------------------
print(f'---future Len={len(future)} Lines...{__file__}....')
print(future.head(args.preview_rows).to_string())
print(future.tail(args.preview_rows).to_string())

