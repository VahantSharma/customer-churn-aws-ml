#!/usr/bin/env python3
"""
High-Quality Customer Churn Prediction Model Training (Optimized)

Strategy:
  1. Feature engineering (22 numeric + 3 categorical -> 30 features after OHE)
  2. Hyperparameter tuning on a STRATIFIED SAMPLE (50K) for speed
  3. Train FINAL model on FULL DATASET with best hyperparameters
  4. Build a Stacking Ensemble from the top models
  5. Comprehensive evaluation on held-out test set (20%)
  6. Tree-based feature importance

Output:
  model/model.joblib          - Trained sklearn Pipeline (preprocessor + model)
  model/metrics.json          - All evaluation metrics
  model/feature_importance.csv - Feature importance ranking
  model/confusion_matrix.png  - Confusion matrix plot
  model/roc_curve.png         - ROC curve plot
  model/precision_recall.png  - Precision-Recall curve plot
  model/feature_importance.png - Feature importance plot
"""

import os, sys, json, warnings, logging, time
import numpy as np
import pandas as pd
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.model_selection import (
    train_test_split, StratifiedKFold, RandomizedSearchCV,
)
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.ensemble import (
    RandomForestClassifier, GradientBoostingClassifier,
    StackingClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score, classification_report,
    confusion_matrix, roc_curve, precision_recall_curve,
    matthews_corrcoef, cohen_kappa_score, log_loss, brier_score_loss,
)
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), "model", "training_log.txt"), mode="w"),
    ],
)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "customer_churn.csv")
MODEL_DIR = os.path.join(BASE_DIR, "model")
os.makedirs(MODEL_DIR, exist_ok=True)

RANDOM_STATE = 42
TUNING_SAMPLE = 50_000   # Tune on 50K sample for speed
N_ITER_SEARCH  = 15       # RandomizedSearchCV iterations (reduced for speed)
CV_FOLDS       = 3        # 3-fold CV for tuning (5-fold used in stacking)
np.random.seed(RANDOM_STATE)


# ===========================================================================
# 1. DATA LOADING & CLEANING
# ===========================================================================
def load_and_clean(path):
    logger.info(f"Loading data from {path}")
    df = pd.read_csv(path)
    logger.info(f"  Raw shape: {df.shape}")

    if "CustomerID" in df.columns:
        df = df.drop("CustomerID", axis=1)

    before = len(df)
    df = df.dropna(subset=["Churn"])
    logger.info(f"  Dropped {before - len(df)} rows with missing target")
    df["Churn"] = df["Churn"].astype(int)

    logger.info(f"  Clean shape: {df.shape}")
    logger.info(f"  Churn rate: {df['Churn'].mean():.4f}")
    return df


# ===========================================================================
# 2. FEATURE ENGINEERING
# ===========================================================================
def engineer_features(df):
    logger.info("Engineering features ...")
    df = df.copy()

    # Interaction features
    df["spend_per_tenure"]   = df["Total Spend"] / (df["Tenure"] + 1)
    df["support_per_tenure"] = df["Support Calls"] / (df["Tenure"] + 1)
    df["usage_per_tenure"]   = df["Usage Frequency"] / (df["Tenure"] + 1)
    df["delay_per_tenure"]   = df["Payment Delay"] / (df["Tenure"] + 1)
    df["cost_per_usage"]     = df["Total Spend"] / (df["Usage Frequency"] + 1)
    df["recency_score"]      = df["Last Interaction"] / 30.0

    # Risk composites
    df["risk_score"]         = df["Support Calls"] * df["Payment Delay"]
    df["frustration_index"]  = df["Support Calls"] / (df["Usage Frequency"] + 1)

    # Binary flags
    df["is_high_support"]  = (df["Support Calls"]  >= 7).astype(int)
    df["is_payment_late"]  = (df["Payment Delay"]  >= 15).astype(int)
    df["is_low_usage"]     = (df["Usage Frequency"] <= 5).astype(int)
    df["is_new_customer"]  = (df["Tenure"]          <= 6).astype(int)
    df["is_long_tenure"]   = (df["Tenure"]          >= 40).astype(int)

    # Ordinal buckets
    df["tenure_bucket"] = pd.cut(
        df["Tenure"], bins=[0, 6, 12, 24, 36, 61],
        labels=[0, 1, 2, 3, 4], include_lowest=True,
    ).astype(float)
    df["age_group"] = pd.cut(
        df["Age"], bins=[0, 25, 35, 45, 55, 100],
        labels=[0, 1, 2, 3, 4], include_lowest=True,
    ).astype(float)

    logger.info(f"  Feature-engineered shape: {df.shape}")
    return df


