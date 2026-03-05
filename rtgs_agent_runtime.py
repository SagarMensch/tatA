from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Dict, Iterable, List, Optional

from advanced_rtgs_ml_engine import (
    AdvancedRTGSEngine,
    MatchDecision,
    OpenItem,
    Transaction,
    select_best_open_item,
)


@dataclass
class AgentTaskResult:
    txn_id: str
    selected_open_item_id: Optional[str]
    lane: str
    action: str
    confidence: float
    reason: str


class RTGSAgentOrchestrator:
    """Agentic coordinator for deterministic + ML-assisted reconciliation."""

    def __init__(self, engine: Optional[AdvancedRTGSEngine] = None) -> None:
        self.engine = engine or AdvancedRTGSEngine()

    def warm_start(self) -> None:
        self.engine.fit_models(
            historical_amounts=[0, 1, 2, 5, 0, 0, 10, 4, 3, 1],
            labeled_feature_vectors=[],
            labels=[],
        )

    def reconcile_one(
        self,
        txn: Transaction,
        open_items: Iterable[OpenItem],
        historical_hit_ratio_lookup: Dict[str, float],
    ) -> AgentTaskResult:
        best_item, decision = select_best_open_item(
            self.engine,
            txn,
            open_items,
            historical_hit_ratio_lookup,
        )
        if decision is None:
            decision = MatchDecision(
                confidence=0.0,
                lane="RED",
                decision="ESCALATE_TO_CONCERN_TEAM",
                reason="no_candidate_open_items",
            )

        return AgentTaskResult(
            txn_id=txn.txn_id,
            selected_open_item_id=best_item.item_id if best_item else None,
            lane=decision.lane,
            action=decision.decision,
            confidence=decision.confidence,
            reason=decision.reason,
        )

    def as_payload(self, result: AgentTaskResult) -> Dict[str, object]:
        return asdict(result)


def build_demo_transaction() -> Transaction:
    return Transaction(
        txn_id="DEMO_TXN_001",
        ca_number="90009999",
        amount=10000,
        txn_date=date(2026, 1, 11),
        description="RTGS PAYMENT CUSTOMER ACME POWER",
        channel="RTGS",
    )


def build_demo_open_items() -> List[OpenItem]:
    return [
        OpenItem(
            item_id="DEMO_OI_A",
            ca_number="81234567",
            expected_amount=10000,
            due_date=date(2026, 1, 10),
            customer_name="ACME CORP",
        ),
        OpenItem(
            item_id="DEMO_OI_B",
            ca_number="90009999",
            expected_amount=10000,
            due_date=date(2026, 1, 11),
            customer_name="ACME POWER",
        ),
    ]
