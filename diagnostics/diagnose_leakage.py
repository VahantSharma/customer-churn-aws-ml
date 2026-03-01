#!/usr/bin/env python3
"""
Data Leakage Diagnostic Script
Checks for all common forms of data leakage in the customer churn dataset.
"""
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score, accuracy_score
import warnings
warnings.filterwarnings("ignore")

print("=" * 70)
print("  DATA LEAKAGE DIAGNOSTIC REPORT")
print("=" * 70)

# ============================================================
# 1. RAW DATASET INSPECTION
# ============================================================
df = pd.read_csv("data/customer_churn.csv")
print(f"\n{'='*60}")
print("1. RAW DATASET INSPECTION")
print(f"{'='*60}")
print(f"Shape: {df.shape}")
print(f"Columns: {list(df.columns)}")
print(f"\nData types:")
for c in df.columns:
    print(f"  {c}: {df[c].dtype} | unique={df[c].nunique()} | nulls={df[c].isnull().sum()}")
print(f"\nFirst 5 rows:")
print(df.head().to_string())
print(f"\nChurn distribution:")
print(df["Churn"].value_counts())
print(f"Churn rate: {df['Churn'].mean():.4f} ({df['Churn'].mean()*100:.1f}%)")

# ============================================================
# 2. CORRELATION WITH TARGET
# ============================================================
print(f"\n{'='*60}")
print("2. FEATURE CORRELATION WITH CHURN (raw features only)")
print(f"{'='*60}")
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
if "Churn" in numeric_cols:
    corr = df[numeric_cols].corr()["Churn"].drop("Churn").sort_values(ascending=False)
    print(corr.to_string())
    high_corr = corr[corr.abs() > 0.5]
    if len(high_corr) > 0:
        print(f"\n*** WARNING: Features with |corr| > 0.5 with Churn: {list(high_corr.index)}")
    else:
        print("\n  No individual raw feature has correlation > 0.5 with Churn")

# ============================================================
# 3. CHECK FOR DUPLICATES
# ============================================================
print(f"\n{'='*60}")
print("3. DUPLICATE ROWS CHECK")
print(f"{'='*60}")
n_dup = df.duplicated().sum()
print(f"Exact duplicate rows in full dataset: {n_dup}")
if "CustomerID" in df.columns:
    n_dup_id = df["CustomerID"].duplicated().sum()
    print(f"Duplicate CustomerIDs: {n_dup_id}")

# ============================================================
# 4. TEST: RAW FEATURES ONLY (no engineering)
# ============================================================
print(f"\n{'='*60}")
print("4. BASELINE: Train on RAW features only (no feature engineering)")
print(f"{'='*60}")
df_raw = df.copy()
if "CustomerID" in df_raw.columns:
    df_raw = df_raw.drop("CustomerID", axis=1)

# Drop null rows
df_raw = df_raw.dropna(subset=["Churn"])
df_raw = df_raw.dropna()
df_raw["Churn"] = df_raw["Churn"].astype(int)

# One-hot encode categoricals
cat_cols = df_raw.select_dtypes(include=["object"]).columns.tolist()
df_encoded = pd.get_dummies(df_raw, columns=cat_cols, drop_first=True)

