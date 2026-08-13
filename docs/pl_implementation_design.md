# pl_implementation — Dual Object Detection Pipeline Design

> **Status:** Implementation in progress
> **Last updated:** August 2026

---

## Overview

The `pl_implementation` pipeline processes real-world images through **two object detection providers** in parallel, producing independent crops that are then classified by the same Custom Vision models. This enables a direct comparison of detection quality between Azure AI Vision and AWS Rekognition.

---

## Architecture

```
                        ┌──────────────────────┐
                        │   Pipeline Input     │
                        │   image_path (String) │
                        └──────────┬───────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                              ▼
    ┌───────────────────────────┐  ┌───────────────────────────────┐
    │  object_detection_azure   │  │  object_detection_aws         │
    │  (Notebook Activity)      │  │  (Notebook Activity)          │
    │                           │  │                               │
    │  Azure AI Vision 4.0      │  │  AWS Rekognition DetectLabels │
    │  features: objects,tags   │  │  filter: Pet (Cat, Dog)       │
    │                           │  │                               │
    │  Output: JSON list of     │  │  Output: JSON list of         │
    │  cropped abfss:// paths   │  │  cropped abfss:// paths       │
    │  provider: azure_ai_vision│  │  provider: aws_rekognition    │
    └────────────┬──────────────┘  └──────────────┬────────────────┘
                 │                                  │
                 ▼                                  ▼
    ┌───────────────────────────┐  ┌───────────────────────────────┐
    │  ForEachCrop_Azure        │  │  ForEachCrop_AWS              │
    │  (Sequential)             │  │  (Sequential)                 │
    │                           │  │                               │
    │  @json(activity(          │  │  @json(activity(              │
    │    'object_detection_azure│  │    'object_detection_aws'     │
    │    ').output.result       │  │    ).output.result            │
    │    .exitValue)            │  │    .exitValue)                │
    │                           │  │                               │
    │  ┌─────────────────────┐  │  │  ┌─────────────────────────┐  │
    │  │  run_inference      │  │  │  │  run_inference          │  │
    │  │  cropped_path=@item()│  │  │  │  cropped_path=@item()  │  │
    │  │  provider=           │  │  │  │  provider=             │  │
    │  │   "azure_ai_vision" │  │  │  │   "aws_rekognition"    │  │
    │  └─────────────────────┘  │  │  └─────────────────────────┘  │
    └───────────────────────────┘  └───────────────────────────────┘
                 │                                  │
                 └──────────────┬───────────────────┘
                                ▼
              ┌──────────────────────────────────────┐
              │  Delta Tables (lkh_pets Lakehouse)   │
              │  ├── object_detection_metrics        │
              │  │     (col: provider)               │
              │  └── inference_metrics               │
              │        (col: provider)               │
              └──────────────────────────────────────┘
                                │
                                ▼
              ┌──────────────────────────────────────┐
              │  Power BI Dashboard                  │
              │  Comparative analysis by provider    │
              └──────────────────────────────────────┘
```

---

## Pipeline Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `image_path` | String | Relative path inside Lakehouse `Files/` | `development/raw/photo_001.jpg` |

---

## Pipeline Activities (in order)

### 1. object_detection_azure (Notebook Activity)

| Setting | Value |
|---------|-------|
| Notebook | `object_detection` (existing, refactored) |
| Base parameters | `image_path` = `@pipeline().parameters.image_path` |
| Runs | First (no dependency) |

### 2. object_detection_aws (Notebook Activity)

| Setting | Value |
|---------|-------|
| Notebook | `object_detection_aws` (new) |
| Base parameters | `image_path` = `@pipeline().parameters.image_path` |
| Runs | In parallel with Azure (no dependency between them) |

### 3. ForEachCrop_Azure (ForEach Activity)

| Setting | Value |
|---------|-------|
| Items | `@json(activity('object_detection_azure').output.result.exitValue)` |
| Sequential | Yes |
| Depends on | `object_detection_azure` succeeded |

**Inner activity: run_inference (Notebook)**

| Parameter | Value |
|-----------|-------|
| `cropped_path` | `@item()` |
| `provider` | `azure_ai_vision` |

### 4. ForEachCrop_AWS (ForEach Activity)

| Setting | Value |
|---------|-------|
| Items | `@json(activity('object_detection_aws').output.result.exitValue)` |
| Sequential | Yes |
| Depends on | `object_detection_aws` succeeded |

**Inner activity: run_inference (Notebook)**

| Parameter | Value |
|-----------|-------|
| `cropped_path` | `@item()` |
| `provider` | `aws_rekognition` |

---

## Delta Table Schemas (Updated)

### object_detection_metrics

| Column | Type | Description |
|--------|------|-------------|
| `image_name` | String | Cropped filename |
| `detected` | Boolean | Whether a pet was detected |
| `animal_count` | Integer | Total animals detected |
| `object_name` | String | Detected label (e.g. "cat", "Dog") |
| `confidence` | Float | Detection confidence (0-1) |
| `bbox_x` | Integer | Bounding box left |
| `bbox_y` | Integer | Bounding box top |
| `bbox_w` | Integer | Bounding box width |
| `bbox_h` | Integer | Bounding box height |
| `provider` | String | **NEW** — `"azure_ai_vision"` or `"aws_rekognition"` |
| `original_image_url` | String | OneLake URL of original image |
| `cropped_image_url` | String | OneLake URL of cropped image |
| `timestamp` | Timestamp | When detection ran |

