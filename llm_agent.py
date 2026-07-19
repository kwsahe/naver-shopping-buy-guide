from __future__ import annotations

import json
import os
from typing import Any, Literal, NotRequired, TypedDict

import requests

import analysis
import db

TaskType = Literal["compare", "buy_timing", "best_pick"]


class LLMTaskState(TypedDict):
    task_type: TaskType
    input_data: dict[str, Any]
    prompt: str | None
    raw_response: str | None
    parsed_response: dict[str, Any] | None
    validation_error: str | None
    retry_count: int
    max_retries: int
    result: dict[str, Any] | None
    persist: NotRequired[bool]
    mock_responses: NotRequired[list[str]]


def model_name() -> str:
    return os.getenv("LLM_MODEL", "exaone3.5:2.4b")


def input_validation_node(state: LLMTaskState) -> LLMTaskState:
    task_type = state.get("task_type")
    if task_type not in {"compare", "buy_timing", "best_pick"}:
        raise ValueError(f"unsupported task_type: {task_type}")
    if not isinstance(state.get("input_data"), dict):
        raise ValueError("input_data는 dictionary여야 합니다.")
    state.setdefault("retry_count", 0)
    state.setdefault("max_retries", 2)
    state.setdefault("prompt", None)
    state.setdefault("raw_response", None)
    state.setdefault("parsed_response", None)
    state.setdefault("validation_error", None)
    state.setdefault("result", None)
    return state


def score_compute_node(state: LLMTaskState) -> LLMTaskState:
    input_data = dict(state["input_data"])
    if state["task_type"] == "buy_timing" and "current_price" not in input_data:
        product_id = input_data.get("product_id")
        if product_id is None:
            raise ValueError("buy_timing requires product_id or precomputed price stats")
        input_data.update(analysis.compute_price_stats(int(product_id), int(input_data.get("days", 90))))
    elif state["task_type"] == "best_pick" and "products" not in input_data:
        category_id = input_data.get("category_id")
        if category_id is None:
            raise ValueError("best_pick requires category_id or precomputed category scores")
        input_data.update(analysis.compute_category_scores(int(category_id)))
    elif state["task_type"] == "compare" and "products" not in input_data:
        product_ids = input_data.get("product_ids")
        if not product_ids:
            raise ValueError("compare requires product_ids or precomputed products")
        input_data.update(
            analysis.build_compare_payload(
                [int(product_id) for product_id in product_ids],
                input_data.get("user_priority"),
            )
        )
    state["input_data"] = input_data
    return state


def prompt_router_node(state: LLMTaskState) -> LLMTaskState:
    task_type = state["task_type"]
    data = state["input_data"]
    if task_type == "compare":
        state["prompt"] = _compare_prompt(data)
    elif task_type == "buy_timing":
        state["prompt"] = _buy_timing_prompt(data)
    else:
        state["prompt"] = _best_pick_prompt(data)
    return state


def _compare_prompt(data: dict[str, Any]) -> str:
    return f"""
[시스템]
당신은 전자상거래 상품 비교 전문가입니다. 아래 스펙표에 없는 정보는 추측하지 말고
"확인 불가"로 표시하세요. 사용자가 우선순위를 지정하면 그 기준으로 비교 순서를 재정렬하세요.

[스펙 데이터]
{json.dumps({"products": data.get("products", [])}, ensure_ascii=False, indent=2)}

[사용자 우선순위]
{data.get("user_priority") or "균형"}

[출력 형식(JSON)]
{{
  "ranking": ["상품명"],
  "reason": "추천 근거",
  "feature_comparison": [
    {{"feature": "spec_key", "winner": "상품명 또는 확인 불가", "detail": "입력된 스펙 범위 내 설명"}}
  ]
}}
""".strip()


def _buy_timing_prompt(data: dict[str, Any]) -> str:
    stats = {
        "current_price": data["current_price"],
        "min_90d": data.get("min_price"),
        "max_90d": data.get("max_price"),
        "avg_90d": data.get("avg_price"),
        "percentile_rank": data.get("percentile_rank"),
        "sample_size": data.get("sample_size"),
    }
    return f"""
[시스템]
당신은 가격 분석가입니다. 아래 통계는 이미 계산되어 있으니 그대로 인용하고
새로운 숫자를 만들어내지 마세요.

[가격 통계]
{json.dumps(stats, ensure_ascii=False, indent=2)}

[출력 형식(JSON)]
{{"verdict": "buy_now | wait | neutral", "reason": "판단 근거"}}
""".strip()


