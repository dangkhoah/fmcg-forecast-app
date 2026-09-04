import json
import os
import sys
import tempfile
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

# If app.models was already imported from backend, remove it from cache
if 'app' in sys.modules:
    del sys.modules['app']
if 'app.models' in sys.modules:
    del sys.modules['app.models']
if 'app.main' in sys.modules:
    del sys.modules['app.main']

# Add model-service to path
model_service_path = os.path.join(os.path.dirname(__file__), "..", "model-service")
# sys.path.append(model_service_path)
sys.path.insert(0, model_service_path)

from app.models import ForecastEngine


# ═══════════════════════════════════════════════════════════════
#  Fixtures & helpers
# ═══════════════════════════════════════════════════════════════

def _models_dir():
    return os.path.join(os.path.dirname(__file__), "..", "model-service", "cache", "models")


def _cleanup_model(model_key):
    mpath = os.path.join(_models_dir(), f"{model_key}.joblib")
    if os.path.exists(mpath):
        os.remove(mpath)


def _cleanup_all_models(prefix=None):
    models_dir = _models_dir()
    if not os.path.isdir(models_dir):
        return
    for fname in os.listdir(models_dir):
        if fname.endswith(".joblib"):
            if prefix is None or fname.startswith(prefix):
                os.remove(os.path.join(models_dir, fname))


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