### inference_metrics

| Column | Type | Description |
|--------|------|-------------|
| `image_name` | String | Cropped filename |
| `model_size` | String | Model resolution (128, 224, etc.) |
| `predicted` | String | Predicted pet label |
| `confidence` | Float | Classification confidence |
| `provider` | String | **NEW** — `"azure_ai_vision"` or `"aws_rekognition"` |
| `cropped_image_url` | String | OneLake URL of cropped image |
| `timestamp` | Timestamp | When inference ran |

### pipeline_errors

| Column | Type | Description |
|--------|------|-------------|
| `image_name` | String | Filename that failed validation |
| `error` | String | Error message (e.g. "Invalid format: .pdf") |
| `provider` | String | Which notebook rejected it |
| `timestamp` | Timestamp | When the rejection occurred |

> This table is created dynamically on first write. Both detection notebooks log here when input validation fails (invalid file format). The notebook then exits with an empty array `[]` so the pipeline succeeds without processing.

---

## Input Validation

Both `object_detection` and `object_detection_aws` validate the input file before calling any API:

- **Valid extensions:** `.jpg`, `.jpeg`, `.png`, `.webp`, `.heic`
- **On failure:** logs to `pipeline_errors` table and exits with `[]` (empty array)
- **Result:** pipeline succeeds, ForEach loops iterate over nothing, no crops produced

---

## Notebook Changes Summary

### object_detection.py (rename to keep as Azure path)

- Add `provider = "azure_ai_vision"` column to all metrics rows
- No logic changes — keep existing Azure AI Vision detection as-is
- This preserves evidence of Azure's limitation

### object_detection_aws.py (NEW)

- Uses `boto3` to call `rekognition.detect_labels()`
- Filters for labels with Parent = "Pet" or Name in {"Cat", "Dog"}
- Takes bounding box `Instances` for each detection
- Crops each instance and saves to `Files/development/cropped/rekognition/`
- Writes to same `object_detection_metrics` table with `provider = "aws_rekognition"`
- Returns JSON list of cropped paths via `notebookutils.notebook.exit()`

### run_inference.py (refactored)

- New parameter: `provider` (String) — injected by pipeline
- Adds `provider` column to all `inference_metrics` rows
- No other logic changes

---

## OneLake Storage Layout (Updated)

```
Files/development/
├── raw/                        ← User uploads
├── cropped/
│   ├── azure/                  ← Crops from Azure AI Vision
│   │   └── filename_timestamp_0.jpg
│   └── rekognition/            ← Crops from AWS Rekognition
│       └── filename_timestamp_0.jpg
```

---

## Key Vault Secrets (New)

| Secret Name | Used By | Description |
|-------------|---------|-------------|
| `aws-access-key-id` | object_detection_aws | AWS IAM access key |
| `aws-secret-access-key` | object_detection_aws | AWS IAM secret key |
| `aws-region` | object_detection_aws | AWS region (e.g. us-east-1) |

> These should be for an IAM user with **only** `rekognition:DetectLabels` permission.

---

## Dashboard Comparative Metrics

The Power BI dashboard will show:

1. **Detection count by provider** — How many animals each provider found per image
2. **Detection accuracy** — Side-by-side crops showing what each provider detected
3. **Inference confidence by provider** — Do Rekognition crops produce better classification?
4. **Resolution impact** — For each provider, which model size performs best?
5. **Original image + all crops** — Visual evidence of detection quality

---

## Configuration Steps in Fabric Portal

The user must manually configure in the Fabric pipeline canvas:

1. Add `object_detection_aws` as a new Notebook Activity (parallel to existing Azure one)
2. Rename existing notebook activity to `object_detection_azure`
3. Add `ForEachCrop_AWS` activity with items expression
4. Inside `ForEachCrop_AWS`, add `run_inference` notebook with both parameters
5. Update `ForEachCrop_Azure` inner notebook to include `provider` parameter
6. Set both ForEach activities to have no dependency between each other (parallel execution)

---

## Sequence Diagram

```
Pipeline Start
     │
     ├─── [parallel] ──────────────────────────────────────────┐
     │                                                          │
     ▼                                                          ▼
object_detection_azure                            object_detection_aws
     │                                                          │
     │ exitValue: ["abfss://...crop1"]                         │ exitValue: ["abfss://...crop1", "abfss://...crop2"]
     │                                                          │
     ▼                                                          ▼
ForEachCrop_Azure                                  ForEachCrop_AWS
     │                                                          │
     ├─ run_inference(crop1, "azure_ai_vision")                ├─ run_inference(crop1, "aws_rekognition")
     │                                                          ├─ run_inference(crop2, "aws_rekognition")
     │                                                          │
     ▼                                                          ▼
Pipeline End ◄──────────────────────────────────────────────────┘
```

This clearly demonstrates that Rekognition finds more pets (2 crops vs 1 from Azure), resulting in more inference rows and better coverage.