def _best_pick_prompt(data: dict[str, Any]) -> str:
    payload = {
        "category": data.get("category"),
        "products": data.get("products", []),
        "best_performance_candidate": data.get("best_performance_candidate"),
        "best_value_candidate": data.get("best_value_candidate"),
    }
    return f"""
[시스템]
당신은 상품 추천 전문가입니다. 아래 성능 점수/가성비 점수는 이미 계산되어 있으니
그대로 인용하고, 점수를 직접 계산하거나 새로운 숫자를 만들어내지 마세요.
각 베스트픽이 왜 선정됐는지 스펙과 가격을 근거로 설명하세요.

[카테고리 점수 데이터]
{json.dumps(payload, ensure_ascii=False, indent=2)}

[출력 형식(JSON)]
{{
  "best_performance": {{"product": "상품명", "reason": "선정 이유"}},
  "best_value": {{"product": "상품명", "reason": "선정 이유"}}
}}
""".strip()


def llm_call_node(state: LLMTaskState) -> LLMTaskState:
    mock_responses = state.get("mock_responses")
    if mock_responses:
        index = min(state["retry_count"], len(mock_responses) - 1)
        state["raw_response"] = mock_responses[index]
        return state

    provider = os.getenv("LLM_PROVIDER", "disabled")
    llm_enabled = os.getenv("LLM_ENABLED", "0").lower() in {"1", "true", "yes", "y"}
    if provider in {"disabled", "mock"} or not llm_enabled:
        state["raw_response"] = json.dumps(
            fallback_response(
                state["task_type"],
                state["input_data"],
                note="LLM 연결은 보류 상태라 코드 계산 기반 fallback을 사용했습니다.",
            ),
            ensure_ascii=False,
        )
        return state

    try:
        if provider == "local_ollama":
            state["raw_response"] = _call_ollama(state["prompt"] or "")
        elif provider == "remote_openai":
            state["raw_response"] = _call_openai_compatible(state["prompt"] or "")
        else:
            raise RuntimeError(f"unsupported LLM_PROVIDER: {provider}")
    except Exception as exc:
        state["raw_response"] = json.dumps(
            fallback_response(
                state["task_type"],
                state["input_data"],
                note=f"LLM 호출 실패로 코드 fallback 사용: {exc}",
            ),
            ensure_ascii=False,
        )
    return state


def _call_ollama(prompt: str) -> str:
    api_base = os.getenv("LLM_API_BASE", "http://localhost:11434").rstrip("/")
    response = requests.post(
        f"{api_base}/api/generate",
        json={"model": model_name(), "prompt": prompt, "stream": False, "format": "json"},
        timeout=60,
    )
    response.raise_for_status()
    return str(response.json().get("response", ""))


def _call_openai_compatible(prompt: str) -> str:
    api_base = os.getenv("LLM_API_BASE", "").rstrip("/")
    api_key = os.getenv("LLM_API_KEY", "")
    if not api_base:
        raise RuntimeError("remote_openai 사용에는 LLM_API_BASE가 필요합니다.")
    endpoint = f"{api_base}/chat/completions"
    response = requests.post(
        endpoint,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model_name(),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        },
        timeout=60,
    )
    response.raise_for_status()
    return str(response.json()["choices"][0]["message"]["content"])


def json_validation_node(state: LLMTaskState) -> LLMTaskState:
    try:
        parsed = _parse_json_object(state.get("raw_response") or "")
        _validate_schema(state["task_type"], parsed)
        state["parsed_response"] = parsed
        state["result"] = parsed
        state["validation_error"] = None
    except Exception as exc:
        retry_count = state["retry_count"] + 1
        state["retry_count"] = retry_count
        if retry_count > state["max_retries"]:
            state["result"] = fallback_response(
                state["task_type"],
                state["input_data"],
                note=f"AI 응답 JSON 검증 실패: {exc}",
            )
            state["validation_error"] = None
        else:
            state["validation_error"] = str(exc)
    return state


