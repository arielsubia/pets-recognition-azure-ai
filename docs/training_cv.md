# Training Pipeline — Pet Image Classification
> **Role:** Data Scientist | **Platform:** Microsoft Fabric | **Storage:** Microsoft Fabric (OneLake) | **Orchestration:** Fabric Data Pipeline | **Model Service:** Azure Custom Vision

> The training pipeline supports all resolutions including original-size images. Adding `"original"` to the `size_array` parameter triggers training on raw unresized images — no separate notebook needed.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Pipeline Parameters](#pipeline-parameters)
5. [Training Pipeline](#training-pipeline)
   - [training_custom_vision](#training_custom_vision)
6. [Security](#security)
7. [How to Run](#how-to-run)
8. [Output Structure](#output-structure)
9. [Metrics](#metrics)
10. [Upcoming Development](#upcoming-development)

---

## Overview

This document covers the **Data Scientist scope** of the project. The Data Scientist is responsible for:

- Designing and implementing the model training notebooks
- Creating and managing Azure Custom Vision projects
- Evaluating model performance across different image resolutions
- Publishing trained models so they can be consumed by the Developer role

The training pipeline (`pl_ml_training`) trains one **Azure Custom Vision** classification model per image resolution and evaluates each against a held-out test set. It is designed to answer a key research question:

> **Does image resolution affect model performance? Is it worth training on original-size images compared to standardized resolutions?**

A single unified training flow handles all resolutions:

| Flow | Notebook | Input | Models produced | Status |
|---|---|---|---|---|
| All models | `training_custom_vision.py` | Gold layer (`dataset_{size}`) | One model per size: 128, 224, 256, 384, 512, original | ✅ Functional |

The Data Engineer prepares `Files/gold/dataset_original/` via `dataset_builder.py` (reading from the Bronze shortcut), enabling the Data Scientist to train the original-size model without a separate notebook.

All results converge into a single `model_metrics` Delta table, enabling a unified comparison across all models — consumed downstream by the Developer and Data Analyst roles.

> **Handoff to Developer:** Once models are trained and published in Custom Vision, the Developer role uses them inside the `pl_implementation` pipeline for real-world inference. See `pl_implementation_design.md` for details.

---

## Architecture

```
Azure Key Vault
(Credentials)
      │
      │  getSecret()
      ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Microsoft Fabric Workspace                     │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │   pl_ml_training Pipeline (Fabric Data Pipeline)        │    │
│  │                                                          │    │
│  │   Gold Images ──▶ training_custom_vision.py             │    │
│  │   Parameters: size_array                                │    │
│  │   ["128","224","256","384","512","original"]             │    │
│  │                                                          │    │
│  │   ForEach1 (Sequential)                                 │    │
│  │       @item() → IMAGE_SIZE                              │    │
│  │            │                                            │    │
│  │            ▼                                            │    │
│  │   pet-classifier-{size} ────────────────────────────────┼──▶ │
│  │                                                          │    │
│  └──────────────────────────────────────────────────────────┘    │
│                              ▼                                   │
│                    model_metrics (Delta Table)                   │
└──────────────────────────────────────────────────────────────────┘
          │
          │  API calls (train, publish, predict)
          ▼
   Azure Custom Vision
   ┌───────────────────────────┐
   │  pet-classifier-128       │
   │  pet-classifier-224       │
   │  pet-classifier-256       │
   │  pet-classifier-384       │
   │  pet-classifier-512       │
   │  pet-classifier-original  │
   └───────────────────────────┘
```

---

## Prerequisites

| Requirement | Details |
|---|---|
| Microsoft Fabric Workspace | With `lkh_pets` set as the **default Lakehouse** in each notebook |
| Gold layer populated | Run the ETL Images pipeline first to generate `Files/gold/dataset_{size}/` (includes `dataset_original` when `"original"` is in the array) |
| Azure Key Vault | Storing all Custom Vision API credentials |
| Azure Custom Vision | Training and Prediction resources (**S0 Standard tier required** — Free tier limited to 2 projects) |
| Fabric Capacity | F2 or higher recommended to avoid `TooManyRequestsForCapacity` errors |
| Python Libraries | `azure-cognitiveservices-vision-customvision`, `msrest` (installed via `subprocess` at runtime) |

---

## Pipeline Parameters

| Parameter | Type | Default Value | Description |
|---|---|---|---|
| `size_array` | Array | `["128","224","256","384","512","original"]` | Image sizes to train models for |

> ⚠️ **Important:** The parameter type must be set to **Array** in the Fabric pipeline canvas. Setting it as **String** will prevent the ForEach activity from iterating correctly.

> 💡 **Tip:** To retrain only specific sizes, temporarily set `size_array` to a subset e.g. `["224","256"]`, then restore the full array afterward.

---

## Training Pipeline

### training_custom_vision

**Status:** ✅ Functional

**Notebook:** `training_custom_vision.py`

**Input:** Gold layer — `Files/gold/dataset_{IMAGE_SIZE}/train` and `.../test`

**Purpose:** Trains one Custom Vision classification model per image resolution (including original) and evaluates it against the corresponding test set.

#### Notebook logic per iteration

| Step | Description |
|---|---|
| 1 | Resolves absolute `abfss://` paths dynamically from the default Lakehouse |
| 2 | Retrieves all credentials from Azure Key Vault via `notebookutils.credentials.getSecret()` |
| 3 | Creates or **reuses** an existing Custom Vision project named `pet-classifier-{IMAGE_SIZE}` |
| 4 | Creates classification tags dynamically from Gold layer label subfolders |
| 5 | Uploads training images to Custom Vision in **batches of 64** |
| 6 | Validates minimum 5 images per tag before training (Custom Vision requirement) |
| 7 | Trains the model with a **30-minute timeout**, polling status every 10 seconds |
| 8 | Unpublishes any existing published iteration with the same name, then publishes the new one |
| 9 | Evaluates the model against the test set using the Custom Vision Prediction API |
| 10 | Saves precision, recall, AP and accuracy to the `model_metrics` Delta table |

#### Parameters received from pipeline

| Parameter | Type | Description |
|---|---|---|
| `IMAGE_SIZE` | String | Current image size injected by `@item()` from the ForEach activity |

> ⚠️ The base parameter name in the Notebook activity settings must be **`IMAGE_SIZE`** (uppercase) to match the notebook parameter cell variable name exactly.

---

## Security

All credentials are stored in **Azure Key Vault** and retrieved at runtime. No credentials are hardcoded in any notebook.

| Secret Name | Used by | Description |
|---|---|---|
| `cv-training-api-key` | `training_custom_vision` | Custom Vision Training resource API key |
| `cv-endpoint-t-key` | `training_custom_vision` | Custom Vision Training resource endpoint URL |
| `cv-prediction-api-key` | `training_custom_vision` | Custom Vision Prediction resource API key |
| `cv-endpoint-p-key` | `training_custom_vision` | Custom Vision Prediction resource endpoint URL |
| `cv-prediction-resource-id` | `training_custom_vision` | Full Azure Resource ID of the Prediction resource (required for publishing iterations) |

> The Fabric notebook identity must have **Key Vault Secrets User** role assigned on the Key Vault to retrieve secrets at runtime.

---

## How to Run

### Prerequisites check
1. Confirm the **ETL Images** pipeline has completed successfully and Gold layer folders exist
2. Confirm all 5 Key Vault secrets are created and accessible
3. Confirm Azure Custom Vision resources are on **S0 Standard tier**
4. Confirm `lkh_pets` is set as the default Lakehouse in `training_custom_vision`

### Run the training pipeline
1. Open the **`pl_ml_training`** pipeline in your Fabric Workspace
2. Confirm `size_array` parameter is set to **Array** type
3. Confirm **ForEach1** has **Sequential** mode enabled
4. Click **Run**

### Re-running the pipeline
- The notebook automatically **reuses existing projects** — no need to delete Custom Vision projects between runs
- The notebook automatically **unpublishes previous iterations** before publishing new ones — no manual cleanup needed
- The `model_metrics` table automatically **replaces the record** for each `image_size` on every run

---

## Output Structure

```
OneLake (lkh_pets Lakehouse)
│
└── Tables/
    └── model_metrics    ← Delta table with one record per model size

Azure Custom Vision Portal (customvision.ai)
    ├── pet-classifier-128
    ├── pet-classifier-224
    ├── pet-classifier-256
    ├── pet-classifier-384
    ├── pet-classifier-512
    └── pet-classifier-original
```

---

## Metrics

Training results are stored in the `model_metrics` Delta table in the default Lakehouse.

| Column | Type | Description |
|---|---|---|
| `image_size` | String | Resolution used: `"128"`, `"224"`, `"256"`, `"384"`, `"512"`, or `"original"` |
| `precision` | Float | Model precision on the test set |
| `recall` | Float | Model recall on the test set |
| `ap` | Float | Average precision across all tags |
| `accuracy` | Float | Overall classification accuracy on the test set |
| `timestamp` | Timestamp | Date and time the training run completed |

Each pipeline run **replaces** the existing record for a given `image_size`, ensuring the table always reflects the most recent training result per resolution.

> **Downstream consumption:** The `model_metrics` table is consumed by the Developer role in `pl_implementation` for model discovery, and by the Data Analyst role for dashboard visualization. See `pl_implementation_design.md` and `dashboard.md` for details.

---

## Upcoming Development

| Feature | Description | Status |
|---|---|---|
| **Original size model execution** | Run pipeline with `"original"` in `size_array` to train baseline model | 🔜 Pending execution (cost-dependent) |
| **Resource usage tracking** | Log training duration and estimated cost per model run | 🔜 Future consideration |


