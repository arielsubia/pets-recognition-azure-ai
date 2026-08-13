# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "db748fcd-0cc5-478c-a54c-f4938d542b0f",
# META       "default_lakehouse_name": "lkh_pets",
# META       "default_lakehouse_workspace_id": "a96eab2a-8002-45f2-92b4-d2bf05c2540b",
# META       "known_lakehouses": [
# META         {
# META           "id": "db748fcd-0cc5-478c-a54c-f4938d542b0f"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# # Object Detection — Azure AI Vision
# This notebook uses Azure AI Vision 4.0 to detect pets in real-world images.
# It is part of the dual-provider comparison pipeline (`pl_implementation`).
# **Provider:** `azure_ai_vision`
# **Known limitation:** Azure AI Vision object detection has a limited taxonomy
# and does not reliably return bounding boxes for animals in complex scenes.
# This notebook preserves the heuristic-based approach to document the limitation.

# CELL ********************

import requests, json, io, os
from PIL import Image
from datetime import datetime
from pyspark.sql import Row

PROVIDER = "azure_ai_vision"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Pipeline parameter

# PARAMETERS CELL ********************

image_path = "test-object-detection/elsie_mas_2_people.jpg"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Valid extensions

# CELL ********************

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
ext = os.path.splitext(image_path)[1].lower()
if ext not in VALID_EXTENSIONS:
    # Log, move to "rejected/", exit
    error_row = Row(
        image_name=os.path.basename(image_path),
        error=f"Invalid format: {ext}",
        provider=PROVIDER,
        timestamp=datetime.now()
    )
    spark.createDataFrame([error_row]).write.mode("append").saveAsTable("pipeline_errors")
    notebookutils.notebook.exit(json.dumps([]))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Credentials from Key Vault

# CELL ********************

vault_url = "https://cv-training-key.vault.azure.net/"
api_key = notebookutils.credentials.getSecret(vault_url, "det-obj-key")
endpoint = notebookutils.credentials.getSecret(vault_url, "det-obj-endpoint")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Copy image from Lakehouse to local temp

# CELL ********************

files_listing = notebookutils.fs.ls("Files")
lakehouse_root = files_listing[0].path.split("/Files/")[0]
abs_image_path = f"{lakehouse_root}/Files/{image_path}"
notebookutils.fs.cp(abs_image_path, "file:/tmp/input.jpg")

