# FMCG Sales Forecast App - Chat Summary

## Date: 2026-06-07

## Requirements Gathered
- **Frontend:** React
- **Backend:** Python FastAPI
- **Model:** Existing (external API)
- **Data:** CSV/Excel uploads
- **Auth:** JWT
- **Database:** PostgreSQL
- **Charts:** Chart.js
- **Deployment:** Local
- **Timeline:** 1 month+

## Features Built
1. **User Auth** - JWT registration/login
2. **Data Upload** - Drag-drop CSV/Excel with preview
3. **Dashboard** - Summary stats + forecast chart
4. **Forecast** - Parameter tuning (periods, seasonality, confidence)
5. **What-If Scenarios** - Compare multiple forecasts side-by-side
6. **Export** - CSV/Excel download

## Architecture (3 services)

### 1. Backend API (port 8000) — `backend/`
- FastAPI with async SQLAlchemy + PostgreSQL
- JWT auth (python-jose + passlib + bcrypt)
- Models: User, Dataset, ForecastResult, ForecastScenario
- Endpoints: auth, datasets CRUD, forecast execution, export

### 2. Model Service (port 8001) — `model-service/`
- FastAPI + scikit-learn
- ExtraTreesRegressor (100 estimators, based on your retail chain notebook)
- Feature pipeline: label encoding, month extraction, sell_price enrichment
- Generates future date records for all product/outlet combinations
- Returns dates + values + 95% confidence intervals
- Reference data from `Demand Forecast/retail chain/`

### 3. Frontend (port 3000) — `frontend/`
- React 18 + react-router-dom + Chart.js + Axios
- 4 protected pages: Dashboard, Upload, Forecast, Scenarios
- Responsive sidebar layout

## Key Files
| File | Purpose |
|------|---------|
| `backend/app/main.py` | API entry point with CORS + routers |
| `backend/app/routers/forecast.py` | Calls model service at localhost:8001 |
| `model-service/app/models.py` | ForecastEngine with train + predict |
| `frontend/src/pages/Forecast.js` | Parameter tuning + chart UI |
| `frontend/src/pages/Scenarios.js` | What-if comparison |
| `start.ps1` | Launches backend + model service |

## How to Run
```bash
# Terminal 1 - Model Service
cd fmcg-forecast-app/model-service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# Terminal 2 - Backend
cd fmcg-forecast-app/backend
pip install -r requirements.txt
# Ensure PostgreSQL is running with database "fmcg_forecast"
uvicorn app.main:app --reload --port 8000

# Terminal 3 - Frontend
cd fmcg-forecast-app/frontend
npm install
npm start
```
