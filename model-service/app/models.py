import hashlib
import os
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import time, logging
from joblib import Memory
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.svm import SVR
from sklearn.model_selection import train_test_split
from joblib import dump, load
from sklearn.preprocessing import LabelEncoder

try:
    from xgboost import XGBRegressor
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

try:
    import lightgbm as lgb
    HAS_LGB = True
except ImportError:
    HAS_LGB = False

try:
    from prophet import Prophet
    HAS_PROPHET = True
except ImportError:
    HAS_PROPHET = False

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

# Initialize Disk Cache at module level to ensure stable hashing (avoids hashing mutable 'self' state)
cache_dir = os.path.join(os.path.dirname(__file__), "..", "cache")
memory = Memory(cache_dir, verbose=0)
CACHE_FUNC_DIR = os.path.join(cache_dir, "joblib", "app", "models", "_run_forecast_pipeline_cached")
# Global flag to detect pipeline cache HIT vs MISS.
# Set to True by _run_forecast_pipeline_cached when its body executes (MISS).
# Left unchanged on HIT (joblib returns stored result without executing body).
_pipeline_cache_missed = False

class ForecastEngine:
    """
    Engine responsible for training ML models and generating sales forecasts.
    
    Uses an ensemble or regression models to handle non-linear relationships
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
        self.training_metadata: dict = {}
        # New attribute for hyper‑parameters
        self.hyper_params: dict = {}
        # Use ISO-week semantics (weeks start on Monday) internally.
        # For frontend compatibility we may normalize this when returning results.
        self.detected_freq = "W-MON"  # "D"
        # Persistence setup
        self.model_path = os.path.join(os.path.dirname(__file__), "..", "cache", "forecast_engine.joblib")
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        if os.path.exists(self.model_path):
            try:
                persisted = load(self.model_path)
                self.model = persisted.get("model")
                self.feature_columns = persisted.get("feature_columns")
                self.label_encoders = persisted.get("label_encoders", {})
                self.product_outlet_map = persisted.get("product_outlet_map")
                self.detected_freq = persisted.get("detected_freq", self.detected_freq)
                self.mape = persisted.get("mape")
                self.cached = True
                logger.info(f"✅ Loaded persisted ForecastEngine model from {self.model_path}")
            except Exception as e:
                logger.warning(f"Failed to load persisted model: {e}")

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

    def _prepare_training_data(self, file_path: str, date_format: str | None = None, seasonality_period: int = 52) -> pd.DataFrame:
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
            logger.error(f"⚠️ Error occurred while detecting frequency for {file_path}")
            self.detected_freq = "W"
        
        # logger.warning(f"Detected frequency for {file_path}: {self.detected_freq}")

        if self.prod_price is not None and self.date_week is not None:
            date_week = self.date_week.copy()
            # Ensure date in date_week is also datetime64[ns]
            date_week["date"] = pd.to_datetime(date_week["date"], format=date_format)
            merged = pd.merge(self.prod_price, date_week, on="week_id", how="inner")
            
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
        logger.warning(f"✅ Product-outlet mapping created with {len(self.product_outlet_map)} unique combinations.")

        cols_to_drop = ["date", "week_id", "state", "category_of_product"]
        if "id" in df.columns:
            cols_to_drop.append("id")
        if "fold" in df.columns:
            cols_to_drop.append("fold")

        features = df.drop(columns=cols_to_drop, errors="ignore")
        self.feature_columns = [c for c in features.columns if c != "sales"]

        return features

    def _build_model(self):
        name = self.best_model_name
        hp = self.hyper_params or {}

        if name == "ExtraTrees":
            defaults = dict(n_estimators=100, max_features=None, bootstrap=True, oob_score=True, random_state=42, n_jobs=-1)
            return ExtraTreesRegressor(**{**defaults, **hp})
        elif name == "RandomForest":
            defaults = dict(n_estimators=100, max_depth=None, oob_score=True, random_state=42, n_jobs=-1)
            return RandomForestRegressor(**{**defaults, **hp})
        elif name == "XGBoost":
            if not HAS_XGB:
                raise ImportError("XGBoost is not installed. Run `pip install xgboost`.")
            defaults = dict(n_estimators=100, learning_rate=0.1, max_depth=6, random_state=42, n_jobs=-1)
            return XGBRegressor(**{**defaults, **hp})
        elif name == "LightGBM":
            if not HAS_LGB:
                raise ImportError("LightGBM is not installed. Run `pip install lightgbm`.")
            defaults = dict(n_estimators=100, learning_rate=0.1, num_leaves=31, random_state=42, n_jobs=-1, verbose=-1)
            return lgb.LGBMRegressor(**{**defaults, **hp})
        elif name == "SVM":
            defaults = dict(kernel='rbf', C=1.0, gamma='scale', epsilon=0.1)
            return SVR(**{**defaults, **hp})
        elif name == "Prophet":
            if not HAS_PROPHET:
                raise ImportError("Prophet is not installed. Run `pip install prophet`.")
            return None  # handled separately
        else:
            raise ValueError(f"Unknown model: {name}")

    def _compute_mape(self, y_true, y_pred):
        non_zero = y_true != 0
        if non_zero.any():
            return float(np.mean(np.abs((y_true[non_zero] - y_pred[non_zero]) / y_true[non_zero])))
        return 0.0

    def _compute_dataset_hash(self, file_path: str) -> str:
        try:
            with open(file_path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""

    def _gather_feature_importances(self):
        if hasattr(self.model, "feature_importances_"):
            return self.model.feature_importances_.tolist()
        if hasattr(self.model, "coef_"):
            return self.model.coef_.tolist()
        return None

    def _populate_training_metadata(self, file_path: str, start_time: float):
        self.training_metadata = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "dataset_path": file_path,
            "dataset_hash": self._compute_dataset_hash(file_path),
            "reference_data_loaded": self.prod_price is not None,
            "training_duration": round(time.time() - start_time, 3),
            "model_name": self.best_model_name,
            "n_samples": None,
            "n_features": len(self.feature_columns) if self.feature_columns else None,
            "feature_importances": self._gather_feature_importances(),
            "mape": self.mape,
        }

    def train(self, file_path: str, date_format: str | None = None, seasonality_period: int = 52, force_retrain: bool = False):
        """
        Trains the selected model on the provided dataset.
        
        Args:
            file_path: Path to the dataset.
            date_format: Optional strftime format string for date parsing.
            seasonality_period: Length of the cycle to encode.
            force_retrain: Whether to ignore cached model and retrain.
            
        Returns:
            bool: True if training occurred, False if cached model was used.
        """
        if not force_retrain and self.model is not None:
            logger.info(f"ℹ️ Using cached model for {file_path}, skipping retraining.")
            self.training_metadata["cached"] = True
            return False, (None, None)

        train_start = time.time()
        data = self._prepare_training_data(file_path, date_format=date_format, seasonality_period=seasonality_period)
        X = data[self.feature_columns]
        y = data["sales"]

        try:
            if self.best_model_name == "Prophet":
                result = self._train_prophet(file_path, date_format)
                self._populate_training_metadata(file_path, train_start)
                self.training_metadata["n_samples"] = len(y)
                return result
            else:
                self.model = self._build_model()
                has_oob = hasattr(self.model, 'oob_score') and self.model.oob_score

                if has_oob:
                    self.model.fit(X, y)
                    val_preds = self.model.oob_prediction_
                else:
                    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
                    self.model.fit(X_train, y_train)
                    val_preds = self.model.predict(X_val)
                    y = y_val

                self._last_trained_file = file_path
                self.mape = self._compute_mape(y, val_preds)
                self._populate_training_metadata(file_path, train_start)
                self.training_metadata["n_samples"] = len(y)
                self.training_metadata["feature_importances"] = self._gather_feature_importances()
        except Exception as e:
            logger.error(f"Error training model {self.best_model_name}: {e}")
            self.mape = None
            self.training_metadata["error"] = str(e)

        return True, (X, y)

    def _train_prophet(self, file_path: str, date_format: str | None = None):
        if not HAS_PROPHET:
            raise ImportError("Prophet is not installed.")
        if file_path.lower().endswith((".xls", ".xlsx")):
            raw = pd.read_excel(file_path)
        else:
            raw = pd.read_csv(file_path)
        raw["date"] = pd.to_datetime(raw["date"], format=date_format)
        agg = raw.groupby("date", as_index=False)["sales"].sum()
        agg.columns = ["ds", "y"]
        prophet_params = {k: v for k, v in (self.hyper_params or {}).items()
                          if k in ("seasonality_mode", "yearly_seasonality", "weekly_seasonality", "daily_seasonality", "changepoint_prior_scale")}
        defaults = dict(yearly_seasonality=True, weekly_seasonality=True, daily_seasonality=False, seasonality_mode="additive")
        self.model = Prophet(**{**defaults, **prophet_params})
        self.model.fit(agg)
        future = self.model.make_future_dataframe(periods=0)
        forecast = self.model.predict(future)
        val_preds = forecast["yhat"].values[:len(agg)]
        self._last_trained_file = None
        self.mape = self._compute_mape(agg["y"].values, val_preds)
        return True, (None, None)

    def persist_model(self, model_key: str | None = None):
        path = self.model_path
        if model_key:
            models_dir = os.path.join(os.path.dirname(__file__), "..", "cache", "models")
            os.makedirs(models_dir, exist_ok=True)
            path = os.path.join(models_dir, f"{model_key}.joblib")
        dump({
            "model": self.model,
            "feature_columns": self.feature_columns,
            "label_encoders": self.label_encoders,
            "product_outlet_map": self.product_outlet_map,
            "detected_freq": self.detected_freq,
            "mape": self.mape,
            "model_key": model_key,
            "metadata": self.training_metadata,
        }, path)
        logger.info(f"Persisted trained model to {path}")

    def load_trained_model(self, model_key: str) -> bool:
        models_dir = os.path.join(os.path.dirname(__file__), "..", "cache", "models")
        path = os.path.join(models_dir, f"{model_key}.joblib")
        # logger.info(f"🎯 Attempting to load trained model '{model_key}' from {path}")
        
        if not os.path.exists(path):
            logger.warning(f"❌ Trained model not found: {path}")
            return False
        try:
            data = load(path)
            self.model = data.get("model")
            self.feature_columns = data.get("feature_columns")
            self.label_encoders = data.get("label_encoders", {})
            self.product_outlet_map = data.get("product_outlet_map")
            self.detected_freq = data.get("detected_freq", self.detected_freq)
            self.mape = data.get("mape")
            self.training_metadata = data.get("metadata", {})
            logger.info(f"✅ Loaded trained model '{self.model}' with model key '{model_key}' from {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load trained model '{model_key}': {e}")
            return False

    @staticmethod
    def list_trained_models() -> list[dict]:
        models_dir = os.path.join(os.path.dirname(__file__), "..", "cache", "models")
        if not os.path.exists(models_dir):
            return []
        results = []
        for fname in os.listdir(models_dir):
            if fname.endswith(".joblib"):
                model_key = fname[:-7]
                fpath = os.path.join(models_dir, fname)
                mtime = os.path.getmtime(fpath)
                size = os.path.getsize(fpath)
                results.append({"model_key": model_key, "file": fname, "modified": mtime, "size": size})
        results.sort(key=lambda x: x["modified"], reverse=True)
        return results

    @staticmethod
    def load_trained_model_metadata(model_key: str) -> dict | None:
        models_dir = os.path.join(os.path.dirname(__file__), "..", "cache", "models")
        path = os.path.join(models_dir, f"{model_key}.joblib")
        if not os.path.exists(path):
            return None
        try:
            data = load(path)
            meta = data.get("metadata", {})
            meta["model_key"] = data.get("model_key", model_key)
            meta["mape"] = data.get("mape")
            meta["detected_freq"] = data.get("detected_freq")
            meta["n_features"] = len(data.get("feature_columns", []))
            meta["n_estimators"] = data.get("model").n_estimators if data.get("model") and hasattr(data["model"], "n_estimators") else None
            meta["file_size"] = os.path.getsize(path)
            return meta
        except Exception:
            return None

    # Creating the "Future" Skeleton
    def _generate_future_records(self, num_periods: int, seasonality_period: int = 52) -> pd.DataFrame:
        """
        Generates a placeholder DataFrame for future dates to be predicted.
        
        Args:
            num_periods: Number of weeks to forecast.
            seasonality_period: Length of the cycle to encode.
            
        Returns:
            pd.DataFrame: A skeleton containing dates, products, and prices."""
        records = []
        last_date = getattr(self, "max_date", pd.Timestamp("2024-03-04"))
        freq = getattr(self, "detected_freq", "W")

        # future_dates = pd.date_range(start=last_date, periods=num_periods + 1, freq=freq,)[1:] # Skip the first date as it is the last known date
        future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=num_periods, freq=freq,) # do not skip the first date

        # avg_price = self.prod_price["sell_price"].mean() if self.prod_price is not None else 0
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
        seasonality_period: int = 52,
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
        start_time = time.time()
        if force_retrain:
            logger.info("📦 Pipeline cache BYPASSED (force_retrain=True)")
            return self._execute_predict_logic(model_type, file_path, forecast_periods, seasonality_period, confidence_level, aggregation, frequency, date_format, force_retrain)

        # Use a global flag to detect pipeline cache HIT vs MISS reliably.
        # _run_forecast_pipeline_cached sets this to True only when its function body
        # actually executes (MISS). On a HIT, joblib returns the stored result without
        # executing the body, so the flag stays False.
        global _pipeline_cache_missed
        _pipeline_cache_missed = False

        result = _run_forecast_pipeline_cached(
            model_type, file_path, forecast_periods, seasonality_period,
            confidence_level, aggregation, frequency, date_format,
            self.prod_price, self.date_week, force_retrain,
        )

        pipeline_hit = not _pipeline_cache_missed
        status = "HIT" if pipeline_hit else "MISS"
        logger.info(f"📦 Pipeline cache {status} — {CACHE_FUNC_DIR}/")

        # training_time from the cached function is always the original ML execution time
        if not pipeline_hit:
            logger.info(f"📦 Fresh execution — training_time: {result.get('training_time', 'N/A')}s")
        else:
            logger.info(f"📦 Cache HIT — training_time: {result.get('training_time', 'N/A')}s (from original run), processing_time: {time.time() - start_time:.2f}s")
            result["training_time"] = round(time.time() - start_time, 2)  # Update training_time to reflect the time taken for this cached call

        result["cached"] = pipeline_hit

        logger.info(f"⏳ Predict done — training_time: {result.get('training_time', 'N/A')}s, model: {self.model.__class__.__name__ if self.model else model_type}")
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
        
        exec_start = time.time()
        is_trained, (X, y) = self.train(file_path, date_format=date_format, seasonality_period=seasonality_period, force_retrain=force_retrain)

        self.cached = not is_trained # If we trained, then cached is False; if we didn't train (used cache), then cached is True
        logger.info(f"🟢 Training mode for {file_path}. Starting model training (cached: {self.cached}).")
        
        if model_type != "MovingAverage":
            self.best_model_name = model_type
        if frequency:
            self.detected_freq = frequency

        future = self._generate_future_records(forecast_periods, seasonality_period=seasonality_period)
        if future.empty:
            return {"dates": [], "values": [], "detailed_records": []}

        if model_type == "MovingAverage":
            # Load data to calculate historical averages
            data = self._prepare_training_data(file_path, date_format=date_format, seasonality_period=seasonality_period) # already called in train(), but we need it here for averages
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
            train_duration = 0.1
        else:
            # ExtraTrees path
            # Use reindex to ensure future data has exact same columns as training data, filling missing with 0
            X_future = future.reindex(columns=self.feature_columns, fill_value=0)

            if self.model is None: # If self.model is not set (e.g. fallback), set it up
                self.model = ExtraTreesRegressor(
                    n_estimators=100, max_features=None, bootstrap=True, oob_score=True, random_state=42, n_jobs=-1
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

        train_duration = round(time.time() - exec_start, 2)
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
        
        # train_duration = time.time() - start_train # if is_trained else 0

        # logger.info(f"⏳ Predicting with model for {file_path}. Model: {self.model}/{self.model.__class__.__name__}, train duration: {train_duration:.2f}, force_retrain: {force_retrain}, is_trained: {is_trained}, self.cached: {self.cached}")
        
        return {
            "dates": chart_agg["date_str"].tolist(),
            "values": chart_agg["sales_prediction"].round(2).tolist(),
            "lower_bound": chart_agg["lower"].round(2).tolist(),
            "upper_bound": chart_agg["upper"].round(2).tolist(),
            "detailed_records": records, # This stores the "multiple records"
            "cached": not is_trained, # self.cached
            "detected_freq": ("W" if getattr(self, "detected_freq", "W-MON").startswith("W") else getattr(self, "detected_freq", "W-MON")),
            "training_time": round(train_duration, 2),
            "mape": self.mape,
            "model_type": model_type,
            # "model": self.model,
        }


# Standalone function to handle joblib disk caching without hashing the mutable engine instance.
# This function is only executed on a cache miss.
@memory.cache
def _train_model_cached(
    file_path, date_format, seasonality_period, model_type, prod_price, date_week,
):
    """Train a model and return serializable state.

    Cached by dataset + reference data **only** — NOT by forecast parameters
    (forecast_periods, confidence_level, aggregation, etc.).  This means
    changing any forecast parameter reuses the same trained model.
    """
    logger.info("ℹ️ TRAIN CACHE MISS: Training model from scratch.")
    engine = ForecastEngine()
    engine.prod_price = prod_price
    engine.date_week = date_week
    engine.best_model_name = model_type
    engine._last_trained_file = file_path

    is_trained, (X, y) = engine.train(
        file_path, date_format=date_format, seasonality_period=seasonality_period,
        force_retrain=True,
    )

    return {
        "model": engine.model,
        "feature_columns": engine.feature_columns,
        "label_encoders": engine.label_encoders,
        "product_outlet_map": engine.product_outlet_map,
        "detected_freq": engine.detected_freq,
        "mape": engine.mape,
        "training_metadata": engine.training_metadata,
        "max_date": engine.max_date,
    }


@memory.cache
def _run_forecast_pipeline_cached(model_type, file_path, forecast_periods, seasonality_period, 
    confidence_level, aggregation, frequency, date_format, prod_price, date_week,
    force_retrain # Add force_retrain to the cached function's signature
):
    global _pipeline_cache_missed
    _pipeline_cache_missed = True
    logger.info("ℹ️ℹ️ CACHE MISS: Executing _run_forecast_pipeline_cached.")

    # Step 1: Get a trained model — cached by dataset params (separate key)
    trained = _train_model_cached(
        file_path, date_format, seasonality_period, model_type, prod_price, date_week,
    )

    # Step 2: Set up a transient engine with the trained model
    engine = ForecastEngine()
    engine.model = trained["model"]
    engine.feature_columns = trained["feature_columns"]
    engine.label_encoders = trained["label_encoders"]
    engine.product_outlet_map = trained["product_outlet_map"]
    engine.detected_freq = trained["detected_freq"]
    engine.mape = trained["mape"]
    engine.training_metadata = trained["training_metadata"]
    engine.max_date = trained["max_date"]
    engine.prod_price = prod_price
    engine.date_week = date_week
    engine.cached = False
    engine._last_trained_file = file_path
    engine.best_model_name = model_type

    # Step 3: Run prediction — train() skips since model is already set
    return engine._execute_predict_logic(model_type, file_path, forecast_periods, seasonality_period, 
        confidence_level, aggregation, frequency, date_format,
        force_retrain # Pass force_retrain to _execute_predict_logic
    )
