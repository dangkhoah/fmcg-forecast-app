import os
from fastapi import APIRouter, HTTPException
from pathlib import Path

router = APIRouter(prefix="/policy", tags=["policy"])

@router.get("/", response_model=dict)
def get_policy_rules():
    """Return the contents of the .cursorrules file as a JSON mapping.
    Lines beginning with '#' are ignored. Empty lines are skipped.
    Each rule is split on the first ':' into key/value strings.
    """
    # Locate the repository root (two levels up from this file)
    repo_root = Path(__file__).resolve().parents[2]
    cursors_path = repo_root / ".cursorrules"
    if not cursors_path.is_file():
        raise HTTPException(status_code=404, detail=".cursorrules not found")
    rules = {}
    with open(cursors_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, val = line.split(":", 1)
                rules[key.strip()] = val.strip()
    return rules
