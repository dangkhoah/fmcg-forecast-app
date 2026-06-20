import os
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import time, logging
from joblib import Memory
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

# Initialize Disk Cache at module level to ensure stable hashing (avoids hashing mutable 'self' state)
cache_dir = os.path.join(os.path.dirname(__file__), "..", "cache")
memory = Memory(cache_dir, verbose=0)

# Global flag to indicate if we're in training mode (used for logging inside the cached function)
# IS_TRAINING_MODE = False

class ForecastEngine:
    """
    Engine responsible for training ML models and generating sales forecasts.
    
    Uses an ExtraTreesRegressor ensemble to handle non-linear relationships
    in FMCG data such as seasonality and price elasticity.
    """
    def __init__(self):
        self.model = None
        self.label_encoders = {}
        self.feature_columns = None
        self.product_outlet_map = None
        self.prod_price = None
        self.date_week = None
        self.best_model_name = "ExtraTrees"
        self._last_trained_file = None
        self.mape = None
        self.cached = True  # Indicates if reference data has been loaded
        # Use ISO-week semantics (weeks start on Monday) internally.
        # For frontend compatibility we may normalize this when returning results.
        self.detected_freq = "W-MON"

    def load_reference_data(self, ref_dir: str = None):
        """
        Loads auxiliary CSV files for pricing and calendar mapping.
        
        Args:
            ref_dir: Path to the directory containing reference files.
        """
        
        if ref_dir is None:
            ref_dir = os.path.join(os.path.dirname(__file__), "..", "reference")
        ref_dir = Path(ref_dir)
        ref_dir.mkdir(exist_ok=True)

        price_path = ref_dir / "product_prices.csv"
        week_path = ref_dir / "date_to_week_id_map.csv"

        if price_path.exists():
            self.prod_price = pd.read_csv(
                price_path,
                names=["outlet", "product_identifier", "week_id", "sell_price"],
                header=0,
            )
        else:
            logger.warning(f"Reference file not found: {price_path}. Price-related features will be disabled.")

        if week_path.exists():
            # parse_dates ensures the "date" column is converted to datetime64[ns] on load
            self.date_week = pd.read_csv(
                week_path,
                names=["date", "week_id"],
                header=0,
                parse_dates=["date"],
                dayfirst=False  # Explicitly handle US/ISO date formats
            )
        else:
            logger.warning(f"Reference file not found: {week_path}. Calendar-related features will be disabled.")

    def _prepare_training_data(self, file_path: str, date_format: str | None = None, seasonality_period: int = 12) -> pd.DataFrame:
        """
        Cleans raw input data and merges it with reference datasets.
        
        Args:
            file_path: The absolute path to the training CSV/Excel file.
            date_format: Optional strftime format string for date parsing.
            seasonality_period: The length of the seasonal cycle (e.g., 52 for yearly in weekly data).
            
        Returns:
            A DataFrame containing engineered features and the target 'sales' column.
        """
        if file_path.lower().endswith((".xls", ".xlsx")):
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path)

        # Ensure date column exists and is converted to datetime
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], format=date_format)
        else:
            raise ValueError("Uploaded dataset must contain a 'date' column")

        # Detect dataset frequency automatically
        try:
            temp_dates = pd.DatetimeIndex(sorted(df["date"].unique()))
            inferred = pd.infer_freq(temp_dates)
            if inferred:
                # If pandas reports a weekly frequency, normalize to Monday-start ISO weeks
                if isinstance(inferred, str) and inferred.startswith("W"):
                    self.detected_freq = "W-MON"
                else:
                    self.detected_freq = inferred
            else:
                # Heuristic fallback based on mode of day differences (useful if gaps exist)
                diffs = temp_dates.to_series().diff().dt.days.dropna()
                if not diffs.empty:
                    mode_diff = diffs.mode().iloc[0]
                    if mode_diff == 1: self.detected_freq = "D"
                    elif mode_diff == 7: self.detected_freq = "W-MON"
                    elif 28 <= mode_diff <= 31: self.detected_freq = "ME"
                    else: self.detected_freq = "W"
        except Exception:
            logger.error(f"Error occurred while detecting frequency for {file_path}")
            self.detected_freq = "W"

        if self.prod_price is not None and self.date_week is not None:
            # Ensure date in date_week is also datetime64[ns]
            self.date_week["date"] = pd.to_datetime(self.date_week["date"], format=date_format)
            merged = pd.merge(self.prod_price, self.date_week, on="week_id", how="inner")
            
            # Ensure product_identifier and outlet columns are typed correctly as numeric to avoid object/numeric merge conflicts
            df["product_identifier"] = pd.to_numeric(df["product_identifier"], errors="coerce")
            df["outlet"] = pd.to_numeric(df["outlet"], errors="coerce")
            merged["product_identifier"] = pd.to_numeric(merged["product_identifier"], errors="coerce")
            merged["outlet"] = pd.to_numeric(merged["outlet"], errors="coerce")

            df = pd.merge(df, merged, on=["date", "product_identifier", "outlet"], how="inner",)
        else:
            df["week_id"] = df["date"].dt.isocalendar().week.astype(int)

        self.max_date = df["date"].max()

        cat_cols = ["category_of_product", "state"]
        for col in cat_cols:
            if col in df.columns:
                df[col] = df[col].astype("category")

        le = LabelEncoder()
        df["state_encoded"] = le.fit_transform(df["state"].astype(str))
        self.label_encoders["state"] = le

        le = LabelEncoder()
        df["cat_prod_encoded"] = le.fit_transform(df["category_of_product"].astype(str))
        self.label_encoders["category_of_product"] = le

        df["Month"] = df["date"].dt.month

        # Engineer Seasonality Features
        week_val = df["date"].dt.isocalendar().week
        df["sin_season"] = np.sin(2 * np.pi * week_val / seasonality_period)
        df["cos_season"] = np.cos(2 * np.pi * week_val / seasonality_period)

        meta_cols = [
            "product_identifier", "outlet", "department_identifier",
            "category_of_product", "state", "cat_prod_encoded", "state_encoded"
        ]
        # Only select columns that actually exist in the uploaded file
        existing_meta = [c for c in meta_cols if c in df.columns]
        self.product_outlet_map = df[existing_meta].drop_duplicates().reset_index(drop=True)

        cols_to_drop = ["date", "week_id", "state", "category_of_product"]
        if "id" in df.columns:
            cols_to_drop.append("id")
        if "fold" in df.columns:
            cols_to_drop.append("fold")

        features = df.drop(columns=cols_to_drop, errors="ignore")
        self.feature_columns = [c for c in features.columns if c != "sales"]

        return features

    def train(self, file_path: str, date_format: str | None = None, seasonality_period: int = 12, force_retrain: bool = False):
        """
        Trains the ExtraTrees model on the provided dataset.
        
        Args:
            file_path: Path to the dataset.
            date_format: Optional strftime format string for date parsing.
            seasonality_period: Length of the cycle to encode.
            force_retrain: Whether to ignore cached model and retrain.
            
        Returns:
            bool: True if training occurred, False if cached model was used.
        """
        # Correct Caching Logic: 
        # Skip training only if not forced AND we actually have a model in memory for this file.
        # In a transient engine (from joblib miss), self.model is always None, so it will correctly train.
        if not force_retrain and self.model is not None: # self.model is always None in a transient engine, so this condition will be False, and training will occur.
            logger.info(f"⚡⚡ USING CACHED MODEL for {file_path} with model [{self.model}], skipping retraining.")
            return False, (None, None)

        data = self._prepare_training_data(file_path, date_format=date_format, seasonality_period=seasonality_period)
        X = data[self.feature_columns]
        y = data["sales"]

        # Calculate validation MAPE
        try:
            from sklearn.model_selection import train_test_split
            X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)
            eval_model = ExtraTreesRegressor(n_estimators=50, random_state=42, n_jobs=-1)
            eval_model.fit(X_train, y_train)
            val_preds = eval_model.predict(X_val)
            non_zero_mask = y_val != 0
            if non_zero_mask.any():
                self.mape = float(np.mean(np.abs((y_val[non_zero_mask] - val_preds[non_zero_mask]) / y_val[non_zero_mask])))
            else:
                self.mape = 0.0
        except Exception as e:
            logger.error(f"Error calculating MAPE: {e}")
            self.mape = None
        
        return True, (X, y)

    # Creating the "Future" Skeleton
    def _generate_future_records(self, num_periods: int, seasonality_period: int = 12) -> pd.DataFrame:
        """
        Generates a placeholder DataFrame for future dates to be predicted.
        
        Args:
            num_periods: Number of weeks to forecast.
            seasonality_period: Length of the cycle to encode.
            
        Returns:
            pd.DataFrame: A skeleton containing dates, products, and prices."""
        records = []
        last_date = getattr(self, "max_date", pd.Timestamp("2014-03-01"))
        freq = getattr(self, "detected_freq", "W")

        future_dates = pd.date_range(
            start=last_date,
            periods=num_periods + 1,
            freq=freq,
        )[1:] # Skip the first date as it is the last known date

        avg_price = self.prod_price["sell_price"].mean() if self.prod_price is not None else 0
        # Calculate avg price per product for more accurate baseline features
        prod_prices = {}
        if self.prod_price is not None:
            prod_prices = self.prod_price.groupby("product_identifier")["sell_price"].mean().to_dict()

        for date in future_dates:
            for _, row in self.product_outlet_map.iterrows():
                pid = row.get("product_identifier")
                record = {
                    "Month": date.month,
                    # "sell_price": avg_price,
                    "sell_price": prod_prices.get(pid, 0.0),
                    "date": date,
                    # Use ISO week number (Monday-start) for seasonal encoding
                    "sin_season": np.sin(2 * np.pi * date.isocalendar().week / seasonality_period),
                    "cos_season": np.cos(2 * np.pi * date.isocalendar().week / seasonality_period),
                }
                # Inject whatever metadata was found during training
                for col in self.product_outlet_map.columns:
                    record[col] = row[col]
                records.append(record)

        future_df = pd.DataFrame(records)
        return future_df

    def _calculate_intervals(self, X: pd.DataFrame, confidence: float) -> tuple:
        """
        Calculates lower and upper bounds using ensemble variance.
        
        Args:
            X: The feature matrix for prediction.
            confidence: The confidence level (0.0 to 1.0).
            
        Returns:
            tuple: (lower_bounds, upper_bounds) as numpy arrays.
        """
        if not self.model or not hasattr(self.model, "estimators_"):
            return None, None
            
        # Collect predictions from every individual tree in the forest
        per_tree_preds = np.array([tree.predict(X.values) for tree in self.model.estimators_])
        
        # Calculate percentiles based on the confidence level
        lower_p = ((1.0 - confidence) / 2.0) * 100
        upper_p = (1.0 - (1.0 - confidence) / 2.0) * 100
        
        lower = np.percentile(per_tree_preds, lower_p, axis=0)
        upper = np.percentile(per_tree_preds, upper_p, axis=0)
        return lower, upper

    def predict(
        self,
        file_path: str,
        forecast_periods: int = 12,
        seasonality_period: int = 12,
        confidence_level: float = 0.95,
        aggregation: str = "mean",
        model_type: str = "ExtraTrees",
        frequency: str | None = None,
        force_retrain: bool = False,
        date_format: str | None = None,
    ) -> dict:
        """
        Public prediction interface with persistent disk caching.
        """
        if force_retrain:
            # Bypass cache and execute fresh
            # Pass force_retrain to _execute_predict_logic
            return self._execute_predict_logic(model_type, file_path, forecast_periods, seasonality_period, confidence_level, aggregation, frequency, date_format, force_retrain)

        # Call the standalone module-level function for caching to avoid hashing 'self'.
        # We pass the DataFrames as arguments; joblib hashes their content efficiently.
        result =  _run_forecast_pipeline_cached(model_type,
            file_path, forecast_periods, seasonality_period, 
            confidence_level, aggregation, frequency, date_format,
            self.prod_price, self.date_week,
            force_retrain # Pass force_retrain to the cached function
        )
        
        logger.info(f'ℹ️ Just before returning from predict(), RESULT["CACHED"]: {result.get("cached")}, training_time: {result.get("training_time", 0)}s, detected_freq: {result.get("detected_freq")}')
        
        if self.cached: # not cached mean no writing to disk, so we can set training_time to 0.0
            result["cached"] = True
            result["training_time"] = 0.0
        logger.info(f"⚡ USING CACHED MODE - self.cached (default): {self.cached}, RESULT[\"CACHED\"]: {result['cached']}, training_time: {result.get('training_time', 0):.2f}s, detected_freq: {result.get('detected_freq')}")
        return result
    
    def _execute_predict_logic(
        self,
        model_type: str,
        file_path: str,
        forecast_periods: int,
        seasonality_period: int,
        confidence_level: float,
        aggregation: str,
        frequency: str | None,
        date_format: str | None,
        force_retrain: bool # Add force_retrain to the signature
    ) -> dict:
        """
        Internal method that performs the actual heavy lifting.
        This is what joblib hashes and stores to disk.
        """
        # global IS_TRAINING_MODE
        start_train = time.time()
        # Since this method might be called in a new process or via cache miss, 
        # Pass the force_retrain value received by _execute_predict_logic to the train method to ensure it behaves correctly in both cached and non-cached scenarios.
        is_trained, (X, y) = self.train(file_path, date_format=date_format, seasonality_period=seasonality_period, force_retrain=force_retrain)

        self.cached = not is_trained # If we trained, then cached is False; if we didn't train (used cache), then cached is True
        logger.info(f"🟢 Training mode for {file_path}. Starting model training.")
        if frequency:
            self.detected_freq = frequency

        future = self._generate_future_records(forecast_periods, seasonality_period=seasonality_period)
        if future.empty:
            return {"dates": [], "values": [], "detailed_records": []}

        if model_type == "MovingAverage":
            # Load data to calculate historical averages
            data = self._prepare_training_data(file_path, date_format=date_format, seasonality_period=seasonality_period)
            # Calculate mean sales per product and outlet
            averages = data.groupby(["product_identifier", "outlet"])["sales"].mean().reset_index()
            averages.rename(columns={"sales": "sales_prediction"}, inplace=True)
            
            # Merge averages into the future skeleton
            future = pd.merge(future, averages, on=["product_identifier", "outlet"], how="left")
            # Fill products that might not have historical data with 0
            future["sales_prediction"] = future["sales_prediction"].fillna(0)
            
            # For Moving Average, we'll set bounds to the prediction (zero variance baseline)
            predictions = future["sales_prediction"].values
            future['lower'] = predictions
            future['upper'] = predictions
            is_trained = False # SMA doesn't "train" in the ML sense
            self.cached = False # Not training for Moving Average
            train_duration = 0.0
        else:
            # ExtraTrees path
            # Use reindex to ensure future data has exact same columns as training data, filling missing with 0
            X_future = future.reindex(columns=self.feature_columns, fill_value=0)

            if self.model is None or force_retrain: # If we're in training mode, we should fit the model regardless of self.model state
                self.model = ExtraTreesRegressor(
                    n_estimators=100, max_features=None, verbose=0, n_jobs=-1
                )
                self.model.fit(X, y)
                self._last_trained_file = file_path

            # pass this future data to self.model.predict()
            predictions = self.model.predict(X_future)
            future['sales_prediction'] = predictions
        
            # Calculate statistical bounds
            lower_bounds, upper_bounds = self._calculate_intervals(X_future, confidence_level)
            future['lower'] = lower_bounds if lower_bounds is not None else predictions
            future['upper'] = upper_bounds if upper_bounds is not None else predictions

        # Format as a list of detailed records (rows)
        records = []
        for _, row in future.iterrows():
            prod_id = row.get("product_identifier", 0)
            outlet_id = row.get("outlet", 0)
            records.append({
                "date": row["date"].strftime("%Y-%m-%d"),
                "product_id": int(prod_id) if pd.notnull(prod_id) else 0,
                "outlet_id": int(outlet_id) if pd.notnull(outlet_id) else 0,
                "prediction": round(float(row["sales_prediction"]), 2)
            })

        # Aggregated data for the UI Chart
        if not future.empty:
            group = future.groupby("date")["sales_prediction"]
            group_l = future.groupby("date")["lower"]
            group_u = future.groupby("date")["upper"]
            chart_agg = group.sum().reset_index() if aggregation == "sum" else group.mean().reset_index()
            chart_agg["lower"] = group_l.sum().values if aggregation == "sum" else group_l.mean().values
            chart_agg["upper"] = group_u.sum().values if aggregation == "sum" else group_u.mean().values
        else:
            chart_agg = pd.DataFrame()
            
        if chart_agg.empty:
            return {"dates": [], "values": [], "detailed_records": records, "mape": self.mape}

        chart_agg["date_str"] = chart_agg["date"].dt.strftime("%Y-%m-%d")
        
        train_duration = time.time() - start_train if is_trained else 0

        logger.info(f"⏳ Predicting with model for {file_path}. Model: {self.model}, train_duration: {train_duration:.2f}, force_retrain: {force_retrain}, is_trained: {is_trained}, self.cached: {self.cached}")
        
        return {
            "dates": chart_agg["date_str"].tolist(),
            "values": chart_agg["sales_prediction"].round(2).tolist(),
            "lower_bound": chart_agg["lower"].round(2).tolist(),
            "upper_bound": chart_agg["upper"].round(2).tolist(),
            "detailed_records": records, # This stores the "multiple records"
            "cached": self.cached, # : not is_trained
            "detected_freq": ("W" if getattr(self, "detected_freq", "W-MON").startswith("W") else getattr(self, "detected_freq", "W-MON")),
            "training_time": round(train_duration, 2),
            "mape": self.mape
        }


