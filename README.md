# Pet Recognition using Azure AI & Microsoft Fabric

## Overview

This project demonstrates an end-to-end Computer Vision pipeline to recognize individual pets (cats and dogs) using Azure services.

It showcases how to design, build, and operationalize an AI workflow leveraging Microsoft Fabric, Azure Blob Storage, and Azure AI Foundry (Custom Vision).

---


## 🚧 Current Status

- ✅ Data Engineering pipeline completed  
- 🚧 Model training pipeline in progress  

---

## Architecture

The solution follows a layered architecture:

1. Raw images are stored in Azure Blob Storage
2. Data is accessed via a shortcut in Microsoft Fabric Lakehouse
3. A Fabric Data Pipeline orchestrates preprocessing
4. Images are resized into multiple resolutions
5. Processed datasets are stored in Lakehouse (Silver layer)
6. Structured datasets are generated in the Gold layer  
7. (In progress) Models are trained using Azure Custom Vision 

> Architecture diagram available in `/docs/architecture.md`

---

## Key Features

- Scalable image preprocessing pipeline
- Multi-resolution dataset generation (128–512 px)
- Automated labeling based on folder structure
- Pipeline orchestration using Microsoft Fabric
- Clear separation between Data Engineering and AI workflows  
- Modular and reproducible design  

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
│ ├── data_engineering/
│ └── ml_training/ (WIP)
├── docs/
│ ├── images/
│ ├── de_ingestion.md
│ ├── pipelines.md
│ ├── roles_and_workflow.md
│ └── training_cv.md (WIP)
├── experiments/
└── README.md


---

## Data Engineering Pipeline

The pipeline performs the following steps:

1. Reads raw images from Azure Blob Storage (via shortcut)  
2. Iterates through multiple image sizes using a ForEach loop  
3. Resizes and standardizes images  
4. Generates labeled datasets based on folder structure  
5. Stores outputs in the Lakehouse:

`Files/silver/resized/<pet_name>/<size>`
`Files/gold/dataset_<size>/{train|test}/<label>`

---

## Model Training (Work in Progress)

The training pipeline is currently under development.

The goal is to:

- Train one model per image resolution  
- Compare model performance across sizes  
- Track metrics such as:
  - Accuracy  
  - Precision  
  - Recall  
- Store results for further analysis and visualization  

Future implementation includes:

- Automated training pipeline in Microsoft Fabric  
- Integration with Azure Custom Vision  
- Experiment tracking (MLflow)  
- Performance comparison dashboard (Power BI)  

---

## Image Resolutions

Multiple datasets are generated to evaluate performance impact:

- 128x128  
- 224x224  
- 256x256  
- 384x384  
- 512x512  

This enables analysis of trade-offs between:

- Model accuracy  
- Computational cost  
- Training time  

---

## Roles

This project simulates a real-world workflow:

- **Data Engineer** → Builds ingestion and preprocessing pipelines  
- **AI Engineer / Data Scientist** → Trains and evaluates models (in progress)  
- **Tester** → Validates outputs and model performance  

More details in `/docs/roles_and_workflow.md`

---

## How to Run

1. Upload raw images to Azure Blob Storage  
2. Create a shortcut in Fabric Lakehouse  
3. Execute the Data Engineering pipeline  
4. Validate datasets in the Gold layer  
5. (WIP) Execute the training pipeline  

---

## Future Improvements

- Model deployment as an API  
- Automated retraining pipeline  
- Advanced evaluation (confusion matrix, error analysis)  
- CI/CD integration  
- Real-time prediction demo  

---

## Author

This project is part of a personal portfolio focused on Data Engineering and AI Engineering using Azure and Microsoft Fabric.