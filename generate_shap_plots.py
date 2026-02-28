import pandas as pd
import joblib
import shap
import matplotlib.pyplot as plt
import os
from src.model_explainability import ModelExplainer

def main():
    # 1. Load Data
    print("Loading data...")
    # Load processed data to avoid passing it through preprocessor manually if you prefer
    # Or load raw and transform it
    df = pd.read_csv("data/customer_churn.csv")
    
    # Optional: Take a small sample if the dataset is too large to compute SHAP values quickly
    df_sample = df.sample(n=1000, random_state=42)
    
    X_raw = df_sample.drop(["CustomerID", "Churn"], axis=1)
    
    # 2. Load Model and Preprocessor
    print("Loading model and preprocessor...")
    model_path = "model/best_model_xgboost.joblib"
    preprocessor_path = "model/preprocessor.joblib"
    
    if not os.path.exists(model_path) or not os.path.exists(preprocessor_path):
        print("Model files not found! Please run the notebook or training script first.")
        return
        
    model = joblib.load(model_path)
    preprocessor = joblib.load(preprocessor_path)
    
    # 3. Process the Data
    X_processed = preprocessor.transform(X_raw)
    
    # Get feature names after preprocessing
    num_cols = ['Age', 'Tenure', 'Usage Frequency', 'Support Calls', 'Payment Delay', 'Total Spend', 'Last Interaction']
    cat_cols = ['Gender', 'Subscription Type', 'Contract Length']
    cat_features = preprocessor.named_transformers_['cat'].get_feature_names_out(cat_cols)
    feature_names = num_cols + list(cat_features)
    
    X_processed_df = pd.DataFrame(X_processed, columns=feature_names)
    
    # 4. Generate SHAP Values
    print("Calculating SHAP values...")
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_processed_df)
    
    # Make sure we have a directory to save plots
    os.makedirs("shap_plots", exist_ok=True)
    
    # 5. Generate and Save Plots
    print("Generating Summary Plot (Bar)...")
    plt.figure(figsize=(10, 8))
    shap.summary_plot(shap_values, X_processed_df, plot_type="bar", show=False)
    plt.tight_layout()
    plt.savefig("shap_plots/shap_feature_importance_bar.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    print("Generating Summary Plot (Beeswarm)...")
    plt.figure(figsize=(10, 8))
    shap.summary_plot(shap_values, X_processed_df, show=False)
    plt.tight_layout()
    plt.savefig("shap_plots/shap_beeswarm.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    print("Generating First Customer Waterfall Plot...")
    plt.figure(figsize=(10, 5))
    shap_obj = explainer(X_processed_df.iloc[[0]])
    shap.plots.waterfall(shap_obj[0], show=False)
    plt.tight_layout()
    plt.savefig("shap_plots/shap_waterfall_single_customer.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    print("Done! Plots are saved in the 'shap_plots' directory.")

if __name__ == "__main__":
    main()
