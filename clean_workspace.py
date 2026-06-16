import os
import shutil
import re

ROOT_DIR = r"d:\Namitech_next"
LEGACY_DIR = os.path.join(ROOT_DIR, "legacy")
EXPERIMENTS_DIR = os.path.join(ROOT_DIR, "experiments")

# Patterns to match backup versions
BACKUP_SUFFIX_PATTERNS = [
    r"_bk\d*$",              # _bk, _bk1, _bk2
    r"_BK\d*$",              # _BK, _BK01, _BK2
    r"_ok\d*$",              # _ok, _ok01
    r"_OK\d*$",              # _OK, _OK01, _OK13
    r"_v\d+$",               # _v1, _v2, _v5
    r"_ori$",                # _ori
    r" - Copy( \(\d+\))?$",  # - Copy, - Copy (2)
    r" copy( \(\d+\))?$",    # copy, copy (2)
    r"_session copy$",       # _session copy
    r"\._OLDpy$"             # ._OLDpy extension helper
]

def should_move_to_legacy(filename):
    name, ext = os.path.splitext(filename)
    if ext == "._OLDpy":
        return True
        
    for pattern in BACKUP_SUFFIX_PATTERNS:
        if re.search(pattern, name):
            return True
    return False

def clean():
    print("--- Starting Workspace Consolidation ---")
    moved_to_legacy_count = 0
    moved_to_experiments_count = 0
    
    # Iterate files in root directory
    for item in os.listdir(ROOT_DIR):
        item_path = os.path.join(ROOT_DIR, item)
        
        # Exclude directories
        if os.path.isdir(item_path):
            continue
            
        name, ext = os.path.splitext(item)
        
        # 1. Handle Jupyter Notebooks (.ipynb) -> Move to experiments/
        if ext == ".ipynb":
            dest_path = os.path.join(EXPERIMENTS_DIR, item)
            print(f"[EXPERIMENT] Moving: {item} -> experiments/")
            shutil.move(item_path, dest_path)
            moved_to_experiments_count += 1
            continue
            
        # 2. Handle backup/suffix files -> Move to legacy/
        if should_move_to_legacy(item):
            dest_path = os.path.join(LEGACY_DIR, item)
            print(f"[LEGACY] Moving: {item} -> legacy/")
            shutil.move(item_path, dest_path)
            moved_to_legacy_count += 1
            continue

    print("\n--- Consolidation Summary ---")
    print(f"Total files moved to legacy/: {moved_to_legacy_count}")
    print(f"Total files moved to experiments/: {moved_to_experiments_count}")
    print("Done!")

if __name__ == "__main__":
    clean()
