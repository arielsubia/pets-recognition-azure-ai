# Development Pipeline — Real-World Pet Inference
> **Role:** Developer | **Platform:** Microsoft Fabric | **Storage:** Microsoft Fabric (OneLake) | **Object Detection:** Azure AI Vision | **Classification:** Azure Custom Vision | **Orchestration:** Fabric Data Pipeline

> ⚠️ **Work in Progress** — Core object detection and cropping are functional. End-to-end pipeline integration with inference is in progress.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Pipeline Parameters](#pipeline-parameters)
5. [Notebooks](#notebooks)
   - [object_detection](#object_detectionipynb)
   - [run_inference](#run_inferenceipynb)
6. [Security](#security)
7. [How to Run](#how-to-run)
8. [Output Structure](#output-structure)
9. [Delta Tables](#delta-tables)
10. [Known Limitations](#known-limitations)
11. [Upcoming Development](#upcoming-development)

---

## Overview

The development pipeline (`pl_implementation`) processes **real-world images** to evaluate how well the trained classification models perform outside of controlled training conditions.

The core challenge is that real-world images are complex — a photo of a pet typically contains people, backgrounds, furniture and other distracting elements. Passing the full image directly to a classification model produces unreliable results.

This pipeline addresses that through three stages:

1. **Detect** — Azure AI Vision pre-trained object detection identifies pets and returns bounding box coordinates
2. **Crop** — each detected pet is isolated into its own image
3. **Classify** — each cropped image is evaluated against all trained Custom Vision models simultaneously

Results are stored in Delta tables for downstream dashboard consumption by the Data Analyst role.

> **Role boundary:** The Data Scientist is responsible for providing trained and published Custom Vision models. The Developer builds and maintains this pipeline consuming those models. See `training_cv.md` for the Data Scientist scope.

---

## Architecture

```
Developer / User
        │
        │  uploads image
        ▼
Azure Blob Storage
        │
        │  OneLake Shortcut
        ▼
Files/development/raw/
        │
        ▼ (triggered manually or via blob event)
┌──────────────────────────────────────────────────────────────────┐
│                pl_implementation Pipeline                        │
│                (Fabric Data Pipeline)                            │
│                                                                  │
│  Parameter: image_path                                           │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  object_detection_ntb                                   │    │
│  │  Detects pets → crops → saves → exits with paths        │    │
│  └──────────────────────────────────────────────────────────┘    │
│                    │                                             │
│     @json(activity('object_detection_ntb')                       │
│            .output.result.exitValue)                             │
│                    ▼                                             │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  ForEachCrop (Sequential)                               │    │
│  │  One iteration per cropped image path                   │    │
│  │                                                          │    │
│  │      run_inference_ntb                                  │    │
│  │      Classifies crop against all models → saves results │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────┐
│  Delta Tables (lkh_pets Lakehouse)│
│  ├── object_detection_metrics     │
│  └── inference_metrics            │
└───────────────────────────────────┘
        │
        ▼
  Power BI Dashboard ← Data Analyst scope (planned)
```

---

## Prerequisites

| Requirement | Details |
|---|---|
| Microsoft Fabric Workspace | With `lkh_pets` set as the default Lakehouse in each notebook |
| `pl_ml_training` completed | All `pet-classifier-{size}` projects trained and published in Custom Vision |
| Azure AI Vision resource | Computer Vision resource (any tier) |
| Azure Custom Vision resources | S0 Standard tier — Training + Prediction resources |
| Azure Key Vault | All API credentials stored as secrets |
| Fabric Capacity | F2 or higher recommended |
| Python Libraries | `requests`, `Pillow`, `azure-cognitiveservices-vision-customvision`, `msrest` |

---

## Pipeline Parameters

| Parameter | Type | Description |
|---|---|---|
| `image_path` | String | Relative path to the image inside the Lakehouse `Files/` folder |

**Example values:**
```
development/raw/photo_001.jpg
test-object-detection/image2.jpg
```

### Activity base parameters

**`object_detection_ntb`:**

| Name | Type | Value |
|---|---|---|
| `image_path` | String | `@pipeline().parameters.image_path` |

**`run_inference_ntb`** (inside ForEachCrop):

| Name | Type | Value |
|---|---|---|
| `cropped_path` | String | `@item()` |

---

## Notebooks

### object_detection.ipynb

**Status:** ✅ Functional

**Purpose:** Receives an image path, calls the Azure AI Vision REST API to detect animals, filters and deduplicates results, crops each detected pet and saves the crops to the Lakehouse. Exits with a JSON list of full `abfss://` paths to the cropped images, which the pipeline uses to feed `ForEachCrop`.

**Key behaviors:**
- Uses image-level tags and object-level tags together to correctly identify animals, including breed-specific labels such as `"retriever"` or `"chihuahua"`
- Explicitly excludes people and non-animal objects from detections
- Applies IoU deduplication to remove overlapping bounding boxes of the same animal
- Saves one cropped image per detected pet with a timestamped filename
- Logs every detection event to `object_detection_metrics`

---

### run_inference.ipynb

**Status:** ✅ Functional

**Purpose:** Receives a single cropped image path and classifies it against all available trained Custom Vision models. Discovers models dynamically at runtime — no hardcoded sizes — so it automatically picks up new models added by future training runs. Saves one result row per model to `inference_metrics`.

**Key behaviors:**
- Training credentials are used **read-only** solely to discover available `pet-classifier-*` projects dynamically
- Handles both manual execution (relative path) and pipeline execution (full `abfss://` path) transparently
- Logs results for all models in a single pipeline iteration

---

## Security

All credentials stored in **Azure Key Vault** — no hardcoded secrets in any notebook.

| Secret Name | Used by | Description |
|---|---|---|
| `ai-vision-api-key` | `object_detection` | Azure AI Vision API key |
| `ai-vision-endpoint` | `object_detection` | Azure AI Vision endpoint URL |
| `cv-prediction-api-key` | `run_inference` | Custom Vision Prediction API key |
| `cv-endpoint-p-key` | `run_inference` | Custom Vision Prediction endpoint URL |
| `cv-training-api-key` | `run_inference` | Custom Vision Training API key (read-only) |
| `cv-endpoint-t-key` | `run_inference` | Custom Vision Training endpoint URL |

> Fabric notebook identity must have **Key Vault Secrets User** role assigned on the Key Vault.

---

## How to Run

### Manual run

1. Upload an image to `Files/development/raw/` in the Lakehouse
2. Open **`pl_implementation`** pipeline in Fabric
3. Set `image_path` parameter to the relative path of the uploaded image
4. Confirm `ForEachCrop` has **Sequential** mode enabled
5. Click **Run**
6. Check `object_detection_metrics` and `inference_metrics` tables for results

### Expected outputs per run

For an image containing **N detected pets** and **M trained models**:

| Output | Count |
|---|---|
| Cropped images saved to Lakehouse | N files |
| `object_detection_metrics` rows | N rows |
| `inference_metrics` rows | N × M rows |

**Example** — image with 1 cat + 1 dog, 5 trained models → 2 crops, 10 inference rows.

### No pet detected

If Azure AI Vision finds no animals, a single row is logged to `object_detection_metrics` with `detected = false`. `ForEachCrop` receives an empty list and skips inference entirely.

---

## Output Structure

```
OneLake (lkh_pets Lakehouse)
│
├── Files/
│   └── development/
│       ├── raw/        ← input images
│       └── cropped/    ← one file per detected pet per run
│
└── Tables/
    ├── object_detection_metrics
    └── inference_metrics
```

---

## Delta Tables

### object_detection_metrics

One row per detected object per image run.

| Column | Type | Description |
|---|---|---|
| `image_name` | String | Cropped filename with timestamp |
| `detected` | Boolean | Whether a pet was detected |
| `animal_count` | Integer | Total animals detected in the image |
| `object_name` | String | Detected label e.g. `"cat"`, `"retriever"`, `"none"` |
| `confidence` | Float | Detection confidence (0–1) |
| `bbox_x` | Integer | Bounding box left position in pixels |
| `bbox_y` | Integer | Bounding box top position in pixels |
| `bbox_w` | Integer | Bounding box width in pixels |
| `bbox_h` | Integer | Bounding box height in pixels |
| `timestamp` | Timestamp | When the detection ran |

### inference_metrics

One row per cropped image per model.

| Column | Type | Description |
|---|---|---|
| `image_name` | String | Cropped filename — links to `object_detection_metrics` |
| `model_size` | String | Model used e.g. `"128"`, `"224"`, `"512"` |
| `predicted` | String | Predicted pet label |
| `confidence` | Float | Classification confidence (0–1) |
| `timestamp` | Timestamp | When the inference ran |

> Both tables use `append` write mode — every run adds new rows, enabling historical trend analysis.

---

## Known Limitations

**Partially occluded animals:** Azure AI Vision object detection may not generate a bounding box for animals that are partially hidden — for example a dog held in a person's arms. In such cases the animal may appear in the image-level tags but not in the object detection results, and therefore no crop is produced for it. This is a known limitation of the pre-trained model and affects images where the pet is significantly occluded by a person or object.

As a result, only clearly visible pets produce reliable crops and inference results.

---

## Upcoming Development

| Feature | Description | Status |
|---|---|---|
| **Blob event trigger** | Automatically trigger `pl_implementation` when a new image is uploaded | 🔜 Planned |
| **Dashboard** | Power BI report consuming `inference_metrics` and `object_detection_metrics` | 🔜 Planned |
| **Original size model inference** | Include `pet-classifier-original` once `real_size_cv` is complete | 🔜 Planned |
| **Multi-image batch processing** | Process a folder of images in a single pipeline run | 🔜 Future consideration |

---

*Built with ❤️ on Microsoft Fabric — OneLake, Spark, Data Pipelines, Azure AI Vision, and Azure Custom Vision.*
