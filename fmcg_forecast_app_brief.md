# FMCG Forecast App — Project Brief

## 🏗️ Architecture Overview

A **3-tier full-stack** application for FMCG (Fast-Moving Consumer Goods) sales demand forecasting.

```
┌─────────────┐    ┌──────────────────────┐    ┌──────────────────┐
│  Frontend   │───▶│  Backend API         │───▶│  Model Service   │
│  React/JS   │    │  FastAPI + SQLite    │    │  FastAPI + ML    │
│  :3000      │    │  :8000               │    │  :8001           │
└─────────────┘    └──────────────────────┘    └──────────────────┘
```

---

## 🧩 Components

### 1. Frontend — `frontend/src/`

React app (Create React App + Tailwind CSS) with these pages:

| Page | Purpose |
|------|---------|
| `Dashboard.js` | Overview & KPI summary |
| `Upload.js` | CSV data upload |
| `Forecast.js` | Run & visualize forecasts |
| `TrainModel.jsx` | Configure & train ML models |
| `Scenarios.js` | What-if scenario analysis |
| `Settings.js` | App configuration |

Auth-protected routes with login/register flow.

---

### 2. Backend API — `backend/app/`

FastAPI service backed by **SQLite** (via SQLAlchemy + Alembic). Key routers:

| Router | Responsibility |
|--------|---------------|
| `auth.py` | User auth (JWT) |
| `datasets.py` | Upload/manage CSV datasets |
| `forecast.py` | Forecast request proxy |
| `train.py` | Trigger model training |
| `schedules.py` | Scheduled auto-retraining |
| `versions.py` | Model version management |
| `training_history.py` | Training audit log |

Has **APScheduler** for automated periodic retraining (daily/weekly/monthly).

---

### 3. Model Service — `model-service/app/`

Dedicated FastAPI microservice that owns the ML logic:

- **Algorithm**: `ExtraTreesRegressor` (sklearn)
- **Key class**: `ForecastEngine` — handles training, prediction, confidence intervals, model caching/persistence
- **Features used**: lag features, seasonality, sell price, product/outlet identifiers
- **Output**: future date predictions with configurable confidence bands, MAPE via OOB scoring
- **Endpoints**: `POST /predict`, `POST /train`, `GET /trained-models`, `GET /health`

---

## 📦 Data Flow

```
User uploads CSV → Backend stores file
→ User triggers forecast → Backend calls model-service /predict
→ ForecastEngine trains (or loads cached) ExtraTrees model
→ Returns future predictions with CI bands → Frontend charts results
```

---

## ⚠️ Known Issues (from AGENTS.md)

1. **Empty-merge crash** — NaT date crash when CSV dates don't overlap reference data
2. **Training without reference data** — `train.py` doesn't call `load_reference_data()`, so `sell_price` is missing as a feature
3. **Global mutable engine** — single `engine` instance shared across concurrent requests (state corruption risk)
4. **MAPE with zero sales** — division by zero produces NaN/Inf
5. **No model metadata persistence** — no training date, dataset hash, or feature importances saved

---

## 🛠️ Tech Stack Summary

| Layer | Stack |
|-------|-------|
| Frontend | React, Tailwind CSS, React Router, react-hot-toast |
| Backend | FastAPI, SQLAlchemy (async), Alembic, APScheduler, SQLite |
| Model Service | FastAPI, scikit-learn (`ExtraTreesRegressor`), pandas, joblib |
| Package manager | `uv` |
| Dev runner | PowerShell `.ps1` scripts for launching all 3 services |

---

*Generated: 2026-08-31*
