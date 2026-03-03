import os
import subprocess
import time
import shutil

def process_all_files():
    # Exact 5 files requested by user
    # Note: User will convert the .xls and .xlsm to .xlsx manually before running
    files = [
        "SR31B2512312.txt",
        "31.12.2025.xlsx",
        "SR31A2512312.txt",
        "Converter_RTGS.xlsx",     # Updated to xlsx per user manual conversion
        "DEC statament 2025.xlsx"  # Updated to xlsx per user manual conversion
    ]
    
    output_dir = "Final_Extracted_Markdown"
    os.makedirs(output_dir, exist_ok=True)
    
    success_count = 0
    
    print("Starting Specific Document OCR Pipeline...")
    print("="*40)
    
    for file in files:
        if file.startswith(output_dir):
            continue
            
        if not os.path.exists(file):
            print(f"[WARNING] Cannot find file: {file} (Make sure you saved it as .xlsx!)")
            continue
            
        print(f"\n[Processing]: {file}")
        
        try:
            result = subprocess.run(
                [r'ocr_env\Scripts\python.exe', 'robust_ocr_pipeline.py', file], 
                check=True
            )
            
            # Move the generated markdown file into the final folder
            base_name = os.path.splitext(file)[0]
            md_file = f"{base_name}_processed.md"
            if os.path.exists(md_file):
                shutil.move(md_file, os.path.join(output_dir, md_file))
                
            # Move the image extraction folder if it exists
            work_folder = f"ocr_work_{base_name}"
            if os.path.exists(work_folder):
                dest_folder = os.path.join(output_dir, work_folder)
                if os.path.exists(dest_folder):
                    shutil.rmtree(dest_folder) # replace if already exists
                shutil.move(work_folder, dest_folder)
                
            success_count += 1
            print(f"[SUCCESS] Extracted and moved to {output_dir}: {file}")
            
            print("Pausing 10 seconds to respect LLM rate limits...")
            time.sleep(10) 
            
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to process {file}. Error: {e}")
            
    print("="*40)
    print(f"Batch Processing Complete! {success_count} files extracted into '{output_dir}'.")

if __name__ == "__main__":
    process_all_files()
