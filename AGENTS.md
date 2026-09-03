# AGENTS.md – fmcg‑forecast‑app
## Project Overview
- **Name**: FMCG Forecast App
- **Domain**: Time‑series demand forecasting for fast‑moving consumer goods.
- **Primary language**: Python 3.11+ (backend, model‑service, utilities).
- **Entry points**: `backend/app/routers/forecast.py`, `model-service/app/main.py`, `move_with_structure.py`.
---
## Coding Style & Formatting
| Rule | Tool | Config |
|------|------|--------|
| Code formatter | **Black** | `black .` – line‑length 88 |
| Import order | **isort** | `isort .` – `known_first_party=backend,model-service,frontend` |
| Linting | **flake8** | max‑line‑length 88, ignore `E203,W503` |
| Static typing | **mypy** | `strict = True` (no implicit `Any`) |
| Docstrings | – | Google‑style for all public functions/classes |
| File naming | – | Python files `snake_case.py`, tests `test_*.py` |
---
## Safety & Interaction Policies
- `acceptance_prompt: true` – Antigravity must request Accept/Reject before any code change.
- `accept_reject_prompt: true` – Show UI buttons after each run.
- `acceptance_prompt_actions: accept,reject` – Provide both Accept and Reject options.
- `confirm_repo_modifications: true` – Any `git`, `npm`, `pip`, `conda`, or OS‑level mutating command requires explicit confirmation.
- `file_reference_path: after` – File references are followed by their absolute path (e.g., `[move_with_structure.py](file:///d:/Apps/fmcg-forecast-app/move_with_structure.py) – d:/Apps/fmcg-forecast-app/move_with_structure.py`).
- `skip_tests_on_start: db,backend,model-service` – Do not automatically run database, backend, or model‑service test suites when a new task begins. Tests can still be triggered manually with `uv run pytest`.
- `environment_diagnostics`:
  - Before executing any Python commands (e.g., tests, syntax checks), check for virtual environments in the directory tree.
  - Note that Python virtual environments in this workspace are located in subdirectories:
    - Backend: `d:/Apps/fmcg-forecast-app/backend/.venv`
    - Model Service: `d:/Apps/fmcg-forecast-app/model-service/.venv`
  - Always use the absolute path to the virtual environment's interpreter (e.g., `backend/.venv/Scripts/python.exe`) rather than running `python` globally.
---
## CLI Defaults (move_with_structure.py)
| Flag | Default | Reason |
|------|---------|--------|
| `--dry-run` | **off** (must be passed explicitly) | Prevent accidental moves. |
| `--archive` | `d:/Apps/archive_fmcg-forecast-app` | Central archive for backup/experiment files. |
| `--root` | `d:/Apps/fmcg-forecast-app` | Project root; overrides config if supplied. |
---
## Dependency Management
- **Package manager**: **uv** (fast, deterministic). `uv lock` creates `uv.lock` at repo root.
- **Python version**: `>=3.11,<3.13`.
- **Core dependencies** (pinned in `requirements.txt`):
  ```text
  fastapi==0.111.0
  uvicorn[standard]==0.30.1
  pydantic==2.8.2
  numpy==2.0.0
  pandas==2.2.2
  openpyxl==3.1.2
  scikit-learn==1.5.0
  ```
- **Dev dependencies** (testing & linting):
  ```text
  pytest==8.3.2
  pytest-cov==5.0.0
  black==24.4.2
  isort==5.13.2
  flake8==7.1.1
  mypy==1.11.0
  pre-commit==3.7.1
  ```
---
## Testing & CI
1. **Unit tests** – located under `tests/` and `backend/tests/`.
2. **Coverage target** – ≥ 90 % for core modules.
3. **CI pipeline** – GitHub Actions (`.github/workflows/ci.yml`) runs:
   - `uv sync && uv run pytest --cov`
   - `black --check .`
   - `isort --check-only .`
   - `flake8 .`
   - `mypy .`
---
## Documentation
- Docs source: `docs/` (MkDocs).
- Auto‑generate API reference via `mkdocstrings` (reads docstrings).
- README must contain a **Quick‑Start** block:
  ```markdown
  ```bash
  # Install dependencies
  uv sync
  # Run the API
  uv run python -m backend.app.main
  ```
  ```
- Changelog: `CHANGELOG.md` using *Keep a Changelog* format.
---
## Project Layout (high‑level)
```
 fmcg-forecast-app/
 ├─ backend/                # FastAPI service
 │   └─ app/
 │       └─ routers/
 │           └─ forecast.py
 ├─ model-service/          # Model serving (FastAPI)
 │   └─ app/
 │       └─ main.py
 ├─ frontend/               # Optional UI code
 ├─ scripts/                # Utility scripts (e.g., move_with_structure.py)
 ├─ tests/                  # Core unit tests
 ├─ docs/                   # MkDocs documentation
 ├─ move_config.yaml        # Default config for the move script
 ├─ AGENTS.md               # ← **this file**
 └─ .cursorrules           # Antigravity UI preferences (already present)
```
---
## Model Training & Validation
- **Algorithm**: `ExtraTreesRegressor` (100 estimators, max features=None, bootstrap=True, random state 42).
- **Training Frequency**: The model is trained exactly **once** on the full historical dataset (if not cached or if `force_retrain` is `True`).
- **Validation (MAPE)**: MAPE is calculated via Out-of-Bag (OOB) predictions on the training dataset. This estimates generalization performance without needing a separate split or double training.
---
## Miscellaneous
- **Environment variables** (template in `.env.example`):
  | Variable | Description | Example |
  |----------|-------------|---------|
  | `PYTHONPATH` | Adds `backend` and `model-service` to import path | `PYTHONPATH=backend:model-service` |
  | `APP_ENV` | `development` | `production` | `development` |
  | `LOG_LEVEL` | Logging verbosity for the API | `INFO` |
- **Secret handling** – Use `python‑dotenv`; never commit real secrets.
- **Versioning** – Tag releases with `vMAJOR.MINOR.PATCH` (semantic versioning).
- **Pre‑commit** – Include a `.pre-commit-config.yaml` that runs Black, isort, flake8, and mypy on every commit.
---
## Suggested Improvements (recorded 2026-07-28)
1. **Fix the empty-merge crash** – When CSV dates don't overlap with reference data, `_prepare_training_data` produces an empty DataFrame with `max_date = NaT`. Calling `_generate_future_records` afterward crashes with `ValueError: Neither 'start' nor 'end' can be NaT`. Either gracefully fall back to computing `week_id` from the date directly or raise a clear user-facing error.
2. **Load reference data during training** – `model-service/app/routers/train.py:47` creates a bare `engine = ForecastEngine()` without calling `load_reference_data()`. This means the model trains **without** `sell_price`, even when reference data exists. The training endpoint should load reference data so `sell_price` is actually used as a feature.
3. **Make the global engine stateless** – `model-service/app/main.py:45` has a single global `engine = ForecastEngine()`. Every `/predict` request mutates it. Concurrent requests will corrupt each other's state. Use per-request engine instances or an engine pool instead.
4. **Handle zero-sales in MAPE** – MAPE divides by `actual`. When `actual == 0`, this produces infinity/NaN. The OOB test passes but the value is meaningless. Filter out zero rows, use a cap, or switch to MAE / SMAPE.
5. **Add metadata to persisted models** – `persist_model` stores only the bare minimum. Add: training date, dataset hash, reference data state, training duration, and feature importances. This aids model governance and debugging.
---
*This file is read automatically by Antigravity and applied to all interactions with the `fmcg‑forecast‑app` repository.*
