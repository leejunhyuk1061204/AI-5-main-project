import torch
import torchvision.transforms as T
from PIL import Image
import os
from pathlib import Path
import random

def augment_engine_cover():
    target_dir = Path(r"C:\Users\301\Desktop\data\classification\Engine_Cover\train\abnormal")
    if not target_dir.exists():
        print(f"Error: Target directory {target_dir} does not exist.")
        return

    # List only original images (exclude existing augmented images if any)
    image_extensions = (".png", ".PNG", ".jpg", ".JPG", ".jpeg")
    all_files = [f for f in target_dir.iterdir() if f.suffix in image_extensions]
    original_images = [f for f in all_files if "_aug_" not in f.name]

    print(f"Found {len(original_images)} original images.")

    # Augmentation Pipeline
    transform = T.Compose([
        T.RandomHorizontalFlip(p=0.5),
        T.RandomVerticalFlip(p=0.5),
        T.RandomRotation(degrees=20),
        T.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.1, hue=0.05),
        T.RandomApply([T.GaussianBlur(kernel_size=3)], p=0.3),
    ])

    num_augs_per_image = 11

    for img_path in original_images:
        try:
            with Image.open(img_path) as img:
                # RGB conversion to support both PNG/JPG
                img = img.convert("RGB")
                
                for i in range(num_augs_per_image):
                    aug_img = transform(img)
                    aug_name = f"{img_path.stem}_aug_{i}.jpg"
                    aug_path = target_dir / aug_name
                    
                    # Save as JPG to standardize
                    aug_img.save(aug_path, "JPEG", quality=90)
            
            print(f"Augmented {img_path.name} -> 11 images.")
        except Exception as e:
            print(f"Failed to process {img_path.name}: {e}")

    print("\n[SUCCESS] Augmentation completed.")

if __name__ == "__main__":
    augment_engine_cover()
