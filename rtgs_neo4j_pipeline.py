from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import Dict


def _driver(uri: str, username: str, password: str):
    try:
        from neo4j import GraphDatabase
    except Exception as exc:
        raise RuntimeError("neo4j driver required. Install with: pip install neo4j") from exc
    return GraphDatabase.driver(uri, auth=(username, password))


def wait_and_validate_connection(uri: str, username: str, password: str, database: str, wait_seconds: int = 60) -> Dict[str, str]:
    import time

    time.sleep(wait_seconds)
    with _driver(uri, username, password) as drv:
        drv.verify_connectivity()
        with drv.session(database=database) as session:
            val = session.run("RETURN 'ok' AS status").single()
    return {"status": val["status"], "database": database, "uri": uri}


def apply_schema(uri: str, username: str, password: str, database: str) -> None:
    statements = [
        "CREATE CONSTRAINT txn_id_unique IF NOT EXISTS FOR (n:Transaction) REQUIRE n.txn_id IS UNIQUE",
        "CREATE CONSTRAINT customer_ca_unique IF NOT EXISTS FOR (n:Customer) REQUIRE n.ca_number IS UNIQUE",
        "CREATE CONSTRAINT open_item_unique IF NOT EXISTS FOR (n:OpenItem) REQUIRE n.open_item_id IS UNIQUE",
        "CREATE CONSTRAINT bank_ifsc_unique IF NOT EXISTS FOR (n:BankIFSC) REQUIRE n.ifsc IS UNIQUE",
        "CREATE CONSTRAINT lane_name_unique IF NOT EXISTS FOR (n:Lane) REQUIRE n.name IS UNIQUE",
        "CREATE CONSTRAINT policy_name_unique IF NOT EXISTS FOR (n:Policy) REQUIRE n.name IS UNIQUE",
    ]
    with _driver(uri, username, password) as drv:
        with drv.session(database=database) as session:
            for q in statements:
                session.run(q)


