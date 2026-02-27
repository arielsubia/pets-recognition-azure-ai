import os
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from pillow_heif import register_heif_opener
import logging
register_heif_opener()

SUPPORTED_FORMATS = (".jpg", ".jpeg", ".png", ".bmp", ".heic")
TARGET_SIZE = (512, 512)

def standardize_image(input_path: Path, output_path: Path):
    try:
        with Image.open(input_path) as img:
            img = img.convert("RGB")
            img = img.resize(TARGET_SIZE)

            output_path.parent.mkdir(parents=True, exist_ok=True) 
            img.save(output_path, format="JPEG", quality=95)

        logging.info(f"Processed: {input_path.name}")

    except UnidentifiedImageError:
        logging.warning(f"Invalid image file skipped: {input_path}")

    except Exception as e:
        logging.error(f"Error processing {input_path}: {e}")


def process_directory(raw_dir: Path, processed_dir: Path):
    for pet_folder in raw_dir.iterdir():
        if pet_folder.is_dir():
            for image_file in pet_folder.iterdir():
                if image_file.suffix.lower() in SUPPORTED_FORMATS:

                    relative_path = image_file.relative_to(raw_dir)
                    output_file = processed_dir / relative_path
                    output_file = output_file.with_suffix(".jpg")

                    standardize_image(image_file, output_file)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    RAW_PATH = Path("data/raw")
    PROCESSED_PATH = Path("data/processed")

    process_directory(RAW_PATH, PROCESSED_PATH)
