# Development Pipeline — Real-World Pet Inference
> **Platform:** Microsoft Fabric | **Storage:** Microsoft Fabric (OneLake) | **Object Detection:** Azure AI Vision | **Classification:** Azure Custom Vision | **Orchestration:** Fabric Data Pipeline

> ⚠️ **Work in Progress** — The development pipeline is currently under active development. Core object detection and cropping are functional. ForEach inference integration is in progress.

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
10. [Upcoming Development](#upcoming-development)

---

## Overview

The development pipeline (`pl_implementation`) processes **real-world images** uploaded by users or developers to evaluate how well the trained classification models perform outside of controlled training conditions.

The core challenge it solves is this: **real-world images are messy**. A photo of a pet typically contains people, backgrounds, furniture and other objects. Passing the entire image directly to a classification model produces unreliable results. This pipeline addresses that by:

1. **Detecting** pets in the image using Azure AI Vision pre-trained object detection — no custom training required
2. **Cropping** each detected pet into its own image using the bounding box coordinates
3. **Classifying** each cropped image against **all trained Custom Vision models** simultaneously
4. **Logging** every result to Delta tables for dashboard consumption

This enables a fair, controlled evaluation of each model's real-world performance.

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
Files/development/raw/         ← input images
        │
        ▼ (pipeline triggered manually or via blob event)
┌──────────────────────────────────────────────────────────────────┐
│                pl_implementation Pipeline                        │
│                (Fabric Data Pipeline)                            │
│                                                                  │
│  Parameter: image_path                                           │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  object_detection_ntb (Notebook Activity)               │    │
│  │                                                          │    │
│  │  1. Copies image from Lakehouse to /tmp/                 │    │
│  │  2. Calls Azure AI Vision REST API                       │    │
│  │  3. Filters pet objects (excludes people)                │    │
│  │  4. Deduplicates overlapping bounding boxes (IoU)        │    │
│  │  5. Crops each pet → saves to Files/development/cropped/ │    │
│  │  6. Saves detection metrics to object_detection_metrics  │    │
│  │  7. Exits with JSON list of cropped paths                │    │
│  └──────────────────────────────────────────────────────────┘    │
│                    │                                             │
│                    │  @json(activity('object_detection_ntb')     │
│                    │         .output.runOutput)                  │
│                    ▼                                             │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  ForEachCrop (Sequential)                               │    │
│  │  Items: one cropped image path per iteration            │    │
│  │                                                          │    │
│  │      run_inference_ntb (Notebook Activity)              │    │
│  │                                                          │    │
│  │      1. Discovers all pet-classifier-* projects          │    │
│  │         dynamically via trainer.get_projects()           │    │
│  │      2. Runs each model against the cropped image        │    │
│  │      3. Saves results to inference_metrics               │    │
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
| Microsoft Fabric Workspace | With `lkh_pets` With lkh_pets set as the default Lakehouse in each notebook |
| `pl_ml_training` completed | All `pet-classifier-{size}` projects must be trained and published in Custom Vision |
| Azure AI Vision resource | Computer Vision resource (any tier) for pre-trained object detection |
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

In the `object_detection_ntb` Notebook activity Base Parameters:

| Name | Type | Value |
|---|---|---|
| `image_path` | String | `@pipeline().parameters.image_path` |

In the `run_inference_ntb` Notebook activity Base Parameters (inside ForEachCrop):

| Name | Type | Value |
|---|---|---|
| `cropped_path` | String | `@item()` |

---

## Notebooks

### object_detection.ipynb

**Status:** ✅ Functional (standalone) | 🚧 Pipeline integration in progress

**Role:** Developer

**Purpose:** Detects pets in a real-world image, filters non-animal objects, deduplicates overlapping detections, crops each pet individually and saves results.

#### Key design decisions

**Why Azure AI Vision instead of Custom Vision Object Detection:**
Azure AI Vision provides a pre-trained model that detects dogs, cats and animals out of the box — no bounding box tagging or model training required.

**Why IoU deduplication:**
Azure AI Vision sometimes returns multiple overlapping bounding boxes for the same animal. IoU (Intersection over Union) removes duplicates by discarding boxes that overlap more than 30% with a higher-confidence box.

**Why breed-aware filtering:**
The model returns specific breed names like `"retriever"` or `"chihuahua"` instead of generic `"dog"`. The filter uses two layers:
- Object-level: checks if the object's own tags match `PET_TAGS`
- Image-level fallback: if the image contains a pet tag and the object is not a person, accept it

```python
PET_TAGS     = {"dog", "cat", "animal", "pet", "kitten", "puppy", "canine", "feline"}
PERSON_TAGS  = {"person", "woman", "man", "girl", "boy", "child"}

is_pet = bool(obj_tags & PET_TAGS) or (
    image_has_pet and not bool(obj_tags & PERSON_TAGS)
)
```

**Cropped image naming convention:**
```
{filename_base}_{timestamp}_{index}.jpg
# e.g. image2_20260501_094512_0.jpg
#      image2_20260501_094512_1.jpg
#      image2_20260501_094512_2.jpg
```

---

### run_inference.ipynb

**Status:** 🚧 Under development

**Role:** Developer

**Purpose:** Takes a single cropped pet image and evaluates it against all trained Custom Vision classification models dynamically, saving one result row per model.

#### Why training credentials are included

Training credentials are used **read-only** exclusively for `trainer.get_projects()` — to dynamically discover all available `pet-classifier-{size}` projects at runtime. This avoids hardcoding model sizes and ensures `run_inference` automatically picks up new models added by future `pl_ml_training` runs without any code changes.


---

## Security

All credentials stored in **Azure Key Vault** — no hardcoded secrets anywhere.

| Secret Name | Used by | Description |
|---|---|---|
| `ai-vision-api-key` | `object_detection` | Azure AI Vision API key |
| `ai-vision-endpoint` | `object_detection` | Azure AI Vision endpoint URL |
| `cv-prediction-api-key` | `run_inference` | Custom Vision Prediction API key |
| `cv-endpoint-p-key` | `run_inference` | Custom Vision Prediction endpoint URL |
| `cv-training-api-key` | `run_inference` | Custom Vision Training API key (read-only, for project discovery) |
| `cv-endpoint-t-key` | `run_inference` | Custom Vision Training endpoint URL |

> Fabric notebook identity must have **Key Vault Secrets User** role assigned on the Key Vault.

---

## How to Run

### Manual run (current)

1. Upload an image to `Files/development/raw/` in the Lakehouse
2. Open **`pl_implementation`** pipeline in Fabric
3. Set `image_path` parameter to the relative path of the uploaded image
4. Confirm `ForEachCrop` has **Sequential** mode enabled
5. Click **Run**
6. Check `object_detection_metrics` and `inference_metrics` tables for results

### Expected outputs per run

For an image containing **N pets** and **M trained models**:

| Output | Count |
|---|---|
| Cropped images saved to Lakehouse | N files |
| `object_detection_metrics` rows | N rows (one per detected pet) |
| `inference_metrics` rows | N × M rows (one per crop per model) |

**Example** — image with 1 cat + 2 dogs, 5 trained models:
- 3 cropped images saved
- 3 rows in `object_detection_metrics`
- 15 rows in `inference_metrics`

### No pet detected

If Azure AI Vision finds no animals in the image, the pipeline logs a single row to `object_detection_metrics` with `detected = false` and `object_name = "none"`. The ForEachCrop receives an empty list and skips inference entirely.

---

## Output Structure

```
OneLake (lkh_pets Lakehouse)
│
├── Files/
│   └── development/
│       ├── raw/                          ← input images
│       └── cropped/                      ← output crops per detected pet
│           ├── image2_20260501_094512_0.jpg   ← pet 0 (shepherd)
│           ├── image2_20260501_094512_1.jpg   ← pet 1 (cat)
│           └── image2_20260501_094512_2.jpg   ← pet 2 (chihuahua)
│
└── Tables/
    ├── object_detection_metrics          ← detection events
    └── inference_metrics                 ← classification results per model
```

---

## Delta Tables

### object_detection_metrics

Logs every object detection event — one row per detected object per image.

| Column | Type | Description |
|---|---|---|
| `image_name` | String | Cropped filename with timestamp e.g. `image2_20260501_094512_0.jpg` |
| `detected` | Boolean | Whether a pet was detected |
| `animal_count` | Integer | Total animals detected in the original image |
| `object_name` | String | Detected object label e.g. `"retriever"`, `"cat"`, `"none"` |
| `confidence` | Float | Detection confidence score (0–1) |
| `bbox_x` | Integer | Bounding box left position in pixels |
| `bbox_y` | Integer | Bounding box top position in pixels |
| `bbox_w` | Integer | Bounding box width in pixels |
| `bbox_h` | Integer | Bounding box height in pixels |
| `timestamp` | Timestamp | When the detection ran |

### inference_metrics

Logs classification results — one row per cropped image per model.

| Column | Type | Description |
|---|---|---|
| `image_name` | String | Cropped filename — links to `object_detection_metrics` |
| `model_size` | String | Model used e.g. `"128"`, `"224"`, `"original"` |
| `predicted` | String | Predicted pet label e.g. `"gato_phil"`, `"perro_serena"` |
| `confidence` | Float | Classification confidence score (0–1) |
| `timestamp` | Timestamp | When the inference ran |

> Both tables use `append` write mode — every pipeline run adds new rows without overwriting history, enabling trend analysis over time.

---

## Upcoming Development

| Feature | Description | Status |
|---|---|---|
| **Blob event trigger** | Automatically trigger `pl_implementation` when a new image is uploaded to Blob Storage | 🔜 Planned |
| **run_inference completion** | Finalize ForEachCrop → `run_inference_ntb` wiring and end-to-end testing | 🚧 In progress |
| **Dashboard** | Power BI report consuming `inference_metrics` and `object_detection_metrics` for visual comparison | 🔜 Planned |
| **original size model inference** | Include `pet-classifier-original` once `real_size_cv` training is complete | 🔜 Planned |
| **Multi-image batch processing** | Extend pipeline to process a folder of images in one run | 🔜 Future consideration |

---

*Built with ❤️ on Microsoft Fabric — OneLake, Spark, Data Pipelines, Azure AI Vision, and Azure Custom Vision.*
