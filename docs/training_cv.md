# Training & Development Pipeline — Pet Image Classification
> **Platform:** Microsoft Fabric | **Storage:** Microsoft Fabric (OneLake) | **Orchestration:** Fabric Data Pipeline | **Model Service:** Azure Custom Vision | **Object Detection:** Azure AI Vision

> ⚠️ **Work in Progress** — The core training pipeline for resized images is functional. The original-size model (`real_size_cv`) and the development inference pipeline are currently under active development.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Pipeline Parameters](#pipeline-parameters)
5. [Training Pipelines](#training-pipelines)
   - [training_custom_vision](#training_custom_vision)
   - [real_size_cv](#real_size_cv-under-development)
6. [Development Pipeline](#development-pipeline-preview)
   - [object_detection](#object_detectionipynb)
   - [run_inference](#run_inferenceipynb)
7. [Security](#security)
8. [How to Run](#how-to-run)
9. [Output Structure](#output-structure)
10. [Metrics](#metrics)
11. [Upcoming Development](#upcoming-development)

---

## Overview

This document covers two related pipelines built on **Microsoft Fabric**:

**1. Training Pipeline (`pl_ml_training`)**
Trains Azure Custom Vision classification models and evaluates each against a held-out test set. Designed to answer:

> **Does image resolution affect model performance? Is it worth training on original-size images compared to standardized resolutions?**

**2. Development Pipeline (`Implementation_ppl`) — Preview**
Processes real-world images uploaded by users. Uses **Azure AI Vision** (pre-trained, no custom training needed) to detect and crop pets from complex scenes, then evaluates the cropped image against all trained classification models simultaneously.

| Pipeline | Input | Status |
|---|---|---|
| `pl_ml_training` → `training_custom_vision` | Gold layer resized images | ✅ Functional |
| `pl_ml_training` → `real_size_cv` | Bronze layer raw images | 🚧 In progress |
| `Implementation_ppl` | User-uploaded real-world images | 🚧 In progress |

---

## Architecture

### Training Pipeline

![Training Architecture](images/ds_arquitecture.jpg)

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
│  │   ┌─────────────────────────────────────────────────┐   │    │
│  │   │  Flow 1 — Resized Models                        │   │    │
│  │   │  Gold Images ──▶ training_custom_vision.ipynb   │   │    │
│  │   │  Parameters: size_array                         │   │    │
│  │   │  ["128","224","256","384","512"]                 │   │    │
│  │   │           pet-classifier-{size} ────────────────┼───┼──▶ │
│  │   └─────────────────────────────────────────────────┘   │    │
│  │                                                          │    │
│  │   ┌─────────────────────────────────────────────────┐   │    │
│  │   │  Flow 2 — Original Size Model (Under Dev.)      │   │    │
│  │   │  Shortcut Raw Images ──▶ real_size_cv.ipynb     │   │    │
│  │   │           pet-classifier-original ──────────────┼───┼──▶ │
│  │   └─────────────────────────────────────────────────┘   │    │
│  └──────────────────────────────────────────────────────────┘    │
│                              ▼                                   │
│                    model_metrics (Delta Table)                   │
└──────────────────────────────────────────────────────────────────┘
          │  API calls (train, publish, predict)
          ▼
   Azure Custom Vision
   (pet-classifier-128/224/256/384/512/original)
```

### Development Pipeline *(Preview)*

![Development Architecture](images/development_arquitecture.jpg)

```
User uploads image
        │
        ▼
Azure Blob Storage ──▶ OneLake Shortcut (development images)
        │
        ▼ (blob trigger)
Implementation_ppl
        │
        ├──▶ object_detection.ipynb
        │         │  Azure AI Vision API (pre-trained)
        │         │  Detects pet → crops bounding box
        │         │
        │         ├── Pet found ──▶ run_inference.ipynb
        │         │                     ForEach all model sizes
        │         │                     → inference_metrics (Delta Table)
        │         │
        │         └── No pet found ──▶ log_no_detection
        │                               → inference_metrics (detected=false)
        │
        └──▶ object_detection_metrics (Delta Table)
                  (logs every detection event)
                        │
                        ▼
                   Dashboard (Power BI) ← Data Analyst scope
```

---

## Prerequisites

| Requirement | Details |
|---|---|
| Microsoft Fabric Workspace | With at least one attached Lakehouse (`lkh_pets`) |
| Gold layer populated | Run the ETL Images pipeline first |
| Bronze layer available | OneLake Shortcut from Azure Blob Storage |
| Azure Key Vault | Storing all API credentials |
| Azure Custom Vision | S0 Standard tier (**Free tier limited to 2 projects**) |
| Azure AI Vision | Computer Vision resource for pre-trained object detection |
| Fabric Capacity | F2 or higher recommended |
| Python Libraries | `azure-cognitiveservices-vision-customvision`, `msrest`, `requests`, `Pillow` |

---

## Pipeline Parameters

### pl_ml_training

| Parameter | Type | Default Value | Description |
|---|---|---|---|
| `size_array` | Array | `["128","224","256","384","512"]` | Image sizes to train models for |

> ⚠️ Must be **Array** type in the Fabric pipeline canvas — not String.

> 💡 To retrain only specific sizes, temporarily set `size_array` to a subset e.g. `["224","256"]`.

### Implementation_ppl

| Parameter | Type | Description |
|---|---|---|
| `image_path` | String | Path to the uploaded image, injected by the blob trigger |

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
| 2 | Retrieves credentials from Azure Key Vault via `notebookutils.credentials.getSecret()` |
| 3 | Creates or **reuses** an existing Custom Vision project named `pet-classifier-{IMAGE_SIZE}` |
| 4 | Creates classification tags dynamically from Gold layer label subfolders |
| 5 | Uploads training images in **batches of 64** |
| 6 | Validates minimum 5 images per tag before training |
| 7 | Trains the model with a **30-minute timeout**, polling every 10 seconds |
| 8 | Unpublishes any existing iteration with the same name, then publishes the new one |
| 9 | Evaluates the model against the test set using the Custom Vision Prediction API |
| 10 | Saves precision, recall, AP and accuracy to the `model_metrics` Delta table |

#### Parameters received from pipeline

| Parameter | Type | Description |
|---|---|---|
| `IMAGE_SIZE` | String | Current image size injected by `@item()` |

> ⚠️ Must be **`IMAGE_SIZE`** uppercase in the Notebook activity Base Parameters settings.

---

### real_size_cv *(Under Development)*

**Status:** 🚧 In progress

**Input:** Bronze layer — Shortcut Raw Images (original resolution, unmodified)

**Purpose:** Trains a baseline Custom Vision model on raw unresized images to answer:

> *Does standardizing image resolution improve or hurt model performance compared to training on variable-size originals?*

**Expected output:** One record in `model_metrics` with `image_size = "original"` for direct dashboard comparison.

---

## Development Pipeline *(Preview)*

### object_detection.ipynb

**Status:** 🚧 In progress

**Purpose:** Detects pets in real-world user-uploaded images using the **Azure AI Vision pre-trained object detection model** — no custom training required. Crops the detected pet bounding box and saves it for classification.

**Key logic:**
- Calls Azure AI Vision REST API with `features: objects,tags`
- Uses image-level tags to confirm animal presence — handles breed-specific labels like `"retriever"` by matching parent categories `"dog"` and `"animal"`
- Crops the highest-confidence bounding box
- Saves cropped image to `Files/development/cropped/`
- Logs every transaction to `object_detection_metrics` Delta table

**Why Azure AI Vision instead of Custom Vision Object Detection:**
Azure AI Vision provides a **pre-trained** model that already detects dogs, cats and animals out of the box — no bounding box tagging or model training is required, saving significant Data Scientist effort.

---

### run_inference.ipynb

**Status:** 🚧 In progress

**Purpose:** Takes the cropped pet image and runs it through **all trained classification models** simultaneously via ForEach, saving one result row per model to `inference_metrics`.

---

## Security

All credentials stored in **Azure Key Vault** — no hardcoded secrets anywhere.

| Secret Name | Used by | Description |
|---|---|---|
| `cv-training-api-key` | `training_custom_vision` | Custom Vision Training API key |
| `cv-endpoint-t-key` | `training_custom_vision` | Custom Vision Training endpoint |
| `cv-prediction-api-key` | `training_custom_vision`, `run_inference` | Custom Vision Prediction API key |
| `cv-endpoint-p-key` | `training_custom_vision`, `run_inference` | Custom Vision Prediction endpoint |
| `cv-prediction-resource-id` | `training_custom_vision` | Full Azure Resource ID for publishing |
| `ai-vision-api-key` | `object_detection` | Azure AI Vision API key |
| `ai-vision-endpoint` | `object_detection` | Azure AI Vision endpoint |

> Fabric notebook identity must have **Key Vault Secrets User** role on the Key Vault.

---

## How to Run

### Training pipeline
1. Confirm ETL Images pipeline completed and Gold layer folders exist
2. Confirm all Key Vault secrets are set
3. Confirm Azure Custom Vision is on **S0 Standard tier**
4. Open **`pl_ml_training`** → confirm `size_array` is Array type and Sequential ON
5. Click **Run**

### Development pipeline *(Preview)*
1. Confirm all training models are published in Custom Vision
2. Confirm Azure AI Vision resource is created and secrets added to Key Vault
3. Upload a test image to the designated Blob Storage folder
4. `Implementation_ppl` triggers automatically
5. Check `inference_metrics` and `object_detection_metrics` tables for results

### Re-running
- Training: notebook reuses existing projects and replaces metrics records automatically
- Development: each image upload creates new rows in `inference_metrics` — no cleanup needed

---

## Output Structure

```
OneLake (lkh_pets Lakehouse)
│
├── Files/
│   └── development/
│       ├── raw/        ← User uploaded images
│       └── cropped/    ← Cropped pet bounding boxes
│
└── Tables/
    ├── model_metrics              ← Training evaluation (one record per model size)
    ├── inference_metrics          ← Real-world inference (one record per image per model)
    └── object_detection_metrics   ← Detection events log (one record per detected object)

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

### model_metrics

| Column | Type | Description |
|---|---|---|
| `image_size` | String | `"128"`, `"224"`, `"256"`, `"384"`, `"512"`, or `"original"` |
| `precision` | Float | Model precision on the test set |
| `recall` | Float | Model recall on the test set |
| `ap` | Float | Average precision across all tags |
| `accuracy` | Float | Overall classification accuracy |
| `timestamp` | Timestamp | Training run completion time |

### inference_metrics

| Column | Type | Description |
|---|---|---|
| `image_name` | String | Original uploaded filename |
| `model_size` | String | Model used for this prediction |
| `detected` | Boolean | Whether a pet was found |
| `tag` | String | Predicted pet label or `"no_animal"` |
| `confidence` | Float | Classification confidence score |
| `timestamp` | Timestamp | Inference run time |

### object_detection_metrics

| Column | Type | Description |
|---|---|---|
| `image_name` | String | Original uploaded filename |
| `detected` | Boolean | Whether any pet was detected |
| `animal_count` | Integer | Number of animals found |
| `object_name` | String | Detected object label (e.g. `"retriever"`, `"dog"`) |
| `confidence` | Float | Detection confidence score |
| `bbox_x/y/w/h` | Integer | Bounding box coordinates in pixels |
| `timestamp` | Timestamp | Detection run time |

---

## Upcoming Development

| Feature | Description | Status |
|---|---|---|
| **Original size model** | Train `real_size_cv` on raw images as a baseline | 🚧 In progress |
| **run_inference notebook** | ForEach inference across all models per uploaded image | 🚧 In progress |
| **Blob trigger** | Automatic `Implementation_ppl` trigger on image upload | 🔜 Planned |
| **Dashboard** | Power BI consuming `inference_metrics` and `model_metrics` | 🔜 Planned |
| **Full dataset training** | Expand to ~75 images per label | 🔜 Planned |
| **Resource usage tracking** | Log training duration and estimated cost per run | 🔜 Future consideration |

> **Note on MLflow:** Azure Custom Vision manages iteration history internally and does not integrate with MLflow. MLflow would apply if the project migrates to a custom PyTorch/TensorFlow model trained directly in Fabric — under evaluation for a future iteration.

---

*Built with ❤️ on Microsoft Fabric — OneLake, Spark, Data Pipelines, Azure Custom Vision, and Azure AI Vision.*
