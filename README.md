# Pet Recognition using Azure AI & Microsoft Fabric

## Overview

This project focuses on building an end-to-end Computer Vision pipeline to recognize individual pets (cats and dogs) using Azure services.

It demonstrates how to design, implement, and operationalize an AI workflow using Microsoft Fabric, Azure Blob Storage, and Azure AI Foundry (Custom Vision).

---

## Architecture

The solution follows a layered architecture:

1. Raw images are stored in Azure Blob Storage
2. Data is accessed via a shortcut in Microsoft Fabric Lakehouse
3. A Fabric Data Pipeline orchestrates preprocessing
4. Images are resized into multiple resolutions
5. Processed datasets are stored in Lakehouse (Silver layer)
6. Labeled datasets are used for model training in Custom Vision

> Architecture diagram available in `/docs/architecture.md`

---

## Key Features

- Scalable image preprocessing pipeline
- Multi-resolution dataset generation (128–512 px)
- Automated labeling based on folder structure
- Pipeline orchestration using Microsoft Fabric
- Separation of development and testing environments
- Reproducible and modular design

---

## Technologies Used

- Microsoft Fabric (Lakehouse, Notebooks, Pipelines)
- Azure Blob Storage
- Azure AI Foundry (Custom Vision)
- PySpark
- Python (Pillow, image processing)
- GitHub (version control)

---

## Project Structure

pet-recognition-azure-ai/

├── src/
├── notebooks/
├── pipelines/
├── experiments/
├── docs/
└── README.md


---

## Data Pipeline

The pipeline performs the following steps:

1. Reads raw images from Blob Storage (via shortcut)
2. Iterates through multiple image sizes using a ForEach loop
3. Resizes and standardizes images
4. Stores outputs in Lakehouse:

`Files/silver/resized/<pet_name>/<size>`

---

## Resize

Multiple models are trained using different image resolutions:

- 128x128
- 224x224
- 256x256
- 384x384
- 512x512

This allows comparison of:

- Accuracy
- Training time
- Model performance

---

## Roles

This project simulates a real-world workflow with two roles:

- **Developer** → Builds pipelines and models
- **Tester** → Validates outputs and results

More details in `/docs/roles_and_workflow.md`

---

## How to Run

1. Upload raw images to Azure Blob Storage
2. Create a shortcut in Fabric Lakehouse
3. Execute the Fabric pipeline
4. Validate outputs in the Lakehouse
5. Train models using Custom Vision

---

## Future Improvements

- Object detection for automatic pet cropping
- Model deployment as an API
- CI/CD integration
- Automated retraining pipeline

---

## Author

Project developed as part of a portfolio to demonstrate skills in Data Engineering and AI Engineering using Azure.