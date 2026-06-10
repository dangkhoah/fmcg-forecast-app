import sys
import os

# Add the venv site-packages to sys.path
venv_path = os.path.join(os.getcwd(), "backend", ".venv", "Lib", "site-packages")
sys.path.insert(0, venv_path)

import uvicorn

if __name__ == "__main__":
    # Change directory to backend so app.main:app works
    os.chdir("backend")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
