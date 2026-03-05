"""Generate 2-year synthetic RTGS/NEFT/IMPS reconciliation data.

Outputs finance-authentic, SAP-oriented datasets:
- rtgs_transactions.csv
- sap_open_items.csv
- reconciliation_outcomes.csv
- policy_audit_log.csv
- graph_edges.csv

The data is designed for:
1) ML training (match confidence / anomaly detection)
2) Rule-engine validation
3) Graph analytics over payment relationships
4) PostgreSQL warehousing and BI
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

SEED = 42
CHANNELS = ["RTGS", "NEFT", "IMPS"]
LANES = ["GREEN", "YELLOW", "RED"]
POLICIES = [
    "AUTO_POST_FP25",
    "AUTO_WRITE_OFF_AND_POST",
    "PARK_AND_NOTIFY_APPROVER",
    "ESCALATE_TO_CONCERN_TEAM",
]


@dataclass
class Customer:
    ca_number: str
    bp_number: str
    customer_name: str
    segment: str
    city: str
    bank_ifsc: str
    account_masked: str


def daterange(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def random_ifsc(rng: random.Random) -> str:
    bank = rng.choice(["HDFC", "ICIC", "SBIN", "UTIB", "KKBK", "PUNB"])
    return f"{bank}0{rng.randint(1000, 9999)}"


def build_customers(count: int, rng: random.Random) -> List[Customer]:
    cities = ["Mumbai", "Delhi", "Pune", "Chennai", "Kolkata", "Noida", "Bengaluru"]
    segments = ["Industrial", "Commercial", "Residential", "Government"]
    customers: List[Customer] = []
    for idx in range(count):
        ca = f"9{rng.randint(1000000, 9999999)}"
        bp = f"BP{rng.randint(100000, 999999)}"
        customers.append(
            Customer(
                ca_number=ca,
                bp_number=bp,
                customer_name=f"Customer_{idx:04d}_Energy",
                segment=rng.choice(segments),
                city=rng.choice(cities),
                bank_ifsc=random_ifsc(rng),
                account_masked=f"XXXXXX{rng.randint(1000,9999)}",
            )
        )
    return customers


def seasonal_multiplier(day: date) -> float:
    month = day.month
    # Month-end and quarter-end pressure patterns for utilities.
    if month in (3, 6, 9, 12):
        return 1.25
    if month in (1, 4, 7, 10):
        return 1.05
    return 0.95


def generate_dataset(
    start_date: date,
    end_date: date,
    customers: List[Customer],
    out_dir: Path,
    base_daily_txn: int,
    seed: int = SEED,
) -> Dict[str, int]:
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    tx_path = out_dir / "rtgs_transactions.csv"
    open_item_path = out_dir / "sap_open_items.csv"
    recon_path = out_dir / "reconciliation_outcomes.csv"
    policy_path = out_dir / "policy_audit_log.csv"
    graph_path = out_dir / "graph_edges.csv"

    tx_count = 0
    open_item_count = 0
    recon_count = 0
    policy_count = 0
    graph_count = 0

    with (
        tx_path.open("w", newline="", encoding="utf-8") as f_tx,
        open_item_path.open("w", newline="", encoding="utf-8") as f_open,
        recon_path.open("w", newline="", encoding="utf-8") as f_recon,
        policy_path.open("w", newline="", encoding="utf-8") as f_pol,
        graph_path.open("w", newline="", encoding="utf-8") as f_graph,
    ):
        tx_writer = csv.DictWriter(
            f_tx,
            fieldnames=[
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
        )
        open_writer = csv.DictWriter(
            f_open,
            fieldnames=[
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
        )
        recon_writer = csv.DictWriter(
            f_recon,
            fieldnames=[
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
        )
        policy_writer = csv.DictWriter(
            f_pol,
            fieldnames=[
                "event_id",
                "txn_id",
                "policy_name",
                "decision",
                "human_override",
                "approver_id",
                "approved_at",
                "notes",
            ],
        )
        graph_writer = csv.DictWriter(
            f_graph,
            fieldnames=[
                "src_type",
                "src_id",
                "edge_type",
                "dst_type",
                "dst_id",
                "weight",
                "edge_ts",
            ],
        )

        for writer in (tx_writer, open_writer, recon_writer, policy_writer, graph_writer):
            writer.writeheader()

        txn_idx = 1
        open_idx = 1
        for d in daterange(start_date, end_date):
            vol = max(20, int(base_daily_txn * seasonal_multiplier(d) + rng.gauss(0, 8)))
            for _ in range(vol):
                c = rng.choice(customers)
                channel = rng.choices(CHANNELS, weights=[0.45, 0.40, 0.15], k=1)[0]
                base_amt = rng.choice([1500, 2500, 5000, 7500, 10000, 15000, 25000, 50000, 100000])
                amount = round(max(1.0, base_amt * (1 + rng.uniform(-0.12, 0.18))), 2)

                # controlled anomalies
                if rng.random() < 0.01:
                    amount = round(amount * rng.uniform(5.0, 20.0), 2)

                txn_id = f"TXN{txn_idx:09d}"
                open_item_id = f"OI{open_idx:09d}"
                txn_time = datetime.combine(d, datetime.min.time()) + timedelta(
                    hours=rng.randint(8, 23), minutes=rng.randint(0, 59), seconds=rng.randint(0, 59)
                )
                due_date = d + timedelta(days=rng.randint(-3, 7))
                expected_amount = round(amount + rng.choice([0, 0, 0, 0, 2, -2, 5, -5, 10, -10, 150]), 2)
                amount_delta = abs(amount - expected_amount)
                date_gap_days = abs((d - due_date).days)

                # advanced confidence logic proxy (for synthetic labels)
                confidence = 1.0
                confidence -= min(amount_delta / max(expected_amount, 1.0), 1.0) * 0.55
                confidence -= min(date_gap_days / 10, 1.0) * 0.20
                confidence -= 0.05 if channel == "IMPS" else 0.0
                confidence += rng.uniform(-0.04, 0.04)
                confidence = min(1.0, max(0.0, round(confidence, 4)))

                if confidence >= 0.99 and amount_delta == 0:
                    lane, action, reason = "GREEN", "AUTO_POST_FP25", "green_autopost"
                elif confidence >= 0.95 and amount_delta <= 10:
                    lane, action, reason = "GREEN", "AUTO_WRITE_OFF_AND_POST", "green_small_writeoff"
                elif confidence >= 0.80 and amount_delta <= 100:
                    lane, action, reason = "YELLOW", "PARK_AND_NOTIFY_APPROVER", "yellow_manual_approval"
                else:
                    lane, action, reason = "RED", "ESCALATE_TO_CONCERN_TEAM", "red_investigation"

                match_status = "MATCHED" if lane in ("GREEN", "YELLOW") else "EXCEPTION"

                tx_writer.writerow(
                    {
                        "txn_id": txn_id,
                        "txn_ts": txn_time.isoformat(),
                        "value_date": d.isoformat(),
                        "ca_number": c.ca_number,
                        "bp_number": c.bp_number,
                        "channel": channel,
                        "amount": amount,
                        "currency": "INR",
                        "narration": f"{channel} COLLECTION {c.customer_name} SAP-AR",
                        "bank_ref": f"BR{rng.randint(1000000000, 9999999999)}",
                        "ifsc": c.bank_ifsc,
                        "city": c.city,
                        "source_file": f"StandcVA_{d.strftime('%Y%m%d')}.xlsx",
                    }
                )
                tx_count += 1

                open_writer.writerow(
                    {
                        "open_item_id": open_item_id,
                        "ca_number": c.ca_number,
                        "bp_number": c.bp_number,
                        "posting_date": d.isoformat(),
                        "due_date": due_date.isoformat(),
                        "expected_amount": expected_amount,
                        "gl_account": rng.choice(["110100", "110200", "110500"]),
                        "profit_center": f"PC{rng.randint(1000,1099)}",
                        "business_area": rng.choice(["MUM1", "DEL1", "PUN1", "CHN1"]),
                        "customer_name": c.customer_name,
                        "sap_doc_type": rng.choice(["DZ", "DR", "RV"]),
                    }
                )
                open_item_count += 1

                recon_id = f"RCN{txn_idx:09d}"
                recon_writer.writerow(
                    {
                        "recon_id": recon_id,
                        "txn_id": txn_id,
                        "open_item_id": open_item_id,
                        "confidence": confidence,
                        "amount_delta": round(amount_delta, 2),
                        "date_gap_days": date_gap_days,
                        "lane": lane,
                        "action": action,
                        "match_status": match_status,
                        "model_version": "rtgs-neuro-symbolic-v2.1",
                        "rule_reason": reason,
                    }
                )
                recon_count += 1

                override = "N"
                approver = ""
                approved_at = ""
                notes = ""
                if lane == "YELLOW":
                    override = rng.choice(["N", "Y"])
                    if override == "Y":
                        approver = f"AR{rng.randint(1001,1099)}"
                        approved_at = (
                            txn_time + timedelta(minutes=rng.randint(15, 240))
                        ).isoformat()
                        notes = "Approved after variance validation and NCC cross-check."
                elif lane == "RED":
                    notes = "Escalated for investigation: possible unknown VA or anomaly."

                policy_writer.writerow(
                    {
                        "event_id": f"POL{txn_idx:09d}",
                        "txn_id": txn_id,
                        "policy_name": reason,
                        "decision": action,
                        "human_override": override,
                        "approver_id": approver,
                        "approved_at": approved_at,
                        "notes": notes,
                    }
                )
                policy_count += 1

                # graph edges for Graph AI
                edges = [
                    ("TRANSACTION", txn_id, "BELONGS_TO", "CUSTOMER", c.ca_number, 1.0),
                    ("TRANSACTION", txn_id, "MATCHED_TO", "OPEN_ITEM", open_item_id, confidence),
                    ("CUSTOMER", c.ca_number, "USES_IFSC", "BANK_IFSC", c.bank_ifsc, 1.0),
                    ("TRANSACTION", txn_id, "RISK_LANE", "LANE", lane, 1.0),
                    ("TRANSACTION", txn_id, "DECIDED_BY", "POLICY", reason, 1.0),
                ]
                for src_t, src_id, e_t, dst_t, dst_id, w in edges:
                    graph_writer.writerow(
                        {
                            "src_type": src_t,
                            "src_id": src_id,
                            "edge_type": e_t,
                            "dst_type": dst_t,
                            "dst_id": dst_id,
                            "weight": round(float(w), 4),
                            "edge_ts": txn_time.isoformat(),
                        }
                    )
                    graph_count += 1

                txn_idx += 1
                open_idx += 1

    return {
        "transactions": tx_count,
        "open_items": open_item_count,
        "reconciliations": recon_count,
        "policy_events": policy_count,
        "graph_edges": graph_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic RTGS data for 2 years")
    parser.add_argument("--start", default="2025-01-01")
    parser.add_argument("--end", default="2026-12-31")
    parser.add_argument("--customers", type=int, default=800)
    parser.add_argument("--base-daily-txn", type=int, default=140)
    parser.add_argument("--out-dir", default="synthetic_rtgs_data")
    args = parser.parse_args()

    start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end, "%Y-%m-%d").date()
    if end_date < start_date:
        raise ValueError("end date must be >= start date")

    rng = random.Random(SEED)
    customers = build_customers(args.customers, rng)
    stats = generate_dataset(
        start_date=start_date,
        end_date=end_date,
        customers=customers,
        out_dir=Path(args.out_dir),
        base_daily_txn=args.base_daily_txn,
        seed=SEED,
    )

    print("Synthetic RTGS data generated successfully")
    for k, v in stats.items():
        print(f"- {k}: {v}")


if __name__ == "__main__":
    main()
