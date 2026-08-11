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

# # Object Detection — AWS Rekognition
# This notebook uses AWS Rekognition `DetectLabels` to detect pets in real-world images.
# It is part of the dual-provider comparison pipeline (`pl_implementation`).
#
# **Provider:** `aws_rekognition`
#
# **Advantage:** Rekognition explicitly supports bounding boxes for "Pet" category labels
# (Cat, Dog) and returns individual instances with coordinates, making it reliable
# for pet detection in complex scenes with people and backgrounds.

# METADATA ********************

# META {
# META   "language": "markdown",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import subprocess
subprocess.run(["pip", "install", "boto3", "--quiet"], check=True)

import boto3, json, os
from PIL import Image
from datetime import datetime
from pyspark.sql import Row

PROVIDER = "aws_rekognition"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Credentials from Key Vault

# METADATA ********************

# META {
# META   "language": "markdown",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

vault_url = "https://cv-training-key.vault.azure.net/"

aws_access_key = notebookutils.credentials.getSecret(vault_url, "aws-access-key-id")
aws_secret_key = notebookutils.credentials.getSecret(vault_url, "aws-secret-access-key")
aws_region = notebookutils.credentials.getSecret(vault_url, "aws-region")

rekognition = boto3.client(
    "rekognition",
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key,
    region_name=aws_region
)

print(f"AWS Rekognition client initialized (region: {aws_region})")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Pipeline parameter

# METADATA ********************

# META {
# META   "language": "markdown",
# META   "language_group": "synapse_pyspark"
# META }

# PARAMETERS CELL ********************

image_path = "test-object-detection/elsie_mas_2_people.jpg"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Copy image from Lakehouse to local temp

# METADATA ********************

# META {
# META   "language": "markdown",
# META   "language_group": "synapse_pyspark"
# META }

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

# #### Call AWS Rekognition DetectLabels
# We send the image bytes directly to Rekognition and filter for labels
# whose ancestors include "Pet" (this covers Cat, Dog, Kitten, Puppy, etc.)

# METADATA ********************

# META {
# META   "language": "markdown",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

with open("/tmp/input.jpg", "rb") as img:
    image_bytes = img.read()

response = rekognition.detect_labels(
    Image={"Bytes": image_bytes},
    MinConfidence=40.0,
    Features=["GENERAL_LABELS"]
)

print(f"API response: {len(response['Labels'])} labels detected")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Filter for pet detections with bounding boxes
# Rekognition returns a hierarchical taxonomy. We filter labels that have
# "Pet" or "Animal" as a parent AND have bounding box Instances.

# METADATA ********************

# META {
# META   "language": "markdown",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

PET_LABELS = {"Cat", "Dog", "Kitten", "Puppy", "Pet"}
PET_PARENTS = {"Pet", "Cat", "Dog"}

detections = []

for label in response["Labels"]:
    label_name = label["Name"]
    parent_names = {p["Name"] for p in label.get("Parents", [])}

    # Include if the label itself is a pet type OR has a pet parent
    is_pet = label_name in PET_LABELS or bool(parent_names & PET_PARENTS)

    if is_pet and label.get("Instances"):
        for instance in label["Instances"]:
            if instance.get("BoundingBox"):
                detections.append({
                    "label": label_name,
                    "confidence": instance["Confidence"] / 100.0,
                    "bbox": instance["BoundingBox"]
                })

print(f"Pet instances with bounding boxes: {len(detections)}")
for d in detections:
    print(f"  - {d['label']} ({d['confidence']:.2%})")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Crop, save, and build metrics

# METADATA ********************

# META {
# META   "language": "markdown",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

filename_base = os.path.splitext(os.path.basename(image_path))[0]
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
cropped_paths = []
rows = []

if not detections:
    print("No pet detected by AWS Rekognition")
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
    with Image.open("/tmp/input.jpg") as img:
        img_width, img_height = img.size

    for i, det in enumerate(detections):
        bbox = det["bbox"]
        # Rekognition returns relative coordinates (0-1), convert to pixels
        x = int(bbox["Left"] * img_width)
        y = int(bbox["Top"] * img_height)
        w = int(bbox["Width"] * img_width)
        h = int(bbox["Height"] * img_height)

        cropped_name = f"{filename_base}_{timestamp}_rekognition_{i}.jpg"

        with Image.open("/tmp/input.jpg") as img:
            cropped = img.crop((x, y, x + w, y + h))
            local_out = f"/tmp/cropped_rekognition_{i}.jpg"
            cropped.save(local_out)

        cropped_dest = f"{lakehouse_root}/Files/development/cropped/rekognition/{cropped_name}"
        notebookutils.fs.cp(f"file:{local_out}", cropped_dest)
        cropped_paths.append(cropped_dest)

        rows.append(Row(
            image_name=cropped_name,
            detected=True,
            animal_count=len(detections),
            object_name=det["label"],
            confidence=float(det["confidence"]),
            bbox_x=x,
            bbox_y=y,
            bbox_w=w,
            bbox_h=h,
            provider=PROVIDER,
            original_image_url=f"https://onelake.dfs.fabric.microsoft.com/petsproject/lkh_pets.Lakehouse/Files/{image_path}",
            cropped_image_url=f"https://onelake.dfs.fabric.microsoft.com/petsproject/lkh_pets.Lakehouse/Files/development/cropped/rekognition/{cropped_name}",
            timestamp=datetime.now()
        ))

        print(f"Crop {i+1}: '{det['label']}' ({det['confidence']:.2%}) -> {cropped_name}")

print(f"\nTotal crops saved: {len(cropped_paths)}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Save to object_detection_metrics table

# METADATA ********************

# META {
# META   "language": "markdown",
# META   "language_group": "synapse_pyspark"
# META }

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

# METADATA ********************

# META {
# META   "language": "markdown",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

notebookutils.notebook.exit(json.dumps(cropped_paths))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
