"""Advanced RTGS matching engine with neuro-symbolic decisioning.

This module combines:
1. Feature-driven ML scoring (Decision Tree classifier).
2. Rete-inspired rule evaluation network for policy execution.
3. Deterministic mathematical checks for financial safety.

It is designed to support RTGS/NEFT reconciliation pipelines where business
rules must remain explainable and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Transaction:
    txn_id: str
    ca_number: str
    amount: float
    txn_date: date
    description: str
    channel: str


@dataclass(frozen=True)
class OpenItem:
    item_id: str
    ca_number: str
    expected_amount: float
    due_date: date
    customer_name: str


@dataclass(frozen=True)
class MatchFeatures:
    amount_delta: float
    amount_delta_pct: float
    date_gap_days: int
    ca_exact_match: int
    channel_rtgs_like: int
    description_similarity: float
    historical_hit_ratio: float

    def as_vector(self) -> List[float]:
        return [
            self.amount_delta,
            self.amount_delta_pct,
            float(self.date_gap_days),
            float(self.ca_exact_match),
            float(self.channel_rtgs_like),
            self.description_similarity,
            self.historical_hit_ratio,
        ]


@dataclass
class MatchDecision:
    confidence: float
    lane: str
    decision: str
    reason: str


class AmountAnomalyModel:
    """Robust anomaly logic using MAD (Median Absolute Deviation)."""

    def __init__(self) -> None:
        self._median: float = 0.0
        self._mad: float = 1.0

    def fit(self, historical_amounts: Sequence[float]) -> None:
        if not historical_amounts:
            self._median = 0.0
            self._mad = 1.0
            return
        self._median = float(median(historical_amounts))
        deviations = [abs(a - self._median) for a in historical_amounts]
        mad = float(median(deviations))
        self._mad = mad if mad > 0 else 1.0

    def score(self, amount: float) -> float:
        # Modified z-score using 0.6745 factor.
        return abs(0.6745 * (amount - self._median) / self._mad)

    def is_anomalous(self, amount: float, threshold: float = 3.5) -> bool:
        return self.score(amount) > threshold


class DecisionTreeConfidenceModel:
    """Wrapper around sklearn decision tree with deterministic fallback."""

    def __init__(self) -> None:
        self._model = None

    def fit(self, vectors: Sequence[Sequence[float]], labels: Sequence[int]) -> None:
        if not vectors:
            return
        try:
            from sklearn.tree import DecisionTreeClassifier

            model = DecisionTreeClassifier(
                max_depth=6,
                min_samples_leaf=5,
                random_state=42,
                class_weight="balanced",
            )
            model.fit(vectors, labels)
            self._model = model
        except Exception:
            self._model = None

    def predict_confidence(self, vector: Sequence[float]) -> float:
        if self._model is None:
            # Fallback confidence heuristic when sklearn is unavailable.
            amount_delta_pct = vector[1]
            date_gap_days = vector[2]
            ca_match = vector[3]
            sim = vector[5]
            raw = (
                0.45 * max(0.0, 1.0 - min(amount_delta_pct, 1.0))
                + 0.2 * max(0.0, 1.0 - min(date_gap_days / 7.0, 1.0))
                + 0.25 * ca_match
                + 0.1 * sim
            )
            return max(0.0, min(raw, 1.0))

        prob = self._model.predict_proba([vector])[0]
        # class 1 is "match"
        if len(prob) == 2:
            return float(prob[1])
        return float(max(prob))


class ReteLikeRuleEngine:
    """A minimal Rete-inspired alpha network for policy routing."""

    def __init__(self) -> None:
        self._rules: List[Tuple[str, Callable[[Dict[str, float]], bool], str, str]] = []

    def add_rule(
        self,
        name: str,
        condition: Callable[[Dict[str, float]], bool],
        lane: str,
        decision: str,
    ) -> None:
        self._rules.append((name, condition, lane, decision))

    def evaluate(self, facts: Dict[str, float]) -> Optional[Tuple[str, str, str]]:
        for name, condition, lane, decision in self._rules:
            if condition(facts):
                return name, lane, decision
        return None


class AdvancedRTGSEngine:
    def __init__(self) -> None:
        self.anomaly_model = AmountAnomalyModel()
        self.tree_model = DecisionTreeConfidenceModel()
        self.rule_engine = ReteLikeRuleEngine()
        self._bootstrap_rules()

    def _bootstrap_rules(self) -> None:
        self.rule_engine.add_rule(
            "green_autopost",
            lambda f: f["confidence"] >= 0.99 and f["amount_delta"] == 0 and f["anomaly"] == 0,
            lane="GREEN",
            decision="AUTO_POST_FP25",
        )
        self.rule_engine.add_rule(
            "green_small_writeoff",
            lambda f: f["confidence"] >= 0.95 and f["amount_delta"] <= 10 and f["anomaly"] == 0,
            lane="GREEN",
            decision="AUTO_WRITE_OFF_AND_POST",
        )
        self.rule_engine.add_rule(
            "yellow_manual_approval",
            lambda f: f["confidence"] >= 0.80 and f["amount_delta"] <= 100,
            lane="YELLOW",
            decision="PARK_AND_NOTIFY_APPROVER",
        )
        self.rule_engine.add_rule(
            "red_investigation",
            lambda f: True,
            lane="RED",
            decision="ESCALATE_TO_CONCERN_TEAM",
        )

    @staticmethod
    def _token_jaccard(a: str, b: str) -> float:
        sa = {x for x in a.lower().split() if x}
        sb = {x for x in b.lower().split() if x}
        if not sa and not sb:
            return 1.0
        inter = len(sa.intersection(sb))
        union = len(sa.union(sb)) or 1
        return inter / union

    def build_features(
        self,
        txn: Transaction,
        item: OpenItem,
        historical_hit_ratio: float,
    ) -> MatchFeatures:
        amount_delta = abs(txn.amount - item.expected_amount)
        amount_delta_pct = amount_delta / max(item.expected_amount, 1.0)
        date_gap_days = abs((txn.txn_date - item.due_date).days)
        ca_exact = int(txn.ca_number == item.ca_number)
        channel_rtgs_like = int(txn.channel.upper() in {"RTGS", "NEFT", "IMPS"})
        description_similarity = self._token_jaccard(txn.description, item.customer_name)

        return MatchFeatures(
            amount_delta=amount_delta,
            amount_delta_pct=amount_delta_pct,
            date_gap_days=date_gap_days,
            ca_exact_match=ca_exact,
            channel_rtgs_like=channel_rtgs_like,
            description_similarity=description_similarity,
            historical_hit_ratio=historical_hit_ratio,
        )

    def fit_models(
        self,
        historical_amounts: Sequence[float],
        labeled_feature_vectors: Sequence[Sequence[float]],
        labels: Sequence[int],
    ) -> None:
        self.anomaly_model.fit(historical_amounts)
        self.tree_model.fit(labeled_feature_vectors, labels)

    def decide(self, features: MatchFeatures) -> MatchDecision:
        confidence = self.tree_model.predict_confidence(features.as_vector())
        anomaly = int(self.anomaly_model.is_anomalous(features.amount_delta))
        facts = {
            "confidence": confidence,
            "amount_delta": features.amount_delta,
            "anomaly": float(anomaly),
        }

        rule = self.rule_engine.evaluate(facts)
        if not rule:
            return MatchDecision(
                confidence=confidence,
                lane="RED",
                decision="ESCALATE_TO_CONCERN_TEAM",
                reason="no_rule_matched",
            )

        rule_name, lane, decision = rule
        return MatchDecision(
            confidence=confidence,
            lane=lane,
            decision=decision,
            reason=rule_name,
        )


def select_best_open_item(
    engine: AdvancedRTGSEngine,
    txn: Transaction,
    open_items: Iterable[OpenItem],
    historical_hit_ratio_lookup: Dict[str, float],
) -> Tuple[Optional[OpenItem], Optional[MatchDecision]]:
    best_item: Optional[OpenItem] = None
    best_decision: Optional[MatchDecision] = None

    for item in open_items:
        ratio = historical_hit_ratio_lookup.get(item.ca_number, 0.5)
        features = engine.build_features(txn, item, ratio)
        decision = engine.decide(features)

        if best_decision is None or decision.confidence > best_decision.confidence:
            best_item = item
            best_decision = decision

    return best_item, best_decision
