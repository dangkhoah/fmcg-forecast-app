import pandas as pd
import os

model_dir = r"d:\Namitech_Next\fmcg-forecast-app\model-service"
price_path = os.path.join(model_dir, "reference", "product_prices.csv")
week_path = os.path.join(model_dir, "reference", "date_to_week_id_map.csv")
train_path = os.path.join(model_dir, "reference", "train_data.csv")

print("Checking if files exist:")
print(f"price_path: {os.path.exists(price_path)}")
print(f"week_path: {os.path.exists(week_path)}")
print(f"train_path: {os.path.exists(train_path)}")

# 1. Load data
prod_price = pd.read_csv(
    price_path,
    names=["outlet", "product_identifier", "week_id", "sell_price"],
    header=0,
)
print("\nprod_price types:")
print(prod_price.dtypes)

date_week = pd.read_csv(
    week_path,
    names=["date", "week_id"],
    header=0,
    parse_dates=["date"],
)
print("\ndate_week types:")
print(date_week.dtypes)

df = pd.read_csv(train_path, parse_dates=["date"])
print("\ndf types:")
print(df.dtypes)

# Try merge 1
merged = pd.merge(prod_price, date_week, on="week_id", how="inner")
print("\nmerged types:")
print(merged.dtypes)

# Try merge 2
try:
    df_merged = pd.merge(
        df, merged,
        on=["date", "product_identifier", "outlet"],
        how="inner",
    )
    print("\nMerge successful!")
    print(df_merged.head())
except Exception as e:
    print("\nMerge failed with error:")
    import traceback
    traceback.print_exc()
