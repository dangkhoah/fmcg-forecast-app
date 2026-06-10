# Move App Checklist

## 1. Get the source code
```bash
# If you have a remote repo (e.g. GitHub)
git clone <repo‑url> fmcg-forecast-app
cd fmcg-forecast-app
```
*If you don’t use Git, just copy the whole folder (`d:\Apps\fmcg-forecast-app`) to the new machine.*

## 2. Install system prerequisites
| Tool | Recommended version | Install command |
|------|--------------------|-----------------|
| **Python** | 3.12 |[python.org] installer (add to PATH) |
| **Node.js** | 20.x |`npm install -g npm@latest` (includes Node) |
| **uv** (optional) | 0.4.x |`pip install uv` |
| **Git** (if using Git) | any recent |`winget install –id Git.Git` (Windows) / `sudo apt install git` (Linux) |

## 3. Set up the Python environments
### 3.1 Backend
```powershell
cd backend
python -m venv .venv        # or: uv venv .venv
.\.venv\Scripts\Activate.ps1   # .venv\Scripts\activate (Linux/macOS)
pip install -r requirements.txt
```
### 3.2 Model service
```powershell
cd ..\model-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 4. Set up the Node environment (frontend)
```powershell
cd ..\frontend
npm ci               # installs exactly the lock‑file versions
```

## 5. Copy / create runtime data
- **backend/.env** – copy and change `SECRET_KEY` to a new random value (`python -c "import secrets; print(secrets.token_urlsafe())"`).
- **backend/fmcg_forecast.db** – copy if you need existing data; otherwise a fresh DB will be created.
- **model-service/reference/** – ensure the folder with CSV files exists.

## 6. Verify ports & firewall
| Service | Port | URL |
|---------|------|-----|
| Model service | **8001** | `http://localhost:8001` |
| Backend API   | **8000** | `http://localhost:8000` |
| Frontend dev server | **3000** | `http://localhost:3000` |
Make sure the ports are open.

## 7. Run the app
### 7.1 Using the supplied PowerShell script (recommended)
```powershell
.\start.ps1
```
It launches model‑service, backend, and prints a reminder to start the frontend in another terminal:
```
cd fmcg-forecast-app\frontend && npm start
```
### 7.2 Manually (separate terminals)
```powershell
# Terminal 1 – Model service
cd model-service
.\.venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# Terminal 2 – Backend
cd backend
.\.venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 3 – Frontend
cd frontend
npm start
```
Press any key in the PowerShell window that ran `start.ps1` to stop all services.

## 8. (Optional) Production build
1. **Frontend** – build static assets:
```bash
cd frontend
npm run build   # creates `build/`
```
2. **Serve the built UI** – either mount it in FastAPI or use a static web server.
3. Run only the two FastAPI services; the UI will be served from the built folder.

## 9. Quick‑start script (optional)
Save this as `setup_and_run.ps1` in the project root and execute it once on a fresh machine:
```powershell
# 1️⃣ Install Python packages
cd backend
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd ..

cd model-service
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd ..

# 2️⃣ Install Node packages
cd frontend
npm ci
cd ..

# 3️⃣ Start everything
.\start.ps1
```

## 10. Common pitfalls & fixes
| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `ImportError: No module named uvicorn` | Python env not activated | Re‑activate the venv and run `pip install -r requirements.txt`. |
| `sqlite3.OperationalError: unable to open database file` | Wrong working directory or missing DB | Run the backend from the `backend` folder or set `DATABASE_URL` correctly. |
| `npm ERR! code ENOENT` on `npm start` | `node_modules` missing | Run `npm ci` again in `frontend`. |
| Port conflict (`EADDRINUSE`) | Another app listening on the same port | Change the port numbers in `start.ps1` or stop the conflicting service. |
| CORS errors in the UI | Backend not allowing origin | The FastAPI apps already allow `*`; ensure you hit the correct URLs (`localhost`). |

---
**TL;DR**: copy the folder, create & activate two Python venvs, run `npm ci`, copy `.env` (new secret), then run `.
start.ps1` (or launch services manually). The app will be available at `http://localhost:3000` (dev) or `http://localhost:8000` (prod).
