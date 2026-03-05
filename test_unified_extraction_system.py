from pathlib import Path

from unified_extraction_system import UnifiedExtractionSystem


def test_process_text_file_native(tmp_path: Path):
    input_file = tmp_path / "sample.txt"
    input_file.write_text("Hello RTGS world", encoding="utf-8")

    out_dir = tmp_path / "out"
    system = UnifiedExtractionSystem(output_dir=out_dir, openrouter_api_key="")
    artifact = system.process_file(input_file)

    assert artifact.source_layer == "native"
    assert "Hello RTGS world" in artifact.text_content
    assert (out_dir / "sample_extracted.md").exists()


def test_process_folder_report(tmp_path: Path):
    (tmp_path / "a.txt").write_text("A", encoding="utf-8")
    (tmp_path / "b.csv").write_text("col1,col2\n1,2\n", encoding="utf-8")

    out_dir = tmp_path / "out"
    system = UnifiedExtractionSystem(output_dir=out_dir, openrouter_api_key="")
    report = system.process_folder(tmp_path)

    assert report.total_files == 2
    assert report.succeeded == 2
    assert report.failed == 0
    assert (out_dir / "extraction_report.json").exists()