print(f"Image copied to /tmp/input.jpg from: {image_path}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Call Azure AI Vision 4.0 Object Detection API

# CELL ********************

detect_url = f"{endpoint}/computervision/imageanalysis:analyze"

params = {
    "features": "objects,tags,denseCaptions",
    "api-version": "2023-10-01"
}
headers = {
    "Ocp-Apim-Subscription-Key": api_key,
    "Content-Type": "application/octet-stream"
}

with open("/tmp/input.jpg", "rb") as img:
    response = requests.post(detect_url, params=params, headers=headers, data=img)

result = response.json()
print(f"API response status: {response.status_code}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Filter for animal/pet detections
# Azure AI Vision does not have a dedicated "Pet" category with reliable bounding boxes.
# We use a heuristic: combine image-level tags with object-level tags to identify pets.

# CELL ********************

PET_TAGS = {"dog", "cat", "animal", "pet", "kitten", "puppy", "canine", "feline",
            "retriever", "poodle", "chihuahua", "tabby", "siamese"}
EXCLUDE_TAGS = {"person", "woman", "man", "girl", "boy", "child", "human"}
THRESHOLD = 0.4

# Step 1 — Image-level tags
image_tags = {t["name"].lower() for t in result.get("tagsResult", {}).get("values", [])
              if t["confidence"] >= THRESHOLD}
image_has_pet = bool(image_tags & PET_TAGS)

print(f"Image-level tags: {sorted(image_tags)}")
print(f"Pet detected at image level: {image_has_pet}")

# Step 2 — Filter pet objects from bounding boxes
detections = []
for obj in result.get("objectsResult", {}).get("values", []):
    obj_tags = {t["name"].lower() for t in obj.get("tags", [])}
    obj_confidence = obj.get("tags", [{}])[0].get("confidence", 0)
    is_pet = bool(obj_tags & PET_TAGS) or (
        image_has_pet and not bool(obj_tags & EXCLUDE_TAGS)
    )
    if obj_confidence >= THRESHOLD and is_pet:
        detections.append(obj)

print(f"Pet objects before deduplication: {len(detections)}")

# Step 3 — IoU deduplication
def iou(box1, box2):
    x1 = max(box1["x"], box2["x"])
    y1 = max(box1["y"], box2["y"])
    x2 = min(box1["x"] + box1["w"], box2["x"] + box2["w"])
    y2 = min(box1["y"] + box1["h"], box2["y"] + box2["h"])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    union = box1["w"] * box1["h"] + box2["w"] * box2["h"] - intersection
    return intersection / union if union > 0 else 0

def deduplicate(dets, iou_threshold=0.3):
    sorted_dets = sorted(dets, key=lambda o: o["tags"][0]["confidence"], reverse=True)
    kept = []
    for det in sorted_dets:
        if not any(iou(det["boundingBox"], k["boundingBox"]) > iou_threshold for k in kept):
            kept.append(det)
    return kept

detections = deduplicate(detections)
print(f"Pet objects after deduplication: {len(detections)}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Crop, save, and build metrics

# CELL ********************

filename_base = os.path.splitext(os.path.basename(image_path))[0]
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
cropped_paths = []
rows = []

if not detections:
    print("No pet detected by Azure AI Vision")
    rows.append(Row(
        image_name=f"{filename_base}_{timestamp}_no_detection.jpg",
        detected=False,
        animal_count=0,
        object_name="none",
        confidence=0.0,
        bbox_x=0, bbox_y=0, bbox_w=0, bbox_h=0,
        provider=PROVIDER,
        original_image_url=f"https://onelake.dfs.fabric.microsoft.com/petsproject/lkh_pets.Lakehouse/Files/{image_path}",
        cropped_image_url="",
        timestamp=datetime.now()
    ))
else:
    for i, det in enumerate(detections):
        box = det["boundingBox"]
        tag = det["tags"][0]["name"]
        conf = det["tags"][0]["confidence"]
        cropped_name = f"{filename_base}_{timestamp}_azure_{i}.jpg"

        with Image.open("/tmp/input.jpg") as img:
            cropped = img.crop((box["x"], box["y"], box["x"] + box["w"], box["y"] + box["h"]))
            local_out = f"/tmp/cropped_azure_{i}.jpg"
            cropped.save(local_out)

        cropped_dest = f"{lakehouse_root}/Files/development/cropped/azure/{cropped_name}"
        notebookutils.fs.cp(f"file:{local_out}", cropped_dest)
        cropped_paths.append(cropped_dest)

        rows.append(Row(
            image_name=cropped_name,
            detected=True,
            animal_count=len(detections),
            object_name=tag,
            confidence=float(conf),
            bbox_x=int(box["x"]),
            bbox_y=int(box["y"]),
            bbox_w=int(box["w"]),
            bbox_h=int(box["h"]),
            provider=PROVIDER,
            original_image_url=f"https://onelake.dfs.fabric.microsoft.com/petsproject/lkh_pets.Lakehouse/Files/{image_path}",
            cropped_image_url=f"https://onelake.dfs.fabric.microsoft.com/petsproject/lkh_pets.Lakehouse/Files/development/cropped/azure/{cropped_name}",
            timestamp=datetime.now()
        ))

        print(f"Crop {i+1}: '{tag}' ({conf:.2%}) -> {cropped_name}")

print(f"\nTotal crops saved: {len(cropped_paths)}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Save to object_detection_metrics table

# CELL ********************

detection_df = spark.createDataFrame(rows)
detection_df.write.mode("append").option("mergeSchema", "true").saveAsTable("object_detection_metrics")

print(f"Detection metrics saved: {len(rows)} row(s) | provider: {PROVIDER}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Exit with cropped paths for pipeline ForEach

# CELL ********************

notebookutils.notebook.exit(json.dumps(cropped_paths))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
