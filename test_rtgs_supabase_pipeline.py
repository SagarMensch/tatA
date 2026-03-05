from pathlib import Path

import rtgs_supabase_pipeline as sup


def test_build_session_pooler_url():
    url = sup.build_session_pooler_url("kyobidaobfnngvzrkvpx", "secret", "aws-1-ap-southeast-2")
    assert "postgres.kyobidaobfnngvzrkvpx:secret" in url
    assert url.endswith("/postgres")


def test_ensure_synthetic_data_skips_when_files_exist(tmp_path: Path):
    for f in [
        "rtgs_transactions.csv",
        "sap_open_items.csv",
        "reconciliation_outcomes.csv",
        "policy_audit_log.csv",
    ]:
        (tmp_path / f).write_text("x")

    sup.ensure_synthetic_data(tmp_path)
    assert (tmp_path / "rtgs_transactions.csv").read_text() == "x"
