#!/usr/bin/env python3
"""Analyze which rows are deterministic vs ambiguous."""
import pandas as pd
import numpy as np

df = pd.read_csv("data/customer_churn.csv").dropna()
df["Churn"] = df["Churn"].astype(int)
if "CustomerID" in df.columns:
    df = df.drop("CustomerID", axis=1)

print(f"Total rows: {len(df)}")
print(f"Churn=1: {df['Churn'].sum()}, Churn=0: {(df['Churn']==0).sum()}")

# Identify deterministic churn rules
rule1 = df["Support Calls"] >= 6
rule2 = df["Contract Length"] == "Monthly"
rule3 = df["Payment Delay"] > 20
rule4 = df["Total Spend"] <= df["Total Spend"].quantile(0.2)

# Check: are all these 100% churn?
for name, mask in [("Support>=6", rule1), ("Monthly", rule2), ("PayDelay>20", rule3), ("LowSpend Q1", rule4)]:
    subset = df[mask]
    print(f"\n{name}: {len(subset)} rows, churn_rate={subset['Churn'].mean():.4f}")

# Combined deterministic mask
deterministic = rule1 | rule2 | rule3 | rule4
print(f"\nAny deterministic rule: {deterministic.sum()} rows ({deterministic.sum()/len(df)*100:.1f}%)")
print(f"  Churn rate in deterministic: {df[deterministic]['Churn'].mean():.4f}")

# What's left after removing deterministic 
ambiguous = df[~deterministic]
print(f"\nAMBIGUOUS rows (after removing deterministic): {len(ambiguous)} ({len(ambiguous)/len(df)*100:.1f}%)")
print(f"  Churn rate: {ambiguous['Churn'].mean():.4f} ({ambiguous['Churn'].mean()*100:.1f}%)")
print(f"  Churn=1: {ambiguous['Churn'].sum()}, Churn=0: {(ambiguous['Churn']==0).sum()}")

# Check: are there also deterministic NON-churn patterns?
for col in ["Support Calls", "Payment Delay", "Total Spend"]:
    if col == "Support Calls":
        for v in range(11):
            subset = ambiguous[ambiguous[col] == v]
            if len(subset) > 100:
                print(f"  Ambiguous block: {col}={v}: churn={subset['Churn'].mean():.4f} (n={len(subset)})")
    elif col == "Total Spend":
        for q_label, q_low, q_high in [("Low", 0, 0.25), ("Mid", 0.25, 0.75), ("High", 0.75, 1.0)]:
            low_v = ambiguous[col].quantile(q_low)
            high_v = ambiguous[col].quantile(q_high)
            subset = ambiguous[(ambiguous[col] >= low_v) & (ambiguous[col] < high_v)]
            if len(subset) > 100:
                print(f"  Ambiguous block: {col} {q_label}({low_v:.0f}-{high_v:.0f}): churn={subset['Churn'].mean():.4f} (n={len(subset)})")

# Also check Gender distribution in ambiguous
print(f"\nGender in ambiguous:")
for g in ambiguous["Gender"].unique():
    sub = ambiguous[ambiguous["Gender"] == g]
    print(f"  {g}: churn={sub['Churn'].mean():.4f} (n={len(sub)})")

# Contract in ambiguous
print(f"\nContract in ambiguous:")
for c in ambiguous["Contract Length"].unique():
    sub = ambiguous[ambiguous["Contract Length"] == c]
    print(f"  {c}: churn={sub['Churn'].mean():.4f} (n={len(sub)})")

print(f"\nSubscription in ambiguous:")
for s in ambiguous["Subscription Type"].unique():
    sub = ambiguous[ambiguous["Subscription Type"] == s]
    print(f"  {s}: churn={sub['Churn'].mean():.4f} (n={len(sub)})")