# Standalone function to handle joblib disk caching without hashing the mutable engine instance.
# This function is only executed on a cache miss.
@memory.cache
def _run_forecast_pipeline_cached(model_type, file_path, forecast_periods, seasonality_period, 
    confidence_level, aggregation, frequency, date_format,prod_price, date_week,
    force_retrain # Add force_retrain to the cached function's signature
):
    logger.info("ℹ️ CACHE MISS: Executing _run_forecast_pipeline_cached. This should not appear on the second run.")
    
    # global IS_TRAINING_MODE
    # IS_TRAINING_MODE = True # Set global flag to indicate we're in training mode (used for logging inside the cached function)
    
    # Create a transient engine instance to perform the work using the provided maps.
    # This engine lives only for the duration of this call (Transient/Temporary  Engine) and is not the same as the long-lived engine instance used for caching logic.
    engine = ForecastEngine() # This is a new, blank engine that will be used for this specific prediction task. It will not retain any state after this function finishes, which is ideal for caching.
    # The reference dataframes (prod_price, date_week) that were passed as arguments are assigned to the prod_price and date_week attributes of this transient engine instance. This makes them available for methods like _prepare_training_data and _generate_future_records within this temporary engine.
    engine.prod_price = prod_price
    engine.date_week = date_week
    engine.cached = False # This transient engine is not using a cached model; it's a fresh instance for this specific prediction task.
    
    # Execute the internal logic. Note: force_retrain=True inside is correct here 
    # because we want this transient instance to fit the model if we've reached this point.
    return engine._execute_predict_logic(model_type, file_path, forecast_periods, seasonality_period, 
        confidence_level, aggregation, frequency, date_format,
        force_retrain # Pass force_retrain to _execute_predict_logic
    )
