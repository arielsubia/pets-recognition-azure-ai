# Dashboard — Pet Recognition Comparative Report

> **Role:** Data Analyst | **Platform:** Microsoft Fabric | **Visualization:** Power BI
> **Data source:** OneLake Lakehouse (`lkh_pets`) — SQL Analytics Endpoint
> **Semantic Model:** `sem_pet_inference`

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Data Sources](#data-sources)
5. [DAX Measures](#dax-measures)
6. [Report Pages](#report-pages)
7. [Step-by-Step Build Guide](#step-by-step-build-guide)
8. [How to Publish](#how-to-publish)
9. [How to Run](#how-to-run)

---

## Overview

This Power BI report is the analytics layer of the pet recognition project. It provides a **comparative view** of two object detection providers — **Azure AI Vision** and **AWS Rekognition** — showing how each provider's crops perform when classified by the same Custom Vision models.

The report consumes three Delta tables from `lkh_pets`:

| Table | Content |
|-------|---------|
| `object_detection_metrics` | Detection events per provider (bounding boxes, confidence) |
| `inference_metrics` | Classification results per crop per model size |
| `model_metrics` | Training performance per model resolution |

---

## Architecture

```
lkh_pets Lakehouse (SQL Analytics Endpoint)
│
├── Tables/
│   ├── object_detection_metrics  ← provider: azure_ai_vision | aws_rekognition
│   ├── inference_metrics         ← provider: azure_ai_vision | aws_rekognition
│   └── model_metrics             ← training accuracy per image_size
│
└── Files/development/
    ├── raw/                      ← original uploaded images
    └── cropped/
        ├── azure/                ← crops from Azure AI Vision
        └── rekognition/          ← crops from AWS Rekognition
```

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Power BI Report (4 pages)                         │
│                                                                     │
│  Page 1 — Provider Comparison (landing page)                        │
│  Page 2 — Detection Analysis                                        │
│  Page 3 — Inference Explorer                                        │
│  Page 4 — Model Training Performance                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

| Requirement | Details |
|---|---|
| Microsoft Fabric Workspace | `petsproject` with `lkh_pets` Lakehouse |
| Pipeline executed | `pl_implementation` run at least once with both providers |
| Power BI Desktop | Latest version (June 2024+) |
| Workspace access | Contributor role to publish |
| Custom visuals | **Image Grid** from AppSource |

---

## Data Sources

### object_detection_metrics

| Column | Type | Description |
|---|---|---|
| `image_name` | String | Cropped filename (or `*_no_detection.jpg`) |
| `detected` | Boolean | Whether a pet was detected |
| `animal_count` | Integer | Total animals found in the image |
| `object_name` | String | Detected label (e.g. "cat", "Dog") |
| `confidence` | Float | Detection confidence (0–1) |
| `bbox_x` | Integer | Bounding box left (px) |
| `bbox_y` | Integer | Bounding box top (px) |
| `bbox_w` | Integer | Bounding box width (px) |
| `bbox_h` | Integer | Bounding box height (px) |
| `provider` | String | `"azure_ai_vision"` or `"aws_rekognition"` |
| `original_image_url` | String | OneLake URL of original image |
| `cropped_image_url` | String | OneLake URL of cropped image |
| `timestamp` | Timestamp | When detection ran |

### inference_metrics

| Column | Type | Description |
|---|---|---|
| `image_name` | String | Cropped filename |
| `model_size` | String | Model resolution (128, 224, 256, 384, 512, original) |
| `predicted` | String | Predicted pet label (`gato_phil` or `perro_serena`) |
| `confidence` | Float | Classification confidence (0–1) |
| `provider` | String | `"azure_ai_vision"` or `"aws_rekognition"` |
| `cropped_image_url` | String | OneLake URL of cropped image |
| `timestamp` | Timestamp | When inference ran |

### model_metrics

| Column | Type | Description |
|---|---|---|
| `image_size` | String | Training resolution (128, 224, 256, 384, 512) |
| `precision` | Float | Model precision |
| `recall` | Float | Model recall |
| `ap` | Float | Average precision |
| `accuracy` | Float | Overall accuracy |
| `timestamp` | Timestamp | When training completed |

---

## Data Model (Relationships)

```
┌───────────────────────────┐
│   object_detection_metrics │
│   (image_name, provider)   │
└─────────────┬─────────────┘
              │ Many:Many
              │ (image_name)
              ▼
┌───────────────────────────┐
│     inference_metrics      │
│   (image_name, provider)   │
└───────────────────────────┘

┌───────────────────────────┐
│      model_metrics         │  (standalone — no relationship)
└───────────────────────────┘
```

- Relationship: `object_detection_metrics[image_name]` ↔ `inference_metrics[image_name]`
- Cardinality: **Many to Many**
- Cross-filter: **Both directions**
- Filter by `provider` is applied independently via slicers (not through the relationship)

---

## DAX Measures

Create these measures in the semantic model (`sem_pet_inference`) for reuse across pages:

```dax
// Detection rate per provider
Detection Rate =
DIVIDE(
    COUNTROWS(FILTER(object_detection_metrics, object_detection_metrics[detected] = TRUE())),
    COUNTROWS(object_detection_metrics)
)

// Average detection confidence
Avg Detection Confidence =
AVERAGE(object_detection_metrics[confidence])

// Average inference confidence
Avg Inference Confidence =
AVERAGE(inference_metrics[confidence])

// Total detections count
Total Detections =
COUNTROWS(FILTER(object_detection_metrics, object_detection_metrics[detected] = TRUE()))

// No-detection count
No Detections =
COUNTROWS(FILTER(object_detection_metrics, object_detection_metrics[detected] = FALSE()))

// Average animals per image
Avg Animals Per Image =
AVERAGE(object_detection_metrics[animal_count])

// Top model (highest avg confidence)
Best Model Size =
VAR _table =
    ADDCOLUMNS(
        VALUES(inference_metrics[model_size]),
        "AvgConf", CALCULATE(AVERAGE(inference_metrics[confidence]))
    )
RETURN
    MAXX(TOPN(1, _table, [AvgConf], DESC), inference_metrics[model_size])
```

---

## Report Pages

### Page 1 — Provider Comparison (Landing Page)

**Purpose:** At-a-glance side-by-side comparison of Azure AI Vision vs AWS Rekognition.

```
┌─────────────────────────────────────────────────────────────────────┐
│  🐾 Pet Recognition — Provider Comparison                           │
├─────────────────────────────────────────────────────────────────────┤
│  Slicers: [Timestamp range ▼]  [Pet label ▼]                       │
├────────────────────────────┬────────────────────────────────────────┤
│  KPI Cards (full width)    │                                        │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐                       │
│  │ Total  │ │ Azure  │ │ AWS    │ │ Best   │                       │
│  │ Images │ │ Det.%  │ │ Det.%  │ │ Model  │                       │
│  └────────┘ └────────┘ └────────┘ └────────┘                       │
├────────────────────────────┬────────────────────────────────────────┤
│  Detection Confidence      │  Inference Confidence                  │
│  (Grouped bar chart)       │  (Grouped bar chart)                   │
│                            │                                        │
│  X: provider               │  X: model_size                         │
│  Y: avg confidence         │  Y: avg confidence                     │
│  Legend: —                  │  Legend: provider                       │
├────────────────────────────┴────────────────────────────────────────┤
│  Animals Detected per Image (Clustered column chart)                │
│  X: image (original_image_url base name)                            │
│  Y: animal_count                                                    │
│  Legend: provider                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

**Visuals:**

| # | Visual Type | Fields | Notes |
|---|---|---|---|
| 1 | Multi-row Card | Total images processed, Azure detection rate, AWS detection rate, Best model size | Use DAX measures |
| 2 | Clustered bar chart | Y: `Avg Detection Confidence`, X: `provider` | Color: Azure=#0078D4, AWS=#FF9900 |
| 3 | Clustered bar chart | Y: `Avg Inference Confidence`, X: `model_size`, Legend: `provider` | Shows which model benefits more from each provider |
| 4 | Clustered column chart | Y: `animal_count` (sum), X: original image name, Legend: `provider` | Reveals detection quantity differences |

**Key insight this page answers:** Which provider finds more animals and with higher confidence?

---

### Page 2 — Detection Analysis

**Purpose:** Deep-dive into object detection quality — what was found, where, and confidence levels.

```
┌─────────────────────────────────────────────────────────────────────┐
│  🔍 Detection Analysis                                              │
├─────────────────────────────────────────────────────────────────────┤
│  Slicers: [Provider ▼]  [Timestamp ▼]  [Detected: Yes/No]          │
├───────────────────────────────┬─────────────────────────────────────┤
│                               │  Crops Gallery                      │
│  Original Image               │  ┌──────┐ ┌──────┐ ┌──────┐       │
│  (single image from URL)      │  │crop_1│ │crop_2│ │crop_3│       │
│                               │  └──────┘ └──────┘ └──────┘       │
│                               │  (Image Grid visual)               │
├───────────────────────────────┴─────────────────────────────────────┤
│  Detection Details Table                                            │
│  image_name │ object_name │ confidence │ bbox │ provider │ timestamp│
├─────────────────────────────────────────────────────────────────────┤
│  Confidence Distribution (Histogram)                                │
│  X: confidence bins (0.4-0.5, 0.5-0.6, ..., 0.9-1.0)              │
│  Y: count of detections                                            │
│  Legend: provider                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

**Visuals:**

| # | Visual Type | Fields | Notes |
|---|---|---|---|
| 1 | Image | `original_image_url` | Filtered by table selection |
| 2 | Image Grid (AppSource) | Image: `cropped_image_url`, Title: `object_name` | Shows all crops for selected image |
| 3 | Table | `image_name`, `object_name`, `confidence`, `bbox_w`×`bbox_h`, `provider`, `timestamp` | Sortable, conditional formatting on confidence |
| 4 | Histogram/Column chart | Bins of `confidence`, count, legend by `provider` | Compare confidence distributions |

**Key insight this page answers:** How reliable are the bounding boxes from each provider?

---

### Page 3 — Inference Explorer

**Purpose:** Classification results — how each model size performs on crops from each provider.

```
┌─────────────────────────────────────────────────────────────────────┐
│  🏷️ Inference Explorer                                              │
├─────────────────────────────────────────────────────────────────────┤
│  Slicers: [Provider ▼] [Model size ▼] [Predicted ▼] [Timestamp ▼]  │
├─────────────────────────────────┬───────────────────────────────────┤
│  Confidence by Model Size       │  Confidence by Provider           │
│  (Line chart)                   │  (Donut chart per label)          │
│                                 │                                   │
│  X: model_size                  │  Values: avg confidence           │
│  Y: avg confidence              │  Legend: provider                  │
│  Legend: provider                │                                   │
├─────────────────────────────────┴───────────────────────────────────┤
│  Cropped Image  │  Results Table                                    │
│  (selected)     │  image │ model │ predicted │ confidence │ provider│
│                 │  ...   │ ...   │ ...       │ ...        │ ...     │
├─────────────────┴───────────────────────────────────────────────────┤
│  Heatmap: Model Size × Provider (avg confidence as color intensity) │
│  Rows: model_size (128, 224, 256, 384, 512)                        │
│  Columns: provider (azure_ai_vision, aws_rekognition)               │
│  Values: avg confidence (green=high, red=low)                       │
└─────────────────────────────────────────────────────────────────────┘
```

**Visuals:**

| # | Visual Type | Fields | Notes |
|---|---|---|---|
| 1 | Line chart | X: `model_size`, Y: avg `confidence`, Legend: `provider` | Key comparison visual |
| 2 | Donut chart | Values: avg `confidence`, Legend: `provider` | Quick split view |
| 3 | Image | `cropped_image_url` | Updates on table row selection |
| 4 | Table | `image_name`, `model_size`, `predicted`, `confidence`, `provider` | Conditional formatting on confidence |
| 5 | Matrix/Heatmap | Rows: `model_size`, Cols: `provider`, Values: avg `confidence` | Background color scale |

**Key insight this page answers:** Do AWS Rekognition crops produce better classification results than Azure AI Vision crops?

---

### Page 4 — Model Training Performance

**Purpose:** Training metrics for the Custom Vision models — independent of provider (trained on gold dataset).

```
┌─────────────────────────────────────────────────────────────────────┐
│  📊 Model Training Performance                                      │
├─────────────────────────────────────────────────────────────────────┤
│  Slicer: [Image size ▼]                                             │
├─────────────────────────────────┬───────────────────────────────────┤
│  KPI Cards                      │  Radar Chart                      │
│  ┌────────┐ ┌────────┐         │  (precision, recall, AP, accuracy) │
│  │Accuracy│ │  AP    │         │  per model size                   │
│  └────────┘ └────────┘         │                                   │
│  ┌────────┐ ┌────────┐         │                                   │
│  │Precision│ │Recall │         │                                   │
│  └────────┘ └────────┘         │                                   │
├─────────────────────────────────┴───────────────────────────────────┤
│  Metrics Comparison (Grouped bar chart)                             │
│  X: image_size                                                      │
│  Y: value (precision, recall, AP, accuracy)                         │
│  Legend: metric name                                                 │
├─────────────────────────────────────────────────────────────────────┤
│  Training History Table                                             │
│  image_size │ precision │ recall │ ap │ accuracy │ timestamp        │
└─────────────────────────────────────────────────────────────────────┘
```

**Visuals:**

| # | Visual Type | Fields | Notes |
|---|---|---|---|
| 1 | Card | `accuracy` (latest per size) | Filtered by slicer |
| 2 | Card | `ap` (average precision) | Filtered by slicer |
| 3 | Card | `precision` | Filtered by slicer |
| 4 | Card | `recall` | Filtered by slicer |
| 5 | Radar chart (custom visual) | Axes: precision, recall, AP, accuracy; Series: model sizes | Overall model comparison |
| 6 | Clustered bar chart | X: `image_size`, Y: metric values, Legend: metric name | Requires unpivot in Power Query |
| 7 | Table | All `model_metrics` columns | Reference detail |

**Key insight this page answers:** Which model resolution gives the best balance of precision and recall?

---

## Step-by-Step Build Guide

### Step 1 — Connect to the Lakehouse SQL endpoint

1. Open **Power BI Desktop**
2. **Get Data → Microsoft Fabric → Lakehouses** (or SQL Server)
3. Sign in with `dev_ariel@arielsubiahotmail.onmicrosoft.com`
4. Select workspace `petsproject` → `lkh_pets`
5. In Navigator, select all three tables:
   - `object_detection_metrics`
   - `inference_metrics`
   - `model_metrics`
6. Click **Load** (or Transform Data if you want to preview)

---

### Step 2 — Configure the data model

In **Model view**:

1. Create relationship:
   - `object_detection_metrics[image_name]` ↔ `inference_metrics[image_name]`
   - Cardinality: Many to Many
   - Cross-filter: Both
2. No relationship for `model_metrics` (standalone table)
3. Set `provider` columns to **Data category: None** (used as slicer, not geo)
4. Set URL columns to **Data category: Image URL**:
   - `object_detection_metrics[original_image_url]`
   - `object_detection_metrics[cropped_image_url]`
   - `inference_metrics[cropped_image_url]`

---

### Step 3 — Create DAX measures

In **Modeling → New measure**, create all measures from the [DAX Measures](#dax-measures) section above.

---

### Step 4 — Build Page 1 (Provider Comparison)

1. Rename Page 1 to "Provider Comparison"
2. Add a text box with title: "Pet Recognition — Provider Comparison"
3. Add slicers: timestamp (date range), predicted label (dropdown)
4. Add Multi-row Card with KPI measures
5. Add two clustered bar charts as described in the layout
6. Add the animals-per-image column chart
7. Apply theme colors: Azure=#0078D4, AWS=#FF9900

---

### Step 5 — Build Page 2 (Detection Analysis)

1. Add new page, rename to "Detection Analysis"
2. Add slicers: provider (buttons), timestamp (range), detected (Yes/No)
3. Add Image visual for `original_image_url` (left panel)
4. Install **Image Grid** from AppSource → set image to `cropped_image_url`, title to `object_name`
5. Add Table visual with detection columns + conditional formatting
6. Add histogram for confidence distribution by provider

---

### Step 6 — Build Page 3 (Inference Explorer)

1. Add new page, rename to "Inference Explorer"
2. Add slicers: provider, model_size (list), predicted (list), timestamp
3. Add Line chart: X=model_size, Y=avg confidence, Legend=provider
4. Add Donut chart: values=avg confidence, legend=provider
5. Add Image visual for selected crop
6. Add Table visual with all inference columns
7. Add Matrix: rows=model_size, columns=provider, values=avg confidence
   - Apply background color conditional formatting (green→red scale)

---

### Step 7 — Build Page 4 (Model Training)

1. Add new page, rename to "Model Training"
2. Add slicer: image_size (list)
3. Add 4 Card visuals for accuracy, AP, precision, recall
4. In Power Query, unpivot `model_metrics` to get (image_size, metric_name, value) format:
   - Select `image_size` and `timestamp` → **Unpivot Other Columns**
5. Add clustered bar chart with unpivoted data
6. Add Table visual with raw model_metrics for reference
7. (Optional) Install Radar Chart custom visual for multi-axis comparison

---

### Step 8 — Apply report-level formatting

1. **Theme:** Create a custom theme JSON or use a neutral theme
   - Provider colors: Azure `#0078D4`, AWS `#FF9900`
   - Background: `#f5f5f7`
   - Text: `#4a4a55`
2. **Page size:** 16:9 (1280×720)
3. **Navigation:** Add page navigator buttons at the top of each page
4. **Tooltips:** Enable report-level tooltips showing crop image on hover

---

## Report Theme (JSON)

Save as `pet-recognition-theme.json` and apply via **View → Themes → Browse for themes**:

```json
{
  "name": "Pet Recognition",
  "dataColors": ["#0078D4", "#FF9900", "#d4768a", "#5c5c6b", "#7a7a88", "#e0899b"],
  "background": "#f5f5f7",
  "foreground": "#4a4a55",
  "tableAccent": "#d4768a",
  "visualStyles": {
    "*": {
      "*": {
        "background": [{"color": {"solid": {"color": "#ffffff"}}}]
      }
    }
  }
}
```

Color mapping:
- Index 0 (`#0078D4`): Azure AI Vision
- Index 1 (`#FF9900`): AWS Rekognition
- Index 2 (`#d4768a`): Accent (Phil Dev pink)
- Index 3–5: Neutral supporting colors

---

## How to Publish

### From Power BI Desktop

1. **File → Publish → Publish to Power BI**
2. Select workspace: `petsproject`
3. The report appears alongside the Lakehouse and pipelines
4. The semantic model `sem_pet_inference` is created automatically on first publish

### From Fabric Portal (web)

1. Navigate to `petsproject` workspace
2. Click **+ New → Report → Pick a published semantic model**
3. Select `sem_pet_inference`
4. Build using the web editor (limited compared to Desktop)

---

## How to Run

The dashboard is **read-only** — no pipeline knowledge required.

**Data flow:**
1. Developer runs `pl_implementation` with a new image path
2. Both detection notebooks (Azure + AWS) execute in parallel
3. `object_detection_metrics` and `inference_metrics` tables receive new rows
4. Data Analyst **refreshes** the report to see updated results

**Refresh options:**
- **DirectQuery** (recommended): Data is always current, no manual refresh needed
- **Import mode**: Click Refresh in Desktop, or schedule refresh in Fabric
- **Scheduled refresh**: Configure in Fabric → Semantic model settings → Schedule refresh

---

## File Organization

```
pets-recognition-azure-ai/
├── docs/
│   └── dashboard.md                    ← this file
└── src/
    └── dashboard/
        ├── pet_inference_dashboard.pbix   ← Power BI report file
        └── pet-recognition-theme.json     ← custom theme
```

> `.pbix` files are binary — commit message should describe what changed visually.

---

## Commit Strategy

```
feat(dashboard): add comparative Power BI report with 4 pages
```

Only commit after the report is validated with real data from `pl_implementation`.
