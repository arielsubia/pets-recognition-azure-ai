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
│  Slicers: [provider ▼]  [model_size ▼]                      │
├───────────────────────────┬─────────────────────────────────┤
│                           │                                 │
│   Imagen Original         │   Imagen Cropped               │
│   (from shortcut/raw)     │   (from pipeline crop)         │
│                           │                                 │
├───────────────────────────┴─────────────────────────────────┤
│  KPI Cards:                                                 │
│  Total detecciones │ Avg confidence │ Detection rate        │
├─────────────────────────────────────────────────────────────┤
│  Tabla de resultados (cross-filter activo):                 │
│  original_image │ crop │ provider │ model_size │ predicted  │
│  │ confidence │ timestamp                                   │
├─────────────────────────────────────────────────────────────┤
│  Chart: confianza por model_size (grouped bar by provider)  │
└─────────────────────────────────────────────────────────────┘
```

### Interaction Flow

1. El usuario aplica slicers (provider, model_size) para filtrar globalmente
2. En la tabla de resultados, hace clic en una fila
3. Cross-filter actualiza:
   - Imagen original (muestra la foto de origen)
   - Imagen cropped (muestra el recorte que el pipeline generó)
   - KPI cards (métricas de esa selección)
   - Chart (se resalta la barra correspondiente)

### Visual Details

| Visual | Source Field | Notes |
|---|---|---|
| Imagen Original | `object_detection_metrics[original_image_url]` | Image visual, OneLake URL |
| Imagen Cropped | `inference_metrics[cropped_image_url]` | Image visual, OneLake URL |
| Slicer Provider | `inference_metrics[provider]` | Dropdown |
| Slicer Model Size | `inference_metrics[model_size]` | Dropdown |
| Card: Total detecciones | `[Total Detections]` measure | |
| Card: Avg confidence | `[Avg Inference Confidence]` measure | |
| Card: Detection rate | `[Detection Rate]` measure | |
| Results Table | Multiple columns (see below) | Cross-filter enabled |
| Chart | `model_size` axis, `confidence` value, `provider` legend | Grouped bar |

### Results Table Columns

| Column | Source |
|---|---|
| original_image | `object_detection_metrics[image_name]` |
| crop | `inference_metrics[image_name]` |
| provider | `inference_metrics[provider]` |
| model_size | `inference_metrics[model_size]` |
| predicted | `inference_metrics[predicted]` |
| confidence | `inference_metrics[confidence]` |
| timestamp | `inference_metrics[timestamp]` |

Conditional formatting on `confidence`: green (>0.8), yellow (0.5–0.8), red (<0.5).

---

## DAX Measures

```dax
Total Detections = COUNTROWS(object_detection_metrics)

Avg Detection Confidence = AVERAGE(object_detection_metrics[confidence])

Avg Inference Confidence = AVERAGE(inference_metrics[confidence])

Detection Rate =
DIVIDE(
    COUNTROWS(FILTER(object_detection_metrics, object_detection_metrics[detected] = TRUE())),
    COUNTROWS(object_detection_metrics)
)
```

---

## Image Visibility

Las URLs de OneLake requieren autenticación Entra ID. Este dashboard es **interno** (solo workspace members), por lo que los viewers ya están autenticados y las imágenes deberían renderizar en los Image visuals.

**Approach:** Usar URLs directas de OneLake en Image visuals. Los campos `original_image_url` y `cropped_image_url` contienen las URLs completas.

**Fallback:** Si Power BI no renderiza las imágenes (rendering server-side sin token del usuario), convertir los campos de imagen en hiperlinks que abran el archivo en el Lakehouse file browser.

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

## How to Create

1. Open `lkh_pets` → SQL analytics endpoint
2. Select tables: `object_detection_metrics`, `inference_metrics` → **New report**
3. In Model view: configure relationship `image_name` (Many:Many, bi-directional)
4. Add slicers: provider, model_size
5. Add Image visuals: original (from `original_image_url`), cropped (from `cropped_image_url`)
6. Add KPI cards with DAX measures
7. Add results table with cross-filter interaction
8. Add grouped bar chart (model_size × confidence × provider)
9. Apply conditional formatting on confidence column
10. Apply theme JSON
11. Save as `rep_pet_inference`

---

## Prerequisites

- At least 2–3 images processed through `pl_implementation` (data in both Delta tables)
- Both providers (Azure AI Vision, AWS Rekognition) should have run for comparison data
- `original_image_url` and `cropped_image_url` fields populated in the tables
