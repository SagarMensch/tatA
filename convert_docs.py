from docling.document_converter import DocumentConverter
import os

files = [
    r"C:\Users\sagar\Downloads\TataAgentic AI\31.12.2025.xlsx",
    r"C:\Users\sagar\Downloads\TataAgentic AI\SR31A2512312.txt",
    r"C:\Users\sagar\Downloads\TataAgentic AI\Converter_RTGS.xlsm",
    r"C:\Users\sagar\Downloads\TataAgentic AI\BRD FOR RTGS NEW ONE (1).docx",
    r"C:\Users\sagar\Downloads\TataAgentic AI\DEC statament 2025.xls",
    r"C:\Users\sagar\Downloads\TataAgentic AI\SR31B2512312.txt"
]

def main():
    print("Initializing DocumentConverter...")
    try:
        converter = DocumentConverter()
    except Exception as e:
        print(f"Failed to initialize DocumentConverter: {e}")
        return
    
    for file_path in files:
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            continue
            
        try:
            print(f"Converting {file_path}...")
            result = converter.convert(file_path)
            md_content = result.document.export_to_markdown()
            
            base_name = os.path.splitext(file_path)[0]
            out_path = base_name + ".md"
            
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            print(f"Successfully converted to {out_path}")
        except Exception as e:
            print(f"Error converting {file_path}: {e}")

if __name__ == '__main__':
    main()
