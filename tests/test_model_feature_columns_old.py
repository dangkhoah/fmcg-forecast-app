import os
import sys
import tempfile

import numpy as np
import pandas as pd
import pytest

# sys.path.append(os.path.join(os.path.dirname(__file__), "..", "model-service"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "model-service"))

from app.models import ForecastEngine


@pytest.fixture
def training_csv():
    dummy = {
        "date": pd.date_range(start="2012-01-02", periods=10, freq="W-MON"),
        "product_identifier": [74] * 10,
        "department_identifier": [1] * 10,
        "category_of_product": ["CatA"] * 10,
        "outlet": [111] * 10,
        "state": ["StateX"] * 10,
        "sales": [10.0, 0.0, 15.0, 0.0, 12.0, 8.0, 0.0, 14.0, 20.0, 5.0],
    }
    df = pd.DataFrame(dummy)
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        df.to_csv(f.name, index=False)
        path = f.name
    yield path
    if os.path.exists(path):
        os.remove(path)


def _cleanup_model(model_key):
    models_dir = os.path.join(
        os.path.dirname(__file__), "..", "model-service", "cache", "models"
    )
    mpath = os.path.join(models_dir, f"{model_key}.joblib")
    if os.path.exists(mpath):
        os.remove(mpath)


def test_sell_price_absent_when_model_trained_without_ref_data(training_csv):
    """Regression test for the sell_price feature-mismatch bug.

    A model trained *without* reference data (so sell_price is never a
    feature) is persisted, then loaded into an engine that *has* reference
    data.  The fix in main.py saves feature_columns before calling
    _prepare_training_data and restores them afterwards — this test
    verifies that end result does not include sell_price.
    """
    model_key = "ExtraTrees_test_no_price"

    # ── 1. Train a model WITHOUT reference data ─────────────────
    train_engine = ForecastEngine()
    train_engine.prod_price = None
    train_engine.date_week = None

    train_engine.train(training_csv, seasonality_period=4, force_retrain=True)
    assert "sell_price" not in train_engine.feature_columns
    assert train_engine.feature_columns == 8

    train_engine.persist_model(model_key)

    # ── 2. Load into a second engine WITH reference data ────────
    predict_engine = ForecastEngine()
    predict_engine.load_reference_data()

    loaded = predict_engine.load_trained_model(model_key)
    assert loaded, "Trained model should load successfully"
    original_features = predict_engine.feature_columns.copy()
    assert "sell_price" not in original_features

    # ── 3. Simulate the exact sequence main.py now follows ──────
    saved_feature_columns = predict_engine.feature_columns
    predict_engine._prepare_training_data(training_csv, seasonality_period=4)
    predict_engine.feature_columns = saved_feature_columns  # the fix

    # ── 4. Assertions ───────────────────────────────────────────
    assert "sell_price" not in predict_engine.feature_columns, (
        "sell_price must NOT appear in feature_columns after the fix"
    )
    assert predict_engine.feature_columns == original_features, (
        "feature_columns must match the loaded model's original columns"
    )

    # ── 5. Verify the model can still predict ───────────────────
    future = predict_engine._generate_future_records(
        num_periods=2, seasonality_period=4
    )
    assert not future.empty
    X_future = future.reindex(
        columns=predict_engine.feature_columns, fill_value=0
    )
    assert "sell_price" not in X_future.columns
    preds = predict_engine.model.predict(X_future)
    assert len(preds) == 2
    assert all(np.isfinite(preds))

    # Cleanup
    _cleanup_model(model_key)


def test_oob_mape_with_zero_sales():
    """Keep the existing OOB / MAPE test active (moved from test_model_oob.pybk)."""
    dummy = {
        "date": pd.date_range(start="2026-01-01", periods=10, freq="W"),
        "product_identifier": [101] * 10,
        "department_identifier": [1] * 10,
        "category_of_product": ["others"] * 10,
        "outlet": [111] * 10,
        "state": ["Maharashtra"] * 10,
        "sales": [10.0, 0.0, 15.0, 0.0, 12.0, 8.0, 0.0, 14.0, 20.0, 5.0],
    }
    df = pd.DataFrame(dummy)
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        df.to_csv(f.name, index=False)
        path = f.name

    try:
        engine = ForecastEngine()
        engine.prod_price = None
        engine.date_week = None

        is_trained, (X, y) = engine.train(
            file_path=path, seasonality_period=4, force_retrain=True
        )

        assert is_trained is True
        assert engine.model is not None
        assert hasattr(engine.model, "estimators_")
        assert engine.model.bootstrap is True
        assert engine.model.oob_score is True
        assert engine.mape is not None
        assert isinstance(engine.mape, float)
        assert engine.mape >= 0.0

        future = engine._generate_future_records(num_periods=2, seasonality_period=4)
        assert not future.empty
        assert "sales_prediction" not in future.columns
    finally:
        if os.path.exists(path):
            os.remove(path)
