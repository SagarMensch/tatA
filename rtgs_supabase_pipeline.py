from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from synthetic_rtgs_data_generator import build_customers, generate_dataset
from datetime import date
import random

DDL_STATEMENTS = [
    """
    create schema if not exists raw_ingestion;
    create schema if not exists curated_finance;
    create schema if not exists audit_policy;
    """,
    """
    create table if not exists raw_ingestion.rtgs_transactions (
        txn_id text primary key,
        txn_ts timestamptz not null,
        value_date date not null,
        ca_number text not null,
        bp_number text not null,
        channel text not null,
        amount numeric(18,2) not null,
        currency text not null,
        narration text,
        bank_ref text,
        ifsc text,
        city text,
        source_file text,
        ingested_at timestamptz default now()
    );
    """,
    """
    create table if not exists curated_finance.sap_open_items (
        open_item_id text primary key,
        ca_number text not null,
        bp_number text not null,
        posting_date date not null,
        due_date date not null,
        expected_amount numeric(18,2) not null,
        gl_account text,
        profit_center text,
        business_area text,
        customer_name text,
        sap_doc_type text,
        ingested_at timestamptz default now()
    );
    """,
    """
    create table if not exists curated_finance.reconciliation_outcomes (
        recon_id text primary key,
        txn_id text not null references raw_ingestion.rtgs_transactions(txn_id),
        open_item_id text not null references curated_finance.sap_open_items(open_item_id),
        confidence numeric(8,4) not null,
        amount_delta numeric(18,2) not null,
        date_gap_days int not null,
        lane text not null,
        action text not null,
        match_status text not null,
        model_version text,
        rule_reason text,
        ingested_at timestamptz default now()
    );
    """,
    """
    create table if not exists audit_policy.policy_audit_log (
        event_id text primary key,
        txn_id text not null references raw_ingestion.rtgs_transactions(txn_id),
        policy_name text not null,
        decision text not null,
        human_override text,
        approver_id text,
        approved_at timestamptz,
        notes text,
        ingested_at timestamptz default now()
    );
    """,
]


def build_session_pooler_url(project_ref: str, password: str, region: str = "aws-1-ap-southeast-2") -> str:
    return (
        f"postgresql://postgres.{project_ref}:{password}@"
        f"{region}.pooler.supabase.com:5432/postgres"
    )


def _connect(db_url: str):
    try:
        import psycopg
    except Exception as exc:
        raise RuntimeError("psycopg is required. Install with: pip install psycopg[binary]") from exc
    return psycopg.connect(db_url)


def apply_schema(db_url: str) -> None:
    with _connect(db_url) as conn:
        with conn.cursor() as cur:
            for stmt in DDL_STATEMENTS:
                cur.execute(stmt)
        conn.commit()


def _copy_csv(cur, table_name: str, columns: List[str], csv_path: Path) -> int:
    row_count = 0
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        with cur.copy(f"COPY {table_name} ({', '.join(columns)}) FROM STDIN WITH (FORMAT CSV)") as copy:
            for row in reader:
                copy.write_row([row.get(c, "") for c in columns])
                row_count += 1
    return row_count


def load_synthetic_csvs(db_url: str, data_dir: Path) -> Dict[str, int]:
    mapping: List[Tuple[str, str, List[str]]] = [
        (
            "rtgs_transactions.csv",
            "raw_ingestion.rtgs_transactions",
            [
                "txn_id",
                "txn_ts",
                "value_date",
                "ca_number",
                "bp_number",
                "channel",
                "amount",
                "currency",
                "narration",
                "bank_ref",
                "ifsc",
                "city",
                "source_file",
            ],
        ),
        (
            "sap_open_items.csv",
            "curated_finance.sap_open_items",
            [
                "open_item_id",
                "ca_number",
                "bp_number",
                "posting_date",
                "due_date",
                "expected_amount",
                "gl_account",
                "profit_center",
                "business_area",
                "customer_name",
                "sap_doc_type",
            ],
        ),
        (
            "reconciliation_outcomes.csv",
            "curated_finance.reconciliation_outcomes",
            [
                "recon_id",
                "txn_id",
                "open_item_id",
                "confidence",
                "amount_delta",
                "date_gap_days",
                "lane",
                "action",
                "match_status",
                "model_version",
                "rule_reason",
            ],
        ),
        (
            "policy_audit_log.csv",
            "audit_policy.policy_audit_log",
            [
                "event_id",
                "txn_id",
                "policy_name",
                "decision",
                "human_override",
                "approver_id",
                "approved_at",
                "notes",
            ],
        ),
    ]

    out: Dict[str, int] = {}
    with _connect(db_url) as conn:
        with conn.cursor() as cur:
            for file_name, table_name, columns in mapping:
                p = data_dir / file_name
                if not p.exists():
                    raise FileNotFoundError(f"missing input file: {p}")
                out[table_name] = _copy_csv(cur, table_name, columns, p)
        conn.commit()
    return out


def ensure_synthetic_data(data_dir: Path) -> None:
    required = [
        data_dir / "rtgs_transactions.csv",
        data_dir / "sap_open_items.csv",
        data_dir / "reconciliation_outcomes.csv",
        data_dir / "policy_audit_log.csv",
    ]
    if all(p.exists() for p in required):
        return
    customers = build_customers(250, random.Random(42))
    generate_dataset(
        start_date=date(2025, 1, 1),
        end_date=date(2026, 12, 31),
        customers=customers,
        out_dir=data_dir,
        base_daily_txn=60,
        seed=42,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy RTGS schema and synthetic data to Supabase Postgres")
    parser.add_argument("--db-url", default=os.getenv("SUPABASE_DB_URL", ""))
    parser.add_argument("--project-ref", default=os.getenv("SUPABASE_PROJECT_REF", ""))
    parser.add_argument("--password", default=os.getenv("SUPABASE_DB_PASSWORD", ""))
    parser.add_argument("--region", default=os.getenv("SUPABASE_REGION", "aws-1-ap-southeast-2"))
    parser.add_argument("--data-dir", default="synthetic_rtgs_data")
    parser.add_argument("--schema-only", action="store_true")
    args = parser.parse_args()

    db_url = args.db_url
    if not db_url and args.project_ref and args.password:
        db_url = build_session_pooler_url(args.project_ref, args.password, args.region)
    if not db_url:
        raise ValueError("Provide --db-url or (SUPABASE_PROJECT_REF + SUPABASE_DB_PASSWORD)")

    apply_schema(db_url)
    print("Schema applied successfully")

    if args.schema_only:
        return

    data_dir = Path(args.data_dir)
    ensure_synthetic_data(data_dir)
    counts = load_synthetic_csvs(db_url, data_dir)
    print("Loaded rows:")
    for k, v in counts.items():
        print(f"- {k}: {v}")


if __name__ == "__main__":
    main()
