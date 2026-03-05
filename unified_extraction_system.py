"""Unified document extraction system for RTGS workloads.

Architecture:
1) Layer-1 (always first): Docling conversion attempt
2) Layer-2: Native deterministic extraction by file type
3) Layer-3: Optional LLM enrichment via OpenRouter (rate-limit aware)

Supported input families:
- Documents: .pdf, .docx, .txt, .md
- Spreadsheets: .xlsx, .xls, .csv
- Images: .png, .jpg, .jpeg, .bmp, .tiff
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SUPPORTED_DOCS = {".pdf", ".docx", ".txt", ".md"}
SUPPORTED_SHEETS = {".xlsx", ".xls", ".csv"}
SUPPORTED_IMAGES = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"}
ALL_SUPPORTED = SUPPORTED_DOCS | SUPPORTED_SHEETS | SUPPORTED_IMAGES


@dataclass
class ExtractionArtifact:
    file_path: str
    source_layer: str
    text_content: str
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class ExtractionReport:
    artifacts: List[ExtractionArtifact]
    total_files: int
    succeeded: int
    failed: int


class DoclingLayer:
    """Layer-1 extractor. Always attempted first for supported files."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir

    def extract(self, file_path: Path) -> Optional[str]:
        docling_md = self.output_dir / f"{file_path.stem}_docling.md"
        cmd = [
            "python",
            "-m",
            "docling",
            "convert",
            str(file_path),
            "--to",
            "markdown",
            "--output",
            str(docling_md),
        ]
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if completed.returncode == 0 and docling_md.exists():
                return docling_md.read_text(encoding="utf-8", errors="ignore")
            return None
        except Exception:
            return None


class NativeExtractionLayer:
    """Layer-2 deterministic extraction if Docling output is unavailable."""

    @staticmethod
    def _read_text(path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="ignore")

    @staticmethod
    def _read_csv(path: Path) -> str:
        rows: List[List[str]] = []
        with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
            reader = csv.reader(f)
            for idx, row in enumerate(reader):
                rows.append(row)
                if idx > 2000:
                    break
        return "\n".join(",".join(cell.strip() for cell in row) for row in rows)

    @staticmethod
    def _read_spreadsheet(path: Path) -> str:
        import pandas as pd

        try:
            sheets = pd.read_excel(path, sheet_name=None)
        except Exception:
            return ""

        blocks: List[str] = []
        for sheet_name, df in sheets.items():
            blocks.append(f"## Sheet: {sheet_name}")
            blocks.append(df.head(3000).to_csv(index=False))
        return "\n".join(blocks)

    @staticmethod
    def _read_docx(path: Path) -> str:
        from docx import Document

        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    @staticmethod
    def _read_pdf(path: Path) -> str:
        import fitz

        doc = fitz.open(str(path))
        pages: List[str] = []
        for p in doc:
            pages.append(p.get_text("text"))
        return "\n".join(pages)

    @staticmethod
    def _read_image(path: Path) -> str:
        # Keep dependency-light; return placeholder when OCR dependencies are absent.
        return f"[IMAGE_INPUT] {path.name} (OCR integration required for full text extraction)"

    def extract(self, file_path: Path) -> str:
        ext = file_path.suffix.lower()
        if ext in {".txt", ".md"}:
            return self._read_text(file_path)
        if ext == ".csv":
            return self._read_csv(file_path)
        if ext in {".xlsx", ".xls"}:
            return self._read_spreadsheet(file_path)
        if ext == ".docx":
            return self._read_docx(file_path)
        if ext == ".pdf":
            return self._read_pdf(file_path)
        if ext in SUPPORTED_IMAGES:
            return self._read_image(file_path)
        return ""


