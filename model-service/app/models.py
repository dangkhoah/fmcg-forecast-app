import os
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings("ignore")


class ForecastEngine:
    def __init__(self):
        self.model = None
        self.label_encoders = {}
        self.feature_columns = None
        self.product_outlet_map = None
        self.prod_price = None
        self.date_week = None
        self.best_model_name = "ExtraTrees"

    def load_reference_data(self, ref_dir: str = None):
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
        if week_path.exists():
            self.date_week = pd.read_csv(
                week_path,
                names=["date", "week_id"],
                header=0,
                parse_dates=["date"],
            )

    def _prepare_training_data(self, file_path: str) -> pd.DataFrame:
        if file_path.lower().endswith((".xls", ".xlsx")):
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path)

        # Ensure date column exists and is converted to datetime
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        else:
            raise ValueError("Uploaded dataset must contain a 'date' column")

        if self.prod_price is not None and self.date_week is not None:
            # Ensure date in date_week is also datetime64[ns]
            self.date_week["date"] = pd.to_datetime(self.date_week["date"])
            merged = pd.merge(self.prod_price, self.date_week, on="week_id", how="inner")
            
            # Ensure product_identifier and outlet columns are typed correctly as numeric to avoid object/numeric merge conflicts
            df["product_identifier"] = pd.to_numeric(df["product_identifier"], errors="coerce")
            df["outlet"] = pd.to_numeric(df["outlet"], errors="coerce")
            merged["product_identifier"] = pd.to_numeric(merged["product_identifier"], errors="coerce")
            merged["outlet"] = pd.to_numeric(merged["outlet"], errors="coerce")

            df = pd.merge(
                df, merged,
                on=["date", "product_identifier", "outlet"],
                how="inner",
            )
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

    def train(self, file_path: str):
        data = self._prepare_training_data(file_path)
        X = data[self.feature_columns]
        y = data["sales"]

        self.model = ExtraTreesRegressor(
            n_estimators=100,
            max_features=None,
            verbose=0,
            n_jobs=-1,
        )
        self.model.fit(X, y)

    def _generate_future_records(self, num_periods: int) -> pd.DataFrame:
        records = []
        last_date = getattr(self, "max_date", pd.Timestamp("2014-03-01"))
        future_dates = pd.date_range(
            start=last_date + pd.Timedelta(days=1),
            periods=num_periods,
            freq="W",
        )

        avg_price = self.prod_price["sell_price"].mean() if self.prod_price is not None else 0

        for date in future_dates:
            for _, row in self.product_outlet_map.iterrows():
                record = {
                    "Month": date.month,
                    "sell_price": avg_price,
                    "date": date,
                }
                # Inject whatever metadata was found during training
                for col in self.product_outlet_map.columns:
                    record[col] = row[col]
                records.append(record)

        future_df = pd.DataFrame(records)
        return future_df

    def predict(
        self,
        file_path: str,
        forecast_periods: int = 12,
        seasonality_period: int = 12,
        confidence_level: float = 0.95,
    ) -> dict:
        self.train(file_path)

        future = self._generate_future_records(forecast_periods)
        if future.empty:
            return {"dates": [], "values": [], "records": []}

        # Use reindex to ensure future data has exact same columns as training data, filling missing with 0
        X_future = future.reindex(columns=self.feature_columns, fill_value=0)

        predictions = self.model.predict(X_future)
        future['sales_prediction'] = predictions

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

        # Aggregated data for the UI Chart (Mean sales per date)
        chart_agg = future.groupby("date")["sales_prediction"].mean().reset_index() if not future.empty else pd.DataFrame()
        if chart_agg.empty:
            return {"dates": [], "values": [], "records": records}

        chart_agg["date_str"] = chart_agg["date"].dt.strftime("%Y-%m-%d")

        return {
            "dates": chart_agg["date_str"].tolist(),
            "values": chart_agg["sales_prediction"].round(2).tolist(),
            "records": records # This stores the "multiple records"
        }
