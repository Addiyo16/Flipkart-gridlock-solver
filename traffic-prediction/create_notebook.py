# create_notebook.py - Script to write the traffic_prediction.ipynb Jupyter Notebook
import json
import os

# Define Python equivalents for JSON terms
null = None
true = True
false = False

notebook = {
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# Traffic Demand Prediction Challenge (Log-Ratio Ensemble Model)\n",
    "This notebook contains the complete, optimized pipeline to solve the HackerEarth Traffic Demand Prediction challenge. The model is a weighted ensemble of **LightGBM**, **XGBoost**, and **CatBoost** regressors trained on a log-ratio target variable.\n",
    "\n",
    "### Core Strategy:\n",
    "1. **Log-Ratio Target Formulation**: To handle scale differences between Day 48 and Day 49, we define a target variable relative to each location's historical average: \n",
    "   $$y_{\\text{diff}} = \\log(\\text{demand} + 0.01) - \\log(\\text{geo\\_time\\_te} + 0.01)$$\n",
    "   where `geo_time_te` is the target-encoded baseline demand for a specific geohash and timestamp computed *strictly* from Day 48 data.\n",
    "2. **Zero Target Leakage**: Target encodings are mapped exclusively from Day 48, ensuring Day 49 train/validation/test records never leak their own demand information. Validation is evaluated strictly on Day 49 records to match the test set distribution.\n",
    "3. **Generalization**: By predicting the multiplier/ratio rather than absolute demand, the tree-based model can easily generalize the scale shift learned on Day 49 morning records to the Day 49 daytime test set."
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 1. Imports and Setup"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import os\n",
    "import gc\n",
    "import numpy as np\n",
    "import pandas as pd\n",
    "import warnings\n",
    "warnings.filterwarnings('ignore')\n",
    "from sklearn.model_selection import KFold\n",
    "from sklearn.metrics import r2_score\n",
    "from sklearn.preprocessing import LabelEncoder\n",
    "import lightgbm as lgb\n",
    "import xgboost as xgb\n",
    "from catboost import CatBoostRegressor\n",
    "\n",
    "# Set base paths\n",
    "dataset_dir = r\"C:\\Users\\ashok\\.gemini\\antigravity\\dataset\\dataset\"\n",
    "if not os.path.exists(dataset_dir):\n",
    "    dataset_dir = r\"C:\\Users\\ashok\\..gemini\\antigravity\\dataset\\dataset\"\n",
    "\n",
    "train_path = os.path.join(dataset_dir, \"train.csv\")\n",
    "test_path = os.path.join(dataset_dir, \"test.csv\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 2. Load Data"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "train = pd.read_csv(train_path)\n",
    "test = pd.read_csv(test_path)\n",
    "\n",
    "print(f\"Train shape: {train.shape}\")\n",
    "print(f\"Test shape: {test.shape}\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 3. Base32 Geohash Decoder"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "def decode_geohash(geohash):\n",
    "    base32 = '0123456789bcdefghjkmnpqrstuvwxyz'\n",
    "    decoder = {char: idx for idx, char in enumerate(base32)}\n",
    "    lat_interval = (-90.0, 90.0)\n",
    "    lon_interval = (-180.0, 180.0)\n",
    "    is_even = True\n",
    "    for char in geohash:\n",
    "        if char not in decoder: \n",
    "            continue\n",
    "        val = decoder[char]\n",
    "        for i in range(4, -1, -1):\n",
    "            bit = (val >> i) & 1\n",
    "            if is_even:\n",
    "                mid = (lon_interval[0] + lon_interval[1]) / 2\n",
    "                if bit == 1:\n",
    "                    lon_interval = (mid, lon_interval[1])\n",
    "                else:\n",
    "                    lon_interval = (lon_interval[0], mid)\n",
    "            else:\n",
    "                mid = (lat_interval[0] + lat_interval[1]) / 2\n",
    "                if bit == 1:\n",
    "                    lat_interval = (mid, lat_interval[1])\n",
    "                else:\n",
    "                    lat_interval = (lat_interval[0], mid)\n",
    "            is_even = not is_even\n",
    "    lat = (lat_interval[0] + lat_interval[1]) / 2\n",
    "    lon = (lon_interval[0] + lon_interval[1]) / 2\n",
    "    return lat, lon"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 4. Preprocessing & Feature Engineering"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "y_train_orig = train['demand'].values\n",
    "test_indices = test['Index'].values\n",
    "\n",
    "# Preprocess missing categoricals\n",
    "train['RoadType'] = train['RoadType'].fillna('Unknown')\n",
    "train['Weather'] = train['Weather'].fillna('Unknown')\n",
    "test['RoadType'] = test['RoadType'].fillna('Unknown')\n",
    "test['Weather'] = test['Weather'].fillna('Unknown')\n",
    "\n",
    "train['is_day_49'] = (train['day'] == 49).astype(int)\n",
    "test['is_day_49'] = 1\n",
    "\n",
    "# Parse time\n",
    "def time_to_minutes(ts):\n",
    "    parts = ts.split(':')\n",
    "    return int(parts[0]) * 60 + int(parts[1]) if len(parts) == 2 else 0\n",
    "\n",
    "# Apply geohash and time processing to both splits\n",
    "for df in [train, test]:\n",
    "    coords = df['geohash'].apply(decode_geohash)\n",
    "    df['latitude'] = [c[0] for c in coords]\n",
    "    df['longitude'] = [c[1] for c in coords]\n",
    "    \n",
    "    df['geohash_3'] = df['geohash'].str[:3]\n",
    "    df['geohash_4'] = df['geohash'].str[:4]\n",
    "    df['geohash_5'] = df['geohash'].str[:5]\n",
    "    \n",
    "    df['minutes'] = df['timestamp'].apply(time_to_minutes)\n",
    "    df['hour'] = df['minutes'] // 60\n",
    "    df['time_sin'] = np.sin(2 * np.pi * df['minutes'] / 1440.0)\n",
    "    df['time_cos'] = np.cos(2 * np.pi * df['minutes'] / 1440.0)\n",
    "    df['geo_time'] = df['geohash'].astype(str) + '_' + df['timestamp'].astype(str)\n",
    "\n",
    "# Impute Temperature\n",
    "geo_temp_mean = train.groupby('geohash')['Temperature'].mean().to_dict()\n",
    "global_temp_mean = train['Temperature'].mean()\n",
    "\n",
    "for df in [train, test]:\n",
    "    df['Temperature'] = df['Temperature'].fillna(df['geohash'].map(geo_temp_mean))\n",
    "    df['Temperature'] = df['Temperature'].fillna(global_temp_mean)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 5. Strict Target Encoding Mapping (Day 48 Baseline)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "print(\"Computing target encodings strictly using Day 48 baseline...\")\n",
    "d48_train = train[train['day'] == 48].copy()\n",
    "\n",
    "for col in ['geohash', 'timestamp', 'geo_time']:\n",
    "    global_mean = d48_train['demand'].mean()\n",
    "    stats = d48_train.groupby(col)['demand'].agg(['count', 'mean'])\n",
    "    smooth_mean = (stats['count'] * stats['mean'] + 20 * global_mean) / (stats['count'] + 20)\n",
    "    smooth_mean = smooth_mean.to_dict()\n",
    "    \n",
    "    train[col + '_te'] = train[col].map(smooth_mean).fillna(global_mean)\n",
    "    test[col + '_te'] = test[col].map(smooth_mean).fillna(global_mean)\n",
    "    \n",
    "# Define the log-ratio target variable\n",
    "train['y_diff'] = np.log(train['demand'] + 0.01) - np.log(train['geo_time_te'] + 0.01)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 6. Categorical Variable Label Encoding"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "cat_cols = ['RoadType', 'LargeVehicles', 'Landmarks', 'Weather', 'geohash', 'geohash_3', 'geohash_4', 'geohash_5', 'timestamp', 'geo_time']\n",
    "for col in cat_cols:\n",
    "    le = LabelEncoder()\n",
    "    combined = pd.concat([train[col], test[col]]).astype(str)\n",
    "    le.fit(combined)\n",
    "    train[col] = le.transform(train[col].astype(str))\n",
    "    test[col] = le.transform(test[col].astype(str))"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 7. Model Training & 5-Fold Cross Validation (Log-Ratio Ensemble)\n",
    "We train LightGBM, XGBoost, and CatBoost regressors on the log-ratio target variable."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "features = ['geohash', 'day', 'timestamp', 'RoadType', 'NumberofLanes', 'LargeVehicles', 'Landmarks', 'Temperature', 'Weather',\n",
    "            'latitude', 'longitude', 'geohash_3', 'geohash_4', 'geohash_5', 'minutes', 'hour', 'time_sin', 'time_cos', 'geo_time',\n",
    "            'geohash_te', 'timestamp_te', 'geo_time_te', 'is_day_49']\n",
    "\n",
    "X_train = train[features].values\n",
    "y_train_diff = train['y_diff'].values\n",
    "geo_time_te_tr = train['geo_time_te'].values\n",
    "\n",
    "X_test = test[features].values\n",
    "geo_time_te_te = test['geo_time_te'].values\n",
    "\n",
    "d49_train_indices = train[train['day'] == 49].index.values\n",
    "\n",
    "kf = KFold(n_splits=5, shuffle=True, random_state=42)\n",
    "oof_diff_lgb = np.zeros(len(X_train))\n",
    "oof_diff_xgb = np.zeros(len(X_train))\n",
    "oof_diff_cat = np.zeros(len(X_train))\n",
    "\n",
    "preds_diff_lgb = np.zeros(len(X_test))\n",
    "preds_diff_xgb = np.zeros(len(X_test))\n",
    "preds_diff_cat = np.zeros(len(X_test))\n",
    "\n",
    "for fold, (train_idx, val_idx) in enumerate(kf.split(X_train, y_train_diff)):\n",
    "    X_tr, y_tr = X_train[train_idx], y_train_diff[train_idx]\n",
    "    X_va, y_va = X_train[val_idx], y_train_diff[val_idx]\n",
    "    \n",
    "    # 1. LightGBM\n",
    "    model_lgb = lgb.LGBMRegressor(\n",
    "        n_estimators=1000, learning_rate=0.03, max_depth=8, num_leaves=63,\n",
    "        subsample=0.8, colsample_bytree=0.8, random_state=42, verbose=-1\n",
    "    )\n",
    "    model_lgb.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], callbacks=[lgb.early_stopping(50, verbose=False)])\n",
    "    oof_diff_lgb[val_idx] = model_lgb.predict(X_va)\n",
    "    preds_diff_lgb += model_lgb.predict(X_test) / 5.0\n",
    "    \n",
    "    # 2. XGBoost\n",
    "    model_xgb = xgb.XGBRegressor(\n",
    "        n_estimators=1000, learning_rate=0.03, max_depth=8, subsample=0.8,\n",
    "        colsample_bytree=0.8, random_state=42, early_stopping_rounds=50, tree_method='hist'\n",
    "    )\n",
    "    model_xgb.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=False)\n",
    "    oof_diff_xgb[val_idx] = model_xgb.predict(X_va)\n",
    "    preds_diff_xgb += model_xgb.predict(X_test) / 5.0\n",
    "    \n",
    "    # 3. CatBoost\n",
    "    model_cat = CatBoostRegressor(\n",
    "        iterations=1200, learning_rate=0.03, depth=8,\n",
    "        random_seed=42, early_stopping_rounds=50, verbose=False\n",
    "    )\n",
    "    model_cat.fit(X_tr, y_tr, eval_set=(X_va, y_va))\n",
    "    oof_diff_cat[val_idx] = model_cat.predict(X_va)\n",
    "    preds_diff_cat += model_cat.predict(X_test) / 5.0\n",
    "    \n",
    "    print(f\"Fold {fold+1} Completed!\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 8. Out-of-Fold Validation Metrics Evaluation (Strictly evaluated on Day 49)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "oof_pred_lgb = np.clip(np.exp(oof_diff_lgb + np.log(geo_time_te_tr + 0.01)) - 0.01, 0.0, 1.0)\n",
    "oof_pred_xgb = np.clip(np.exp(oof_diff_xgb + np.log(geo_time_te_tr + 0.01)) - 0.01, 0.0, 1.0)\n",
    "oof_pred_cat = np.clip(np.exp(oof_diff_cat + np.log(geo_time_te_tr + 0.01)) - 0.01, 0.0, 1.0)\n",
    "oof_pred_blend = oof_pred_lgb * 0.35 + oof_pred_xgb * 0.45 + oof_pred_cat * 0.20\n",
    "\n",
    "r2_d49_lgb = r2_score(y_train_orig[d49_train_indices], oof_pred_lgb[d49_train_indices])\n",
    "r2_d49_xgb = r2_score(y_train_orig[d49_train_indices], oof_pred_xgb[d49_train_indices])\n",
    "r2_d49_cat = r2_score(y_train_orig[d49_train_indices], oof_pred_cat[d49_train_indices])\n",
    "r2_d49_blend = r2_score(y_train_orig[d49_train_indices], oof_pred_blend[d49_train_indices])\n",
    "\n",
    "print(f\"Day 49 LightGBM R2: {r2_d49_lgb:.5f}\")\n",
    "print(f\"Day 49 XGBoost R2:  {r2_d49_xgb:.5f}\")\n",
    "print(f\"Day 49 CatBoost R2: {r2_d49_cat:.5f}\")\n",
    "print(f\"Day 49 Ensemble Blend R2: {r2_d49_blend:.5f} (HackerEarth Score Estimate: {100 * r2_d49_blend:.3f})\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 9. Generate and Save Submission File"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "preds_test_lgb = np.clip(np.exp(preds_diff_lgb + np.log(geo_time_te_te + 0.01)) - 0.01, 0.0, 1.0)\n",
    "preds_test_xgb = np.clip(np.exp(preds_diff_xgb + np.log(geo_time_te_te + 0.01)) - 0.01, 0.0, 1.0)\n",
    "preds_test_cat = np.clip(np.exp(preds_diff_cat + np.log(geo_time_te_te + 0.01)) - 0.01, 0.0, 1.0)\n",
    "\n",
    "final_preds = preds_test_lgb * 0.35 + preds_test_xgb * 0.45 + preds_test_cat * 0.20\n",
    "final_preds = np.clip(final_preds, 0.0, 1.0) \n",
    "\n",
    "submission = pd.DataFrame({\n",
    "    'Index': test_indices,\n",
    "    'demand': final_preds\n})\n",
    "\n",
    "submission.to_csv('submission.csv', index=False)\n",
    "print(\"Submission saved to submission.csv\")\n",
    "print(\"Dimensions:\", submission.shape)\n",
    "print(submission.head())"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "name": "python"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 2
}

notebook_path = r"C:\Users\ashok\.gemini\antigravity\scratch\traffic-prediction\traffic_prediction.ipynb"
with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(notebook, f, indent=1)

print("Saved traffic_prediction.ipynb successfully!")