class OpenRouterLLMLayer:
    """Layer-3 enrichment with backoff and free-model rotation."""

    def __init__(self, api_key: str, timeout_s: int = 60) -> None:
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.models = [
            "meta-llama/llama-3.1-8b-instruct:free",
            "microsoft/phi-3-mini-128k-instruct:free",
            "google/gemma-2-9b-it:free",
        ]

    def _post_chat(self, model: str, prompt: str) -> str:
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a financial document extraction normalizer. Return concise structured markdown.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
        }
        data = json.dumps(payload).encode("utf-8")
        req = Request(
            url="https://openrouter.ai/api/v1/chat/completions",
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/SagarMensch/tatA",
                "X-Title": "RTGS Unified Extraction",
            },
        )
        with urlopen(req, timeout=self.timeout_s) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            parsed = json.loads(body)
            return parsed["choices"][0]["message"]["content"]

    def enrich(self, raw_text: str, file_name: str, max_retries: int = 4) -> str:
        prompt = (
            f"File: {file_name}\n"
            "Normalize this extracted text into markdown sections: Summary, Key Tables,"
            " Financial Entities (CA/BP/Amount/Date), and Exceptions.\n\n"
            f"RAW:\n{raw_text[:12000]}"
        )

        last_error = ""
        for model in self.models:
            for attempt in range(max_retries):
                try:
                    return self._post_chat(model, prompt)
                except HTTPError as err:
                    last_error = f"HTTP {err.code}"
                    if err.code in {429, 500, 502, 503, 504}:
                        time.sleep(min(20, 2 ** attempt))
                        continue
                    break
                except URLError as err:
                    last_error = f"URLError {err.reason}"
                    time.sleep(min(20, 2 ** attempt))
                except Exception as err:
                    last_error = str(err)
                    break
        return f"[LLM_ENRICHMENT_SKIPPED] {last_error}\n\n{raw_text[:5000]}"


class UnifiedExtractionSystem:
    def __init__(self, output_dir: Path, openrouter_api_key: str = "") -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.docling = DoclingLayer(output_dir=output_dir)
        self.native = NativeExtractionLayer()
        self.llm = OpenRouterLLMLayer(openrouter_api_key) if openrouter_api_key else None

    def process_file(self, file_path: Path) -> ExtractionArtifact:
        ext = file_path.suffix.lower()
        if ext not in ALL_SUPPORTED:
            return ExtractionArtifact(
                file_path=str(file_path),
                source_layer="unsupported",
                text_content="",
                metadata={"status": "skipped", "reason": "unsupported_extension"},
            )

        # Layer 1: Docling first (always attempted)
        docling_text = self.docling.extract(file_path)
        if docling_text:
            source = "docling"
            raw_text = docling_text
        else:
            source = "native"
            raw_text = self.native.extract(file_path)

        final_text = raw_text
        if self.llm and raw_text.strip():
            final_text = self.llm.enrich(raw_text=raw_text, file_name=file_path.name)
            source = f"{source}+openrouter"

        out_file = self.output_dir / f"{file_path.stem}_extracted.md"
        out_file.write_text(final_text, encoding="utf-8")

        return ExtractionArtifact(
            file_path=str(file_path),
            source_layer=source,
            text_content=final_text,
            metadata={"output_file": str(out_file), "status": "ok"},
        )

    def process_folder(self, input_dir: Path) -> ExtractionReport:
        artifacts: List[ExtractionArtifact] = []
        files = sorted(p for p in input_dir.iterdir() if p.is_file())
        for f in files:
            artifacts.append(self.process_file(f))
        succeeded = sum(1 for a in artifacts if a.metadata.get("status") == "ok")
        failed = len(artifacts) - succeeded
        report = ExtractionReport(
            artifacts=artifacts,
            total_files=len(files),
            succeeded=succeeded,
            failed=failed,
        )

        report_path = self.output_dir / "extraction_report.json"
        report_path.write_text(
            json.dumps(
                {
                    "total_files": report.total_files,
                    "succeeded": report.succeeded,
                    "failed": report.failed,
                    "artifacts": [asdict(x) for x in report.artifacts],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Docling-first unified extraction system")
    parser.add_argument("input", help="Input file or folder")
    parser.add_argument("--output-dir", default="unified_extraction_output")
    parser.add_argument("--openrouter-key", default=os.getenv("OPENROUTER_API_KEY", ""))
    args = parser.parse_args()

    system = UnifiedExtractionSystem(
        output_dir=Path(args.output_dir),
        openrouter_api_key=args.openrouter_key,
    )

    path = Path(args.input)
    if path.is_file():
        artifact = system.process_file(path)
        print(json.dumps(asdict(artifact), indent=2))
    elif path.is_dir():
        report = system.process_folder(path)
        print(json.dumps(asdict(report), indent=2))
    else:
        raise FileNotFoundError(f"Input path not found: {path}")


if __name__ == "__main__":
    main()
