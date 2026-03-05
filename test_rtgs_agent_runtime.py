from rtgs_agent_runtime import RTGSAgentOrchestrator, build_demo_open_items, build_demo_transaction


def test_agent_orchestrator_demo_flow():
    agent = RTGSAgentOrchestrator()
    agent.warm_start()

    result = agent.reconcile_one(
        build_demo_transaction(),
        build_demo_open_items(),
        {"81234567": 0.6, "90009999": 0.95},
    )

    payload = agent.as_payload(result)
    assert payload["txn_id"] == "DEMO_TXN_001"
    assert payload["selected_open_item_id"] in {"DEMO_OI_A", "DEMO_OI_B"}
    assert payload["lane"] in {"GREEN", "YELLOW", "RED"}
