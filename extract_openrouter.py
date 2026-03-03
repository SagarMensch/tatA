import os
import time
import requests

API_KEY = "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"

FILES_TO_PROCESS = [
    r"C:\Users\sagar\Downloads\TataAgentic AI\31.12.2025.xlsx",
    r"C:\Users\sagar\Downloads\TataAgentic AI\SR31A2512312.txt",
    r"C:\Users\sagar\Downloads\TataAgentic AI\Converter_RTGS.xlsm",
    r"C:\Users\sagar\Downloads\TataAgentic AI\BRD FOR RTGS NEW ONE (1).docx",
    r"C:\Users\sagar\Downloads\TataAgentic AI\DEC statament 2025.xls",
    r"C:\Users\sagar\Downloads\TataAgentic AI\SR31B2512312.txt"
]

LOG_FILE = "extraction.log"

def log(msg):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def get_free_models():
    try:
        res = requests.get('https://openrouter.ai/api/v1/models')
        if res.status_code == 200:
            data = res.json().get('data', [])
            # Priority to larger parameter models if available, filter for free
            free_models = [m['id'] for m in data if 'free' in m['id'].lower() or 'gemini-2.0-flash-lite-preview' in m['id'].lower()]
            # prioritize top known ones first
            priority = [
                "nvidia/nemotron-nano-12b-v2-vl:free",
                "google/gemini-2.0-flash-lite-preview-02-05:free",
                "google/gemini-2.0-pro-exp-02-05:free",
                "cognitivecomputations/dolphin3.0-r1-mistral-24b:free",
                "meta-llama/llama-3.3-70b-instruct:free",
                "qwen/qwen-2-7b-instruct:free",
                "meta-llama/llama-3.2-3b-instruct:free",
                "meta-llama/llama-3.1-8b-instruct:free"
            ]
            final_models = [m for m in priority if m in free_models]
            for m in free_models:
                if m not in final_models:
                    final_models.append(m)
            return final_models if final_models else priority
    except Exception as e:
        log(f"Failed to fetch models: {e}")
    # Fallback list if fetching fails
    return [
        "nvidia/nemotron-nano-12b-v2-vl:free",
        "google/gemini-2.0-flash-lite-preview-02-05:free",
        "google/gemini-2.0-pro-exp-02-05:free",
        "cognitivecomputations/dolphin3.0-r1-mistral-24b:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen-2-7b-instruct:free",
        "meta-llama/llama-3.1-8b-instruct:free"
    ]

def call_openrouter(content, filename, models_to_try):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = "You are a data extraction expert. Your ONLY job is to take the provided raw text or document dump and format it into a perfect, comprehensive Markdown document. Extract EVERYTHING. Do not skip any rows, columns, or text. Do not add conversational filler. Maintain tabular structure as Markdown tables where applicable."
    
    for model in models_to_try:
        log(f"  Attempting with model {model}...")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract everything accurately into Markdown. Ensure you extract the ENTIRE document content without truncating. Raw Text:\n\n{content}"}
            ]
        }
        
        try:
            res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            if res.status_code == 200:
                md = res.json()['choices'][0]['message']['content']
                log(f"  Success with {model}!")
                return md
            elif res.status_code == 429:
                log(f"  Model {model} hit a rate limit (429).")
            elif res.status_code == 404:
                log(f"  Model {model} gave 404 not found.")
            else:
                log(f"  Model {model} failed with status {res.status_code}: {res.text[:100]}")
        except Exception as e:
            log(f"  Exception with {model}: {e}")
            
    return None

def extract_local_text(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    log(f"Local extraction for {filepath} with ext {ext}")
    try:
        if ext in ['.xls', '.xlsx', '.xlsm']:
            import pandas as pd
            engine = 'xlrd' if ext == '.xls' else 'openpyxl'
            dfs = pd.read_excel(filepath, sheet_name=None, engine=engine)
            output = f"# Data from {os.path.basename(filepath)}\n\n"
            for sheet_name, df in dfs.items():
                output += f"## Sheet: {sheet_name}\n\n"
                
                # Format to Markdown table rather than pure CSV to help the LLM out if possible
                try:
                    output += df.to_markdown(index=False) + "\n\n"
                except ImportError:
                    # Fallback to CSV format if tabulate is missing
                    output += df.to_csv(index=False) + "\n\n"
                    
            return output
        elif ext == '.docx':
            import docx
            doc = docx.Document(filepath)
            output = f"# Document: {os.path.basename(filepath)}\n\n"
            for para in doc.paragraphs:
                if para.text.strip():
                    output += para.text + "\n"
            tables_out = ""
            for table in doc.tables:
                for row in table.rows:
                    tables_out += " | ".join([cell.text.replace("\n", " ").strip() for cell in row.cells]) + "\n"
                tables_out += "\n"
            if tables_out:
                output += "\n# Tables\n" + tables_out
            return output
        elif ext in ['.txt', '.csv']:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
    except Exception as e:
        log(f"  Local extraction error: {e}")
        return None

def main():
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
    log("Starting extraction process...")
    log("Fetching free models from OpenRouter...")
    models_to_try = get_free_models()
    log(f"Found {len(models_to_try)} free models available.")
    
    for fp in FILES_TO_PROCESS:
        filename = os.path.basename(fp)
        log(f"\nProcessing {filename}...")
        if not os.path.exists(fp):
            log(f"File not found: {fp}")
            continue
            
        raw_text = extract_local_text(fp)
        if not raw_text:
            log(f"Could not locally extract {filename}, skipping.")
            continue
            
        log(f"Length of raw content: {len(raw_text)} chars. Sending to OpenRouter...")
        md_content = call_openrouter(raw_text, filename, models_to_try)
        
        if md_content:
            out_path = os.path.join(os.path.dirname(fp), f"{os.path.splitext(filename)[0]}_ai.md")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            log(f"Saved formatted markdown to {os.path.basename(out_path)}")
        else:
            log(f"Failed to format {filename} with any OpenRouter model. Proceeding to save raw extracted content as fallback...")
            out_path = os.path.join(os.path.dirname(fp), f"{os.path.splitext(filename)[0]}_raw.md")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(raw_text)
            log(f"Saved RAW extracted text to {os.path.basename(out_path)}")
            
        time.sleep(2) # Protect against immediate concurrent rate limits

if __name__ == '__main__':
    main()
