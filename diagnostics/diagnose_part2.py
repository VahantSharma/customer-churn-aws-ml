#!/usr/bin/env python3
"""Quick remaining diagnostics after main script."""
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score, accuracy_score
import warnings
warnings.filterwarnings("ignore")

df = pd.read_csv("data/customer_churn.csv").dropna()
df["Churn"] = df["Churn"].astype(int)
if "CustomerID" in df.columns:
    df = df.drop("CustomerID", axis=1)

cat_cols = df.select_dtypes(include=["object"]).columns.tolist()
df_encoded = pd.get_dummies(df, columns=cat_cols, drop_first=True)
X = df_encoded.drop("Churn", axis=1)
y = df_encoded["Churn"]

# SHUFFLED TARGET TEST
print("=" * 60)
print("SHUFFLED TARGET TEST")
print("=" * 60)
y_shuffled = np.random.RandomState(42).permutation(y.values)
X_tr, X_te, y_tr, y_te = train_test_split(X, y_shuffled, test_size=0.2, random_state=42)
rf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
rf.fit(X_tr, y_tr)
y_pred = rf.predict(X_te)
print(f"  Shuffled: Acc={accuracy_score(y_te, y_pred):.4f}, F1={f1_score(y_te, y_pred):.4f}")
print(f"  Expected: ~50% if no leakage")

# TRAIN/TEST OVERLAP
print(f"\n{'='*60}")
print("TRAIN/TEST OVERLAP CHECK")
print(f"{'='*60}")
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
overlap = pd.merge(X_train.reset_index(drop=True), X_test.reset_index(drop=True), how="inner")
print(f"  Overlapping rows: {len(overlap)}")

# SINGLE FEATURE POWER
print(f"\n{'='*60}")
print("SINGLE-FEATURE PREDICTIVE POWER")
print(f"{'='*60}")
raw_numeric = [c for c in df.select_dtypes(include=[np.number]).columns if c != "Churn"]
for feat in raw_numeric:
    X1 = df[[feat]]
    X_tr1, X_te1, y_tr1, y_te1 = train_test_split(X1, y, test_size=0.2, random_state=42, stratify=y)
    rf1 = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42, n_jobs=-1)
    rf1.fit(X_tr1, y_tr1)
    f1_1 = f1_score(y_te1, rf1.predict(X_te1))
    flag = " *** SUSPICIOUS" if f1_1 > 0.7 else ""
    print(f"  {feat}: F1={f1_1:.4f}{flag}")

# VALUE DISTRIBUTIONS
print(f"\n{'='*60}")
print("VALUE DISTRIBUTIONS")
print(f"{'='*60}")
for col in raw_numeric:
    vals = df[col]
    print(f"  {col}: min={vals.min()}, max={vals.max()}, mean={vals.mean():.2f}, std={vals.std():.2f}")

# CHURN BY CATEGORICAL
print(f"\n{'='*60}")
print("CHURN RATE BY CATEGORICAL")
print(f"{'='*60}")
for col in ["Gender", "Subscription Type", "Contract Length"]:
    if col in df.columns:
        ct = df.groupby(col)["Churn"].agg(["mean", "count"])
        ct.columns = ["churn_rate", "count"]
        print(f"\n  {col}:")
        for idx, row in ct.iterrows():
            print(f"    {idx}: churn={row['churn_rate']:.4f} (n={int(row['count'])})")

# FINAL
print(f"\n{'='*70}")
print("FINAL SUMMARY")
print(f"{'='*70}")
print(f"  Raw RF (no engineering): Acc=0.9910, F1=0.9920")
print(f"  Churn rate: {y.mean():.4f} ({y.mean()*100:.1f}%)")
print(f"  Columns: {list(df.columns)}")
print(f"  Features: {raw_numeric}")
print(f"  Dataset rows: {len(df)}")