@pytest.fixture
def non_overlapping_csv():
    dummy = {
        "date": pd.date_range(start="2099-01-05", periods=5, freq="W-MON"),
        "product_identifier": [999] * 5,
        "department_identifier": [1] * 5,
        "category_of_product": ["CatZ"] * 5,
        "outlet": [999] * 5,
        "state": ["Test"] * 5,
        "sales": [1.0, 2.0, 3.0, 4.0, 5.0],
    }
    df = pd.DataFrame(dummy)
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        df.to_csv(f.name, index=False)
        path = f.name
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def backend_uploads_dir():
    """Path where the model-service /predict endpoint looks for uploads."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "backend", "uploads"
    )
    os.makedirs(path, exist_ok=True)
    return path


@pytest.fixture
def csv_in_backend_uploads(training_csv, backend_uploads_dir):
    """Copy training_csv into backend/uploads as if the user uploaded it."""
    dest = os.path.join(backend_uploads_dir, "test_upload.csv")
    import shutil
    shutil.copy2(training_csv, dest)
    yield dest
    if os.path.exists(dest):
        os.remove(dest)


# ═══════════════════════════════════════════════════════════════
#  1. Feature columns WITH reference data (sell_price present)
# ═══════════════════════════════════════════════════════════════

def test_sell_price_present_when_trained_with_ref_data(training_csv):
    """When the engine has reference data, sell_price IS a feature."""
    engine = ForecastEngine()
    engine.load_reference_data()
    assert engine.prod_price is not None
    assert engine.date_week is not None

    engine.train(training_csv, seasonality_period=4, force_retrain=True)

    assert "sell_price" in engine.feature_columns, (
        "sell_price must be present when reference data is loaded"
    )
    assert len(engine.feature_columns) == 9  # 8 base + sell_price


# ═══════════════════════════════════════════════════════════════
#  2. Empty merge graceful handling  (NaT max_date)
# ═══════════════════════════════════════════════════════════════

def test_empty_merge_handles_nat_max_date(non_overlapping_csv):
    """When CSV dates don't overlap with reference data, the merge
    produces an empty DataFrame.  _prepare_training_data must not
    crash — even though max_date becomes NaT."""
    engine = ForecastEngine()
    engine.load_reference_data()

    result = engine._prepare_training_data(non_overlapping_csv, seasonality_period=4)
    assert result.empty
    assert len(result) == 0
    assert engine.max_date is pd.NaT
    assert engine.feature_columns is not None
    assert "sell_price" in engine.feature_columns
    assert engine.product_outlet_map is not None
    assert len(engine.product_outlet_map) == 0


# ═══════════════════════════════════════════════════════════════
#  3.  /predict endpoint integration  (force_retrain path)
# ═══════════════════════════════════════════════════════════════

def test_predict_endpoint_force_retrain(csv_in_backend_uploads):
    """The /predict endpoint returns a valid PredictResponse when
    force_retrain=True (exercises the full request/response cycle)."""
    from fastapi.testclient import TestClient
    
    # Ensure model-service is in the path
    model_service_path = os.path.join(os.path.dirname(__file__), "..", "model-service")
    if model_service_path not in sys.path:
        sys.path.insert(0, model_service_path)
    
    # Import the model-service app, NOT the backend app
    from app.main import app

    client = TestClient(app)
    filename = os.path.basename(csv_in_backend_uploads)

    payload = {
        "file_path": filename,
        "forecast_periods": 2,
        "seasonality_period": 4,
        "confidence_level": 0.95,
        "model_type": "ExtraTrees",
        "aggregation": "sum",
        "force_retrain": True,
    }

    resp = client.post("/predict", json=payload)
    assert resp.status_code == 200, f"Body: {resp.text}"
    data = resp.json()
    assert "dates" in data
    assert "values" in data
    assert "lower_bound" in data
    assert "upper_bound" in data
    assert len(data["dates"]) == 2
    assert all(isinstance(v, (int, float)) for v in data["values"])
    assert data["model_type"] == "ExtraTrees"
    assert data["mape"] is not None
    # Clean up the model.cache joblib left behind
    cache_joblib = os.path.join(
        os.path.dirname(__file__), "..", "model-service", "cache",
        "forecast_engine.joblib"
    )
    if os.path.exists(cache_joblib):
        os.remove(cache_joblib)


# ═══════════════════════════════════════════════════════════════
#  4.  _calculate_intervals edge cases
# ═══════════════════════════════════════════════════════════════

def test_calculate_intervals_no_model():
    """When the engine has no model (or model without estimators_),
    _calculate_intervals returns (None, None)."""
    engine = ForecastEngine()
    X = pd.DataFrame({"a": [1.0, 2.0]})
    lower, upper = engine._calculate_intervals(X, 0.95)
    assert lower is None
    assert upper is None


def test_calculate_intervals_zero_confidence(training_csv):
    """With confidence=0, the interval bounds equal the median prediction."""
    engine = ForecastEngine()
    engine.load_reference_data()
    engine.train(training_csv, seasonality_period=4, force_retrain=True)

    future = engine._generate_future_records(2, seasonality_period=4)
    X = future.reindex(columns=engine.feature_columns, fill_value=0)
    per_tree = np.array([
        tree.predict(X.values)
        for tree in engine.model.estimators_
    ])
    median = np.percentile(per_tree, 50, axis=0)

    lower, upper = engine._calculate_intervals(X, 0.0)
    lower_manual = np.percentile(per_tree, 50, axis=0)
    np.testing.assert_array_almost_equal(lower, lower_manual)


def test_calculate_intervals_full_confidence(training_csv):
    """With confidence=1.0, the interval spans min..max across trees."""
    engine = ForecastEngine()
    engine.load_reference_data()
    engine.train(training_csv, seasonality_period=4, force_retrain=True)

    future = engine._generate_future_records(2, seasonality_period=4)
    X = future.reindex(columns=engine.feature_columns, fill_value=0)
    per_tree = np.array([
        tree.predict(X.values)
        for tree in engine.model.estimators_
    ])

    lower, upper = engine._calculate_intervals(X, 1.0)
    expected_lower = np.percentile(per_tree, 0, axis=0)
    expected_upper = np.percentile(per_tree, 100, axis=0)
    np.testing.assert_array_almost_equal(lower, expected_lower)
    np.testing.assert_array_almost_equal(upper, expected_upper)


# ═══════════════════════════════════════════════════════════════
#  5.  Model key round-trip  (persist → list → load → predict)
# ═══════════════════════════════════════════════════════════════

def test_model_round_trip(training_csv):
    """A model survives persist -> list -> load -> predict."""
    model_key = "ExtraTrees_test_roundtrip"
    _cleanup_model(model_key)

    # ── Train & persist ────────────────────────────────────────
    train_engine = ForecastEngine()
    train_engine.prod_price = None
    train_engine.date_week = None
    train_engine.train(training_csv, seasonality_period=4, force_retrain=True)
    train_engine.persist_model(model_key)

    expected_features = train_engine.feature_columns.copy()
    expected_mape = train_engine.mape

    # ── List should include the new model ──────────────────────
    models = ForecastEngine.list_trained_models()
    keys = [m["model_key"] for m in models]
    assert model_key in keys, f"{model_key} not in {keys}"

    # ── Load into a fresh engine ───────────────────────────────
    fresh = ForecastEngine()
    fresh.prod_price = None
    fresh.date_week = None
    loaded = fresh.load_trained_model(model_key)
    assert loaded

    assert fresh.feature_columns == expected_features
    assert fresh.mape == expected_mape
    assert fresh.model is not None

    # ── Predict with loaded model ──────────────────────────────
    fresh._prepare_training_data(training_csv, seasonality_period=4)
    fresh.feature_columns = expected_features  # restore (same fix as main.py)

    future = fresh._generate_future_records(3, seasonality_period=4)
    assert not future.empty

    X_future = future.reindex(columns=fresh.feature_columns, fill_value=0)
    preds = fresh.model.predict(X_future)
    assert len(preds) == 3
    assert all(np.isfinite(preds))

    _cleanup_model(model_key)


# ═══════════════════════════════════════════════════════════════
#  Legacy test kept from test_model_oob.pybk
# ═══════════════════════════════════════════════════════════════

def test_oob_mape_with_zero_sales():
    """OOB MAPE calculation with zero and non-zero sales values."""
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
