import os
import shutil
import re
import argparse
import logging
import yaml
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration (adjust as needed)
# ---------------------------------------------------------------------------
CONFIG_PATH = Path(__file__).with_name('move_config.yaml')

def load_config() -> dict:
    """Load optional YAML config file.

    Returns a dict with keys ``project_root`` and ``archive_root``.
    If the file does not exist, defaults are used.
    """
    default = {
        'project_root': r"d:\\Apps\\fmcg-forecast-app",
        'archive_root': r"d:\\Apps\\archive_fmcg-forecast-app",
    }
    if CONFIG_PATH.is_file():
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                import yaml as _yaml
                cfg = _yaml.safe_load(f) or {}
                return {**default, **cfg}
        except Exception as e:
            logging.warning("Failed to read config %s: %s", CONFIG_PATH, e)
    return default

cfg = load_config()
PROJECT_ROOT = Path(cfg['project_root'])
ARCHIVE_ROOT = Path(cfg['archive_root'])

# Backup‑suffix patterns – identical to clean_workspace.py
BACKUP_SUFFIX_PATTERNS = [
    r"_bk\d*$",               # _bk, _bk1, _bk2
    r"_BK\d*$",               # _BK, _BK01, _BK2
    r"_ok\d*$",               # _ok, _ok01
    r"_OK\d*$",               # _OK, _OK01, _OK13
    r"_v\d+$",                # _v1, _v2, _v5
    r"_ori$",                 # _ori
    r" - Copy( \(\d+\))?$",   # - Copy, - Copy (2)
    r" copy( \(\d+\))?$",      # copy, copy (2)
    r"_session copy$",        # _session copy
    r"\._OLDpy$",               # ._OLDpy extension helper
    # r"_(.*?)err\d*$"
]

def should_move(file_name: str) -> bool:
    """Return True if the file matches any backup‑suffix pattern.

    The function mirrors the logic in ``clean_workspace.py`` so the same
    set of files are identified.
    """
    name, ext = os.path.splitext(file_name)
    if ext == "._OLDpy":
        return True
    for pattern in BACKUP_SUFFIX_PATTERNS:
        if re.search(pattern, name):
            return True
    return False

def move_file(src: Path, dst_root: Path) -> None:
    """Move *src* into *dst_root* while preserving its relative hierarchy.

    Example:
        src = PROJECT_ROOT / "src" / "utils" / "data_bk1.py"
        dst_root = ARCHIVE_ROOT
        → dst = ARCHIVE_ROOT / "src" / "utils" / "data_bk1.py"
    """
    relative_path = src.relative_to(PROJECT_ROOT)
    dst_path = dst_root / relative_path
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    logging.info("Moving %s → %s", src, dst_path)
    shutil.move(str(src), str(dst_path))

def walk_and_move(dry_run: bool = False) -> None:
    """Recursively scan *PROJECT_ROOT* and move matching files.

    *Files inside the archive folder itself are ignored* to avoid a
    moving‑loop. The function respects the ``dry_run`` flag – when set, it
    only logs the actions without performing any filesystem modifications.
    """
    for root, _, files in os.walk(PROJECT_ROOT):
        root_path = Path(root)
        # Skip the archive directory
        if ARCHIVE_ROOT.resolve().is_relative_to(root_path.resolve()):
            continue
        for file in files:
            src_path = root_path / file
            if should_move(file):
                if dry_run:
                    logging.info("[DRY‑RUN] Would move %s → %s", src_path, ARCHIVE_ROOT / src_path.relative_to(PROJECT_ROOT))
                else:
                    move_file(src_path, ARCHIVE_ROOT)

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Move backup‑suffix files into an archive while preserving folder hierarchy."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be moved without touching the filesystem.",
    )
    parser.add_argument(
        "--archive", type=str, default=None, help="Optional archive path to override config (e.g., d:/custom/archive).",
    )
    parser.add_argument(
        "--root", type=str, default=None, help="Optional project root path to override config.",
    )
    args = parser.parse_args()

    # Override configuration from CLI if provided
    global PROJECT_ROOT, ARCHIVE_ROOT
    if args.root:
        PROJECT_ROOT = Path(args.root).expanduser().resolve()
    if args.archive:
        ARCHIVE_ROOT = Path(args.archive).expanduser().resolve()

    # Safety checks
    if ARCHIVE_ROOT == PROJECT_ROOT:
        raise ValueError("Archive directory must be different from project root.")
    if ARCHIVE_ROOT.is_relative_to(PROJECT_ROOT):
        raise ValueError("Archive directory cannot be inside the project root.")

    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s",
    )

    logging.info("Starting workspace cleanup → archive: %s", ARCHIVE_ROOT)
    walk_and_move(dry_run=args.dry_run)
    logging.info("Finished.")

if __name__ == "__main__":
    main()
