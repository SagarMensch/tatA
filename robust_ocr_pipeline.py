import os
import fitz  # PyMuPDF
import cv2
import numpy as np
from paddleocr import PaddleOCR
import json
import logging
import requests
from pathlib import Path
import docx
import openpyxl

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

API_KEY = "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"

def pdf_to_images(pdf_path, output_dir, dpi=350):
    """Step 1: Convert PDF to High Quality Images"""
    logging.info(f"Converting {pdf_path} to images at {dpi} DPI...")
    doc = fitz.open(pdf_path)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    image_paths = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=dpi)
        img_path = os.path.join(output_dir, f"page_{i+1}.png")
        pix.save(img_path)
        image_paths.append(img_path)
        logging.info(f" Saved {img_path}")
    return image_paths

def deskew_image(image):
    """Deskew the image using OpenCV."""
    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
    coords = np.column_stack(np.where(image > 0))
    if len(coords) == 0:
        return image 
        
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
        
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated

def preprocess_image(image_path, output_path):
    """Step 2: Preprocessing Layer"""
    logging.info(f"Preprocessing {image_path}...")
    img = cv2.imread(image_path, 0)
    inverted = cv2.bitwise_not(img)
    deskewed = deskew_image(inverted)
    deskewed = cv2.bitwise_not(deskewed)

    th = cv2.adaptiveThreshold(
        deskewed, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 2
    )

    denoised = cv2.medianBlur(th, 3)
    cv2.imwrite(output_path, denoised)
    return output_path

class DocumentParser:
    def __init__(self):
        logging.info("Initializing PaddleOCR model...")
        # Step 3: Strong OCR (No layoutparser, just PaddleOCR)
        self.ocr = PaddleOCR(
            lang='en',
            use_textline_orientation=True,
            ocr_version='PP-OCRv4'
        )

    def process_page(self, preprocessed_image_path, page_num):
        """Processes a single preprocessed page image."""
        logging.info(f"Running OCR on page {page_num}...")
        
        # Step 3: OCR full image at once
        ocr_result = self.ocr.ocr(preprocessed_image_path, cls=True)
        
        page_data = {
            "page_number": page_num,
            "blocks": []
        }
        
        if not ocr_result or not ocr_result[0]:
            logging.info(f" No text found on page {page_num}")
            return page_data
            
        lines = ocr_result[0]
        
        # Step 4: Line Sorting & Heuristic Segmentation
        # Sort lines strictly top-to-bottom
        lines.sort(key=lambda x: x[0][0][1]) # Sort by Y1 coordinate of bounding box
        
        current_block = []
        last_y = -1
        
        for i, line in enumerate(lines):
            bbox = line[0]
            text = line[1][0]
            confidence = line[1][1]
            
            # Extract coordinates
            y1 = bbox[0][1]
            y2 = bbox[2][1]
            h = y2 - y1
            
            # Step 5: Heuristics to categorize structural blocks
            block_type = "paragraph"
            
            # Heuristic 1: If text is short, uppercase, or ends in colon, it's likely a heading/title
            if len(text) < 40 and (text.isupper() or text.istitle() or text.endswith(':')):
                block_type = "heading"
                
            # Heuristic 2: Tabular detection based on large multi-spaces or pipe formatting
            if "   " in text or "|" in text or len(text.split()) > 8 and any(char.isdigit() for char in text):
                block_type = "table_row"
                
            page_data["blocks"].append({
                "id": f"line_{i}",
                "type": block_type,
                "text": text,
                "bbox": bbox
            })

        return page_data

def convert_json_to_markdown(structured_pages, output_filepath):
    """Step 6: LLM Integration - Convert JSON to exact Markdown"""
    logging.info("Sending structured JSON telemetry to OpenRouter LLM for Markdown assembly...")
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = """You are a precision Markdown compiler. Convert the following structured page JSON exactly into Markdown.
Rules:
- Preserve all numbers and words EXACTLY as provided in the 'text' fields. Do NOT modify, summarize, or hallucinate content.
- Treat 'table_row' blocks as sequential rows to compile into a visually aligned generic tablular markdown layout.
- Use # for Titles/Headings if the object type is 'heading'.
- Keep all text intact. Fix obviously misspelled single OCR characters but do not rephrase."""

    model = "nvidia/nemotron-nano-12b-v2-vl:free"
    # Alternative fallback if nemotron isn't acting right
    fallback_model = "meta-llama/llama-3.3-70b-instruct:free"
    
    final_md = ""
    for page in structured_pages:
        page_json_str = json.dumps(page, indent=2)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Convert the following structured content for Page {page['page_number']} to Markdown:\n\n{page_json_str}"}
            ]
        }
        
        try:
            res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            if res.status_code == 200:
                md_text = res.json()['choices'][0]['message']['content']
                final_md += f"\n\n<!-- Page {page['page_number']} -->\n\n" + md_text
                logging.info(f" Got Markdown for Page {page['page_number']}")
            else:
                logging.error(f" LLM failed for Page {page['page_number']}: {res.status_code} - {res.text}")
                crude = "\n".join([b.get('text', "") for b in page['blocks']])
                final_md += f"\n\n<!-- Page {page['page_number']} (LLM Failed Fallback) -->\n\n{crude}"
        except Exception as e:
            logging.error(f" OpenRouter request exception: {e}")
            
    with open(output_filepath, "w", encoding="utf-8") as f:
        f.write(final_md)
    logging.info(f"Final comprehensive Markdown saved to {output_filepath}")

