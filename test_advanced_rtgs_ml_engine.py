from datetime import date

from advanced_rtgs_ml_engine import (
    AdvancedRTGSEngine,
    OpenItem,
    Transaction,
    select_best_open_item,
)


def test_feature_builder_and_decision_lane_green_or_yellow():
    engine = AdvancedRTGSEngine()
    engine.fit_models(
        historical_amounts=[0, 0, 5, 10, 0, 15, 0, 8],
        labeled_feature_vectors=[],
        labels=[],
    )

    txn = Transaction(
        txn_id="T1",
        ca_number="90001234",
        amount=10000,
        txn_date=date(2026, 1, 10),
        description="RTGS PAYMENT FROM TATA POWER LTD",
        channel="RTGS",
    )
    item = OpenItem(
        item_id="I1",
        ca_number="90001234",
        expected_amount=10000,
        due_date=date(2026, 1, 10),
        customer_name="TATA POWER",
    )

    features = engine.build_features(txn, item, historical_hit_ratio=0.95)
    decision = engine.decide(features)

    assert features.ca_exact_match == 1
    assert decision.lane in {"GREEN", "YELLOW"}
    assert decision.decision in {
        "AUTO_POST_FP25",
        "AUTO_WRITE_OFF_AND_POST",
        "PARK_AND_NOTIFY_APPROVER",
    }


def test_best_item_selection_prefers_better_ca_match():
    engine = AdvancedRTGSEngine()
    engine.fit_models(
        historical_amounts=[0, 1, 2, 3, 4, 5],
        labeled_feature_vectors=[],
        labels=[],
    )

    txn = Transaction(
        txn_id="T2",
        ca_number="90009999",
        amount=1200,
        txn_date=date(2026, 1, 11),
        description="NEFT CUSTOMER ACME",
        channel="NEFT",
    )

    open_items = [
        OpenItem(
            item_id="A",
            ca_number="81234567",
            expected_amount=1200,
            due_date=date(2026, 1, 11),
            customer_name="ACME CORP",
        ),
        OpenItem(
            item_id="B",
            ca_number="90009999",
            expected_amount=1200,
            due_date=date(2026, 1, 11),
            customer_name="ACME",
        ),
    ]

    best_item, decision = select_best_open_item(
        engine,
        txn,
        open_items,
        historical_hit_ratio_lookup={"81234567": 0.6, "90009999": 0.9},
    )

    assert best_item is not None
    assert decision is not None
    assert best_item.item_id == "B"
