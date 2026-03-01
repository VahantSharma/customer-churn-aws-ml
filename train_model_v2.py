#!/usr/bin/env python3
"""
Customer Churn Prediction — Production Training Pipeline (v2)

This version addresses the synthetic data issue in customer_churn.csv.

PROBLEM DISCOVERED:
  The dataset is synthetically generated with hard-coded deterministic rules:
    - Support Calls >= 6   → 100% churn (118K rows)
    - Contract = Monthly   → 100% churn (87K rows)
    - Payment Delay > 20   → 100% churn (84K rows)
    - Total Spend in Q1    → 100% churn (88K rows)
  Combined: 218K rows (49.6%) have deterministic churn = 1.

  These trivial rules inflate metrics to 99.99% — misleading and not production-worthy.

SOLUTION:
  Phase 1: Build a RULES ENGINE for the deterministic cases (100% precision, by definition)
  Phase 2: Train an ML MODEL on the remaining 222K ambiguous rows (14.2% churn)
  Phase 3: Combine into a HYBRID PREDICTOR:
           - If deterministic rule fires → predict churn (no ML needed)
           - Otherwise → use ML model

  This gives HONEST metrics on the hard cases and PERFECT handling of the easy ones.

Output:
  model/model.joblib              - Trained sklearn Pipeline (ML model for ambiguous cases)
  model/hybrid_predictor.joblib   - Complete hybrid predictor (rules + ML)
  model/metrics.json              - Honest evaluation metrics
  model/data_analysis.json        - Dataset analysis showing the synthetic patterns
  model/confusion_matrix.png      - Confusion matrix (ML model on hard cases)
  model/roc_curve.png             - ROC curve
  model/precision_recall.png      - Precision-Recall curve
  model/feature_importance.png    - Feature importance plot
  model/feature_importance.csv    - Feature importance ranking
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
    RandomForestClassifier, StackingClassifier,
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
        logging.FileHandler(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "model", "training_log.txt"),
            mode="w",
        ),
    ],
)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "customer_churn.csv")
MODEL_DIR = os.path.join(BASE_DIR, "model")
os.makedirs(MODEL_DIR, exist_ok=True)

RANDOM_STATE = 42
TUNING_SAMPLE = 50_000
N_ITER_SEARCH = 20
CV_FOLDS = 5
np.random.seed(RANDOM_STATE)


# ===========================================================================
# 1. DETERMINISTIC RULES ENGINE
# ===========================================================================
class ChurnRulesEngine:
    """
    Captures the deterministic churn patterns in the synthetic data.
    If ANY rule fires, the customer WILL churn (100% precision in training data).
    """

    RULES = [
        ("high_support_calls", lambda df: df["Support Calls"] >= 6),
        ("monthly_contract",   lambda df: df["Contract Length"] == "Monthly"),
        ("high_payment_delay", lambda df: df["Payment Delay"] > 20),
        ("very_low_spend",     lambda df: df["Total Spend"] <= df["Total Spend"].quantile(0.20)),
    ]

    def __init__(self):
        self.spend_threshold = None  # Will be set during fit

    def fit(self, df):
        """Learn the spend threshold from training data."""
        self.spend_threshold = df["Total Spend"].quantile(0.20)
        logger.info(f"  Rules Engine: spend_threshold (Q20) = {self.spend_threshold:.2f}")
        return self

    def predict_mask(self, df):
        """Return boolean mask: True = deterministic churn."""
        mask = pd.Series(False, index=df.index)
        mask |= df["Support Calls"] >= 6
        mask |= df["Contract Length"] == "Monthly"
        mask |= df["Payment Delay"] > 20
        mask |= df["Total Spend"] <= self.spend_threshold
        return mask

    def analyze(self, df):
        """Analyze how many rows each rule captures."""
        results = {}
        for name, rule_fn in self.RULES:
            if name == "very_low_spend":
                rule_mask = df["Total Spend"] <= self.spend_threshold
            else:
                rule_mask = rule_fn(df)
            churn_rate = df.loc[rule_mask, "Churn"].mean() if rule_mask.any() else 0
            results[name] = {
                "count": int(rule_mask.sum()),
                "pct": round(float(rule_mask.sum() / len(df) * 100), 1),
                "churn_rate": round(float(churn_rate), 4),
            }
        combined = self.predict_mask(df)
        results["combined"] = {
            "count": int(combined.sum()),
            "pct": round(float(combined.sum() / len(df) * 100), 1),
            "churn_rate": round(float(df.loc[combined, "Churn"].mean()), 4),
        }
        return results


# ===========================================================================
# 2. HYBRID PREDICTOR
# ===========================================================================
class HybridChurnPredictor:
    """
    Combines rules engine + ML model.
    - If a deterministic rule fires → predict churn (prob=1.0)
    - Otherwise → use ML model
    """

    def __init__(self, rules_engine, ml_pipeline, feature_engineer_fn):
        self.rules_engine = rules_engine
        self.ml_pipeline = ml_pipeline
        self.feature_engineer_fn = feature_engineer_fn

    def predict(self, df_raw):
        """Predict on raw (un-engineered) DataFrame."""
        result = np.zeros(len(df_raw), dtype=int)
        deterministic = self.rules_engine.predict_mask(df_raw)
        result[deterministic.values] = 1

        ambiguous_idx = ~deterministic
        if ambiguous_idx.any():
            df_amb = self.feature_engineer_fn(df_raw[ambiguous_idx])
            result[ambiguous_idx.values] = self.ml_pipeline.predict(df_amb)

        return result

    def predict_proba(self, df_raw):
        """Predict probabilities on raw DataFrame."""
        proba = np.zeros(len(df_raw))
        deterministic = self.rules_engine.predict_mask(df_raw)
        proba[deterministic.values] = 1.0

        ambiguous_idx = ~deterministic
        if ambiguous_idx.any():
            df_amb = self.feature_engineer_fn(df_raw[ambiguous_idx])
            proba[ambiguous_idx.values] = self.ml_pipeline.predict_proba(df_amb)[:, 1]

        return proba


# ===========================================================================
# 3. DATA LOADING & CLEANING
# ===========================================================================
def load_and_clean(path):
    logger.info(f"Loading data from {path}")
    df = pd.read_csv(path)
    logger.info(f"  Raw shape: {df.shape}")

    if "CustomerID" in df.columns:
        df = df.drop("CustomerID", axis=1)

    before = len(df)
    df = df.dropna(subset=["Churn"])
    df = df.dropna()
    logger.info(f"  Dropped {before - len(df)} rows with missing values")
    df["Churn"] = df["Churn"].astype(int)

    logger.info(f"  Clean shape: {df.shape}")
    logger.info(f"  Churn rate: {df['Churn'].mean():.4f} ({df['Churn'].mean()*100:.1f}%)")
    return df


# ===========================================================================
# 4. FEATURE ENGINEERING (conservative — no suspicious composites)
# ===========================================================================
def engineer_features(df):
    """
    Feature engineering for the AMBIGUOUS subset.
    We use only legitimate interaction features — no composites that
    could encode the target indirectly.
    """
    df = df.copy()

    # Ratio features (legitimate business metrics)
    df["spend_per_tenure"] = df["Total Spend"] / (df["Tenure"] + 1)
    df["usage_per_tenure"] = df["Usage Frequency"] / (df["Tenure"] + 1)
    df["cost_per_usage"]   = df["Total Spend"] / (df["Usage Frequency"] + 1)

    # Age/tenure interaction
    df["age_tenure_ratio"] = df["Age"] / (df["Tenure"] + 1)

    # Binary flags (based on non-deterministic thresholds)
    df["is_new_customer"] = (df["Tenure"] <= 6).astype(int)
    df["is_long_tenure"]  = (df["Tenure"] >= 40).astype(int)
    df["is_senior"]       = (df["Age"] >= 50).astype(int)

    # Ordinal buckets
    df["tenure_bucket"] = pd.cut(
        df["Tenure"], bins=[0, 6, 12, 24, 36, 61],
        labels=[0, 1, 2, 3, 4], include_lowest=True,
    ).astype(float)
    df["age_group"] = pd.cut(
        df["Age"], bins=[0, 25, 35, 45, 55, 100],
        labels=[0, 1, 2, 3, 4], include_lowest=True,
    ).astype(float)

    return df


# ===========================================================================
# 5. FEATURE LISTS & PREPROCESSOR
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
# 6. MODEL CONFIGS & TUNING
# ===========================================================================
def get_model_configs():
    return {
        "XGBoost": (
            XGBClassifier(
                eval_metric="logloss", use_label_encoder=False,
                random_state=RANDOM_STATE, tree_method="hist", n_jobs=-1,
                scale_pos_weight=1,  # Will be overridden in tuning
            ),
            {
                "model__n_estimators": [200, 400, 600],
                "model__max_depth": [4, 6, 8],
                "model__learning_rate": [0.01, 0.05, 0.1],
                "model__subsample": [0.7, 0.8, 0.9],
                "model__colsample_bytree": [0.7, 0.8, 0.9],
                "model__min_child_weight": [1, 3, 5, 10],
                "model__gamma": [0, 0.1, 0.3],
                "model__reg_alpha": [0, 0.01, 0.1],
                "model__reg_lambda": [1, 1.5, 2],
                "model__scale_pos_weight": [1, 3, 6],  # Handle imbalance
            },
        ),
        "LightGBM": (
            LGBMClassifier(
                random_state=RANDOM_STATE, n_jobs=-1, verbose=-1,
            ),
            {
                "model__n_estimators": [200, 400, 600],
                "model__max_depth": [4, 6, 8, -1],
                "model__learning_rate": [0.01, 0.05, 0.1],
                "model__num_leaves": [31, 50, 80],
                "model__subsample": [0.7, 0.8, 0.9],
                "model__colsample_bytree": [0.7, 0.8, 0.9],
                "model__min_child_samples": [10, 20, 50],
                "model__reg_alpha": [0, 0.01, 0.1],
                "model__reg_lambda": [0, 1, 2],
                "model__is_unbalance": [True, False],
            },
        ),
        "RandomForest": (
            RandomForestClassifier(random_state=RANDOM_STATE, n_jobs=-1),
            {
                "model__n_estimators": [200, 300, 500],
                "model__max_depth": [10, 15, 20],
                "model__min_samples_split": [2, 5, 10],
                "model__min_samples_leaf": [1, 2, 4],
                "model__max_features": ["sqrt", "log2"],
                "model__class_weight": ["balanced", "balanced_subsample", None],
            },
        ),
    }


def tune_on_sample(name, estimator, param_dist, preprocessor, X_sample, y_sample):
    logger.info(f"  Tuning {name} on {len(X_sample)} samples ...")
    t0 = time.time()

    pipe = Pipeline([("preprocessor", preprocessor), ("model", estimator)])
    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)

    search = RandomizedSearchCV(
        pipe, param_distributions=param_dist,
        n_iter=N_ITER_SEARCH, scoring="f1", cv=cv,
        n_jobs=1, random_state=RANDOM_STATE, verbose=0,
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
# 7. EVALUATION
# ===========================================================================
def evaluate(model, X_test, y_test, label="Model"):
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    m = {
        "accuracy":          float(accuracy_score(y_test, y_pred)),
        "precision":         float(precision_score(y_test, y_pred, zero_division=0)),
        "recall":            float(recall_score(y_test, y_pred)),
        "f1":                float(f1_score(y_test, y_pred)),
        "roc_auc":           float(roc_auc_score(y_test, y_proba)),
        "avg_precision":     float(average_precision_score(y_test, y_proba)),
        "matthews_corrcoef": float(matthews_corrcoef(y_test, y_pred)),
        "cohen_kappa":       float(cohen_kappa_score(y_test, y_pred)),
        "log_loss":          float(log_loss(y_test, y_proba)),
        "brier_score":       float(brier_score_loss(y_test, y_proba)),
    }

    logger.info(f"  [{label}]  Acc={m['accuracy']:.4f}  Prec={m['precision']:.4f}"
                f"  Rec={m['recall']:.4f}  F1={m['f1']:.4f}  AUC={m['roc_auc']:.4f}"
                f"  MCC={m['matthews_corrcoef']:.4f}")
    return m, y_pred, y_proba


# ===========================================================================
# 8. PLOTS
# ===========================================================================
def plot_confusion_matrix(y_test, y_pred, path):
    cm = confusion_matrix(y_test, y_pred)
    fig, ax = plt.subplots(figsize=(7, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=["No Churn", "Churn"],
                yticklabels=["No Churn", "Churn"], ax=ax)
    ax.set_xlabel("Predicted"); ax.set_ylabel("Actual")
    ax.set_title("Confusion Matrix (ML Model — Ambiguous Cases Only)")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)
    logger.info(f"  Saved -> {path}")


def plot_roc(y_test, y_proba, auc, path):
    fpr, tpr, _ = roc_curve(y_test, y_proba)
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(fpr, tpr, lw=2, label=f"AUC = {auc:.4f}")
    ax.plot([0, 1], [0, 1], "k--", lw=1)
    ax.set_xlabel("FPR"); ax.set_ylabel("TPR")
    ax.set_title("ROC Curve (ML Model — Ambiguous Cases)")
    ax.legend(loc="lower right")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)
    logger.info(f"  Saved -> {path}")


def plot_pr(y_test, y_proba, ap, path):
    prec, rec, _ = precision_recall_curve(y_test, y_proba)
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(rec, prec, lw=2, label=f"AP = {ap:.4f}")
    ax.set_xlabel("Recall"); ax.set_ylabel("Precision")
    ax.set_title("Precision-Recall Curve (ML Model — Ambiguous Cases)")
    ax.legend()
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)
    logger.info(f"  Saved -> {path}")


def plot_feature_importance(imp_df, path):
    top = imp_df.head(20)
    fig, ax = plt.subplots(figsize=(9, 7))
    sns.barplot(data=top, x="importance", y="feature", palette="viridis", ax=ax)
    ax.set_title("Top 20 Feature Importances")
    ax.set_xlabel("Importance")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)
    logger.info(f"  Saved -> {path}")


# ===========================================================================
# 9. FEATURE IMPORTANCE
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

        if len(feature_names) != len(importances):
            logger.warning(f"Feature names ({len(feature_names)}) != importances ({len(importances)})")
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
# 10. MAIN
# ===========================================================================
def main():
    t0 = time.time()
    logger.info("=" * 70)
    logger.info("  CUSTOMER CHURN MODEL TRAINING v2 — Honest Pipeline")
    logger.info("=" * 70)

    # ---- Load & Clean ----
    df = load_and_clean(DATA_PATH)

    # ---- PHASE 0: Analyze & Split Deterministic vs Ambiguous ----
    logger.info("\n" + "=" * 60)
    logger.info("PHASE 0: DATA ANALYSIS — Finding Deterministic Patterns")
    logger.info("=" * 60)

    rules_engine = ChurnRulesEngine()
    rules_engine.fit(df)
    rules_analysis = rules_engine.analyze(df)

    deterministic_mask = rules_engine.predict_mask(df)
    n_det = deterministic_mask.sum()
    n_amb = (~deterministic_mask).sum()

    logger.info(f"  Deterministic churn rows: {n_det} ({n_det/len(df)*100:.1f}%)")
    for rule, info in rules_analysis.items():
        logger.info(f"    {rule}: {info['count']} rows ({info['pct']}%), churn_rate={info['churn_rate']}")
    logger.info(f"  Ambiguous rows: {n_amb} ({n_amb/len(df)*100:.1f}%)")
    logger.info(f"  Ambiguous churn rate: {df[~deterministic_mask]['Churn'].mean():.4f}")

    # ---- Work with ambiguous rows only ----
    df_ambiguous = df[~deterministic_mask].copy().reset_index(drop=True)
    logger.info(f"\n  Training ML model on {len(df_ambiguous)} ambiguous rows")
    logger.info(f"  Churn rate in ambiguous: {df_ambiguous['Churn'].mean():.4f} ({df_ambiguous['Churn'].mean()*100:.1f}%)")

    # ---- Feature Engineering ----
    df_ambiguous = engineer_features(df_ambiguous)

    target = "Churn"
    X = df_ambiguous.drop(target, axis=1)
    y = df_ambiguous[target]

    # 80/20 stratified split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y,
    )
    logger.info(f"  Train: {X_train.shape}   Test: {X_test.shape}")
    logger.info(f"  Train churn rate: {y_train.mean():.4f}")
    logger.info(f"  Test churn rate: {y_test.mean():.4f}")

    numeric_features, categorical_features = get_feature_lists(df_ambiguous)
    logger.info(f"  Numeric ({len(numeric_features)}): {numeric_features}")
    logger.info(f"  Categorical ({len(categorical_features)}): {categorical_features}")

    # ---- Create tuning sample ----
    sample_n = min(TUNING_SAMPLE, len(X_train))
    X_sample, _, y_sample, _ = train_test_split(
        X_train, y_train, train_size=sample_n,
        random_state=RANDOM_STATE, stratify=y_train,
    )
    logger.info(f"  Tuning sample: {X_sample.shape}")

    # ---- PHASE 1: HYPERPARAMETER TUNING ----
    preprocessor = build_preprocessor(numeric_features, categorical_features)
    configs = get_model_configs()
    tuning_results = {}

    logger.info("\n" + "=" * 60)
    logger.info("PHASE 1: HYPERPARAMETER TUNING (on sample)")
    logger.info("=" * 60)

    for name, (est, params) in configs.items():
        try:
            best_params, cv_f1 = tune_on_sample(
                name, est, params, preprocessor, X_sample, y_sample,
            )
            tuning_results[name] = {"estimator": est, "params": best_params, "cv_f1": cv_f1}
        except Exception as e:
            logger.error(f"  {name} tuning failed: {e}")

    # ---- PHASE 2: TRAIN ON FULL AMBIGUOUS TRAINING SET ----
    logger.info("\n" + "=" * 60)
    logger.info(f"PHASE 2: TRAINING ON FULL AMBIGUOUS SET ({len(X_train)} rows)")
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

    # ---- PHASE 3: STACKING ENSEMBLE ----
    logger.info("\n" + "=" * 60)
    logger.info("PHASE 3: STACKING ENSEMBLE (ML models only)")
    logger.info("=" * 60)

    if len(final_models) >= 2:
        estimators_list = [
            (name, res["pipeline"].named_steps["model"])
            for name, res in final_models.items()
        ]

        stacking = StackingClassifier(
            estimators=estimators_list,
            final_estimator=LogisticRegression(
                max_iter=1000, C=1.0, random_state=RANDOM_STATE,
                class_weight="balanced",
            ),
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
    else:
        stack_metrics = {"f1": 0}
        stack_pipe = None

    # ---- Choose final ML model ----
    if stack_pipe and stack_metrics["f1"] >= best["metrics"]["f1"]:
        final_ml_pipeline = stack_pipe
        final_name = "StackingEnsemble"
        final_metrics = stack_metrics
        final_y_pred = stack_y_pred
        final_y_proba = stack_y_proba
    else:
        final_ml_pipeline = best["pipeline"]
        final_name = best_name
        final_metrics = best["metrics"]
        final_y_pred = best["y_pred"]
        final_y_proba = best["y_proba"]

    logger.info(f"\n>> FINAL ML MODEL: {final_name}")

    # ---- PHASE 4: BUILD HYBRID PREDICTOR ----
    logger.info("\n" + "=" * 60)
    logger.info("PHASE 4: HYBRID PREDICTOR (Rules + ML)")
    logger.info("=" * 60)

    hybrid = HybridChurnPredictor(rules_engine, final_ml_pipeline, engineer_features)

    # Evaluate hybrid on the FULL dataset (not just ambiguous)
    # Use a held-out portion of the full dataset
    X_full = df.drop("Churn", axis=1)
    y_full = df["Churn"]
    _, X_full_test, _, y_full_test = train_test_split(
        X_full, y_full, test_size=0.2, random_state=RANDOM_STATE, stratify=y_full,
    )

    hybrid_pred = hybrid.predict(X_full_test)
    hybrid_proba = hybrid.predict_proba(X_full_test)

    hybrid_metrics = {
        "accuracy":          float(accuracy_score(y_full_test, hybrid_pred)),
        "precision":         float(precision_score(y_full_test, hybrid_pred)),
        "recall":            float(recall_score(y_full_test, hybrid_pred)),
        "f1":                float(f1_score(y_full_test, hybrid_pred)),
        "roc_auc":           float(roc_auc_score(y_full_test, hybrid_proba)),
        "avg_precision":     float(average_precision_score(y_full_test, hybrid_proba)),
        "matthews_corrcoef": float(matthews_corrcoef(y_full_test, hybrid_pred)),
    }

    logger.info(f"  [Hybrid Full-Data]  Acc={hybrid_metrics['accuracy']:.4f}"
                f"  Prec={hybrid_metrics['precision']:.4f}"
                f"  Rec={hybrid_metrics['recall']:.4f}"
                f"  F1={hybrid_metrics['f1']:.4f}"
                f"  AUC={hybrid_metrics['roc_auc']:.4f}")

    # ---- Plots (ML model on ambiguous cases) ----
    logger.info("\nGenerating plots ...")
    plot_confusion_matrix(y_test, final_y_pred, os.path.join(MODEL_DIR, "confusion_matrix.png"))
    plot_roc(y_test, final_y_proba, final_metrics["roc_auc"], os.path.join(MODEL_DIR, "roc_curve.png"))
    plot_pr(y_test, final_y_proba, final_metrics["avg_precision"], os.path.join(MODEL_DIR, "precision_recall.png"))

    # ---- Feature importance ----
    logger.info("Computing feature importance ...")
    fitted_pp = final_ml_pipeline.named_steps["preprocessor"]
    imp_df = compute_feature_importance(final_ml_pipeline, fitted_pp)
    imp_df.to_csv(os.path.join(MODEL_DIR, "feature_importance.csv"), index=False)
    if len(imp_df) > 0:
        plot_feature_importance(imp_df, os.path.join(MODEL_DIR, "feature_importance.png"))

    # ---- Save models ----
    model_path = os.path.join(MODEL_DIR, "model.joblib")
    hybrid_path = os.path.join(MODEL_DIR, "hybrid_predictor.joblib")
    joblib.dump(final_ml_pipeline, model_path)
    joblib.dump(hybrid, hybrid_path)
    logger.info(f"  ML Pipeline saved -> {model_path}")
    logger.info(f"  ML Pipeline size: {os.path.getsize(model_path) / 1024 / 1024:.1f} MB")
    logger.info(f"  Hybrid Predictor saved -> {hybrid_path}")
    logger.info(f"  Hybrid size: {os.path.getsize(hybrid_path) / 1024 / 1024:.1f} MB")

    # ---- Classification report ----
    logger.info(f"\n{'='*60}")
    logger.info("CLASSIFICATION REPORT (ML Model — Ambiguous Cases)")
    logger.info(f"{'='*60}")
    logger.info("\n" + classification_report(y_test, final_y_pred, target_names=["No Churn", "Churn"]))

    # ---- Save metrics ----
    all_model_results = {}
    for name, res in final_models.items():
        all_model_results[name] = {
            "cv_f1_on_sample": round(res["cv_f1"], 4),
            **{k: round(v, 4) for k, v in res["metrics"].items()},
        }
    if stack_pipe:
        all_model_results["StackingEnsemble"] = {
            "cv_f1_on_sample": None,
            **{k: round(v, 4) for k, v in stack_metrics.items()},
        }

    # Data analysis report
    data_analysis = {
        "dataset": {
            "total_rows": len(df),
            "total_churn_rate": round(float(df["Churn"].mean()), 4),
            "is_synthetic": True,
            "explanation": "Dataset contains hard-coded deterministic churn rules. "
                           "49.6% of rows have 100% churn rate based on simple thresholds.",
        },
        "deterministic_rules": rules_analysis,
        "ambiguous_subset": {
            "rows": len(df_ambiguous),
            "churn_rate": round(float(df_ambiguous["Churn"].mean()), 4),
            "pct_of_total": round(float(n_amb / len(df) * 100), 1),
        },
    }

    metrics_report = {
        "approach": "hybrid",
        "description": "Rules engine for deterministic cases + ML model for ambiguous cases",
        "final_ml_model": final_name,
        "ml_model_metrics_on_ambiguous": {k: round(v, 4) for k, v in final_metrics.items()},
        "hybrid_metrics_on_full_data": {k: round(v, 4) for k, v in hybrid_metrics.items()},
        "all_models": all_model_results,
        "data_analysis": data_analysis,
        "dataset_info": {
            "total_rows": len(df),
            "ambiguous_rows": len(df_ambiguous),
            "train_rows": len(X_train),
            "test_rows": len(X_test),
            "n_features": X.shape[1],
            "ambiguous_churn_rate": round(float(y.mean()), 4),
        },
        "feature_importance_top10": (
            imp_df.head(10).to_dict(orient="records") if len(imp_df) > 0 else []
        ),
    }

    with open(os.path.join(MODEL_DIR, "metrics.json"), "w") as f:
        json.dump(metrics_report, f, indent=2)

    with open(os.path.join(MODEL_DIR, "data_analysis.json"), "w") as f:
        json.dump(data_analysis, f, indent=2)

    elapsed = time.time() - t0
    logger.info(f"\n{'='*70}")
    logger.info(f"  TRAINING COMPLETE — {elapsed:.1f}s ({elapsed/60:.1f} min)")
    logger.info(f"{'='*70}")
    logger.info(f"  Approach: HYBRID (Rules Engine + {final_name})")
    logger.info(f"")
    logger.info(f"  ML Model Performance (on ambiguous cases — the HONEST metrics):")
    logger.info(f"    Accuracy    : {final_metrics['accuracy']:.4f}")
    logger.info(f"    Precision   : {final_metrics['precision']:.4f}")
    logger.info(f"    Recall      : {final_metrics['recall']:.4f}")
    logger.info(f"    F1 Score    : {final_metrics['f1']:.4f}")
    logger.info(f"    ROC AUC     : {final_metrics['roc_auc']:.4f}")
    logger.info(f"    MCC         : {final_metrics['matthews_corrcoef']:.4f}")
    logger.info(f"")
    logger.info(f"  Hybrid Performance (on full dataset):")
    logger.info(f"    Accuracy    : {hybrid_metrics['accuracy']:.4f}")
    logger.info(f"    F1 Score    : {hybrid_metrics['f1']:.4f}")
    logger.info(f"    ROC AUC     : {hybrid_metrics['roc_auc']:.4f}")
    logger.info(f"{'='*70}")


if __name__ == "__main__":
    main()
