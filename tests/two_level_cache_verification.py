import tempfile, os, sys, shutil
import pandas as pd
import numpy as np
sys.path.append('model-service')
os.chdir('model-service')
from app.models import ForecastEngine, CACHE_FUNC_DIR

# Clean any prior cache
cache_dir = os.path.join('cache', 'joblib')
if os.path.exists(cache_dir):
    shutil.rmtree(cache_dir)

# Create minimal CSV
dummy = {'date': pd.date_range('2012-01-02', periods=10, freq='W-MON'),
         'product_identifier': [74]*10, 'department_identifier': [1]*10,
         'category_of_product': ['CatA']*10, 'outlet': [111]*10,
         'state': ['StateX']*10, 'sales': [10,0,15,0,12,8,0,14,20,5]}
df = pd.DataFrame(dummy)
with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
    df.to_csv(f.name, index=False)
    path = f.name

engine = ForecastEngine()
engine.load_reference_data()

# Run 1: full cold start
print('=== RUN 1 (cold) ===')
r1 = engine.predict(path, forecast_periods=2, seasonality_period=4)
print('  forecast:', r1['values'])

# Run 2: different forecast_periods — model should be cached
print('=== RUN 2 (different forecast_periods) ===')
r2 = engine.predict(path, forecast_periods=3, seasonality_period=4)
print('  forecast:', r2['values'])

# Run 3: same params — pipeline hit
print('=== RUN 3 (same params) ===')
r3 = engine.predict(path, forecast_periods=3, seasonality_period=4)
print('  forecast:', r3['values'])

print('Temp path: ', path)
os.remove(path)
print('=== SUCCESS ===')