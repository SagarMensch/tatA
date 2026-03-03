import sys
import os
import traceback
from docling.document_converter import DocumentConverter

def main():
    if len(sys.argv) < 2:
        print("Usage: python convert_single_doc.py <file_path>")
        sys.exit(1)
        
    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        sys.exit(1)
        
    base_name = os.path.splitext(file_path)[0]
    out_path = base_name + ".md"
    ext = os.path.splitext(file_path)[1].lower()

    if ext == '.txt':
        print(f"Docling does not support raw .txt files natively. Wrapping text into {out_path}.")
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"```text\n{text}\n```")
        print(f"SUCCESS: {out_path}")
        sys.exit(0)

    print(f"Initializing DocumentConverter for {file_path}...")
    try:
        converter = DocumentConverter()
    except Exception as e:
        print(f"Failed to initialize DocumentConverter: {e}")
        sys.exit(1)
        
    try:
        print(f"Converting {file_path}...")
        result = converter.convert(file_path)
        md_content = result.document.export_to_markdown()
        
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"SUCCESS: {out_path}")
    except Exception as e:
        err = traceback.format_exc()
        print(f"Error converting {file_path}:\n{err}")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"Failed to convert `{os.path.basename(file_path)}` using docling.\n\nError details:\n```python\n{err}\n```\n")
        sys.exit(1)

if __name__ == '__main__':
    main()
