# Pet Recognition using Azure AI & Microsoft Fabric

## Overview

This project demonstrates an end-to-end Computer Vision pipeline to recognize individual pets (cats and dogs) using Azure services.

It showcases how to design, build, and operationalize an AI workflow leveraging Microsoft Fabric, Azure Blob Storage, Azure AI Vision, and Azure Custom Vision — covering the full journey from raw image ingestion to real-time pet detection and model evaluation.

---

## 🚧 Current Status

| Phase | Description | Status |
|---|---|---|
| Data Engineering | Image ingestion, resizing and dataset generation | ✅ Completed |
| Model Training | Custom Vision classification per image size | 🚧 In progress |
| Development Pipeline | Object detection + inference on real-world images | 🚧 In progress |
| Dashboard | Power BI metrics visualization | 🔜 Planned |

---

## Architecture

The solution is organized into two workspaces with clearly separated roles:

### Training Workspace
Responsible for data preparation and model training.

![Training Architecture](docs/images/ds_arquitecture.jpg)

### Development Workspace *(Preview)*
Responsible for real-world image inference using trained models.

> ⚠️ **Preview** — The development pipeline architecture is currently under active development.

![Development Architecture](docs/images/develpment_arquitecture.jpg)

The solution follows a layered medallion architecture:

```
Azure Blob Storage (Raw Images)
        │
        │  OneLake Shortcut
        ▼
Microsoft Fabric Workspace
        │
        ├── ETL Images Pipeline
        │       ├── ForEachResizing  → image_exploring.ipynb   → Silver layer
        │       └── ForEachGold      → dataset_builder.ipynb   → Gold layer
        │
        ├── pl_ml_training Pipeline
        │       ├── training_custom_vision.ipynb  → pet-classifier-{size}
        │       └── real_size_cv.ipynb            → pet-classifier-original (WIP)
        │
        └── Implementation_ppl Pipeline (Preview)
                ├── object_detection.ipynb   → Azure AI Vision (object detection)
                └── run_inference.ipynb      → All classification models
                        └── inference_metrics (Delta Table) → Dashboard
```

---

## Key Features

- Scalable image preprocessing pipeline built on **Microsoft Fabric**
- Multi-resolution dataset generation (128 × 128 to 512 × 512 px)
- Automated stratified train/test split with **zero data leakage** across sizes
- Automated labeling based on folder structure — no manual tagging required
- Real-world image preprocessing using **Azure AI Vision** object detection
- Pet cropping from complex scenes (people, backgrounds) before classification
- Multi-model inference — same image evaluated against all trained models simultaneously
- Full credential management via **Azure Key Vault** — no hardcoded secrets
- Clear separation of roles: Data Engineer, Data Scientist, Developer, Data Analyst

---

## Technologies Used

| Technology | Purpose |
|---|---|
| Microsoft Fabric (Lakehouse, Notebooks, Pipelines) | Core platform — storage, compute, orchestration |
| Azure Blob Storage | Raw and development image storage |
| Azure AI Vision (Computer Vision) | Pre-trained object detection — pet cropping |
| Azure Custom Vision | Pet classification model training and inference |
| Azure Key Vault | Credentials management |
| PySpark | Distributed data processing and Delta table management |
| Python (Pillow) | Image resizing and cropping |
| Power BI | Metrics dashboard (planned) |
| GitHub | Version control |

---

## Project Structure

```
pet-recognition-azure-ai/
│
├── src/
│   ├── data_engineering/
│   │   ├── image_exploring.ipynb       ← Bronze → Silver (resize)
│   │   └── dataset_builder.ipynb       ← Silver → Gold (train/test split)
│   ├── ml_training/
│   │   ├── training_custom_vision.ipynb ← Train per image size
│   │   └── real_size_cv.ipynb           ← Train on original size (WIP)
│   └── development/                     ← Preview
│       ├── object_detection.ipynb       ← Azure AI Vision crop
│       └── run_inference.ipynb          ← Classification inference
│
├── docs/
│   ├── images/
│   │   ├── ds_arquitecture.jpg
│   │   └── develpment_arquitecture.jpg
│   ├── de_ingestion.md
│   ├── training_cv.md
│   ├── pipelines.md
│   └── roles_and_workflow.md
│
├── experiments/
└── README.md
```

---

## Data Engineering Pipeline

The pipeline performs the following steps:

1. Reads raw images from Azure Blob Storage via **OneLake Shortcut**
2. Iterates through multiple image sizes using a **ForEach** activity
3. Resizes and standardizes images — outputs as `.jpg`
4. Applies a **stratified train/test split** (80/20) per label based on original filename — guaranteeing zero overlap across all sizes
5. Stores outputs in the Lakehouse:

```
Files/images/raw/          ← Bronze (Shortcut — read only)
Files/images/resized/      ← Silver (resized per size per label)
Files/gold/dataset_{size}/ ← Gold (train/test split per size)
```

More details in [`docs/de_ingestion.md`](docs/de_ingestion.md)

---

## Model Training *(In Progress)*

The training pipeline trains one **Azure Custom Vision** classification model per image resolution and evaluates each against a held-out test set.

**Research question:**
> Does image resolution affect model performance? Is it worth training on original-size images?

| Model | Input | Status |
|---|---|---|
| `pet-classifier-128` | 128×128 resized images | ✅ Functional |
| `pet-classifier-224` | 224×224 resized images | ✅ Functional |
| `pet-classifier-256` | 256×256 resized images | ✅ Functional |
| `pet-classifier-384` | 384×384 resized images | ✅ Functional |
| `pet-classifier-512` | 512×512 resized images | ✅ Functional |
| `pet-classifier-original` | Original resolution | 🚧 In progress |

Results are stored in the `model_metrics` Delta table for dashboard consumption.

More details in [`docs/training_cv.md`](docs/training_cv.md)

---

## Development Pipeline *(Preview)*

The development pipeline processes **real-world images** uploaded by users:

1. User uploads an image to Azure Blob Storage
2. **`Implementation_ppl`** pipeline is triggered automatically
3. **`object_detection.ipynb`** calls **Azure AI Vision** to detect pets and crop the bounding box
4. If a pet is detected, the cropped image is evaluated against **all trained models** via **`run_inference.ipynb`**
5. If no pet is detected, the event is logged as `no_animal`
6. All results are saved to the `inference_metrics` Delta table
7. The **Data Analyst** builds a Power BI dashboard from `inference_metrics`

```
Files/development/
    ├── raw/        ← User uploads
    └── cropped/    ← Cropped pet images (output of object detection)

Tables/
    ├── model_metrics        ← Training evaluation results
    ├── inference_metrics    ← Real-world inference results
    └── object_detection_metrics ← Detection events log
```

---

## Image Resolutions

Multiple datasets are generated to evaluate the impact of resolution on model performance:

| Resolution | Use case |
|---|---|
| 128×128 | Lightweight, fast inference |
| 224×224 | Standard for many CNN architectures |
| 256×256 | Moderate detail |
| 384×384 | High detail |
| 512×512 | Maximum detail |
| Original | Baseline — no standardization |

---

## Roles

This project simulates a real-world multi-role workflow:

| Role | Responsibilities |
|---|---|
| **Data Engineer** | Builds ingestion, resizing and dataset generation pipelines |
| **Data Scientist** | Creates Azure AI Vision resource, trains and evaluates Custom Vision models |
| **Developer** | Builds `Implementation_ppl`, object detection and inference notebooks |
| **Data Analyst** | Connects Power BI to Lakehouse, builds inference and metrics dashboard |

More details in [`docs/roles_and_workflow.md`](docs/roles_and_workflow.md)

---

## How to Run

### Training workflow
1. Upload raw images to Azure Blob Storage organized by label folder
2. Create a shortcut in Fabric Lakehouse pointing to the Blob container
3. Execute the **ETL Images** pipeline — confirm `size_array` is Array type
4. Validate Gold layer datasets in the Lakehouse
5. Execute the **`pl_ml_training`** pipeline — confirm Sequential mode is ON
6. Check `model_metrics` table for results

### Development workflow *(Preview)*
1. Upload a real-world image to the designated Blob Storage folder
2. `Implementation_ppl` triggers automatically
3. Check `inference_metrics` and `object_detection_metrics` tables for results
4. View Dashboard for visual summary

---

## Future Improvements

- Original size model completion (`real_size_cv`)
- Power BI dashboard for inference and model comparison
- CI/CD integration for automated pipeline deployment
- Automated retraining when new images are uploaded
- Confusion matrix and error analysis per model
- Real-time prediction API endpoint
- Expanded pet categories beyond cats and dogs

---

## Author

This project is part of a personal portfolio focused on Data Engineering and AI Engineering using Azure and Microsoft Fabric.