X = df_encoded.drop("Churn", axis=1)
y = df_encoded["Churn"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# Quick RF with default params
rf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
rf.fit(X_train, y_train)
y_pred = rf.predict(X_test)
raw_acc = accuracy_score(y_test, y_pred)
raw_f1 = f1_score(y_test, y_pred)
print(f"  RF (raw features): Accuracy={raw_acc:.4f}, F1={raw_f1:.4f}")

# Feature importance on raw features
imp = pd.Series(rf.feature_importances_, index=X.columns).sort_values(ascending=False)
print(f"\n  Feature importance (raw):")
for feat, val in imp.head(15).items():
    print(f"    {feat}: {val:.4f}")

print(f"\n  >>> If F1 > 0.95 on RAW features, the DATASET ITSELF is the problem")
print(f"  >>> (not our feature engineering)")

# ============================================================
# 5. TEST: Engineered features (what our train_model.py does)
# ============================================================
print(f"\n{'='*60}")
print("5. WITH ENGINEERED FEATURES (same as train_model.py)")
print(f"{'='*60}")

df2 = df.copy()
if "CustomerID" in df2.columns:
    df2 = df2.drop("CustomerID", axis=1)

# Same engineering as train_model.py
df2["spend_per_tenure"]   = df2["Total Spend"] / (df2["Tenure"] + 1)
df2["support_per_tenure"] = df2["Support Calls"] / (df2["Tenure"] + 1)
df2["usage_per_tenure"]   = df2["Usage Frequency"] / (df2["Tenure"] + 1)
df2["delay_per_tenure"]   = df2["Payment Delay"] / (df2["Tenure"] + 1)
df2["cost_per_usage"]     = df2["Total Spend"] / (df2["Usage Frequency"] + 1)
df2["recency_score"]      = df2["Last Interaction"] / 30.0
df2["risk_score"]         = df2["Support Calls"] * df2["Payment Delay"]
df2["frustration_index"]  = df2["Support Calls"] / (df2["Usage Frequency"] + 1)
df2["is_high_support"]    = (df2["Support Calls"]  >= 7).astype(int)
df2["is_payment_late"]    = (df2["Payment Delay"]  >= 15).astype(int)
df2["is_low_usage"]       = (df2["Usage Frequency"] <= 5).astype(int)
df2["is_new_customer"]    = (df2["Tenure"]          <= 6).astype(int)
df2["is_long_tenure"]     = (df2["Tenure"]          >= 40).astype(int)
df2["tenure_bucket"]      = pd.cut(df2["Tenure"], bins=[0,6,12,24,36,61], labels=[0,1,2,3,4], include_lowest=True).astype(float)
df2["age_group"]          = pd.cut(df2["Age"], bins=[0,25,35,45,55,100], labels=[0,1,2,3,4], include_lowest=True).astype(float)

# Correlation with engineered features
eng_numeric = df2.select_dtypes(include=[np.number]).columns.tolist()
corr2 = df2[eng_numeric].corr()["Churn"].drop("Churn").sort_values(ascending=False)
print("  Correlation with Churn (engineered features):")
print(corr2.to_string())

high_corr2 = corr2[corr2.abs() > 0.5]
if len(high_corr2) > 0:
    print(f"\n  *** SUSPICIOUS: Features with |corr| > 0.5: {list(high_corr2.index)}")

# ============================================================
# 6. SHUFFLED TARGET TEST (THE ULTIMATE LEAKAGE CHECK)
# ============================================================
print(f"\n{'='*60}")
print("6. SHUFFLED TARGET TEST (ultimate leakage check)")
print(f"{'='*60}")
print("  If model still gets high accuracy with shuffled labels -> leakage")

X_raw = df_encoded.drop("Churn", axis=1)
y_shuffled = np.random.RandomState(42).permutation(y.values)

X_tr_s, X_te_s, y_tr_s, y_te_s = train_test_split(
    X_raw, y_shuffled, test_size=0.2, random_state=42
)
rf_shuffled = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
rf_shuffled.fit(X_tr_s, y_tr_s)
y_pred_s = rf_shuffled.predict(X_te_s)
shuf_acc = accuracy_score(y_te_s, y_pred_s)
shuf_f1 = f1_score(y_te_s, y_pred_s)
print(f"  Shuffled target: Accuracy={shuf_acc:.4f}, F1={shuf_f1:.4f}")
print(f"  Expected: ~50% accuracy. If much higher -> DATA LEAKAGE")

# ============================================================
# 7. TRAIN/TEST OVERLAP CHECK
# ============================================================
print(f"\n{'='*60}")
print("7. TRAIN/TEST OVERLAP CHECK")
print(f"{'='*60}")
overlap = pd.merge(
    X_train.reset_index(drop=True), X_test.reset_index(drop=True), how="inner"
)
print(f"  Overlapping rows between train and test: {len(overlap)}")
if len(overlap) > 0:
    print(f"  *** LEAKAGE: {len(overlap)} identical rows exist in both train and test!")
else:
    print(f"  OK: No exact row overlap.")

# ============================================================
# 8. CHECK INDIVIDUAL FEATURE PREDICTIVE POWER
# ============================================================
print(f"\n{'='*60}")
print("8. SINGLE-FEATURE PREDICTIVE POWER")
print(f"{'='*60}")
print("  Training a model with EACH feature alone to find overly predictive features")

raw_numeric = [c for c in df.select_dtypes(include=[np.number]).columns if c != "Churn"]
y_full = df["Churn"]

for feat in raw_numeric:
    X_single = df[[feat]].fillna(0)
    X_tr1, X_te1, y_tr1, y_te1 = train_test_split(X_single, y_full, test_size=0.2, random_state=42, stratify=y_full)
    rf1 = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42, n_jobs=-1)
    rf1.fit(X_tr1, y_tr1)
    f1_single = f1_score(y_te1, rf1.predict(X_te1))
    flag = " *** SUSPICIOUS" if f1_single > 0.7 else ""
    print(f"  {feat}: F1={f1_single:.4f}{flag}")

# ============================================================
# 9. CHECK DATA RANGES / DISTRIBUTION
# ============================================================
print(f"\n{'='*60}")
print("9. VALUE DISTRIBUTIONS (detect synthetic patterns)")
print(f"{'='*60}")
for col in raw_numeric:
    vals = df[col]
    print(f"  {col}: min={vals.min()}, max={vals.max()}, mean={vals.mean():.2f}, "
          f"std={vals.std():.2f}, median={vals.median()}")

# ============================================================
# 10. CROSS-TAB: Churn by each categorical
# ============================================================
print(f"\n{'='*60}")
print("10. CHURN RATE BY CATEGORICAL FEATURES")
print(f"{'='*60}")
for col in df.select_dtypes(include=["object"]).columns:
    ct = df.groupby(col)["Churn"].agg(["mean", "count"])
    ct.columns = ["churn_rate", "count"]
    print(f"\n  {col}:")
    print(ct.to_string())

# ============================================================
# FINAL SUMMARY
# ============================================================
print(f"\n{'='*70}")
print("  DIAGNOSIS SUMMARY")
print(f"{'='*70}")
print(f"  Raw features RF:      Accuracy={raw_acc:.4f}, F1={raw_f1:.4f}")
print(f"  Shuffled target RF:   Accuracy={shuf_acc:.4f}, F1={shuf_f1:.4f}")
print(f"  Train/test overlap:   {len(overlap)} rows")
print(f"  Churn rate:           {df['Churn'].mean():.4f} ({df['Churn'].mean()*100:.1f}%)")
print()
if raw_f1 > 0.95:
    print("  *** VERDICT: The DATASET is too easy / likely synthetic.")
    print("  *** The raw features alone give near-perfect predictions.")
    print("  *** This is NOT a feature engineering leakage problem.")
    print("  *** The data itself is synthetic with clear decision boundaries.")
elif raw_f1 > 0.85:
    print("  VERDICT: Raw features give reasonable results.")
    print("  Feature engineering may be adding some leakage if engineered F1 >> raw F1.")
else:
    print("  VERDICT: Raw features alone are not enough.")
    print("  Check if engineered features are causing leakage.")
print()