import base64

def analyze_image_with_vlm(image_path):
    """Pass an extracted image to Nemotron Multimodal VL to get a description."""
    logging.info(f"Analyzing image with VLM: {image_path}")
    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
        ext = os.path.splitext(image_path)[1].lower().replace('.', '')
        if ext == 'jpg': ext = 'jpeg'
        mime_type = f"image/{ext}"
        
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "nvidia/nemotron-nano-12b-v2-vl:free",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe the contents, text, and data in this image, chart, or diagram clearly and concisely. If it contains a table, transcribe it exactly as a Markdown table. Do not hallucinate."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded_string}"}}
                    ]
                }
            ]
        }
        
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
        if res.status_code == 200:
            description = res.json()['choices'][0]['message']['content']
            return description
        else:
            logging.error(f"VLM Analysis Failed: {res.status_code} - {res.text}")
            return "*[Image extraction failed]*"
            
    except Exception as e:
        logging.error(f"Error during VLM image analysis: {e}")
        return f"*[Image analysis error: {str(e)}]*"

def extract_docx(docx_path, output_dir):
    """Extract text and images from DOCX using python-docx and VLM."""
    logging.info(f"Extracting DOCX natively with images: {docx_path}")
    doc = docx.Document(docx_path)
    text = []
    
    for para in doc.paragraphs:
        if para.text.strip():
            text.append(para.text)
            
    for table in doc.tables:
        text.append("\n")
        for row in table.rows:
            row_data = [cell.text.strip() for cell in row.cells]
            text.append(" | ".join(row_data))
        text.append("\n")
            
    # Extract images from the docx package (it's a zip file)
    import zipfile
    image_counter = 1
    try:
        with zipfile.ZipFile(docx_path, 'r') as docx_zip:
            img_dir = os.path.join(output_dir, "extracted_images")
            Path(img_dir).mkdir(parents=True, exist_ok=True)
            for item in docx_zip.namelist():
                if item.startswith('word/media/'):
                    img_data = docx_zip.read(item)
                    ext = os.path.splitext(item)[1]
                    img_path = os.path.join(img_dir, f"doc_img_{image_counter}{ext}")
                    with open(img_path, 'wb') as f:
                        f.write(img_data)
                    
                    # Call VLM to extract the intelligence from the image
                    vlm_description = analyze_image_with_vlm(img_path)
                    
                    text.append(f"\n> **Image {image_counter} VLM Extraction:**\n>\n> {vlm_description}\n\n![Embedded Document Image]({img_path})\n")
                    image_counter += 1
    except Exception as e:
        logging.warning(f"Could not extract images from docx: {e}")
        
    return "\n\n".join(text)

def extract_excel(excel_path, output_dir=None):
    """Extract text from XLSX/XLSM/XLS using openpyxl or pandas as fallback."""
    logging.info(f"Extracting Excel natively: {excel_path}")
    text = []
    
    try:
        # Try modern openpyxl first
        wb = openpyxl.load_workbook(excel_path, data_only=True)
        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            text.append(f"# Sheet: {sheet_name}\n")
            for row in sheet.iter_rows(values_only=True):
                row_data = [str(cell) if cell is not None else "" for cell in row]
                if any(row_data):
                    text.append(" | ".join(row_data))
            text.append("\n")
            
    except Exception as e:
        logging.warning(f"openpyxl failed ({e}), falling back to pandas for {excel_path}")
        try:
            import pandas as pd
            # Pandas can use xlrd for .xls, openpyxl for .xlsx, and generally ignores corrupt drawing xmls
            xls = pd.ExcelFile(excel_path)
            for sheet_name in xls.sheet_names:
                text.append(f"# Sheet: {sheet_name}\n")
                df = pd.read_excel(xls, sheet_name=sheet_name)
                
                # Write header
                headers = [str(c) if not "Unnamed" in str(c) else "" for c in df.columns]
                text.append(" | ".join(headers))
                
                # Write data rows
                for _, row in df.iterrows():
                    row_data = [str(val) if pd.notna(val) else "" for val in row.values]
                    if any(row_data):
                        text.append(" | ".join(row_data))
                text.append("\n")
        except Exception as fallback_e:
            raise Exception(f"Pandas fallback also failed: {fallback_e}")
            
    return "\n".join(text)

def has_text_layer(pdf_path):
    """Check if the PDF has a native text layer. (If >100 chars in first 3 pages)"""
    doc = fitz.open(pdf_path)
    text_length = 0
    for i in range(min(3, len(doc))):
        text_length += len(doc[i].get_text("text").strip())
    return text_length > 100

