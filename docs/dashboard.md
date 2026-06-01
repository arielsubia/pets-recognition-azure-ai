# Dashboard — Pet Inference Results
> **Role:** Data Analyst | **Platform:** Microsoft Fabric | **Visualization:** Power BI | **Data source:** OneLake Lakehouse (lkh_pets)

> ⚠️ **Work in Progress** — Dashboard design defined. Implementation in progress.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Data Sources](#data-sources)
5. [Dashboard Layout](#dashboard-layout)
6. [Step-by-Step Build Guide](#step-by-step-build-guide)
7. [How to Publish](#how-to-publish)
8. [How to Run](#how-to-run)
9. [Upcoming Development](#upcoming-development)

---

## Overview

The dashboard is the final layer of the project — it gives the **Data Analyst** a visual interface to explore how well each trained classification model performed on real-world images processed by the development pipeline.

It consumes two Delta tables from the `lkh_pets` Lakehouse:

- **`object_detection_metrics`** — what was detected in each image and where
- **`inference_metrics`** — how each model classified each cropped pet image

The dashboard is built in **Power BI** and published to the Fabric Workspace, making it accessible to all team members without requiring direct Lakehouse access.

> **Role boundary:** The Data Analyst only needs read access to the Lakehouse SQL endpoint. No pipeline or notebook knowledge is required.

---

## Architecture

```
lkh_pets Lakehouse
│
├── Tables/
│   ├── object_detection_metrics   ← detection events
│   └── inference_metrics          ← classification results
│
└── Files/
    └── development/
        ├── raw/      ← original uploaded images
        └── cropped/  ← cropped pet images
              │
              │  OneLake Files API or direct URL
              ▼
┌─────────────────────────────────────────┐
│         Power BI Report                 │
│                                         │
│  Page 1 — Inference Explorer            │
│  ┌──────────────┐  ┌─────────────────┐  │
│  │ Original     │  │ Cropped Images  │  │
│  │ Image        │  │ Pet_1  Pet_2    │  │
│  │              │  │ Pet_3  Pet_4    │  │
│  └──────────────┘  └─────────────────┘  │
│  ┌─────────────────────────────────┐    │
│  │ Results Table                   │    │
│  │ image │ model │ predicted │ conf│    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

---

## Prerequisites

| Requirement | Details |
|---|---|
| Microsoft Fabric Workspace | With `lkh_pets` Lakehouse containing populated Delta tables |
| `pl_implementation` executed | At least one full pipeline run to populate `inference_metrics` |
| Power BI Desktop | Latest version installed (for local development) |
| Fabric Workspace access | Contributor role to publish reports |
| OneLake access | Read access to `lkh_pets` SQL analytics endpoint |

---

## Data Sources

### inference_metrics

Main table for the Results section.

| Column | Type | Used for |
|---|---|---|
| `image_name` | String | Linking crops to results, image display |
| `model_size` | String | Model filter slicer |
| `predicted` | String | Predicted label display |
| `confidence` | Float | Confidence bar / conditional formatting |
| `timestamp` | Timestamp | Run filter slicer |

### object_detection_metrics

Used to display original image context and detection confidence.

| Column | Type | Used for |
|---|---|---|
| `image_name` | String | Linking to inference_metrics |
| `detected` | Boolean | No-detection filter |
| `object_name` | String | Detected label display |
| `confidence` | Float | Detection confidence display |
| `timestamp` | Timestamp | Run filter |

---

## Dashboard Layout

The dashboard follows the design preview with three sections on a single page:

```
┌─────────────────────────────────────────────────────────────┐
│  Slicers: [Run timestamp ▼]  [Model size ▼]  [Pet label ▼] │
├───────────────────┬─────────────────────────────────────────┤
│                   │  Cropped Images                         │
│  Original Image   │  ┌──────────┐  ┌──────────┐            │
│                   │  │ Pet_1    │  │ Pet_2    │            │
│  (image display)  │  └──────────┘  └──────────┘            │
│                   │  ┌──────────┐  ┌──────────┐            │
│                   │  │ Pet_3    │  │ Pet_4    │            │
│                   │  └──────────┘  └──────────┘            │
├───────────────────┴─────────────────────────────────────────┤
│  Results Table                                              │
│  image_name │ model_size │ predicted │ confidence │ timestamp│
│  ...        │ ...        │ ...       │ ...        │ ...     │
└─────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Build Guide

### Step 1 — Connect Power BI to the Lakehouse SQL endpoint

1. Open **Power BI Desktop**
2. Click **Get Data → More → Microsoft Fabric → Lakehouse**
3. Sign in with your Microsoft account
4. Select your Fabric Workspace and `lkh_pets` Lakehouse
5. In the Navigator, select both tables:
   - `inference_metrics`
   - `object_detection_metrics`
6. Click **Load**

> Alternatively, use the **SQL analytics endpoint**:
> - In the Lakehouse, click **SQL analytics endpoint** (top right)
> - Copy the server connection string
> - In Power BI: Get Data → SQL Server → paste the connection string

---

### Step 2 — Create the data model relationship

In Power BI Desktop → **Model view**:

1. Draw a relationship between:
   - `inference_metrics[image_name]` → `object_detection_metrics[image_name]`
2. Set cardinality to **Many to Many** (one crop can have multiple model results)
3. Set cross-filter direction to **Both**

---

### Step 3 — Add image URL columns

Power BI can display images from URLs. You need to build the OneLake file URL for each image.

In Power BI Desktop → **Transform Data (Power Query)**:

Add a custom column to `inference_metrics`:

```
= "https://onelake.dfs.fabric.microsoft.com/<workspace-id>/<lakehouse-id>/Files/development/cropped/" & [image_name]
```

Replace `<workspace-id>` and `<lakehouse-id>` with your actual IDs (found in the Lakehouse URL in Fabric).

Then:
1. Select the new column
2. Go to **Column tools** → **Data category** → set to **Image URL**

Repeat for the original image — add a column to `object_detection_metrics`:

```
= "https://onelake.dfs.fabric.microsoft.com/<workspace-id>/<lakehouse-id>/Files/development/raw/" & [original_image_name]
```

> ⚠️ **Note:** OneLake direct file URLs require the report viewer to have OneLake read access. If access is restricted, consider storing image URLs in a separate column when saving to the Delta table in the pipeline.

---

### Step 4 — Build the slicers

Add three slicers at the top of the report page:

| Slicer | Field | Type |
|---|---|---|
| Run timestamp | `inference_metrics[timestamp]` | Dropdown or date range |
| Model size | `inference_metrics[model_size]` | List (128, 224, 256, 384, 512) |
| Predicted label | `inference_metrics[predicted]` | List |

---

### Step 5 — Add the Original Image visual

1. Add an **Image** visual (or **Table** visual with image URL column)
2. Set the field to `object_detection_metrics[original_image_url]`
3. Resize to fit the left panel of the layout

> If the Image visual is not available, install the **Image Grid** custom visual from AppSource.

---

### Step 6 — Add the Cropped Images gallery

1. From **AppSource**, add the **Image Grid** custom visual
2. Set the image field to `inference_metrics[cropped_image_url]`
3. Set the title field to `inference_metrics[predicted]`
4. This will display all cropped images as a grid, filtered by the slicers

---

### Step 7 — Add the Results Table

1. Add a **Table** visual
2. Add these columns:
   - `inference_metrics[image_name]`
   - `inference_metrics[model_size]`
   - `inference_metrics[predicted]`
   - `inference_metrics[confidence]`
   - `inference_metrics[timestamp]`
3. Apply **conditional formatting** on `confidence`:
   - Go to the column → Format → Conditional formatting → Background color
   - Set green for high confidence (>0.8), yellow for medium (0.5–0.8), red for low (<0.5)

---

### Step 8 — Add a confidence bar chart (optional but recommended)

Add a **Clustered bar chart**:
- X axis: `inference_metrics[confidence]` (average)
- Y axis: `inference_metrics[model_size]`
- Legend: `inference_metrics[predicted]`

This gives a quick visual comparison of which model size performs best per label.

---

## How to Publish

### Publish from Power BI Desktop

1. Click **File → Publish → Publish to Power BI**
2. Select your Fabric Workspace
3. The report will appear in the workspace alongside the Lakehouse and pipelines

### Publish directly in Fabric

1. Go to your Fabric Workspace
2. Click **+ New → Report**
3. Select `lkh_pets` as the data source
4. Build the report inline using the Fabric web editor

---

## How to Run

The dashboard is **read-only** — the Data Analyst does not need to run any pipeline. The workflow is:

1. Developer runs `pl_implementation` with a new image
2. `inference_metrics` and `object_detection_metrics` tables are updated automatically
3. Data Analyst **refreshes the report** in Power BI to see new results:
   - In Power BI Desktop: click **Refresh**
   - In Fabric workspace: the report uses DirectQuery by default — data is always current

---

## Upcoming Development

| Feature | Description | Status |
|---|---|---|
| **Image Grid visual** | Display cropped images as a gallery filtered by slicer | 🔜 In progress |
| **Confidence comparison chart** | Bar chart comparing average confidence per model size | 🔜 Planned |
| **No-detection view** | Separate section showing images where no pet was detected | 🔜 Planned |
| **Model metrics page** | Second page consuming `model_metrics` for training performance comparison | 🔜 Planned |
| **Scheduled refresh** | Auto-refresh report when new pipeline runs complete | 🔜 Future consideration |

---

## GitHub Repository

The Power BI report file (`.pbix`) should be committed to the repository under:

```
pet-recognition-azure-ai/
└── src/
    └── dashboard/
        └── pet_inference_dashboard.pbix
```

### Commit message suggestion

```
feat(dashboard): add Power BI report for pet inference results
```

> ⚠️ **Note:** `.pbix` files are binary and do not diff well in Git. Consider adding a note in the commit description summarizing what visuals were added or changed.

---

*Built with ❤️ on Microsoft Fabric — Power BI, OneLake, and Azure Custom Vision.*