def load_graph_edges(uri: str, username: str, password: str, database: str, csv_path: Path) -> int:
    if not csv_path.exists():
        raise FileNotFoundError(f"graph edge file not found: {csv_path}")

    count = 0
    with _driver(uri, username, password) as drv:
        with drv.session(database=database) as session:
            with csv_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    src_type = row["src_type"]
                    src_id = row["src_id"]
                    edge_type = row["edge_type"]
                    dst_type = row["dst_type"]
                    dst_id = row["dst_id"]
                    weight = float(row.get("weight", "1") or 1)
                    edge_ts = row.get("edge_ts", "")

                    # Node upserts by type
                    if src_type == "TRANSACTION":
                        session.run("MERGE (n:Transaction {txn_id:$id})", id=src_id)
                    elif src_type == "CUSTOMER":
                        session.run("MERGE (n:Customer {ca_number:$id})", id=src_id)
                    else:
                        session.run("MERGE (n:Entity {id:$id, kind:$kind})", id=src_id, kind=src_type)

                    if dst_type == "OPEN_ITEM":
                        session.run("MERGE (n:OpenItem {open_item_id:$id})", id=dst_id)
                    elif dst_type == "BANK_IFSC":
                        session.run("MERGE (n:BankIFSC {ifsc:$id})", id=dst_id)
                    elif dst_type == "LANE":
                        session.run("MERGE (n:Lane {name:$id})", id=dst_id)
                    elif dst_type == "POLICY":
                        session.run("MERGE (n:Policy {name:$id})", id=dst_id)
                    elif dst_type == "CUSTOMER":
                        session.run("MERGE (n:Customer {ca_number:$id})", id=dst_id)
                    elif dst_type == "TRANSACTION":
                        session.run("MERGE (n:Transaction {txn_id:$id})", id=dst_id)
                    else:
                        session.run("MERGE (n:Entity {id:$id, kind:$kind})", id=dst_id, kind=dst_type)

                    # Relationship write by known pairs + fallback generic
                    if src_type == "TRANSACTION" and dst_type == "CUSTOMER" and edge_type == "BELONGS_TO":
                        session.run(
                            """
                            MATCH (s:Transaction {txn_id:$src}), (d:Customer {ca_number:$dst})
                            MERGE (s)-[r:BELONGS_TO]->(d)
                            SET r.weight=$weight, r.edge_ts=$edge_ts
                            """,
                            src=src_id,
                            dst=dst_id,
                            weight=weight,
                            edge_ts=edge_ts,
                        )
                    elif src_type == "TRANSACTION" and dst_type == "OPEN_ITEM" and edge_type == "MATCHED_TO":
                        session.run(
                            """
                            MATCH (s:Transaction {txn_id:$src}), (d:OpenItem {open_item_id:$dst})
                            MERGE (s)-[r:MATCHED_TO]->(d)
                            SET r.weight=$weight, r.edge_ts=$edge_ts
                            """,
                            src=src_id,
                            dst=dst_id,
                            weight=weight,
                            edge_ts=edge_ts,
                        )
                    elif src_type == "CUSTOMER" and dst_type == "BANK_IFSC" and edge_type == "USES_IFSC":
                        session.run(
                            """
                            MATCH (s:Customer {ca_number:$src}), (d:BankIFSC {ifsc:$dst})
                            MERGE (s)-[r:USES_IFSC]->(d)
                            SET r.weight=$weight, r.edge_ts=$edge_ts
                            """,
                            src=src_id,
                            dst=dst_id,
                            weight=weight,
                            edge_ts=edge_ts,
                        )
                    elif src_type == "TRANSACTION" and dst_type == "LANE" and edge_type == "RISK_LANE":
                        session.run(
                            """
                            MATCH (s:Transaction {txn_id:$src}), (d:Lane {name:$dst})
                            MERGE (s)-[r:RISK_LANE]->(d)
                            SET r.weight=$weight, r.edge_ts=$edge_ts
                            """,
                            src=src_id,
                            dst=dst_id,
                            weight=weight,
                            edge_ts=edge_ts,
                        )
                    elif src_type == "TRANSACTION" and dst_type == "POLICY" and edge_type == "DECIDED_BY":
                        session.run(
                            """
                            MATCH (s:Transaction {txn_id:$src}), (d:Policy {name:$dst})
                            MERGE (s)-[r:DECIDED_BY]->(d)
                            SET r.weight=$weight, r.edge_ts=$edge_ts
                            """,
                            src=src_id,
                            dst=dst_id,
                            weight=weight,
                            edge_ts=edge_ts,
                        )
                    else:
                        session.run(
                            """
                            MATCH (s:Entity {id:$src, kind:$sk}), (d:Entity {id:$dst, kind:$dk})
                            MERGE (s)-[r:RELATED {edge_type:$etype}]->(d)
                            SET r.weight=$weight, r.edge_ts=$edge_ts
                            """,
                            src=src_id,
                            dst=dst_id,
                            sk=src_type,
                            dk=dst_type,
                            etype=edge_type,
                            weight=weight,
                            edge_ts=edge_ts,
                        )
                    count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and load RTGS graph edges into Neo4j Aura")
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", ""))
    parser.add_argument("--username", default=os.getenv("NEO4J_USERNAME", ""))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD", ""))
    parser.add_argument("--database", default=os.getenv("NEO4J_DATABASE", "neo4j"))
    parser.add_argument("--edge-file", default="synthetic_rtgs_data/graph_edges.csv")
    parser.add_argument("--wait-seconds", type=int, default=60)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    if not args.uri or not args.username or not args.password:
        raise ValueError("Provide Neo4j URI/username/password via args or env vars")

    info = wait_and_validate_connection(
        uri=args.uri,
        username=args.username,
        password=args.password,
        database=args.database,
        wait_seconds=args.wait_seconds,
    )
    print(f"Connectivity validated: {info}")

    if args.validate_only:
        return

    apply_schema(args.uri, args.username, args.password, args.database)
    loaded = load_graph_edges(
        args.uri,
        args.username,
        args.password,
        args.database,
        Path(args.edge_file),
    )
    print(f"Loaded graph edges: {loaded}")


if __name__ == "__main__":
    main()
