import pandas as pd

df = pd.read_csv("test_data_small.csv")
dates = pd.to_datetime(df["date"]).drop_duplicates().sort_values().reset_index(drop=True)

print(f"Total rows: {len(df)}")
print(f"Unique dates: {len(dates)}")
print(f"\nFirst 20 unique dates:")
print(dates.head(20).to_string())
print("")
diffs = dates.diff().dropna()

print(diffs)

print(f"\nDay-difference distribution:")
print(diffs.value_counts().head(10).to_string())

freq = pd.infer_freq(pd.DatetimeIndex(dates))
print(f"\npd.infer_freq result: {freq}")