def _parse_json_object(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if not raw:
        raise ValueError("empty response")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        parsed = json.loads(raw[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("response는 JSON 객체여야 합니다.")
    return parsed


def _validate_schema(task_type: TaskType, parsed: dict[str, Any]) -> None:
    if task_type == "compare":
        if not isinstance(parsed.get("ranking"), list):
            raise ValueError("compare response requires ranking list")
        if not isinstance(parsed.get("reason"), str):
            raise ValueError("compare response requires reason string")
        if not isinstance(parsed.get("feature_comparison"), list):
            raise ValueError("compare response requires feature_comparison list")
    elif task_type == "buy_timing":
        if parsed.get("verdict") not in {"buy_now", "wait", "neutral"}:
            raise ValueError("buy_timing verdict는 buy_now, wait, neutral 중 하나여야 합니다.")
        if not isinstance(parsed.get("reason"), str):
            raise ValueError("buy_timing response requires reason string")
    else:
        for key in ("best_performance", "best_value"):
            value = parsed.get(key)
            if not isinstance(value, dict) or not value.get("product") or not value.get("reason"):
                raise ValueError(f"best_pick response requires {key}.product and {key}.reason")


def _route_after_validation(state: LLMTaskState) -> str:
    if state.get("validation_error"):
        return "retry"
    return "done"


def persist_node(state: LLMTaskState) -> LLMTaskState:
    if not state.get("persist") or not state.get("result"):
        return state

    result = dict(state["result"] or {})
    input_data = state["input_data"]
    if state["task_type"] == "compare":
        report_id = db.create_comparison_report(
            category_id=int(input_data["category_id"]),
            product_ids=[int(product["id"]) for product in input_data.get("products", [])],
            user_priority=input_data.get("user_priority"),
            llm_model=model_name(),
            report=result,
        )
        result["report_id"] = report_id
        state["result"] = result
    elif state["task_type"] == "best_pick":
        _persist_best_pick(input_data, result)
    return state


def _persist_best_pick(input_data: dict[str, Any], result: dict[str, Any]) -> None:
    products = {product["name"]: product for product in input_data.get("products", [])}
    best_value_name = result["best_value"]["product"]
    best_performance_name = result["best_performance"]["product"]
    if best_value_name not in products or best_performance_name not in products:
        return
    db.upsert_category_recommendation(
        category_id=int(input_data["category_id"]),
        best_value_product_id=int(products[best_value_name]["id"]),
        best_value_score=float(products[best_value_name].get("value_score", 0)),
        best_value_reason=result["best_value"]["reason"],
        best_performance_product_id=int(products[best_performance_name]["id"]),
        best_performance_score=float(products[best_performance_name].get("performance_score", 0)),
        best_performance_reason=result["best_performance"]["reason"],
        llm_model=model_name(),
    )


def fallback_response(task_type: TaskType, data: dict[str, Any], note: str | None = None) -> dict[str, Any]:
    if task_type == "compare":
        response = _fallback_compare(data)
    elif task_type == "buy_timing":
        response = analysis.buy_timing_from_stats(data)
    else:
        response = _fallback_best_pick(data)
    if note:
        response["note"] = note
    return response


def _fallback_compare(data: dict[str, Any]) -> dict[str, Any]:
    products = list(data.get("products", []))
    priority = data.get("user_priority") or "균형"

    def rank_key(product: dict[str, Any]) -> tuple[float, float]:
        if priority in product:
            value = product.get(priority)
            numeric = 100.0 if value is True else 0.0 if value is False else float(value)
            if priority in {"weight_g", "latest_price"}:
                numeric *= -1
            return numeric, -float(product.get("latest_price") or 0)
        return -float(product.get("latest_price") or 0), float(product.get("battery_hours") or 0)

    ranked = sorted(products, key=rank_key, reverse=True)
    ranking = [product["name"] for product in ranked]
    feature_comparison = _feature_comparison(products)
    top_name = ranking[0] if ranking else "확인 불가"
    return {
        "ranking": ranking,
        "reason": f"{priority} 기준으로 보면 {top_name}가 가장 유리합니다. 입력된 스펙과 현재가만 근거로 판단했습니다.",
        "feature_comparison": feature_comparison,
    }


def _feature_comparison(products: list[dict[str, Any]]) -> list[dict[str, str]]:
    features = ["battery_hours", "anc", "weight_g", "water_resistance_score", "latest_price"]
    comparisons: list[dict[str, str]] = []
    for feature in features:
        available = [product for product in products if product.get(feature) is not None]
        if not available:
            continue
        if feature in {"weight_g", "latest_price"}:
            winner = min(available, key=lambda product: float(product[feature]))
            detail = f"{feature}는 낮을수록 유리하며 {winner['name']}가 가장 낮습니다."
        elif feature == "anc":
            winner = next((product for product in available if product.get(feature) is True), None)
            detail = "ANC 지원 여부를 입력된 스펙 기준으로 비교했습니다."
        else:
            winner = max(available, key=lambda product: float(product[feature]))
            detail = f"{feature}는 높을수록 유리하며 {winner['name']}가 가장 높습니다."
        comparisons.append(
            {
                "feature": feature,
                "winner": winner["name"] if winner else "확인 불가",
                "detail": detail,
            }
        )
    return comparisons


def _fallback_best_pick(data: dict[str, Any]) -> dict[str, Any]:
    products = list(data.get("products", []))
    best_performance = max(products, key=lambda item: item.get("performance_score", 0), default={})
    best_value = max(products, key=lambda item: item.get("value_score", 0), default={})
    return {
        "best_performance": {
            "product": best_performance.get("name", "확인 불가"),
            "reason": (
                f"성능 점수 {best_performance.get('performance_score', '확인 불가')}점으로 "
                "카테고리 내 핵심 스펙 가중합산 결과가 가장 높습니다."
            ),
        },
        "best_value": {
            "product": best_value.get("name", "확인 불가"),
            "reason": (
                f"가성비 점수 {best_value.get('value_score', '확인 불가')}점으로 "
                "성능 대비 현재가 조건이 가장 좋습니다."
            ),
        },
    }


class SimplePipeline:
    def invoke(self, state: LLMTaskState) -> LLMTaskState:
        state = input_validation_node(state)
        state = score_compute_node(state)
        state = prompt_router_node(state)
        while True:
            state = llm_call_node(state)
            state = json_validation_node(state)
            if _route_after_validation(state) == "done":
                break
        return persist_node(state)


def build_pipeline() -> Any:
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        return SimplePipeline()

    graph = StateGraph(LLMTaskState)
    graph.add_node("input_validation", input_validation_node)
    graph.add_node("score_compute", score_compute_node)
    graph.add_node("prompt_router", prompt_router_node)
    graph.add_node("llm_call", llm_call_node)
    graph.add_node("json_validation", json_validation_node)
    graph.add_node("persist", persist_node)

    graph.set_entry_point("input_validation")
    graph.add_edge("input_validation", "score_compute")
    graph.add_edge("score_compute", "prompt_router")
    graph.add_edge("prompt_router", "llm_call")
    graph.add_edge("llm_call", "json_validation")
    graph.add_conditional_edges(
        "json_validation",
        _route_after_validation,
        {"retry": "llm_call", "done": "persist"},
    )
    graph.add_edge("persist", END)
    return graph.compile()


llm_pipeline = build_pipeline()


def run_llm_task(
    task_type: TaskType,
    input_data: dict[str, Any],
    *,
    persist: bool = False,
    max_retries: int = 2,
    mock_responses: list[str] | None = None,
) -> dict[str, Any]:
    state: LLMTaskState = {
        "task_type": task_type,
        "input_data": input_data,
        "prompt": None,
        "raw_response": None,
        "parsed_response": None,
        "validation_error": None,
        "retry_count": 0,
        "max_retries": max_retries,
        "result": None,
        "persist": persist,
    }
    if mock_responses is not None:
        state["mock_responses"] = mock_responses
    final_state = llm_pipeline.invoke(state)
    return final_state["result"] or fallback_response(task_type, final_state["input_data"])


def generate_best_pick_reasons(score_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    generated: list[dict[str, Any]] = []
    for score_run in score_runs:
        scores = score_run.get("scores", {})
        result = run_llm_task("best_pick", scores, persist=True)
        generated.append(result)
    return generated
