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
# META     },
# META     "environment": {
# META       "environmentId": "31eac2b7-7fc5-46b0-b083-28c95a60eecc",
# META       "workspaceId": "a96eab2a-8002-45f2-92b4-d2bf05c2540b"
# META     }
# META   }
# META }

# MARKDOWN ********************

# pillow-heif library installation

# CELL ********************

%pip install pillow-heif

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# Imports and Settings

# CELL ********************

from pyspark.sql.functions import col, rand
from PIL import Image, UnidentifiedImageError
import io
import os
import matplotlib.pyplot as plt
from pillow_heif import register_heif_opener
register_heif_opener()
TARGET_SIZE = (512, 512)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# Read images from shortcut

# CELL ********************

df = spark.read.format("binaryFile").option("recursiveFileLookup", "true").load("Files/images")

display(df.limit(10))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

df.show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

print(df.count())

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

sample_df = df.orderBy(rand()).limit(6)
samples = sample_df.collect()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

cols = 3
rows = 2

plt.figure(figsize=(10, 6))

for i, row in enumerate(samples):
    try:
        img = Image.open(io.BytesIO(row.content))

        plt.subplot(rows, cols, i + 1)
        plt.imshow(img)
        plt.axis("off")

        # mostrar nombre archivo
        filename = row.path.split("/")[-1]
        plt.title(filename, fontsize=8)

    except Exception as e:
        print(f"Error en imagen {row.path}: {e}")

plt.tight_layout()
plt.show()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
