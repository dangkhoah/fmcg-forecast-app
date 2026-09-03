"""
Detect the temporal frequency of a time-series CSV dataset.

Handles panel data (multiple rows per date, e.g. one row per product/outlet)
by first extracting the unique sorted dates, then inferring the frequency.

Usage:
    python scratch_detect_frequency.py --file test_data_small.csv
    python scratch_detect_frequency.py --file train_data.csv --date_column Date
"""
import argparse
import os
import sys
import pandas as pd
import numpy as np


# ------------------------------------------------------------------
# Frequency-label mapping
# ------------------------------------------------------------------
FREQ_LABELS = {
    "D":    "Daily",
    "B":    "Business Day",
    "W":    "Weekly",
    "W-MON": "Weekly (Monday)",
    "W-TUE": "Weekly (Tuesday)",
    "W-WED": "Weekly (Wednesday)",
    "W-THU": "Weekly (Thursday)",
    "W-FRI": "Weekly (Friday)",
    "W-SAT": "Weekly (Saturday)",
    "W-SUN": "Weekly (Sunday)",
    "MS":   "Month Start",
    "ME":   "Month End",
    "M":    "Month End",
    "QS":   "Quarter Start",
    "QE":   "Quarter End",
    "Q":    "Quarter End",
    "YS":   "Year Start",
    "YE":   "Year End",
    "A":    "Year End",
    "H":    "Hourly",
    "T":    "Minute",
    "min":  "Minute",
    "S":    "Second",
}


def friendly_label(freq_code: str) -> str:
    """Return a human-readable label for a pandas offset alias."""
    if freq_code in FREQ_LABELS:
        return FREQ_LABELS[freq_code]
    # Handle anchored weekly like "W-MON"
    if freq_code.startswith("W-"):
        return f"Weekly ({freq_code.split('-')[1]})"
    return freq_code


def detect_frequency(csv_path: str, date_column: str = "date") -> dict:
    """Detect dataset frequency from a CSV file.

    Returns a dict with:
        pandas_freq  - the pandas offset alias (e.g. "W-SUN", "D", "MS")
        label        - human-readable label
        unique_dates - number of unique dates found
        total_rows   - total number of rows in the CSV
        median_gap   - median gap between consecutive unique dates (timedelta)
        method       - which detection method succeeded
    """
    df = pd.read_csv(csv_path)
    total_rows = len(df)

    if date_column not in df.columns:
        raise ValueError(
            f"Column '{date_column}' not found. "
            f"Available columns: {list(df.columns)}"
        )

    # ---- 1. Extract UNIQUE sorted dates ----
    dt = pd.to_datetime(df[date_column], errors="coerce")
    unique_dates = dt.dropna().drop_duplicates().sort_values().reset_index(drop=True)
    n_unique = len(unique_dates)

    if n_unique < 2:
        return {
            "pandas_freq": "unknown",
            "label": "Cannot determine (fewer than 2 unique dates)",
            "unique_dates": n_unique,
            "total_rows": total_rows,
            "median_gap": None,
            "method": "none",
        }

    # ---- 2. Try pandas infer_freq (needs >= 3 regular points) ----
    idx = pd.DatetimeIndex(unique_dates)
    inferred = pd.infer_freq(idx) if n_unique >= 3 else None

    # ---- 3. Compute gap statistics regardless ----
    gaps = unique_dates.diff().dropna()
    median_gap = gaps.median()
    mode_gap = gaps.mode().iloc[0] if not gaps.mode().empty else median_gap
    min_gap = gaps.min()
    max_gap = gaps.max()
    mode_days = mode_gap.days

    # ---- 4. If infer_freq succeeded AND we have enough dates, trust it ----
    if inferred and n_unique >= 5:
        return {
            "pandas_freq": inferred,
            "label": friendly_label(inferred),
            "unique_dates": n_unique,
            "total_rows": total_rows,
            "median_gap": median_gap,
            "method": "pd.infer_freq (high confidence)",
        }

    # ---- 5. If infer_freq succeeded but few dates, report with caveat ----
    if inferred and n_unique < 5:
        return {
            "pandas_freq": inferred,
            "label": friendly_label(inferred),
            "unique_dates": n_unique,
            "total_rows": total_rows,
            "median_gap": median_gap,
            "method": f"pd.infer_freq (LOW confidence - only {n_unique} unique dates)",
        }

    # ---- 6. Fallback: heuristic based on the MODE of day-gaps ----
    heuristic_map = [
        (1,   "D"),
        (7,   "W"),
        (14,  "2W"),
        (28,  "MS"),
        (30,  "MS"),
        (31,  "MS"),
        (60,  "2MS"),
        (90,  "QS"),
        (91,  "QS"),
        (92,  "QS"),
        (182, "2QS"),
        (183, "2QS"),
        (365, "YS"),
        (366, "YS"),
    ]
    matched_freq = None
    for days, freq in heuristic_map:
        if abs(mode_days - days) <= 2:      # allow +/- 2 days tolerance
            matched_freq = freq
            break

    if matched_freq is None:
        matched_freq = f"{mode_days}D"      # custom N-day frequency

    return {
        "pandas_freq": matched_freq,
        "label": friendly_label(matched_freq),
        "unique_dates": n_unique,
        "total_rows": total_rows,
        "median_gap": median_gap,
        "method": f"heuristic (mode gap = {mode_days} days)",
    }


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Detect dataset frequency for a CSV time-series file."
    )
    parser.add_argument(
        "--file", required=True,
        help="Path to the CSV file (e.g. test_data_small.csv).",
    )
    parser.add_argument(
        "--date_column", default="date",
        help="Name of the date column. Default: 'date'.",
    )
    args = parser.parse_args()

    csv_path = os.path.abspath(args.file)
    if not os.path.isfile(csv_path):
        sys.stderr.write(f"[ERROR] File not found: {csv_path}\n")
        sys.exit(1)

    result = detect_frequency(csv_path, date_column=args.date_column)

    print("=" * 60)
    print("  Dataset Frequency Detection")
    print("=" * 60)
    print(f"  File          : {csv_path}")
    print(f"  Date column   : {args.date_column}")
    print(f"  Total rows    : {result['total_rows']:,}")
    print(f"  Unique dates  : {result['unique_dates']:,}")
    print(f"  Median gap    : {result['median_gap']}")
    print(f"  Frequency     : {result['pandas_freq']}  ({result['label']})")
    print(f"  Method        : {result['method']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
