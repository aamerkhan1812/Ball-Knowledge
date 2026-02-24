from __future__ import annotations

import os

import numpy as np
import pandas as pd
import xgboost as xgb
from loguru import logger
from scipy.stats import spearmanr
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.preprocessing import MinMaxScaler

FEATURE_COLUMNS = [
    "league_weight",
    "is_knockout",
    "is_derby",
    "rank_diff",
    "points_gap",
    "home_form",
    "away_form",
    "is_relegation_battle",
    "is_title_race",
    "is_late_season",
]


def generate_pure_synthetic_elite_data(num_samples: int = 5000) -> pd.DataFrame:
    np.random.seed(42)
    rows = []
    for _ in range(num_samples):
        season = int(np.random.choice([2021, 2022, 2023]))
        league_id = int(np.random.choice([2, 39, 140, 78, 135]))
        league_weight = 1.5 if league_id == 2 else 1.0
        is_knockout = int(np.random.choice([0, 1], p=[0.9, 0.1]))
        is_derby = int(np.random.choice([0, 1], p=[0.95, 0.05]))
        rank_diff = int(np.random.randint(0, 15))
        points_gap = int(np.random.randint(0, 20))
        home_form = int(np.random.randint(2, 16))
        away_form = int(np.random.randint(2, 16))
        is_relegation_battle = int(np.random.choice([0, 1], p=[0.95, 0.05]))
        is_title_race = int(np.random.choice([0, 1], p=[0.95, 0.05]))
        is_late_season = int(np.random.choice([0, 1], p=[0.8, 0.2]))

        target = (
            (league_weight * 5)
            + (is_knockout * 15)
            + (is_derby * 20)
            + (is_title_race * 25)
            + (home_form + away_form)
            + max(0, 15 - rank_diff)
            + max(0, 20 - points_gap)
            + (is_relegation_battle * is_late_season * 15)
            + np.random.normal(0, 8)
        )

        rows.append(
            {
                "season": season,
                "league_id": league_id,
                "league_weight": league_weight,
                "is_knockout": is_knockout,
                "is_derby": is_derby,
                "rank_diff": rank_diff,
                "points_gap": points_gap,
                "home_form": home_form,
                "away_form": away_form,
                "is_relegation_battle": is_relegation_battle,
                "is_title_race": is_title_race,
                "is_late_season": is_late_season,
                "target_hype": min(100, max(0, target)),
            }
        )
    return pd.DataFrame(rows)


def load_data() -> pd.DataFrame:
    filepath = "data/historical_matches_elite.csv"
    if os.path.exists(filepath):
        return pd.read_csv(filepath)

    allow_synthetic = os.getenv("ALLOW_SYNTHETIC_DATA", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if not allow_synthetic:
        raise FileNotFoundError(
            f"Missing dataset {filepath}. Run ml_pipeline/collect_data.py or set ALLOW_SYNTHETIC_DATA=true."
        )

    logger.warning("Dataset missing. Training with synthetic data because ALLOW_SYNTHETIC_DATA=true.")
    return generate_pure_synthetic_elite_data()


def train_xgboost() -> None:
    logger.info("Loading dataset...")
    df = load_data()

    missing_columns = [column for column in FEATURE_COLUMNS + ["target_hype", "season"] if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Dataset is missing required columns: {missing_columns}")

    X = df[FEATURE_COLUMNS]
    y_raw = df["target_hype"]
    seasons = df["season"]

    scaler = MinMaxScaler(feature_range=(10, 100))
    y = scaler.fit_transform(y_raw.values.reshape(-1, 1)).flatten()

    train_mask = seasons <= 2022
    test_mask = seasons >= 2023

    if train_mask.sum() == 0 or test_mask.sum() == 0:
        logger.warning("Time-based split not possible. Falling back to random 80/20 split.")
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
    else:
        logger.info("Using time-based split: train<=2022, test>=2023.")
        X_train, X_test = X[train_mask], X[test_mask]
        y_train, y_test = y[train_mask], y[test_mask]

    param_grid = {
        "max_depth": [3, 5, 6],
        "learning_rate": [0.03, 0.05, 0.1],
        "n_estimators": [100, 300, 500],
        "min_child_weight": [1, 3, 5],
    }

    logger.info("Running GridSearchCV hyperparameter tuning.")
    base_model = xgb.XGBRegressor(objective="reg:squarederror", random_state=42)
    grid_search = GridSearchCV(
        estimator=base_model,
        param_grid=param_grid,
        cv=3,
        scoring="neg_mean_squared_error",
        n_jobs=-1,
    )
    grid_search.fit(X_train, y_train)

    model = grid_search.best_estimator_
    preds = model.predict(X_test)

    rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
    mae = float(mean_absolute_error(y_test, preds))
    r2 = float(r2_score(y_test, preds))
    spearman_corr, _ = spearmanr(y_test, preds)

    logger.info(f"Best parameters: {grid_search.best_params_}")
    logger.info("Final model evaluation metrics:")
    logger.info(f"RMSE: {rmse:.2f}")
    logger.info(f"MAE: {mae:.2f}")
    logger.info(f"R2: {r2:.2f}")
    logger.info(f"Spearman Rank Correlation: {float(spearman_corr):.3f}")

    logger.info("Feature importances:")
    for feature, importance in sorted(
        zip(FEATURE_COLUMNS, model.feature_importances_), key=lambda item: item[1], reverse=True
    ):
        logger.info(f"{feature}: {float(importance):.4f}")

    model_path = "backend/ml_model_elite.json"
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    model.save_model(model_path)
    logger.info(f"Saved model to {model_path}")


if __name__ == "__main__":
    train_xgboost()
