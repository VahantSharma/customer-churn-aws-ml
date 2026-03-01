#!/usr/bin/env python3
"""Single-feature predictive power + distributions"""
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import f1_score
import warnings
warnings.filterwarnings("ignore")

df = pd.read_csv("data/customer_churn.csv").dropna()
df["Churn"] = df["Churn"].astype(int)
if "CustomerID" in df.columns:
    df = df.drop("CustomerID", axis=1)

y = df["Churn"]
raw_numeric = [c for c in df.select_dtypes(include=[np.number]).columns if c != "Churn"]

print("SINGLE-FEATURE PREDICTIVE POWER (Decision Tree, no parallelism)")
print("=" * 60)
for feat in raw_numeric:
    X1 = df[[feat]]
    X_tr, X_te, y_tr, y_te = train_test_split(X1, y, test_size=0.2, random_state=42, stratify=y)
    dt = DecisionTreeClassifier(max_depth=5, random_state=42)
    dt.fit(X_tr, y_tr)
    f1_1 = f1_score(y_te, dt.predict(X_te))
    flag = " *** HIGH" if f1_1 > 0.7 else ""
    print(f"  {feat}: F1={f1_1:.4f}{flag}")

print(f"\nVALUE DISTRIBUTIONS")
print("=" * 60)
for col in raw_numeric:
    vals = df[col]
    print(f"  {col}: min={vals.min():.0f}, max={vals.max():.0f}, mean={vals.mean():.2f}, std={vals.std():.2f}, unique={vals.nunique()}")

# Check churn rate by Support Calls (the most correlated feature)
print(f"\nCHURN RATE BY SUPPORT CALLS")
print("=" * 60)
for sc in sorted(df["Support Calls"].unique()):
    subset = df[df["Support Calls"] == sc]
    print(f"  Support Calls={int(sc)}: churn={subset['Churn'].mean():.4f} (n={len(subset)})")

print(f"\nCHURN RATE BY PAYMENT DELAY BINS")
print("=" * 60)
df["pd_bin"] = pd.cut(df["Payment Delay"], bins=[0,5,10,15,20,25,30], include_lowest=True)
for b in sorted(df["pd_bin"].dropna().unique()):
    subset = df[df["pd_bin"] == b]
    print(f"  PayDelay {b}: churn={subset['Churn'].mean():.4f} (n={len(subset)})")

print(f"\nCHURN RATE BY TOTAL SPEND QUINTILES")
print("=" * 60)
df["ts_q"] = pd.qcut(df["Total Spend"], q=5, labels=["Q1(low)","Q2","Q3","Q4","Q5(high)"])
for q in ["Q1(low)","Q2","Q3","Q4","Q5(high)"]:
    subset = df[df["ts_q"] == q]
    print(f"  {q}: churn={subset['Churn'].mean():.4f} (n={len(subset)})")

# CHURN BY CATEGORICALS
print(f"\nCHURN BY CATEGORICAL FEATURES")
print("=" * 60)
for col in ["Gender", "Subscription Type", "Contract Length"]:
    print(f"\n  {col}:")
    for val in sorted(df[col].unique()):
        subset = df[df[col] == val]
        print(f"    {val}: churn={subset['Churn'].mean():.4f} (n={len(subset)})")
