from __future__ import annotations

from dataclasses import asdict
from typing import Dict, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from advanced_rtgs_ml_engine import OpenItem, Transaction
from rtgs_agent_runtime import (
    RTGSAgentOrchestrator,
    build_demo_open_items,
    build_demo_transaction,
)
from synthetic_rtgs_data_generator import build_customers, generate_dataset
from rtgs_supabase_pipeline import apply_schema, ensure_synthetic_data, load_synthetic_csvs
from rtgs_neo4j_pipeline import apply_schema as apply_neo4j_schema, load_graph_edges, wait_and_validate_connection
import os

from datetime import date
from pathlib import Path
import random

app = FastAPI(title="RTGS Agentic API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = RTGSAgentOrchestrator()
agent.warm_start()


class TxnIn(BaseModel):
    txn_id: str
    ca_number: str
    amount: float
    txn_date: str
    description: str
    channel: str


class OpenItemIn(BaseModel):
    item_id: str
    ca_number: str
    expected_amount: float
    due_date: str
    customer_name: str


class ReconcileRequest(BaseModel):
    transaction: TxnIn
    open_items: List[OpenItemIn]
    historical_hit_ratio_lookup: Dict[str, float] = {}


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "rtgs-agentic-api"}


@app.get("/demo/reconcile")
def demo_reconcile() -> Dict[str, object]:
    result = agent.reconcile_one(
        build_demo_transaction(),
        build_demo_open_items(),
        {"81234567": 0.6, "90009999": 0.95},
    )
    return agent.as_payload(result)


@app.post("/reconcile")
def reconcile(req: ReconcileRequest) -> Dict[str, object]:
    txn = Transaction(
        txn_id=req.transaction.txn_id,
        ca_number=req.transaction.ca_number,
        amount=req.transaction.amount,
        txn_date=date.fromisoformat(req.transaction.txn_date),
        description=req.transaction.description,
        channel=req.transaction.channel,
    )
    items = [
        OpenItem(
            item_id=i.item_id,
            ca_number=i.ca_number,
            expected_amount=i.expected_amount,
            due_date=date.fromisoformat(i.due_date),
            customer_name=i.customer_name,
        )
        for i in req.open_items
    ]

    result = agent.reconcile_one(txn, items, req.historical_hit_ratio_lookup)
    return agent.as_payload(result)


@app.post("/generate/synthetic")
def generate_synthetic() -> Dict[str, int]:
    customers = build_customers(200, random.Random(42))
    return generate_dataset(
        start_date=date(2025, 1, 1),
        end_date=date(2026, 12, 31),
        customers=customers,
        out_dir=Path("synthetic_rtgs_data"),
        base_daily_txn=60,
        seed=42,
    )


@app.post("/deploy/supabase")
def deploy_supabase() -> Dict[str, object]:
    db_url = os.getenv("SUPABASE_DB_URL", "")
    if not db_url:
        return {"status": "error", "message": "SUPABASE_DB_URL env var is required"}

    data_dir = Path("synthetic_rtgs_data")
    apply_schema(db_url)
    ensure_synthetic_data(data_dir)
    counts = load_synthetic_csvs(db_url, data_dir)
    return {"status": "ok", "loaded": counts}


@app.post("/deploy/neo4j")
def deploy_neo4j(wait_seconds: int = 60) -> Dict[str, object]:
    uri = os.getenv("NEO4J_URI", "")
    username = os.getenv("NEO4J_USERNAME", "")
    password = os.getenv("NEO4J_PASSWORD", "")
    database = os.getenv("NEO4J_DATABASE", "neo4j")

    if not uri or not username or not password:
        return {"status": "error", "message": "NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD are required"}

    conn = wait_and_validate_connection(uri, username, password, database, wait_seconds=wait_seconds)

    data_dir = Path("synthetic_rtgs_data")
    ensure_synthetic_data(data_dir)
    edge_file = data_dir / "graph_edges.csv"
    apply_neo4j_schema(uri, username, password, database)
    loaded = load_graph_edges(uri, username, password, database, edge_file)
    return {"status": "ok", "connectivity": conn, "loaded_edges": loaded}
