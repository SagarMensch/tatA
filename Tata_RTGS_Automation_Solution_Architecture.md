# Tata Power - RTGS/NEFT Payment Automation Architecture
**Solution Design Document**

**Prepared For:** Tata Power SAP FICO Team  
**Business Owner:** Mr. Dilip Lohani  
**Target Process:** RTGS / NEFT / IMPS Automated SAP Reconciliation  

---

## 1. Executive Summary
Currently, the RTGS/NEFT/IMPS payment matching process is highly manual, requiring daily extraction of encrypted bank statements, manual filtering of UPI transactions, creation of a consolidated Master File, and manual VLOOKUP reconciliation against SAP export data (T-Code **ZCARP076**). This process consumes approximately 3 hours per day.

**The Solution:** Implement a **Neuro-Symbolic AI Agent Workflow** integrated with a **Hybrid Document Extraction Pipeline**. This solution will seamlessly automate the ingestion of bank statements, mathematically process the data, perform intelligent matching, and interface directly with SAP R/3 to execute the clearings.

---

## 2. To-Be Agentic Architecture

The automation pipeline is broken down into three core Agentic phases:

### Phase 1: Intelligent Data Ingestion (Hybrid Extractor)
The architecture utilizes a Python-based robust extraction pipeline running locally that can natively handle any document type the business receives (`.xlsx`, `.xls`, `.csv`, `.docx`, `.pdf`, `.txt`).

1. **Email Monitoring & Extraction:** The Agent monitors the designated inbox for the `StandcVA` subject line and extracts the password-protected `.zip` attachments.
2. **Dynamic Format Routing:** 
   - Uses `pandas`/`openpyxl` to natively extract tabular data from Excel statements without data loss.
   - For unstructured or scanned PDFs/Docs, it routes through a rigorous CPU-optimized **PaddleOCR** pipeline (with OpenCV deskewing and adaptive thresholding).
3. **Multimodal Vision Parsing:** Any complex embedded screenshots or diagrams found within the documents are intelligently analyzed using a Vision-Language Model (Nemotron-12B-VL) to transcribe SAP screenshots natively into Markdown tables.

### Phase 2: Neuro-Symbolic Data Processing & Master File Consolidation
Once the daily bank statement is converted into a structured Markdown/JSON payload, the Agent applies strict symbolic (deterministic) business logic:

1. **UPI Filtration:** The Agent scans the `Transaction UPI COLLECTIONS` column. It mathematically drops rows where the description is strictly `"UPI"`. It retains rows like `"CR UPI/553214622199..."` as per business rules.
2. **Master File Aggregation:** The Agent appends the filtered daily transactions to the continuously maintained RTGS Master Dataset, dropping any duplicated legacy entries.
3. **Account Targeting:** The Agent isolates only the `'9'` series CA Numbers required for the subsequent SAP clearing operation.

### Phase 3: SAP R/3 Agentic Execution
The Agent interfaces directly with the SAP GUI (via Python win32com or SAP Scripting API) to execute the final steps:

1. **SAP Export:** The Agent executes T-Code **ZCARP076**. It dynamically enters the required date ranges (e.g., Start of Month to End of Month) to pull the target SAP reconciliation lot.
2. **Automated VLOOKUP/Reconciliation:** The Agent uses Pandas to perform deterministic joins (`VLOOKUP`) between the day-to-day Master File and the newly exported SAP ZCARP076 dataset based on CA number and Date.
3. **Posting & Clearing:** Upon identifying successful matches, the Agent formats the final upload file (mimicking the required SAP upload format) and triggers the automated posting routine within SAP FICO. 
4. **Audit Reporting:** A daily exception report is generated outlining unmatched CA numbers or anomalies and emailed directly to the Accounts Receivable team.

---

## 3. Technology Stack

- **Orchestration / Logic Layer:** Python 3.11, Pandas (for deterministic table matching)
- **Document Ingestion:** `PyMuPDF` (PDFs), `python-docx` (Word), `pandas`/`openpyxl`/`xlrd` (Excel).
- **Computer Vision / OCR:** OpenCV (preprocessing), PaddleOCR PP-OCRv4 (CPU-optimized text extraction).
- **Generative AI (VLM):** Nvidia Nemotron-Nano-12B-VL (For intelligently parsing embedded screenshots/images).
- **SAP Integration:** SAP GUI Scripting API (VBScript/Python win32com).

---

## 4. Business Benefits & ROI
- **Zero Data Entry Errors:** Eliminates human transposition errors during VLOOKUPs and manual clearing.
- **Time Savings:** Reclaims an average of 3 hours per day for the SAP FICO team.
- **High-Volume Scalability:** Readily absorbs month-end spikes in transaction volume without requiring additional headcount. 
- **Deterministic Reliability:** Because the pipeline relies on hybrid native parsing and strict symbolic logic (rather than pure unstructured LLMs for the matching phase), the accuracy is guaranteed for financial reconciliation.
