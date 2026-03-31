# Microsoft Fabric Pipeline

## Overview

This pipeline orchestrates the preprocessing of pet images using Microsoft Fabric.

It automates the generation of multiple datasets with different image resolutions to support model training and experimentation.

---

## Pipeline Name

`pl_pet_recognition_training`

---

## Pipeline Components

### 1. Input Data

- Source: Azure Blob Storage
- Access: Fabric Lakehouse Shortcut
- Path: `Files/images/raw/`

---

### 2. ForEach Activity

The pipeline uses a ForEach loop to iterate through multiple image sizes.

#### Configuration

```json
[128, 224, 256, 384, 512]
```

---

### 3. Notebook Activity

#### Notebook

`fabric_preprocessing.ipynb`

#### Parameter

| Name        | Value     |
|------------|----------|
| image_size | @item()  |

---

## Notebook Responsibilities

For each iteration, the notebook:

1. Reads raw images from Lakehouse
2. Applies recursive file lookup
3. Processes images:
   - Resize to target resolution
   - Convert format to JPEG
4. Preserves folder structure (pet-based labeling)
5. Saves processed images

---

## Output Structure

```
Files/
   silver/
      resized/
         <pet_name>/   
            128/
            224/
            256/
            384/
            512/
```

### Each dataset contains:

```  
128/
   image1.jpg/
   image2.jpg/
   image3.jpg/
```

## Execution Flow

ForEach (image_size)
↓
Notebook execution
↓
Save processed dataset


---

## Key Features

- Parameterized processing
- Scalable design
- Separation of raw and processed data
- Support for experimentation

---

## Error Handling (Recommended)

- Validate input paths
- Handle unsupported image formats
- Log failed image processing attempts

---

## Performance Considerations

- Use sequential execution (Batch count = 1)
- Avoid large `.collect()` operations in production
- Optimize image processing logic

---

## Future Enhancements

- Add logging table in Lakehouse
- Integrate with model training pipeline
- Automate dataset versioning
- Add monitoring and alerts

---

## Summary

This pipeline provides a robust and scalable foundation for:

- Image preprocessing
- Dataset generation
- AI model experimentation