# ===========================================================================
# 3. FEATURE LISTS & PREPROCESSOR
# ===========================================================================
def get_feature_lists(df):
    target = "Churn"
    categorical = ["Gender", "Subscription Type", "Contract Length"]
    numeric = [c for c in df.columns if c != target and c not in categorical]
    return numeric, categorical


def build_preprocessor(numeric_features, categorical_features):
    return ColumnTransformer(
        transformers=[
            ("num", Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]), numeric_features),
            ("cat", Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ]), categorical_features),
        ],
        remainder="drop",
    )


# ===========================================================================
# 4. TUNING (on sample) then refit on FULL training set
# ===========================================================================
def get_model_configs():
    return {
        "XGBoost": (
            XGBClassifier(
                eval_metric="logloss", use_label_encoder=False,
                random_state=RANDOM_STATE, tree_method="hist", n_jobs=-1,
            ),
            {
                "model__n_estimators": [200, 400, 600, 800],
                "model__max_depth": [4, 6, 8, 10],
                "model__learning_rate": [0.01, 0.05, 0.1],
                "model__subsample": [0.7, 0.8, 0.9],
                "model__colsample_bytree": [0.7, 0.8, 0.9],
                "model__min_child_weight": [1, 3, 5],
                "model__gamma": [0, 0.1, 0.2],
                "model__reg_alpha": [0, 0.01, 0.1],
                "model__reg_lambda": [1, 1.5, 2],
            },
        ),
        "LightGBM": (
            LGBMClassifier(
                random_state=RANDOM_STATE, n_jobs=-1, verbose=-1,
            ),
            {
                "model__n_estimators": [200, 400, 600, 800],
                "model__max_depth": [4, 6, 8, -1],
                "model__learning_rate": [0.01, 0.05, 0.1],
                "model__num_leaves": [31, 50, 80, 127],
                "model__subsample": [0.7, 0.8, 0.9],
                "model__colsample_bytree": [0.7, 0.8, 0.9],
                "model__min_child_samples": [10, 20, 50],
                "model__reg_alpha": [0, 0.01, 0.1],
                "model__reg_lambda": [0, 1, 2],
            },
        ),
        "RandomForest": (
            RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=-1),
            {
                "model__n_estimators": [200, 300, 500],
                "model__max_depth": [10, 15, 20],
                "model__min_samples_split": [2, 5],
                "model__min_samples_leaf": [1, 2],
                "model__max_features": ["sqrt", "log2"],
            },
        ),
        # GradientBoosting removed: purely sequential, takes hours for
        # negligible gain over XGBoost/LightGBM (both > 0.999 F1).
    }


def tune_on_sample(name, estimator, param_dist, preprocessor, X_sample, y_sample):
    logger.info(f"  Tuning {name} on {len(X_sample)} samples ...")
    t0 = time.time()

    pipe = Pipeline([("preprocessor", preprocessor), ("model", estimator)])
    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)

    search = RandomizedSearchCV(
        pipe, param_distributions=param_dist,
        n_iter=N_ITER_SEARCH, scoring="f1", cv=cv,
        n_jobs=-1, random_state=RANDOM_STATE, verbose=0,
    )
    search.fit(X_sample, y_sample)

    elapsed = time.time() - t0
    logger.info(f"    Best CV F1: {search.best_score_:.4f}  ({elapsed:.0f}s)")
    best_model_params = {
        k.replace("model__", ""): v
        for k, v in search.best_params_.items()
        if k.startswith("model__")
    }
    return best_model_params, search.best_score_


def train_final_model(name, estimator_template, best_params, preprocessor, X_train, y_train):
    logger.info(f"  Training final {name} on {len(X_train)} rows ...")
    t0 = time.time()

    model = estimator_template.__class__(**{
        **estimator_template.get_params(),
        **best_params,
    })
    pipe = Pipeline([("preprocessor", preprocessor), ("model", model)])
    pipe.fit(X_train, y_train)

    logger.info(f"    Trained in {time.time()-t0:.0f}s")
    return pipe