def extract_pdf_native(pdf_path, output_dir):
    """Extract text and images from PDF natively using PyMuPDF and VLM."""
    logging.info(f"Extracting PDF natively (text layer detected): {pdf_path}")
    doc = fitz.open(pdf_path)
    text = []
    img_dir = os.path.join(output_dir, "extracted_images")
    Path(img_dir).mkdir(parents=True, exist_ok=True)
    
    image_counter = 1
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        
        # 1. Extract Native Text
        page_text = page.get_text("text")
        if page_text.strip():
            text.append(page_text)
            
        # 2. Extract Native Images embedded in this page
        image_list = page.get_images(full=True)
        if image_list:
            text.append(f"\n<!-- Media from Page {page_num + 1} -->\n")
            for img_info in image_list:
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                
                # Ignore tiny decorative images (like < 20KB) to prevent spamming
                if len(image_bytes) > 20480: 
                    img_path = os.path.join(img_dir, f"page_{page_num+1}_img_{image_counter}.{image_ext}")
                    with open(img_path, "wb") as f:
                        f.write(image_bytes)
                        
                    # Call VLM to extract the intelligence from the PDF image
                    vlm_description = analyze_image_with_vlm(img_path)
                    
                    text.append(f"\n> **Page {page_num + 1} Image VLM Extraction:**\n>\n> {vlm_description}\n\n![Page {page_num + 1} Extracted Image]({img_path})\n")
                    image_counter += 1

    return "\n\n".join(text)

def extract_txt(txt_path):
    """Extract text from RAW TXT files."""
    logging.info(f"Extracting TXT natively: {txt_path}")
    text = []
    text.append(f"# Raw Text File: {os.path.basename(txt_path)}\n")
    text.append("```text\n")
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            text.append(f.read())
    except UnicodeDecodeError:
        with open(txt_path, 'r', encoding='latin-1') as f:
            text.append(f.read())
    text.append("\n```\n")
    return "".join(text)

def process_document(filepath, output_md_path):
    """Main orchestrator with hybrid format routing."""
    ext = os.path.splitext(filepath)[1].lower()
    base_dir = os.path.dirname(filepath)
    work_dir = os.path.join(base_dir, f"ocr_work_{os.path.splitext(os.path.basename(filepath))[0]}")
    Path(work_dir).mkdir(parents=True, exist_ok=True)
    
    if ext == '.docx':
        final_md = extract_docx(filepath, work_dir)
        with open(output_md_path, "w", encoding="utf-8") as f:
            f.write(final_md)
        logging.info(f"Saved native DOCX extraction to {output_md_path}")
        return
        
    elif ext in ['.xlsx', '.xlsm', '.xls']:
        try:
            final_md = extract_excel(filepath, work_dir)
            with open(output_md_path, "w", encoding="utf-8") as f:
                f.write(final_md)
            logging.info(f"Saved native Excel extraction to {output_md_path}")
        except Exception as e:
            logging.error(f"Failed to extract Excel natively (might be old .xls needing pyexcel/xlrd): {e}")
            with open(output_md_path, "w", encoding="utf-8") as f:
                f.write(f"*[Error extracting Excel: {str(e)}]*")
        return
        
    elif ext == '.txt':
        final_md = extract_txt(filepath)
        with open(output_md_path, "w", encoding="utf-8") as f:
            f.write(final_md)
        logging.info(f"Saved native TXT extraction to {output_md_path}")
        return
        
    elif ext == '.pdf':
        if has_text_layer(filepath):
            final_md = extract_pdf_native(filepath, work_dir)
            with open(output_md_path, "w", encoding="utf-8") as f:
                f.write(final_md)
            logging.info(f"Saved native PDF extraction to {output_md_path}")
            return
            
        else:
            logging.info("PDF is scanned. Falling back to robust OCR pipeline...")
            raw_img_dir = os.path.join(work_dir, "raw_pages")
            clean_img_dir = os.path.join(work_dir, "clean_pages")
            Path(clean_img_dir).mkdir(parents=True, exist_ok=True)
            
            raw_images = pdf_to_images(filepath, raw_img_dir, dpi=350)
            parser = DocumentParser()
            all_pages_data = []
            
            for i, raw_img_path in enumerate(raw_images):
                page_num = i + 1
                clean_img_path = os.path.join(clean_img_dir, f"clean_page_{page_num}.png")
                preprocess_image(raw_img_path, clean_img_path)
                page_data = parser.process_page(clean_img_path, page_num)
                all_pages_data.append(page_data)
                
            debug_json_path = os.path.join(work_dir, "extracted_structure.json")
            with open(debug_json_path, "w") as f:
                json.dump(all_pages_data, f, indent=2)
                
            convert_json_to_markdown(all_pages_data, output_md_path)
            return
            
    else:
        logging.error(f"Unsupported file format: {ext}")
        return

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python robust_ocr_pipeline.py <path_to_file>")
    else:
        input_file = sys.argv[1]
        out_md = os.path.splitext(input_file)[0] + "_processed.md"
        process_document(input_file, out_md)
