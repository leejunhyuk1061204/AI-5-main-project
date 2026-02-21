
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from ai.scripts.audio.data_loader import create_dataloaders, TYPE_LABELS

def check_split():
    print("🚀 Calculating Effective Data Split...", flush=True)
    
    # Run the slit logic (load metadata -> group split)
    # arch='cnn' is dummy, just to get the lists
    train_loader, val_loader, _, test_loader, _, _ = create_dataloaders("cnn", batch_size=1)
    
    train_ds = train_loader.dataset.data
    val_ds = val_loader.dataset.data
    test_ds = test_loader.dataset.data

    def count_class(data):
        counts = {label: 0 for label in TYPE_LABELS}
        counts["normal"] = 0
        for item in data:
            if item["abnormal"] == 0:
                counts["normal"] += 1
            else:
                counts[item["type"]] += 1
        return counts

    tr_c = count_class(train_ds)
    va_c = count_class(val_ds)
    te_c = count_class(test_ds)

    print("\n📊 Effective Dataset Split (Files)", flush=True)
    print("=" * 60)
    print(f"{'Class':<10} | {'Train':<10} | {'Val':<10} | {'Test':<10} | {'Total':<10}")
    print("-" * 60)
    
    cats = ["normal"] + TYPE_LABELS
    total_tr, total_va, total_te = 0, 0, 0
    
    for c in cats:
        tr, va, te = tr_c.get(c,0), va_c.get(c,0), te_c.get(c,0)
        tot = tr + va + te
        print(f"{c:<10} | {tr:<10} | {va:<10} | {te:<10} | {tot:<10}")
        total_tr += tr
        total_va += va
        total_te += te
        
    print("-" * 60)
    print(f"{'ALL':<10} | {total_tr:<10} | {total_va:<10} | {total_te:<10} | {total_tr+total_va+total_te:<10}")
    print("=" * 60)

if __name__ == "__main__":
    check_split()
