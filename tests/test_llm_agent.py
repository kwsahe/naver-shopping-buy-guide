from __future__ import annotations

import json

import llm_agent


def test_llm_task_succeeds_on_first_valid_response() -> None:
    response = json.dumps(
        {
            "verdict": "buy_now",
            "reason": "현재가는 하위 구간입니다.",
        },
        ensure_ascii=False,
    )

    result = llm_agent.run_llm_task(
        "buy_timing",
        {
            "current_price": 79000,
            "min_price": 72000,
            "max_price": 95000,
            "avg_price": 84000,
            "percentile_rank": 18,
            "sample_size": 12,
            "days": 90,
        },
        mock_responses=[response],
    )

    assert result["verdict"] == "buy_now"


def test_llm_task_retries_until_json_is_valid() -> None:
    valid = json.dumps(
        {
            "ranking": ["A", "B"],
            "reason": "A가 배터리 기준 우위입니다.",
            "feature_comparison": [
                {"feature": "battery_hours", "winner": "A", "detail": "A가 더 깁니다."}
            ],
        },
        ensure_ascii=False,
    )

    result = llm_agent.run_llm_task(
        "compare",
        {
            "category_id": 1,
            "category": "무선 이어폰",
            "user_priority": "battery_hours",
            "products": [
                {"id": 1, "name": "A", "battery_hours": 8, "latest_price": 90000},
                {"id": 2, "name": "B", "battery_hours": 6, "latest_price": 70000},
            ],
        },
        mock_responses=["not json", valid],
    )

    assert result["ranking"] == ["A", "B"]
    assert result["feature_comparison"][0]["winner"] == "A"


def test_llm_task_falls_back_after_retry_budget() -> None:
    result = llm_agent.run_llm_task(
        "best_pick",
        {
            "category_id": 1,
            "category": "무선 이어폰",
            "products": [
                {"id": 1, "name": "A", "performance_score": 90, "value_score": 20},
                {"id": 2, "name": "B", "performance_score": 60, "value_score": 95},
            ],
        },
        max_retries=1,
        mock_responses=["not json", "still not json"],
    )

    assert result["best_performance"]["product"] == "A"
    assert result["best_value"]["product"] == "B"
    assert "note" in result


def test_schema_validation_rejects_wrong_verdict() -> None:
    result = llm_agent.run_llm_task(
        "buy_timing",
        {
            "current_price": 100,
            "min_price": 100,
            "max_price": 300,
            "avg_price": 180,
            "percentile_rank": 10,
            "sample_size": 3,
            "days": 90,
        },
        max_retries=0,
        mock_responses=[json.dumps({"verdict": "cheap", "reason": "bad"})],
    )

    assert result["verdict"] == "buy_now"
    assert "note" in result
