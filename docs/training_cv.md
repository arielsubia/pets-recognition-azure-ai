# Training Pipeline — Pet Image Classification
> **Platform:** Microsoft Fabric | **Storage:** Microsoft Fabric (OneLake) | **Orchestration:** Fabric Data Pipeline | **Model Service:** Azure Custom Vision

> ⚠️ **Work in Progress** — The core training pipeline for resized images is functional. The original-size model (`real_size_cv`) and dashboard integration are currently under active development.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Pipeline Parameters](#pipeline-parameters)
5. [Training Pipelines](#training-pipelines)
   - [training_custom_vision](#training_custom_vision)
   - [real_size_cv](#real_size_cv-under-development)
6. [Security](#security)
7. [How to Run](#how-to-run)
8. [Output Structure](#output-structure)
9. [Metrics](#metrics)
10. [Upcoming Development](#upcoming-development)

---

## Overview

This section trains **Azure Custom Vision** classification models and evaluates each one against a held-out test set. The pipeline is designed to answer a key research question:

> **Does image resolution affect model performance? Is it worth training on original-size images compared to standardized resolutions?**

To answer this, two training flows are implemented:

| Flow | Input | Models produced | Status |
|---|---|---|---|
| `training_custom_vision` | Gold layer (resized images) | One model per size: 128, 224, 256, 384, 512 | ✅ Functional |
| `real_size_cv` | Bronze layer (raw original images) | One model at original resolution | 🔜 Under development |

All results converge into a single `model_metrics` Delta table, enabling a **unified comparison** across all models from the Data Analyst dashboard.

---

## Architecture


The following diagram shows the processing flow:

![Pipeline_ds](images/ds_arquitecture.jpg)



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
│  │   ┌─────────────────────────────────────────────────┐   │    │
│  │   │  Flow 1 — Resized Models                        │   │    │
│  │   │                                                 │   │    │
│  │   │  Gold Images ──▶ training_custom_vision.ipynb   │   │    │
│  │   │  Parameters: size_array                         │   │    │
│  │   │  ["128","224","256","384","512"]                 │   │    │
│  │   │                    │                            │   │    │
│  │   │                    ▼                            │   │    │
│  │   │           pet-classifier-128                    │   │    │
│  │   │           pet-classifier-224       ─────────────┼───┼──▶ │
│  │   │           pet-classifier-256                    │   │    │
│  │   │           pet-classifier-384                    │   │    │
│  │   │           pet-classifier-512                    │   │    │
│  │   └─────────────────────────────────────────────────┘   │    │
│  │                                                          │    │
│  │   ┌─────────────────────────────────────────────────┐   │    │
│  │   │  Flow 2 — Original Size Model (Under Dev.)      │   │    │
│  │   │                                                 │   │    │
│  │   │  Shortcut Raw Images ──▶ real_size_cv.ipynb     │   │    │
│  │   │                    │                            │   │    │
│  │   │                    ▼                            │   │    │
│  │   │           pet-classifier-original  ─────────────┼───┼──▶ │
│  │   └─────────────────────────────────────────────────┘   │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                            ▼                    │
│                              ┌─────────────────────────┐        │
│                              │  model_metrics           │        │
│                              │  (Delta Table)           │        │
│                              └─────────────────────────┘        │
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
   │  pet-classifier-original  │ ← Under development
   └───────────────────────────┘
```

---

## Prerequisites

| Requirement | Details |
|---|---|
| Microsoft Fabric Workspace | With at least one attached Lakehouse (`lkh_pets`) |
| Gold layer populated | Run the ETL Images pipeline first to generate `Files/gold/dataset_{size}/` |
| Bronze layer available | OneLake Shortcut from Azure Blob Storage (required for `real_size_cv`) |
| Azure Key Vault | Storing all Custom Vision API credentials |
| Azure Custom Vision | Training and Prediction resources (**S0 Standard tier required** — Free tier limited to 2 projects) |
| Fabric Capacity | F2 or higher recommended to avoid `TooManyRequestsForCapacity` errors |
| Python Libraries | `azure-cognitiveservices-vision-customvision`, `msrest` (installed via `subprocess` at runtime) |

---

## Pipeline Parameters

| Parameter | Type | Default Value | Description |
|---|---|---|---|
| `size_array` | Array | `["128","224","256","384","512"]` | Image sizes to train models for (used by `training_custom_vision` flow only) |

> ⚠️ **Important:** The parameter type must be set to **Array** in the Fabric pipeline canvas. Setting it as **String** will prevent the ForEach activity from iterating correctly.

> 💡 **Tip:** To retrain only specific sizes, temporarily set `size_array` to a subset, e.g. `["224","256"]`, and restore the full array afterward.

---

## Training Pipelines

### training_custom_vision

**Status:** ✅ Functional

**Input:** Gold layer — `Files/gold/dataset_{IMAGE_SIZE}/train` and `.../test`

**Purpose:** Trains one Custom Vision classification model per image resolution and evaluates it against the corresponding test set.

#### Notebook logic per iteration

| Step | Description |
|---|---|
| 1 | Resolves absolute `abfss://` paths dynamically from the attached Lakehouse |
| 2 | Retrieves all credentials from Azure Key Vault via `notebookutils.credentials.getSecret()` |
| 3 | Creates or **reuses** an existing Custom Vision project named `pet-classifier-{IMAGE_SIZE}` |
| 4 | Creates classification tags dynamically from Gold layer label subfolders |
| 5 | Uploads training images to Custom Vision in **batches of 64** |
| 6 | Validates minimum image count per tag before training (minimum 5 per tag required by Custom Vision) |
| 7 | Trains the model with a **30-minute timeout**, polling status every 10 seconds |
| 8 | Unpublishes any existing published iteration with the same name, then publishes the new one |
| 9 | Evaluates the model against the test set using the Custom Vision **Prediction API** |
| 10 | Saves precision, recall, AP and accuracy to the `model_metrics` Delta table |

#### Parameters received from pipeline

| Parameter | Type | Description |
|---|---|---|
| `IMAGE_SIZE` | String | Current image size injected by `@item()` from the ForEach activity |

> ⚠️ The base parameter name in the Notebook activity settings must be **`IMAGE_SIZE`** (uppercase) to match the notebook parameter cell variable name exactly.

---

### real_size_cv *(Under Development)*

**Status:** 🔜 Under development

**Input:** Bronze layer — Shortcut Raw Images (original resolution, unmodified)

**Purpose:** Trains a Custom Vision model using images at their **original resolution** without any standardization. This serves as a **baseline comparison** against the resized models — the key question being:

> *Does standardizing image resolution improve or hurt model performance compared to training on raw, variable-size images?*

**Expected output:** One additional record in `model_metrics` with `image_size = "original"`, enabling direct comparison with all resized models in the same table and dashboard.

> ⚠️ Note: Custom Vision handles variable image sizes internally, but training time and resource usage may differ from standardized inputs. This will be evaluated as part of the development.

---

## Security

All credentials are stored in **Azure Key Vault** and retrieved at runtime. No credentials are hardcoded in any notebook.

| Secret Name | Description |
|---|---|
| `cv-training-api-key` | Custom Vision Training resource API key |
| `cv-endpoint-t-key` | Custom Vision Training resource endpoint URL |
| `cv-prediction-api-key` | Custom Vision Prediction resource API key |
| `cv-endpoint-p-key` | Custom Vision Prediction resource endpoint URL |
| `cv-prediction-resource-id` | Full Azure Resource ID of the Prediction resource (required for publishing iterations) |

> The Fabric notebook identity must have **Key Vault Secrets User** role assigned on the Key Vault to retrieve secrets at runtime.

---

## How to Run

### Prerequisites check
1. Confirm the **ETL Images** pipeline has completed successfully and Gold layer folders exist
2. Confirm all 5 Key Vault secrets are created and accessible
3. Confirm Azure Custom Vision resources are on **S0 Standard tier**

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
    └── model_metrics    ← Delta table with one record per model

Azure Custom Vision Portal (customvision.ai)
    ├── pet-classifier-128
    ├── pet-classifier-224
    ├── pet-classifier-256
    ├── pet-classifier-384
    ├── pet-classifier-512
    └── pet-classifier-original   ← Under development
```

---

## Metrics

Training results are stored in the `model_metrics` Delta table.

| Column | Type | Description |
|---|---|---|
| `image_size` | String | Resolution used: `"128"`, `"224"`, `"256"`, `"384"`, `"512"`, or `"original"` |
| `precision` | Float | Model precision on the test set |
| `recall` | Float | Model recall on the test set |
| `ap` | Float | Average precision across all tags |
| `accuracy` | Float | Overall classification accuracy on the test set |
| `timestamp` | Timestamp | Date and time the training run completed |

Each pipeline run **replaces** the existing record for a given `image_size`, ensuring the table always reflects the most recent result per model.

---

## Upcoming Development

| Feature | Description | Status |
|---|---|---|
| **Original size model** | Train and evaluate `real_size_cv` on raw unresized images as a baseline | 🔜 In progress |
| **Dashboard integration** | Power BI dashboard consuming `model_metrics` for visual comparison across all models | 🔜 Planned |
| **Inference notebook** | Dedicated notebook for the Data Analyst role to test new images against any published model | 🔜 Planned |
| **Full dataset training** | Expand to ~75 images per label per pet category | 🔜 Planned |
| **Resource usage tracking** | Log training duration and estimated cost per model run | 🔜 Future consideration |

> **Note on MLflow:** Azure Custom Vision manages its own iteration history internally and does not integrate with MLflow. MLflow tracking would apply if the project migrates to a custom model trained directly in Fabric using PyTorch or TensorFlow. This is under evaluation for a future iteration of the project.

---

*Built with ❤️ on Microsoft Fabric — OneLake, Spark, Data Pipelines, and Azure Custom Vision.*