# ===========================================================================
# 5. EVALUATION
# ===========================================================================
def evaluate(model, X_test, y_test, label="Model"):
    y_pred  = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    m = {
        "accuracy":         float(accuracy_score(y_test, y_pred)),
        "precision":        float(precision_score(y_test, y_pred)),
        "recall":           float(recall_score(y_test, y_pred)),
        "f1":               float(f1_score(y_test, y_pred)),
        "roc_auc":          float(roc_auc_score(y_test, y_proba)),
        "avg_precision":    float(average_precision_score(y_test, y_proba)),
        "matthews_corrcoef": float(matthews_corrcoef(y_test, y_pred)),
        "cohen_kappa":      float(cohen_kappa_score(y_test, y_pred)),
        "log_loss":         float(log_loss(y_test, y_proba)),
        "brier_score":      float(brier_score_loss(y_test, y_proba)),
    }

    logger.info(f"  [{label}]  Acc={m['accuracy']:.4f}  Prec={m['precision']:.4f}"
                f"  Rec={m['recall']:.4f}  F1={m['f1']:.4f}  AUC={m['roc_auc']:.4f}"
                f"  MCC={m['matthews_corrcoef']:.4f}")
    return m, y_pred, y_proba


# ===========================================================================
# 6. PLOTS
# ===========================================================================
def plot_confusion_matrix(y_test, y_pred, path):
    cm = confusion_matrix(y_test, y_pred)
    fig, ax = plt.subplots(figsize=(7, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=["No Churn","Churn"], yticklabels=["No Churn","Churn"], ax=ax)
    ax.set_xlabel("Predicted"); ax.set_ylabel("Actual")
    ax.set_title("Confusion Matrix")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)
    logger.info(f"  Saved -> {path}")

def plot_roc(y_test, y_proba, auc, path):
    fpr, tpr, _ = roc_curve(y_test, y_proba)
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(fpr, tpr, lw=2, label=f"AUC = {auc:.4f}")
    ax.plot([0,1],[0,1],"k--",lw=1)
    ax.set_xlabel("FPR"); ax.set_ylabel("TPR"); ax.set_title("ROC Curve")
    ax.legend(loc="lower right")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)
    logger.info(f"  Saved -> {path}")

def plot_pr(y_test, y_proba, ap, path):
    prec, rec, _ = precision_recall_curve(y_test, y_proba)
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(rec, prec, lw=2, label=f"AP = {ap:.4f}")
    ax.set_xlabel("Recall"); ax.set_ylabel("Precision")
    ax.set_title("Precision-Recall Curve"); ax.legend()
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)
    logger.info(f"  Saved -> {path}")

def plot_feature_importance(imp_df, path):
    top = imp_df.head(20)
    fig, ax = plt.subplots(figsize=(9, 7))
    sns.barplot(data=top, x="importance", y="feature", palette="viridis", ax=ax)
    ax.set_title("Top 20 Feature Importances"); ax.set_xlabel("Importance")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)
    logger.info(f"  Saved -> {path}")


# ===========================================================================
# 7. FEATURE IMPORTANCE (tree-based)
# ===========================================================================
def compute_feature_importance(model, preprocessor):
    try:
        final_model = model.named_steps["model"]

        ohe = preprocessor.named_transformers_["cat"].named_steps["encoder"]
        cat_names = list(ohe.get_feature_names_out())
        num_names = list(preprocessor.transformers_[0][2])
        feature_names = num_names + cat_names

        if isinstance(final_model, StackingClassifier):
            for name, est in final_model.estimators_:
                if hasattr(est, "feature_importances_"):
                    importances = est.feature_importances_
                    break
            else:
                return pd.DataFrame(columns=["feature", "importance"])
        elif hasattr(final_model, "feature_importances_"):
            importances = final_model.feature_importances_
        else:
            return pd.DataFrame(columns=["feature", "importance"])

        imp_df = (
            pd.DataFrame({"feature": feature_names, "importance": importances})
            .sort_values("importance", ascending=False)
            .reset_index(drop=True)
        )
        return imp_df
    except Exception as e:
        logger.warning(f"Feature importance failed: {e}")
        return pd.DataFrame(columns=["feature", "importance"])


