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

# # Run Inference — Custom Vision Classification
# This notebook receives a single cropped pet image and classifies it against
# all available trained Custom Vision models. It dynamically discovers models
# at runtime so new training sizes are automatically picked up.
#
# **Parameters:**
# - `cropped_path` — full abfss:// path or relative path to the cropped image
# - `provider` — which detection provider produced this crop (`azure_ai_vision` or `aws_rekognition`)

# METADATA ********************

# META {
# META   "language": "markdown",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

import subprocess
subprocess.run(["pip", "install", "azure-cognitiveservices-vision-customvision", "msrest", "--quiet"], check=True)

import importlib, site
importlib.invalidate_caches()
importlib.reload(site)

from azure.cognitiveservices.vision.customvision.prediction import CustomVisionPredictionClient
from azure.cognitiveservices.vision.customvision.training import CustomVisionTrainingClient
from msrest.authentication import ApiKeyCredentials
from datetime import datetime
from pyspark.sql import Row
import os

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Parameters cell

# METADATA ********************

# META {
# META   "language": "markdown",
# META   "language_group": "synapse_pyspark"
# META }

# PARAMETERS CELL ********************

cropped_path = "Files/development/cropped/rekognition/elsie_mas_2_people_20260602_181602_0.jpg"
provider = "aws_rekognition"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Credentials

# METADATA ********************

# META {
# META   "language": "markdown",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

vault_url = "https://cv-training-key.vault.azure.net/"

key_p = notebookutils.credentials.getSecret(vault_url, "cv-prediction-api-key")
endpoint_p = notebookutils.credentials.getSecret(vault_url, "cv-endpoint-p-key")

key_t = notebookutils.credentials.getSecret(vault_url, "cv-training-api-key")
endpoint_t = notebookutils.credentials.getSecret(vault_url, "cv-endpoint-t-key")

predictor = CustomVisionPredictionClient(
    endpoint_p,
    ApiKeyCredentials(in_headers={"Prediction-key": key_p})
)
trainer = CustomVisionTrainingClient(
    endpoint_t,
    ApiKeyCredentials(in_headers={"Training-key": key_t})
)

print("Custom Vision clients initialized")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Resolve path and copy to local

# METADATA ********************

# META {
# META   "language": "markdown",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

if cropped_path.startswith("abfss://"):
    abs_cropped = cropped_path
else:
    files_listing = notebookutils.fs.ls("Files")
    lakehouse_root = files_listing[0].path.split("/Files/")[0]
    abs_cropped = f"{lakehouse_root}/{cropped_path}"

local_tmp = "/tmp/inference_input.jpg"
notebookutils.fs.cp(abs_cropped, f"file:{local_tmp}")

filename = os.path.basename(cropped_path)
print(f"Image ready for inference: {filename} | provider: {provider}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Run inference against all models
# The trainer client is used READ-ONLY to dynamically discover all published
# `pet-classifier-*` projects. This avoids hardcoding sizes.

# METADATA ********************

# META {
# META   "language": "markdown",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

rows = []
timestamp = datetime.now()

all_projects = {
    p.name: p for p in trainer.get_projects()
    if p.name.startswith("pet-classifier-")
}

print(f"Discovered {len(all_projects)} models: {list(all_projects.keys())}")

for project_name, project in all_projects.items():
    size = project_name.replace("pet-classifier-", "")
    publish_name = f"publish_{size}"

    try:
        with open(local_tmp, "rb") as img:
            results = predictor.classify_image(
                project.id,
                publish_name,
                img.read()
            )

        if not results.predictions:
            print(f"No predictions for model {size}")
            continue

        top = results.predictions[0]
        predicted = top.tag_name
        confidence = float(top.probability)

        rows.append(Row(
            image_name=filename,
            model_size=size,
            predicted=predicted,
            confidence=confidence,
            provider=provider,
            cropped_image_url=f"https://onelake.dfs.fabric.microsoft.com/petsproject/lkh_pets.Lakehouse/Files/development/cropped/{filename}",
            timestamp=timestamp
        ))

        print(f"Model {size}: '{predicted}' ({confidence:.2%})")

    except Exception as e:
        print(f"Error on model {size}: {e}")

print(f"\nInference complete: {len(rows)} model(s) evaluated | provider: {provider}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Save to inference_metrics table

# METADATA ********************

# META {
# META   "language": "markdown",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

if rows:
    inference_df = spark.createDataFrame(rows)
    inference_df.write.mode("append").option("mergeSchema", "true").saveAsTable("inference_metrics")
    print(f"Saved {len(rows)} inference results for '{filename}' | provider: {provider}")
else:
    print("No results to save")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
