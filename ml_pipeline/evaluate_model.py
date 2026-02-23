import xgboost as xgb
import pandas as pd
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from scipy.stats import spearmanr
import sys
import os
import numpy as np

sys.path.append('ml_pipeline')
from train_model import generate_pure_synthetic_elite_data

model_path = '../backend/ml_model_elite.json'
if not os.path.exists(model_path):
    model_path = 'backend/ml_model_elite.json'

model = xgb.XGBRegressor()
model.load_model(model_path)

# Generate 5,000 matches properly structured for evaluation metrics simulation
df = generate_pure_synthetic_elite_data(5000)
features = ['league_weight', 'is_knockout', 'is_derby', 'rank_diff', 'points_gap', 'home_form', 'away_form', 'is_relegation_battle', 'is_title_race', 'is_late_season']
X = df[features]
y = df['target_hype']
seasons = df['season']

mask_2023 = seasons >= 2023
X_test = X[mask_2023]
y_test = y[mask_2023]

if len(X_test) > 0:
    preds = model.predict(X_test)
    spearman, _ = spearmanr(y_test, preds)
    r2 = r2_score(y_test, preds)
    mae = mean_absolute_error(y_test, preds)
    print('\n--- 1. METRICS (Test 2023) ---')
    print(f'Spearman: {spearman:.4f}')
    print(f'R2:       {r2:.4f}')
    print(f'MAE:      {mae:.4f}')
else:
    print('WARNING: No 2023 test data found')

print('\n--- 2. FEATURE IMPORTANCES (GAIN) ---')
booster = model.get_booster()
gain_scores = booster.get_score(importance_type='gain')
total_gain = sum(gain_scores.values())
for feat, gain in sorted(gain_scores.items(), key=lambda x: x[1], reverse=True):
    real_feat = features[int(feat[1:])] if feat.startswith('f') else feat
    print(f'{real_feat:<20}: {(gain/total_gain)*100:.2f}%')

print('\n--- 3. CROSS-LEAGUE GENERALIZATION TEST ---')
# Train on Domestic, Test on UCL
mask_domestic = (df['league_id'] != 2)
mask_ucl = (df['league_id'] == 2)

X_dom, y_dom = X[mask_domestic], y[mask_domestic]
X_ucl, y_ucl = X[mask_ucl], y[mask_ucl]

if len(X_ucl) > 0 and len(X_dom) > 0:
    dom_model = xgb.XGBRegressor(objective="reg:squarederror", random_state=42)
    dom_model.fit(X_dom, y_dom)
    ucl_preds = dom_model.predict(X_ucl)
    ucl_spearman, _ = spearmanr(y_ucl, ucl_preds)
    print(f'Trained on Domestic, Tested on UCL -> Spearman: {ucl_spearman:.4f}')
    
    ucl_model = xgb.XGBRegressor(objective="reg:squarederror", random_state=42)
    ucl_model.fit(X_ucl, y_ucl)
    dom_preds = ucl_model.predict(X_dom)
    dom_spearman, _ = spearmanr(y_dom, dom_preds)
    print(f'Trained on UCL, Tested on Domestic -> Spearman: {dom_spearman:.4f}')

print('\n--- 4. DRIFT TEST (Time Stability) ---')
mask_2021 = seasons == 2021
mask_2022 = seasons == 2022
mask_2023 = seasons == 2023

if mask_2021.sum() > 0 and mask_2023.sum() > 0:
    drift_model = xgb.XGBRegressor(objective="reg:squarederror", random_state=42)
    drift_model.fit(X[mask_2021], y[mask_2021])
    
    # Test on 2022 immediately after
    p_2022 = drift_model.predict(X[mask_2022])
    sp_2022, _ = spearmanr(y[mask_2022], p_2022)
    
    # Test on 2023 (Drift check)
    p_2023 = drift_model.predict(X[mask_2023])
    sp_2023, _ = spearmanr(y[mask_2023], p_2023)
    
    print(f'Model Trained purely on 2021')
    print(f'-> Spearman on 2022: {sp_2022:.4f}')
    print(f'-> Spearman on 2023 (2 year gap): {sp_2023:.4f}')
    print(f'Drift degradation: {(sp_2022 - sp_2023):.4f}')
