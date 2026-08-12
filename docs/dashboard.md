# Dashboard — Pet Inference Results

> **Platform:** Power BI embedded in Fabric | **Data source:** `lkh_pets` SQL analytics endpoint
> **Semantic model:** `sem_pet_inference`

---

## Data Sources

### object_detection_metrics

| Column | Type | Description |
|---|---|---|
| `image_name` | String | Cropped filename |
| `detected` | Boolean | Whether a pet was detected |
| `animal_count` | Integer | Total animals found |
| `object_name` | String | Detected label |
| `confidence` | Float | Detection confidence (0–1) |
| `bbox_x`, `bbox_y`, `bbox_w`, `bbox_h` | Integer | Bounding box (px) |
| `provider` | String | `azure_ai_vision` or `aws_rekognition` |
| `original_image_url` | String | OneLake URL of original image |
| `cropped_image_url` | String | OneLake URL of cropped image |
| `timestamp` | Timestamp | Execution time |

### inference_metrics

| Column | Type | Description |
|---|---|---|
| `image_name` | String | Cropped filename |
| `model_size` | String | Model resolution (128–512, original) |
| `predicted` | String | Predicted label (`gato_phil` / `perro_serena`) |
| `confidence` | Float | Classification confidence (0–1) |
| `provider` | String | `azure_ai_vision` or `aws_rekognition` |
| `cropped_image_url` | String | OneLake URL of cropped image |
| `timestamp` | Timestamp | Execution time |

### model_metrics

| Column | Type | Description |
|---|---|---|
| `image_size` | String | Training resolution |
| `precision` | Float | Model precision |
| `recall` | Float | Model recall |
| `ap` | Float | Average precision |
| `accuracy` | Float | Overall accuracy |
| `timestamp` | Timestamp | Training time |

---

## Data Model

- Relationship: `object_detection_metrics[image_name]` ↔ `inference_metrics[image_name]` (Many:Many, bi-directional)
- `model_metrics` is standalone (no relationship)

---

## Layout (Single Page)

```
┌─────────────────────────────────────────────────────────────┐
│  Slicers: [Provider ▼]  [Timestamp ▼]  [Model size ▼]      │
├───────────────────────┬─────────────────────────────────────┤
│                       │  Cropped Images                     │
│                       │  ┌──────────┐  ┌──────────┐        │
│   Original Image      │  │ Pet_1    │  │ Pet_2    │        │
│   (large)             │  └──────────┘  └──────────┘        │
│                       │  ┌──────────┐  ┌──────────┐        │
│                       │  │ Pet_3    │  │ Pet_4    │        │
│                       │  └──────────┘  └──────────┘        │
├───────────────────────┴─────────────────────────────────────┤
│  Results Table                                              │
│  image │ model_size │ predicted │ confidence │ provider     │
└─────────────────────────────────────────────────────────────┘
```

- **Original Image:** Image visual → `object_detection_metrics[original_image_url]`
- **Cropped Images:** Image Grid (AppSource) → `inference_metrics[cropped_image_url]`, title = `predicted`
- **Results Table:** `image_name`, `model_size`, `predicted`, `confidence`, `provider`
  - Conditional formatting on `confidence`: green (>0.8), yellow (0.5–0.8), red (<0.5)

---

## DAX Measures

```dax
Avg Detection Confidence = AVERAGE(object_detection_metrics[confidence])

Avg Inference Confidence = AVERAGE(inference_metrics[confidence])

Detection Rate =
DIVIDE(
    COUNTROWS(FILTER(object_detection_metrics, object_detection_metrics[detected] = TRUE())),
    COUNTROWS(object_detection_metrics)
)
```

---

## Theme

File: `src/dashboard/pet-recognition-theme.json`

| Color | Hex | Usage |
|---|---|---|
| Azure provider | `#0078D4` | Azure AI Vision data series |
| AWS provider | `#FF9900` | AWS Rekognition data series |
| Accent | `#d4768a` | Highlights |
| Background | `#f5f5f7` | Page canvas |
| Text | `#4a4a55` | Labels and titles |

Upload via View → Themes → Browse for themes.

---

## Image Visibility

OneLake URLs require Entra ID authentication — images are only visible to workspace members.

For external sharing (portfolio, web app), images must be stored in a publicly accessible location (Azure Blob Storage with SAS tokens or public container). This is handled by the web application layer, not by this dashboard.

---

## How to Create

1. Open `lkh_pets` → SQL analytics endpoint
2. Select the 3 tables → **New report**
3. Configure relationships in Model view
4. Build visuals per the layout above
5. Save — report is immediately live in the workspace
