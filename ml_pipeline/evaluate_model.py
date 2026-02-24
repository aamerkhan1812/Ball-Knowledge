from __future__ import annotations

import os
import sys

import numpy as np
import xgboost as xgb
from scipy.stats import spearmanr
from sklearn.metrics import mean_absolute_error, r2_score

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.normpath(os.path.join(CURRENT_DIR, ".."))
sys.path.insert(0, CURRENT_DIR)

from train_model import FEATURE_COLUMNS, generate_pure_synthetic_elite_data


def resolve_model_path() -> str:
    candidates = [
        os.path.join(PROJECT_ROOT, "backend", "ml_model_elite.json"),
        os.path.join("backend", "ml_model_elite.json"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    raise FileNotFoundError("Could not find backend/ml_model_elite.json")


def main() -> int:
    model_path = resolve_model_path()
    model = xgb.XGBRegressor()
    model.load_model(model_path)

    df = generate_pure_synthetic_elite_data(5000)
    X = df[FEATURE_COLUMNS]
    y = df["target_hype"]
    seasons = df["season"]

    mask_2023 = seasons >= 2023
    X_test = X[mask_2023]
    y_test = y[mask_2023]

    if len(X_test) == 0:
        print("WARNING: No 2023 test data found.")
        return 1

    preds = model.predict(X_test)
    spearman, _ = spearmanr(y_test, preds)
    r2 = r2_score(y_test, preds)
    mae = mean_absolute_error(y_test, preds)

    print("\n--- 1. METRICS (Test 2023) ---")
    print(f"Spearman: {float(spearman):.4f}")
    print(f"R2:       {float(r2):.4f}")
    print(f"MAE:      {float(mae):.4f}")

    print("\n--- 2. FEATURE IMPORTANCES (GAIN) ---")
    booster = model.get_booster()
    gain_scores = booster.get_score(importance_type="gain")
    total_gain = sum(gain_scores.values()) or 1.0
    for feat, gain in sorted(gain_scores.items(), key=lambda item: item[1], reverse=True):
        real_feat = FEATURE_COLUMNS[int(feat[1:])] if feat.startswith("f") else feat
        print(f"{real_feat:<20}: {(gain / total_gain) * 100:.2f}%")

    print("\n--- 3. CROSS-LEAGUE GENERALIZATION TEST ---")
    mask_domestic = df["league_id"] != 2
    mask_ucl = df["league_id"] == 2
    X_dom, y_dom = X[mask_domestic], y[mask_domestic]
    X_ucl, y_ucl = X[mask_ucl], y[mask_ucl]

    if len(X_ucl) > 0 and len(X_dom) > 0:
        dom_model = xgb.XGBRegressor(objective="reg:squarederror", random_state=42)
        dom_model.fit(X_dom, y_dom)
        ucl_preds = dom_model.predict(X_ucl)
        ucl_spearman, _ = spearmanr(y_ucl, ucl_preds)
        print(f"Trained on Domestic, Tested on UCL -> Spearman: {float(ucl_spearman):.4f}")

        ucl_model = xgb.XGBRegressor(objective="reg:squarederror", random_state=42)
        ucl_model.fit(X_ucl, y_ucl)
        dom_preds = ucl_model.predict(X_dom)
        dom_spearman, _ = spearmanr(y_dom, dom_preds)
        print(f"Trained on UCL, Tested on Domestic -> Spearman: {float(dom_spearman):.4f}")

    print("\n--- 4. DRIFT TEST (Time Stability) ---")
    mask_2021 = seasons == 2021
    mask_2022 = seasons == 2022
    mask_2023 = seasons == 2023

    if mask_2021.sum() > 0 and mask_2023.sum() > 0:
        drift_model = xgb.XGBRegressor(objective="reg:squarederror", random_state=42)
        drift_model.fit(X[mask_2021], y[mask_2021])

        preds_2022 = drift_model.predict(X[mask_2022])
        sp_2022, _ = spearmanr(y[mask_2022], preds_2022)

        preds_2023 = drift_model.predict(X[mask_2023])
        sp_2023, _ = spearmanr(y[mask_2023], preds_2023)

        print("Model trained purely on 2021")
        print(f"-> Spearman on 2022: {float(sp_2022):.4f}")
        print(f"-> Spearman on 2023 (2-year gap): {float(sp_2023):.4f}")
        print(f"Drift degradation: {(float(sp_2022) - float(sp_2023)):.4f}")

    print("\n--- 5. TOP-K (Top-2) ACCURACY METRIC ---")
    np.random.seed(42)
    df_eval = X_test.copy()
    df_eval["target_hype"] = y_test

    top_2_hits = 0
    total_matchdays = 30
    for _ in range(total_matchdays):
        if len(df_eval) < 10:
            break
        day_matches = df_eval.sample(n=10)
        real_top_idx = day_matches["target_hype"].idxmax()
        day_matches["preds"] = model.predict(day_matches[FEATURE_COLUMNS])
        model_top_2 = day_matches.nlargest(2, "preds").index.tolist()
        if real_top_idx in model_top_2:
            top_2_hits += 1

    accuracy = (top_2_hits / total_matchdays) * 100
    print("Simulated 30 matchdays (10 matches per day).")
    print(
        f"Was highest actual hype match inside Model Top 2? {top_2_hits}/{total_matchdays} -> {accuracy:.1f}%"
    )
    if accuracy >= 80:
        print("Status: SYSTEM VALIDATED")
    else:
        print("Status: NEEDS IMPROVEMENT")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
