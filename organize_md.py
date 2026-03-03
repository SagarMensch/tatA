import os
import glob
import shutil

def organize_files():
    final_dir = "Final-MD"
    os.makedirs(final_dir, exist_ok=True)
    
    # Files to absolutely keep in the root folder
    keep_files = [
        "Autonomous_RTGS_CA_Matching.md",
        "Tata_RTGS_Automation_Solution_Architecture.md"
    ]
    
    # Find all markdown files in the current folder
    md_files = glob.glob("*.md")
    
    moved_count = 0
    
    for file in md_files:
        # Don't touch our important architecture/solution docs
        if file in keep_files:
            continue
            
        # Move all process extraction files (like BRD FOR RTGS NEW ONE (1)_processed.md)
        shutil.move(file, os.path.join(final_dir, file))
        moved_count += 1
        print(f"Moved: {file}")
        
    print(f"\nDone! Moved {moved_count} extraction markdown files into '{final_dir}'.")
    print(f"Kept {len(keep_files)} core solution documents safely in the root.")

if __name__ == "__main__":
    organize_files()
