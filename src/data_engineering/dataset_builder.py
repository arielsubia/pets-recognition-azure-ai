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

# #### Imports

# CELL ********************

from pyspark.sql.functions import rand
from pyspark.sql.functions import input_file_name, regexp_extract
import os

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Parameters

# PARAMETERS CELL ********************

# Split
TRAIN_RATIO = 0.8

# Tagged Parameters cell
image_size = ""   # default — overridden by pipeline @item()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Read the entire dataframe regardless of folders

# CELL ********************

if image_size == "original":
    df = spark.read.format("binaryFile") \
        .option("recursiveFileLookup", "true") \
        .load("Files/images/raw/")
else:
    df = spark.read.format("binaryFile") \
        .option("recursiveFileLookup", "true") \
        .load("Files/silver/resized/")

df.show()
print("Shape: ", (df.count(), len(df.columns)))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Filter to only the current size being processed by ForEach
if image_size != "original":
    df = df.filter(
        regexp_extract("path", r"resized/[^/]+/(\d+)/", 1) == str(image_size)
    )

print(f"Filtered to size {image_size}: {df.count()} images")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Get label & size

# CELL ********************

if image_size == "original":
    from pyspark.sql.functions import lit
    df = df.withColumn(
        "label",
        regexp_extract("path", r"raw/([^/]+)/", 1)
    ).withColumn(
        "size",
        lit("original")
    )
else:
    df = df.withColumn(
        "label",
        regexp_extract("path", r"resized/([^/]+)/\d+/", 1)
    ).withColumn(
        "size",
        regexp_extract("path", r"resized/[^/]+/(\d+)/", 1)
    )

df.groupBy("label", "size").count().show()

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

# MARKDOWN ********************

# ### Split generation (train & test)

# CELL ********************

from pyspark.sql import Window
from pyspark.sql.functions import rand, row_number, count, col

# Extract the original filename (the true identity of each image)

df = df.withColumn(
    "filename",
    regexp_extract("path", r"([^/]+)$", 1) 
)


# Get unique filenames per label and assign split there

filename_split = (
    df.select("filename","label")
    .distinct()
    .withColumn("row_num", row_number().over(
        Window.partitionBy("label").orderBy(rand())
    ))
    .withColumn("label_count",count("filename").over(
        Window.partitionBy("label")
    ))
    .withColumn(
        "split",
        (col("row_num")/col("label_count")>TRAIN_RATIO)
    )
    .select("filename","label","split")
)


# Join split decision back to full dataframe
df = df.join(filename_split.select("filename","split"), on="filename", how="left")

train_df = df.filter(col("split") == False)
test_df  = df.filter(col("split") == True)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

print("=== Train distribution ===")
train_df.groupBy("label").count().show()

print("=== Test distribution ===")
test_df.groupBy("label").count().show()

# Safety check — fail early if any label is missing from test
train_labels = {r["label"] for r in train_df.select("label").distinct().collect()}
test_labels  = {r["label"] for r in test_df.select("label").distinct().collect()}
missing      = train_labels - test_labels

if missing:
    raise ValueError(f"❌ These labels are missing from test set: {missing}. "
                     f"Increase dataset size or adjust TRAIN_RATIO.")
else:
    print("✅ All labels present in both train and test sets")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Image saving function

# CELL ********************

def save_images(df, base_path):
    rows = df.select("path", "content", "label").collect()

    for row in rows:
        label = row["label"]
        original_path = row["path"]
        content = row["content"]

        filename = os.path.basename(original_path)

        output_dir = f"/lakehouse/default/{base_path}/{label}"
        os.makedirs(output_dir, exist_ok=True)

        output_path = f"{output_dir}/{filename}"

        with open(output_path, "wb") as f:
            f.write(content)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Final saving into Gold layer

# CELL ********************

if image_size:
    base_output = f"Files/gold/dataset_{image_size}"
else:
    base_output = "Files/gold/dataset_all"

train_path = f"{base_output}/train"
test_path = f"{base_output}/test"

save_images(train_df, train_path)
save_images(test_df, test_path)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# #### Quick validation

# CELL ********************

print("Train count:", train_df.count())
print("Test count:", test_df.count())

train_df.groupBy("label").count().show()
test_df.groupBy("label").count().show()


# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
