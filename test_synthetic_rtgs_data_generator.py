from datetime import date
from pathlib import Path

from synthetic_rtgs_data_generator import build_customers, generate_dataset


def test_generate_two_year_dataset_shape(tmp_path: Path):
    customers = build_customers(40, __import__("random").Random(42))
    stats = generate_dataset(
        start_date=date(2025, 1, 1),
        end_date=date(2026, 12, 31),
        customers=customers,
        out_dir=tmp_path,
        base_daily_txn=20,
        seed=42,
    )

    assert stats["transactions"] > 10000
    assert stats["transactions"] == stats["open_items"] == stats["reconciliations"] == stats["policy_events"]
    assert stats["graph_edges"] == stats["transactions"] * 5

    required = [
        "rtgs_transactions.csv",
        "sap_open_items.csv",
        "reconciliation_outcomes.csv",
        "policy_audit_log.csv",
        "graph_edges.csv",
    ]
    for file_name in required:
        assert (tmp_path / file_name).exists()
