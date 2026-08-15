# Dashboard — Inference & Model Metrics

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
| `timestamp` | Timestamp | Execution time |

### inference_metrics

| Column | Type | Description |
|---|---|---|
| `image_name` | String | Cropped filename |
| `model_size` | String | Model resolution (128–512, original) |
| `predicted` | String | Predicted label |
| `confidence` | Float | Classification confidence (0–1) |
| `provider` | String | `azure_ai_vision` or `aws_rekognition` |
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
┌─────────────────────────────────────────────────────────────────────┐
│  Slicers: [Provider ▼]  [Model size ▼]  [Timestamp ▼]              │
├────────────────┬────────────────┬────────────────┬──────────────────┤
│  KPI Card      │  KPI Card      │  KPI Card      │  KPI Card        │
│  Avg Detection │  Avg Inference │  Detection     │  Total Images    │
│  Confidence    │  Confidence    │  Rate          │  Processed       │
├────────────────┴────────────────┴────────────────┴──────────────────┤
│                                                                     │
│  Provider Comparison (Clustered Bar Chart)                          │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  X-axis: Provider                                          │     │
│  │  Y-axis: Avg Detection Confidence, Avg Inference Confidence│     │
│  │  Color: Azure (#0078D4) / AWS (#FF9900)                    │     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                     │
├─────────────────────────────────┬───────────────────────────────────┤
│                                 │                                   │
│  Model Performance (Table)      │  Temporal Trend (Line Chart)      │
│  ┌───────────────────────────┐  │  ┌───────────────────────────┐   │
│  │ image_size │ precision    │  │  │  X: timestamp             │   │
│  │            │ recall       │  │  │  Y: confidence / accuracy │   │
│  │            │ accuracy     │  │  │  Legend: provider          │   │
│  └───────────────────────────┘  │  └───────────────────────────┘   │
│                                 │                                   │
└─────────────────────────────────┴───────────────────────────────────┘
```

### Visual details

| Visual | Source Table | Fields |
|---|---|---|
| **Avg Detection Confidence** | `object_detection_metrics` | KPI card with `[Avg Detection Confidence]` measure |
| **Avg Inference Confidence** | `inference_metrics` | KPI card with `[Avg Inference Confidence]` measure |
| **Detection Rate** | `object_detection_metrics` | KPI card with `[Detection Rate]` measure |
| **Total Images Processed** | `object_detection_metrics` | KPI card with `[Total Images Processed]` measure |
| **Provider Comparison** | Both detection + inference | Clustered bar chart grouped by `provider` |
| **Model Performance** | `model_metrics` | Table: `image_size`, `precision`, `recall`, `accuracy` |
| **Temporal Trend** | `inference_metrics` | Line chart: `timestamp` on X, `confidence` on Y, `provider` as legend |
| **Slicers** | All tables | Provider, Model size, Timestamp |

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

Total Images Processed =
DISTINCTCOUNT(object_detection_metrics[image_name])
```

---

## Theme

File: `src/dashboard/pet-recognition-theme.json`

| Color | Hex | Usage |
|---|---|---|
| Azure provider | `#0078D4` | Azure AI Vision data series |
| AWS provider | `#FF9900` | AWS Rekognition data series |
| Accent | `#d4768a` | Highlights, KPI labels |
| Background | `#f5f5f7` | Page canvas |
| Text | `#4a4a55` | Labels and titles |

Upload via View → Themes → Browse for themes.

---

## How to Create

1. Open `lkh_pets` → SQL analytics endpoint
2. Select the 3 tables → **New report**
3. Configure relationships in Model view
4. Build visuals per the layout above
5. Apply theme JSON
6. Save — report is immediately live in the workspace
