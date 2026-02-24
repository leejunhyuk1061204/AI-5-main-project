import os
import torch
from pathlib import Path
from anomalib.data import Folder
from anomalib.models import Patchcore
from anomalib.engine import Engine
import warnings
import sys
import io

# Force UTF-8 encoding for stdout to avoid cp949 errors on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore")

# --- Windows Symlink Monkeypatch ---
from anomalib.engine import engine as engine_module
def mock_create_versioned_dir(root_dir):
    # Simply return the root_dir without versioning/symlinking
    # This avoids WinError 1314 on systems without admin privileges
    os.makedirs(root_dir, exist_ok=True)
    return root_dir
engine_module.create_versioned_dir = mock_create_versioned_dir
# ------------------------------------

def train_patchcore_baseline():
    data_root = Path(r"C:\Users\301\Desktop\data\classification")
    results_root = Path(r"C:\Users\301\Desktop\AI-5-main-project\runs\patchcore")
    
    parts = [
        "ABS_Unit", "Air_Filter_Cover", "Battery", "Brake_Fluid", 
        "Engine_Cover", "Engine_Oil_Fill_Cap", "Radiator", "Windshield_Wiper_Fluid"
    ]
    
    for part in parts:
        print(f"\n" + "="*50)
        print(f"Starting PatchCore Baseline for: {part}")
        print("="*50)
        
        # Check if already finished (check for a weights folder or metrics file)
        # Using a simple folder check for simplicity here
        target_metrics_dir = results_root / part / "Patchcore" / part
        if (target_metrics_dir / "weights").exists() and (target_metrics_dir / "images").exists():
            print(f"  [Skip] {part} already seems to have results. Skipping.")
            continue

        try:
            part_data_dir = data_root / part
            if not part_data_dir.exists():
                print(f"  [Error] Data directory not found for {part}. Skipping.")
                continue
                
            # 1. Setup Data Module
            datamodule = Folder(
                name=part,
                root=str(part_data_dir),
                normal_dir="train/normal",
                abnormal_dir="test/abnormal",
                normal_test_dir="test/normal",
                test_split_mode="from_dir",
                train_batch_size=16,
                eval_batch_size=16
            )
            
            # 2. Setup Model
            model = Patchcore(
                backbone="wide_resnet50_2",
                layers=["layer2", "layer3"],
                coreset_sampling_ratio=0.01
            )
            
            # 3. Setup Engine
            engine = Engine(
                max_epochs=1,
                devices=1,
                default_root_dir=str(results_root / part)
            )
            
            # 4. Train (Feature Extraction)
            print(f"  -> Building Memory Bank for {part}...")
            engine.fit(model=model, datamodule=datamodule)
            
            # 5. Test (Performance Evaluation)
            print(f"  -> Evaluating on Test Set for {part}...")
            metrics = engine.test(model=model, datamodule=datamodule)
            
            print(f"\n  [SUCCESS] PatchCore Baseline for {part} completed.")
            print(f"  Metrics: {metrics}")
        except Exception as e:
            print(f"\n  [ERROR] Failed processing {part}: {e}")
            import traceback
            traceback.print_exc()
            continue

if __name__ == "__main__":
    train_patchcore_baseline()
