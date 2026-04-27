## ⚠️ Work in Progress

The model training pipeline using Azure Custom Vision is currently under development.

This section will include automated training, experiment tracking, and model evaluation across different image sizes.

Updates coming soon.


---

# Training Pipeline
> **Platform:** Microsoft Fabric | **Storage:** Microsoft Fabric (OneLake) | **Orchestration:** Fabric Data Pipeline

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Training Pipeline](#training-pipeline)
4. [Security](#security)
5. [How to Run](#how-to-run)
6. [Output Structure](#output-structure)
7. [Metrics](#metrics)


---

## Overview

This section trains classification models using **Azure Custom Vision** — all orchestrated through **Fabric Data Pipelines**.

---

**Pipeline name:** `training_custom_vision`

**Purpose:** Trains one Azure Custom Vision classification model per image size and evaluates its performance against the test set.

**Notebook logic per iteration:**
1. Resolves absolute `abfss://` paths dynamically from the attached Lakehouse
2. Retrieves credentials from Azure Key Vault via `notebookutils.credentials.getSecret()`
3. Creates or reuses a Custom Vision project named `pet-classifier-{IMAGE_SIZE}`
4. Creates classification tags dynamically from Gold layer label folders
5. Uploads training images in batches of 64
6. Trains the model with a 30-minute timeout and polling every 10 seconds
7. Unpublishes any existing iteration with the same name, then publishes the new one
8. Evaluates accuracy against the test set using the Custom Vision Prediction API
9. Saves precision, recall, AP and accuracy to the `model_metrics` Delta table

**Parameters received from pipeline:**

| Parameter | Description |
|---|---|
| `IMAGE_SIZE` | Current image size injected by `@item()` |

> ⚠️ **Important:** The base parameter name in the Notebook activity settings must be **`IMAGE_SIZE`** (uppercase) to match the notebook parameter cell variable name exactly.

---

## Security

All credentials are stored in **Azure Key Vault** and retrieved at runtime using `notebookutils.credentials.getSecret()`. No credentials are hardcoded in any notebook.

| Secret Name | Description |
|---|---|
| `cv-training-api-key` | Custom Vision Training resource API key |
| `cv-endpoint-t-key` | Custom Vision Training resource endpoint URL |
| `cv-prediction-api-key` | Custom Vision Prediction resource API key |
| `cv-endpoint-p-key` | Custom Vision Prediction resource endpoint URL |
| `cv-prediction-resource-id` | Full Azure Resource ID of the Prediction resource |

> The Fabric notebook identity must have **Key Vault Secrets User** role assigned on the Key Vault to retrieve secrets at runtime.

---

## How to Run

### ETL Images Pipeline

1. Open the **ETL Images** pipeline in your Fabric Workspace
2. Confirm `size_array` parameter is set to **Array** type
3. Confirm **ForEachResizing** and **ForEachGold** both have **Sequential** mode enabled
4. Click **Run**

> A **Wait activity** (120 seconds) is placed between `ForEachResizing` and `ForEachGold` to allow Spark sessions from the first ForEach to fully release before the second starts.

### Training Pipeline

1. Delete or clean any existing Custom Vision projects if retraining from scratch
2. Open the **training_custom_vision** pipeline
3. Confirm `size_array` parameter is **Array** type and **ForEach1** is **Sequential**
4. Click **Run**

> To retrain only specific sizes, temporarily set `size_array` to a subset, e.g. `["224","256"]`.

---

## Output Structure

```
OneLake (lkh_pets Lakehouse)
│
├── Files/
│   ├── images/
│   │   ├── raw/              ← Bronze (Shortcut from Azure Blob)
│   │   └── resized/          ← Silver (output of image_standarizer)
│   └── gold/                 ← Gold (output of dataset_builder)
│       ├── dataset_128/
│       ├── dataset_224/
│       ├── dataset_256/
│       ├── dataset_384/
│       └── dataset_512/
│
└── Tables/
    └── model_metrics         ← Delta table (output of training pipeline)
```

---

## Metrics

Training results are stored in the `model_metrics` Delta table in the attached Lakehouse.

| Column | Type | Description |
|---|---|---|
| `image_size` | String | Image resolution used for training (`"128"`, `"224"`, etc.) |
| `precision` | Float | Model precision on the test set |
| `recall` | Float | Model recall on the test set |
| `ap` | Float | Average precision across all tags |
| `accuracy` | Float | Overall classification accuracy on the test set |
| `timestamp` | Timestamp | Date and time the training run completed |

Each pipeline run **replaces** the existing record for a given `image_size`, ensuring the table always reflects the most recent training result per resolution.

---

*Built with ❤️ on Microsoft Fabric — OneLake, Spark, and Data Pipelines.*
