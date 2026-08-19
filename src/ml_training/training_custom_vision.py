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

# #### Parameters from pipeline

# PARAMETERS CELL ********************

IMAGE_SIZE = "128"   # default — overridden by pipeline @item()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

print(f"🔍 IMAGE_SIZE received: '{IMAGE_SIZE}'")
print(f"🔍 Type: {type(IMAGE_SIZE)}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Getting absolute path

# CELL ********************

files_listing= notebookutils.fs.ls("Files")


sample_path = files_listing[0].path
lakehouse_root =sample_path.split("/Files/")[0]

ABS_TRAIN_PATH = f"{lakehouse_root}/Files/gold/dataset_{IMAGE_SIZE}/train"
ABS_TEST_PATH = f"{lakehouse_root}/Files/gold/dataset_{IMAGE_SIZE}/test"

PROJECT_NAME = f"pet-classifier-{IMAGE_SIZE}"

# Validate paths exist before proceeding
print(f"ABS_TRAIN_PATH: {ABS_TRAIN_PATH}")
print(f"ABS_TEST_PATH:  {ABS_TEST_PATH}")

notebookutils.fs.ls(ABS_TRAIN_PATH)  # ← will fail fast here if path is wrong
print("✅ Paths validated successfully")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************


# MARKDOWN ********************

# #### Credentials

# CELL ********************

url_key = 'https://cv-training-key.vault.azure.net/'
training_key = 'cv-training-api-key'
endpoint_key = 'cv-endpoint-t-key'

key = mssparkutils.credentials.getSecret(url_key,training_key)
endpoint = mssparkutils.credentials.getSecret(url_key,endpoint_key)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Install the required packages

# CELL ********************

import subprocess

packages = [
    "azure-cognitiveservices-vision-customvision",
    "msrest"
]

for package in packages:
    subprocess.run(
        ["pip", "install", package, "--quiet"],
        capture_output=False
    )

# Force Python to recognize newly installed packages
import importlib
import site
importlib.invalidate_caches()
importlib.reload(site)

print("✅ Packages installed successfully")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Custom vision client 

# CELL ********************

from azure.cognitiveservices.vision.customvision.training import CustomVisionTrainingClient
from msrest.authentication import ApiKeyCredentials

credentials = ApiKeyCredentials(in_headers={"Training-key": key})
trainer = CustomVisionTrainingClient(endpoint, credentials)

print("✅ Custom Vision client ready")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Create or reuse project

# CELL ********************

project = None

for p in trainer.get_projects():
    if p.name == PROJECT_NAME:
        project = p
        break

if not project:
    project = trainer.create_project(PROJECT_NAME)

print("Using project:", project.name)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Clean previous dataset

# CELL ********************

images = trainer.get_images(project.id)

if images:
    trainer.delete_images(project.id, [img.id for img in images])

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Create tags

# CELL ********************

tags = {}

labels = [f.name for f in notebookutils.fs.ls(ABS_TRAIN_PATH) if f.isDir]

existing_tags = {t.name: t for t in trainer.get_tags(project.id)}

for label in labels:
    tags[label] = existing_tags.get(label) or trainer.create_tag(project.id, label)

print(f"✅ Tags ready: {list(tags.keys())}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Upload images (batch)

# CELL ********************

from azure.cognitiveservices.vision.customvision.training.models import ImageFileCreateEntry, ImageFileCreateBatch

def upload_images(base_path):

    label_infos=[f for f in notebookutils.fs.ls(base_path) if f.isDir]

    for label_info in label_infos:
        label = label_info.name
        folder_path = label_info.path
        files = notebookutils.fs.ls(folder_path)
        batch = []

        for file_info in files:
            filename=file_info.name
            full_path=file_info.path

            local_tmp= f"/tmp/{label}_{filename}"

            # Use full abfss path for source
            notebookutils.fs.cp(full_path, f"file:{local_tmp}")

            with open(local_tmp, "rb") as img:
                batch.append(
                    ImageFileCreateEntry(
                        name=filename,
                        contents=img.read(),
                        tag_ids=[tags[label].id]
                    )
                )

            if len(batch) == 64:
                trainer.create_images_from_files(project.id, ImageFileCreateBatch(images=batch))
                batch = []

        if batch:
            trainer.create_images_from_files(project.id, ImageFileCreateBatch(images=batch))
            print(f"✅ Uploaded {label}: {len(files)} images")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Run upload

# CELL ********************

upload_images(ABS_TRAIN_PATH)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Train model

# CELL ********************

import time

iteration=trainer.train_project(project.id)

MAX_WAIT_MINUTES = 30
MAX_ITERATIONS   = (MAX_WAIT_MINUTES * 60) // 10  # check every 10 seconds
attempts         = 0

print(f"⏳ Training started for size {IMAGE_SIZE}...")

while iteration.status != "Completed":
    if attempts >= MAX_ITERATIONS:
        raise TimeoutError(
            f"❌ Training timed out after {MAX_WAIT_MINUTES} minutes. "
            f"Last status: {iteration.status}"
        )

    time.sleep(10)  # poll every 10s instead of 5s (less API pressure)
    iteration = trainer.get_iteration(project.id, iteration.id)
    attempts += 1

    print(f"   Status: {iteration.status} ({attempts * 10}s elapsed)")

print(f"✅ Training completed for size {IMAGE_SIZE}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

publish_name = f"publish_{IMAGE_SIZE}"
prediction_resource_id = mssparkutils.credentials.getSecret(url_key, "cv-prediction-resource-id")

# Unpublish existing iteration if the name is already taken
try:
    existing_iterations = trainer.get_iterations(project.id)
    for it in existing_iterations:
        if it.publish_name == publish_name:
            trainer.unpublish_iteration(project.id, it.id)
            print(f"🗑️ Unpublished existing iteration: {publish_name}")
            break
except Exception as e:
    print(f"⚠️ No existing published iteration to remove: {e}")

# Now publish the new one
trainer.publish_iteration(
    project.id,
    iteration.id,
    publish_name,
    prediction_resource_id
)
print(f"✅ Iteration published as: {publish_name}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Metrics

# CELL ********************

performance = trainer.get_iteration_performance(project.id, iteration.id)

precision = performance.precision
recall = performance.recall
ap = performance.average_precision

print("Precision:", precision)
print("Recall:", recall)
print("AP:", ap)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Aditional metrics ()

# CELL ********************

from azure.cognitiveservices.vision.customvision.prediction import CustomVisionPredictionClient

prediction_key = 'cv-prediction-api-key'
endpoint_p_key='cv-endpoint-p-key'

key_p = mssparkutils.credentials.getSecret(url_key,prediction_key)
endpoint_p = mssparkutils.credentials.getSecret(url_key,endpoint_p_key)

predictor = CustomVisionPredictionClient(
    endpoint_p,
    ApiKeyCredentials(in_headers={"Prediction-key": key_p})
)

correct = 0
total = 0

for label_info in notebookutils.fs.ls(ABS_TEST_PATH):
    if not label_info.isDir:
        continue
    
    label=label_info.name
    folder_path = label_info.path

    for file_info in notebookutils.fs.ls(folder_path):
        filename = file_info.name
        full_path = file_info.path

        local_tmp = f"/tmp/test_{label}_{filename}"
        notebookutils.fs.cp(full_path, f"file:{local_tmp}")

        with open(local_tmp, "rb") as img:
            results = predictor.classify_image(project.id, publish_name, img.read())
            
        if not results.predictions:
            print(f"⚠️ No predictions for {filename}, skipping")
            continue

        predicted = results.predictions[0].tag_name

        if predicted == label:
            correct += 1

        total += 1

accuracy = correct / total if total > 0 else 0
print(f"✅ Accuracy on test set: {accuracy:.2%} ({correct}/{total})")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Save results

# CELL ********************

from datetime import datetime
from pyspark.sql.functions import col

new_result = spark.createDataFrame(
    [(IMAGE_SIZE, float(precision), float(recall), float(ap), float(accuracy), datetime.now())],
    ["image_size", "precision", "recall", "ap", "accuracy", "timestamp"]
)

# Remove previous entries for this image_size before appending
try:
    existing = spark.read.table("model_metrics")
    cleaned  = existing.filter(col("image_size") != IMAGE_SIZE)
    cleaned.union(new_result).write.mode("overwrite").saveAsTable("model_metrics")
    print(f"✅ Metrics updated for size {IMAGE_SIZE}")
except:
    # Table doesn't exist yet
    print(f"⚠️ Creating table fresh: {e}")
    new_result.write.mode("overwrite").saveAsTable("model_metrics")

print(f"✅ Metrics saved for size {IMAGE_SIZE}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