# ===========================================================================
# 8. MAIN
# ===========================================================================
def main():
    t0 = time.time()
    logger.info("=" * 70)
    logger.info("  CUSTOMER CHURN MODEL TRAINING - High-Quality Pipeline")
    logger.info("=" * 70)

    # ---- Load & Engineer ----
    df = load_and_clean(DATA_PATH)
    df = engineer_features(df)

    target = "Churn"
    X = df.drop(target, axis=1)
    y = df[target]

    # 80/20 stratified split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y,
    )
    logger.info(f"Train: {X_train.shape}   Test: {X_test.shape}")

    numeric_features, categorical_features = get_feature_lists(df)
    logger.info(f"Numeric ({len(numeric_features)}): {numeric_features}")
    logger.info(f"Categorical ({len(categorical_features)}): {categorical_features}")

    # ---- Create tuning sample ----
    sample_n = min(TUNING_SAMPLE, len(X_train))
    X_sample, _, y_sample, _ = train_test_split(
        X_train, y_train, train_size=sample_n,
        random_state=RANDOM_STATE, stratify=y_train,
    )
    logger.info(f"Tuning sample: {X_sample.shape}")

    # ---- Tune all models on sample ----
    preprocessor = build_preprocessor(numeric_features, categorical_features)
    configs = get_model_configs()
    tuning_results = {}

    logger.info("=" * 60)
    logger.info("PHASE 1: HYPERPARAMETER TUNING (on 50K sample)")
    logger.info("=" * 60)

    for name, (est, params) in configs.items():
        try:
            best_params, cv_f1 = tune_on_sample(
                name, est, params, preprocessor, X_sample, y_sample,
            )
            tuning_results[name] = {"estimator": est, "params": best_params, "cv_f1": cv_f1}
        except Exception as e:
            logger.error(f"  {name} tuning failed: {e}")

    # ---- Train final models on FULL training set ----
    logger.info("=" * 60)
    logger.info("PHASE 2: TRAINING ON FULL DATASET (352K rows)")
    logger.info("=" * 60)

    final_models = {}
    preprocessor_full = build_preprocessor(numeric_features, categorical_features)

    for name, info in tuning_results.items():
        try:
            pipe = train_final_model(
                name, info["estimator"], info["params"],
                preprocessor_full, X_train, y_train,
            )
            metrics, y_pred, y_proba = evaluate(pipe, X_test, y_test, label=name)
            final_models[name] = {
                "pipeline": pipe,
                "metrics": metrics,
                "y_pred": y_pred,
                "y_proba": y_proba,
                "cv_f1": info["cv_f1"],
            }
        except Exception as e:
            logger.error(f"  {name} training failed: {e}")

    if not final_models:
        logger.error("All models failed!")
        sys.exit(1)

    # ---- Best single model ----
    best_name = max(final_models, key=lambda n: final_models[n]["metrics"]["f1"])
    best = final_models[best_name]
    logger.info(f"\nBest single model: {best_name}  (F1={best['metrics']['f1']:.4f})")

    # ---- Stacking Ensemble ----
    logger.info("\n" + "=" * 60)
    logger.info("PHASE 3: STACKING ENSEMBLE")
    logger.info("=" * 60)

    estimators_list = [
        (name, res["pipeline"].named_steps["model"])
        for name, res in final_models.items()
    ]

    stacking = StackingClassifier(
        estimators=estimators_list,
        final_estimator=LogisticRegression(max_iter=1000, C=1.0, random_state=RANDOM_STATE),
        cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE),
        stack_method="predict_proba",
        n_jobs=-1,
    )

    stack_pipe = Pipeline([("preprocessor", preprocessor_full), ("model", stacking)])
    logger.info("  Fitting stacking ensemble ...")
    t_stack = time.time()
    stack_pipe.fit(X_train, y_train)
    logger.info(f"  Stacking trained in {time.time()-t_stack:.0f}s")

    stack_metrics, stack_y_pred, stack_y_proba = evaluate(
        stack_pipe, X_test, y_test, label="StackingEnsemble",
    )

    # ---- Choose final model ----
    if stack_metrics["f1"] >= best["metrics"]["f1"]:
        final_model = stack_pipe
        final_name  = "StackingEnsemble"
        final_metrics = stack_metrics
        final_y_pred  = stack_y_pred
        final_y_proba = stack_y_proba
    else:
        final_model   = best["pipeline"]
        final_name    = best_name
        final_metrics = best["metrics"]
        final_y_pred  = best["y_pred"]
        final_y_proba = best["y_proba"]

    logger.info(f"\n>> FINAL MODEL: {final_name}")

    # ---- Plots ----
    logger.info("\nGenerating plots ...")
    plot_confusion_matrix(y_test, final_y_pred, os.path.join(MODEL_DIR, "confusion_matrix.png"))
    plot_roc(y_test, final_y_proba, final_metrics["roc_auc"], os.path.join(MODEL_DIR, "roc_curve.png"))
    plot_pr(y_test, final_y_proba, final_metrics["avg_precision"], os.path.join(MODEL_DIR, "precision_recall.png"))

    # ---- Feature importance ----
    logger.info("Computing feature importance ...")
    fitted_pp = final_model.named_steps["preprocessor"]
    imp_df = compute_feature_importance(final_model, fitted_pp)
    imp_df.to_csv(os.path.join(MODEL_DIR, "feature_importance.csv"), index=False)
    if len(imp_df) > 0:
        plot_feature_importance(imp_df, os.path.join(MODEL_DIR, "feature_importance.png"))

    # ---- Save model ----
    model_path = os.path.join(MODEL_DIR, "model.joblib")
    joblib.dump(final_model, model_path)
    logger.info(f"  Model saved -> {model_path}")
    logger.info(f"  Model size: {os.path.getsize(model_path) / 1024 / 1024:.1f} MB")

    # ---- Full classification report ----
    logger.info(f"\n{'='*60}")
    logger.info("FULL CLASSIFICATION REPORT")
    logger.info(f"{'='*60}")
    logger.info("\n" + classification_report(y_test, final_y_pred, target_names=["No Churn", "Churn"]))

    # ---- Save metrics ----
    all_model_results = {}
    for name, res in final_models.items():
        all_model_results[name] = {
            "cv_f1_on_sample": round(res["cv_f1"], 4),
            **{k: round(v, 4) for k, v in res["metrics"].items()},
        }
    all_model_results["StackingEnsemble"] = {
        "cv_f1_on_sample": None,
        **{k: round(v, 4) for k, v in stack_metrics.items()},
    }

    metrics_report = {
        "final_model": final_name,
        "final_metrics": {k: round(v, 4) for k, v in final_metrics.items()},
        "all_models": all_model_results,
        "dataset": {
            "total_rows": len(df),
            "train_rows": len(X_train),
            "test_rows": len(X_test),
            "n_features_engineered": X.shape[1],
            "churn_rate": round(float(y.mean()), 4),
        },
        "feature_importance_top10": (
            imp_df.head(10).to_dict(orient="records") if len(imp_df) > 0 else []
        ),
    }

    with open(os.path.join(MODEL_DIR, "metrics.json"), "w") as f:
        json.dump(metrics_report, f, indent=2)

    elapsed = time.time() - t0
    logger.info(f"\n{'='*70}")
    logger.info(f"  TRAINING COMPLETE - {elapsed:.1f}s ({elapsed/60:.1f} min)")
    logger.info(f"  Final Model : {final_name}")
    logger.info(f"  Accuracy    : {final_metrics['accuracy']:.4f}")
    logger.info(f"  Precision   : {final_metrics['precision']:.4f}")
    logger.info(f"  Recall      : {final_metrics['recall']:.4f}")
    logger.info(f"  F1 Score    : {final_metrics['f1']:.4f}")
    logger.info(f"  ROC AUC     : {final_metrics['roc_auc']:.4f}")
    logger.info(f"  MCC         : {final_metrics['matthews_corrcoef']:.4f}")
    logger.info(f"  Log Loss    : {final_metrics['log_loss']:.4f}")
    logger.info(f"{'='*70}")


if __name__ == "__main__":
    main()
