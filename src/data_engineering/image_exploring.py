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
# META     },
# META     "warehouse": {
# META       "default_warehouse": "30b6dee2-5c93-4ca1-a1ae-daa9f080cef1",
# META       "known_warehouses": [
# META         {
# META           "id": "30b6dee2-5c93-4ca1-a1ae-daa9f080cef1",
# META           "type": "Lakewarehouse"
# META         }
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# ## Imports and Settings

# CELL ********************

'''
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
# Load image
image = mpimg.imread("/lakehouse/default/Files/gold/dataset_128/test/gato_jorge/IMG-20200429-WA0027.jpg")
# Let the axes disappear
plt.axis('off')
# Plot image in the output
image_plot = plt.imshow(image)
'''

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

'''
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
# Load image
image = mpimg.imread("/lakehouse/default/Files/gold/dataset_128/train/gato_jorge/IMG-20200429-WA0027.jpg")
# Let the axes disappear
plt.axis('off')
# Plot image in the output
image_plot = plt.imshow(image)
'''

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

from PIL import Image
import io
import os

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# Test notebook execution

# PARAMETERS CELL ********************

foreach_item ="128"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cast the injected string to integer
target_size = int(image_size)  # e.g. 128, 224, 256...
print(f"Resizing images to: {target_size}x{target_size}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# Processing cell

# CELL ********************

target_size = int(target_size)

# Root input path
input_root = "Files/images/raw"

# HEIC excluded for now
SUPPORTED_FORMATS = (".png", ".jpg", ".jpeg", ".heic", ".heif")
SKIPPED_FORMATS   = (".heic", ".heif")

# Dynamically list all subfolders
subfolders = [f.name for f in notebookutils.fs.ls(input_root) if f.isDir]
print(f"Found folders: {subfolders}")

for folder in subfolders:
    input_folder  = f"{input_root}/{folder}"
    output_folder = f"Files/silver/resized/{folder}/{target_size}"

    # Create output folder
    notebookutils.fs.mkdirs(output_folder)

    # List images
    try:
        files = notebookutils.fs.ls(input_folder)
    except:
        print(f"⚠️ Could not read: {input_folder}")
        continue

    for file in files:
        filename = file.name
        ext = os.path.splitext(filename)[1].lower()

        if ext in SKIPPED_FORMATS:
            print(f"⏭️ HEIC skipped (unsupported in pipeline): {filename}")
            continue

        if ext in SUPPORTED_FORMATS:

            # Copy to /tmp/ for processing
            notebookutils.fs.cp(
                f"{input_folder}/{filename}",
                f"file:/tmp/{filename}"
                )

                # Open and resize 
            with Image.open(f"/tmp/{filename}") as img:

                    # Convert to RGB
                img = img.convert("RGB")
                resized = img.resize((target_size, target_size))

                # Always save output as JPEG for consistency
                output_filename = os.path.splitext(filename)[0] + ".jpg"
                resized.save(f"/tmp/resized_{output_filename}", format="JPEG")

                notebookutils.fs.cp(
                    f"file:/tmp/resized_{output_filename}",
                    f"{output_folder}/{output_filename}"
                )
                print(f"✅ {folder}/{filename} → resized/{folder}/{target_size}/{output_filename}")

        else:
            print(f"⏭️ Skipping unsupported format: {filename}")

    print(f"🎉 Done! All folders resized to {target_size}x{target_size}")


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

'''
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
# Load image
image = mpimg.imread("/lakehouse/default/Files/gold/dataset_all/test/gato_phil/20221009_141245.jpg")
# Let the axes disappear
plt.axis('off')
# Plot image in the output
image_plot = plt.imshow(image)
'''

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Cargar el archivo CSV en un DataFrame
df = spark.read.format("csv") \
    .option("header", "true") \
    .option("inferSchema", "true") \
    .load("Files/libs/CountryList_csv.csv")

# Escribir el DataFrame en formato Delta (reemplaza si la tabla ya existe)
df.write.format("delta") \
    .mode("overwrite") \
    .saveAsTable("countrylist")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
