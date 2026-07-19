from __future__ import annotations

import re
from statistics import mean
from typing import Any

import db

TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")

SKIN_CONDITION_RULES: dict[str, dict[str, Any]] = {
    "pore_wide": {
        "label": "넓어 보이는 모공",
        "keywords": ("넓은 모공", "모공", "포어"),
    },
    "pore_clogged": {
        "label": "막힌 모공",
        "keywords": ("막힌 모공", "모공 막힘", "블랙헤드", "화이트헤드", "노폐물"),
    },
    "oiliness": {
        "label": "피지·유분",
        "keywords": ("피지", "유분", "번들", "지성", "오일프리", "세범", "산뜻"),
    },
    "dry_tight": {
        "label": "건조·당김",
        "keywords": ("건조", "당김", "보습", "수분", "촉촉", "히알루론산", "세라마이드"),
    },
    "sensitive_redness": {
        "label": "민감·붉음",
        "keywords": ("민감", "붉", "홍조", "진정", "저자극", "순한", "시카", "판테놀"),
    },
    "trouble_acne": {
        "label": "트러블·여드름",
        "keywords": ("트러블", "여드름", "아크네", "티트리", "살리실산", "bha", "바하"),
    },
    "flaky": {
        "label": "각질",
        "keywords": ("각질", "필링", "스크럽", "aha", "아하", "pha", "파하", "효소"),
    },
    "pigmentation_dullness": {
        "label": "색소·칙칙함",
        "keywords": (
            "색소",
            "잡티",
            "칙칙",
            "미백",
            "브라이트닝",
            "비타민c",
            "나이아신아마이드",
            "톤업",
        ),
    },
}

SKIN_PRODUCT_CATEGORIES = (
    "바디워시",
    "로션",
    "폼클렌징",
    "폼클렌저",
    "bodywash",
    "body wash",
    "lotion",
    "cleansing",
)


def apply_skin_condition_scores(
    recommendations: list[dict[str, Any]],
    skin_conditions: list[str],
    *,
    require_condition_match: bool = False,
) -> list[dict[str, Any]]:
    """상품명·설명에서 확인된 피부 상태 표현만 추천 점수와 사유에 반영합니다."""
    if not skin_conditions:
        return recommendations

    scored: list[dict[str, Any]] = []
    for recommendation in recommendations:
        category_name = str(recommendation.get("category_name") or "").lower()
        is_skin_product = any(category in category_name for category in SKIN_PRODUCT_CATEGORIES)
        text = " ".join(
            (
                str(recommendation.get("name") or ""),
                str(recommendation.get("description") or ""),
            )
        ).lower()
        condition_score = 0.0
        condition_reasons: list[str] = []

        if is_skin_product:
            for condition in skin_conditions:
                rule = SKIN_CONDITION_RULES[condition]
                matches = list(dict.fromkeys(keyword for keyword in rule["keywords"] if keyword in text))
                if not matches:
                    continue
                condition_score += len(matches) * 1.5
                condition_reasons.append(
                    f"{rule['label']} 관련 표현이 확인됨: {', '.join(matches)}"
                )

        if require_condition_match and not condition_reasons:
            continue

        enriched = dict(recommendation)
        enriched["recommend_score"] = round(
            float(enriched.get("recommend_score") or 0) + condition_score,
            2,
        )
        enriched["recommend_reasons"] = [
            *list(enriched.get("recommend_reasons") or []),
            *condition_reasons,
        ]
        scored.append(enriched)

    return sorted(
        scored,
        key=lambda item: (
            -float(item.get("recommend_score") or 0),
            item.get("latest_price") or float("inf"),
        ),
    )


def calculate_price_statistics(history: list[dict[str, Any]] | list[int]) -> dict[str, Any]:
    prices = [int(item["price"]) if isinstance(item, dict) else int(item) for item in history]
    if not prices:
        raise ValueError("price history is empty")

    current_price = prices[-1]
    min_price = min(prices)
    max_price = max(prices)
    avg_price = mean(prices)

    if len(prices) == 1:
        percentile_rank = 50.0
    else:
        lower_count = sum(1 for price in prices if price < current_price)
        equal_count = sum(1 for price in prices if price == current_price)
        percentile_rank = ((lower_count + equal_count * 0.5) / len(prices)) * 100

    return {
        "current_price": current_price,
        "min_price": min_price,
        "max_price": max_price,
        "avg_price": round(avg_price, 1),
        "percentile_rank": round(percentile_rank, 1),
        "sample_size": len(prices),
    }


def compute_price_stats(product_id: int, days: int = 90) -> dict[str, Any]:
    history = db.get_price_history(product_id, days=days)
    stats = calculate_price_statistics(history)
    stats["product_id"] = product_id
    stats["days"] = days
    return stats


def buy_timing_from_stats(stats: dict[str, Any]) -> dict[str, str]:
    percentile = float(stats["percentile_rank"])
    if percentile <= 25:
        verdict = "buy_now"
        reason = (
            f"현재가는 최근 {stats['days']}일 표본 중 하위 {percentile:.1f}% 구간입니다. "
            "상대적으로 낮은 가격대라 매수 적기로 볼 수 있습니다."
        )
    elif percentile >= 75:
        verdict = "wait"
        reason = (
            f"현재가는 최근 {stats['days']}일 표본 중 상위 {percentile:.1f}% 구간입니다. "
            "가격이 높은 편이라 추가 하락을 기다리는 편이 낫습니다."
        )
    else:
        verdict = "neutral"
        reason = (
            f"현재가는 최근 {stats['days']}일 표본 중 {percentile:.1f}% 구간입니다. "
            "뚜렷한 저점이나 고점은 아니므로 급하지 않다면 조금 더 관찰해도 좋습니다."
        )
    return {"verdict": verdict, "reason": reason}


def load_score_weights(category_name: str) -> dict[str, dict[str, Any]]:
    for spec_file in db.load_spec_files():
        if spec_file.get("category") == category_name:
            return spec_file.get("score_weights", {})
    return {}


def _numeric_value(value: Any) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if value is None:
        return 0.0
    return float(value)


def _normalize(values: list[Any], direction: str) -> list[float]:
    if direction == "boolean_bonus":
        return [100.0 if bool(value) else 0.0 for value in values]

    numeric_values = [_numeric_value(value) for value in values]
    low = min(numeric_values)
    high = max(numeric_values)
    if high == low:
        return [100.0 for _ in numeric_values]

    normalized: list[float] = []
    for value in numeric_values:
        if direction == "lower_better":
            score = (high - value) / (high - low) * 100
        else:
            score = (value - low) / (high - low) * 100
        normalized.append(score)
    return normalized


def _normalize_raw_scores(values: list[float]) -> list[float]:
    if not values:
        return []
    low = min(values)
    high = max(values)
    if high == low:
        return [round(value, 2) for value in values]
    return [round((value - low) / (high - low) * 100, 2) for value in values]


def calculate_product_scores(
    products: list[dict[str, Any]],
    score_weights: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if not products:
        return []
    if not score_weights:
        raise ValueError("score_weights가 필요합니다.")

    normalized_by_key: dict[str, list[float]] = {}
    for spec_key, config in score_weights.items():
        values = [product.get(spec_key) for product in products]
        normalized_by_key[spec_key] = _normalize(values, config.get("direction", "higher_better"))

    weighted_products: list[dict[str, Any]] = []
    total_weight = sum(float(config.get("weight", 0)) for config in score_weights.values()) or 1.0

    for index, product in enumerate(products):
        performance_score = 0.0
        spec_breakdown: dict[str, float] = {}
        for spec_key, config in score_weights.items():
            weight = float(config.get("weight", 0))
            normalized_score = normalized_by_key[spec_key][index]
            performance_score += normalized_score * weight
            spec_breakdown[spec_key] = round(normalized_score, 2)

        enriched = dict(product)
        enriched["performance_score"] = round(performance_score / total_weight, 2)
        enriched["spec_score_breakdown"] = spec_breakdown
        weighted_products.append(enriched)

    prices = [max(float(product.get("latest_price") or 0), 1.0) for product in weighted_products]
    price_expensiveness = _normalize_price_expensiveness(prices)
    raw_value_scores = [
        product["performance_score"] / max(price_expensiveness[index], 1.0)
        for index, product in enumerate(weighted_products)
    ]
    value_scores = _normalize_raw_scores(raw_value_scores)

    for index, product in enumerate(weighted_products):
        product["price_expensiveness_score"] = round(price_expensiveness[index], 2)
        product["value_score"] = value_scores[index]

    return weighted_products


def calculate_generic_product_scores(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not products:
        return []

    prices = [float(product.get("latest_price") or 0) for product in products]
    affordability_scores = _normalize(prices, "lower_better") if any(prices) else [50.0] * len(products)
    scored: list[dict[str, Any]] = []
    for index, product in enumerate(products):
        metadata_score = _metadata_score(product)
        performance_score = round(metadata_score, 2)
        value_score = round(affordability_scores[index] * 0.7 + metadata_score * 0.3, 2)
        enriched = dict(product)
        enriched["performance_score"] = performance_score
        enriched["value_score"] = value_score
        enriched["price_expensiveness_score"] = round(100 - affordability_scores[index], 2)
        enriched["spec_score_breakdown"] = {
            "metadata": metadata_score,
            "affordability": round(affordability_scores[index], 2),
        }
        scored.append(enriched)
    return scored


def _normalize_price_expensiveness(prices: list[float]) -> list[float]:
    if not prices:
        return []
    low = min(prices)
    high = max(prices)
    if high == low:
        return [50.0 for _ in prices]
    return [1.0 + ((price - low) / (high - low) * 99.0) for price in prices]


def compute_category_scores(category_id: int) -> dict[str, Any]:
    category = db.get_category(category_id)
    if not category:
        raise ValueError(f"category {category_id}를 찾을 수 없습니다.")

    score_weights = load_score_weights(category["name"])
    products = []
    for product in db.get_products(category_id):
        product_with_specs = db.get_product_with_specs(product["id"])
        if product_with_specs:
            products.append(product_with_specs)

    if score_weights:
        scored_products = calculate_product_scores(products, score_weights)
    else:
        scored_products = calculate_generic_product_scores(products)
    best_performance = max(scored_products, key=lambda item: item["performance_score"], default=None)
    best_value = max(scored_products, key=lambda item: item["value_score"], default=None)

    return {
        "category_id": category_id,
        "category": category["name"],
        "score_weights": score_weights,
        "products": scored_products,
        "best_performance_candidate": best_performance["name"] if best_performance else None,
        "best_performance_product_id": best_performance["id"] if best_performance else None,
        "best_value_candidate": best_value["name"] if best_value else None,
        "best_value_product_id": best_value["id"] if best_value else None,
    }


def analyze_selected_product(product_id: int, limit: int = 5) -> dict[str, Any]:
    selected = db.get_product_with_specs(product_id)
    if not selected:
        raise ValueError(f"product {product_id}를 찾을 수 없습니다.")

    products = [
        product
        for product in db.get_products(selected["category_id"])
        if int(product["id"]) != int(product_id)
    ]
    candidates = [db.get_product_with_specs(product["id"]) or product for product in products]
    if not candidates:
        return {
            "selected_product": selected,
            "recommendations": [],
            "similarity_breakdown": [],
            "ranking": [selected["name"]],
            "summary": "비교할 후보 상품이 아직 없습니다. 검색 결과를 더 수집한 뒤 다시 분석하세요.",
            "scoring_criteria": _analysis_criteria(),
            "feature_comparison": [],
        }

    recommendations = _score_comparison_candidates(selected, candidates)
    top_recommendations = recommendations[:limit]
    selected_score = round(
        _metadata_score(selected) * 0.45 + _price_anchor_score(selected, candidates) * 0.55,
        2,
    )
    ranking = [selected["name"], *[item["name"] for item in top_recommendations]]
    feature_comparison = [
        {
            "feature": "recommendation_score",
            "winner": top_recommendations[0]["name"] if top_recommendations else "확인 불가",
            "detail": "상품명 유사도, 가격대 유사도, 가격 매력도, 브랜드 일치, 메타데이터 완성도를 합산했습니다.",
        },
        {
            "feature": "price",
            "winner": _lowest_price_winner([selected, *top_recommendations]),
            "detail": "현재 수집된 네이버 최저가 기준으로 가장 낮은 상품입니다.",
        },
    ]

    summary = (
        f"{selected['name']} 분석 결과, 가장 가까운 비교 후보는 "
        f"{top_recommendations[0]['name']}입니다. 추천 점수 "
        f"{top_recommendations[0]['recommendation_score']}점으로 가격대와 상품명 유사도가 높습니다."
        if top_recommendations
        else "비교 후보를 찾지 못했습니다."
    )
    return {
        "selected_product": {**selected, "selected_score": selected_score},
        "recommendations": top_recommendations,
        "similarity_breakdown": [
            {
                "product_id": item["id"],
                "product_name": item["name"],
                **item["similarity_breakdown"],
            }
            for item in top_recommendations
        ],
        "ranking": ranking,
        "summary": summary,
        "scoring_criteria": _analysis_criteria(),
        "feature_comparison": feature_comparison,
    }


def _score_comparison_candidates(
    selected: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    all_products = [selected, *candidates]
    prices = [float(product.get("latest_price") or 0) for product in all_products]
    affordability_scores = _normalize(prices, "lower_better") if any(prices) else [50.0] * len(prices)
    affordability_by_id = {
        int(product["id"]): affordability_scores[index] for index, product in enumerate(all_products)
    }

    scored: list[dict[str, Any]] = []
    for candidate in candidates:
        name_score = _name_similarity_score(selected.get("name", ""), candidate.get("name", ""))
        price_similarity = _price_similarity_score(
            selected.get("latest_price"),
            candidate.get("latest_price"),
        )
        price_value = affordability_by_id.get(int(candidate["id"]), 50.0)
        brand_score = _brand_match_score(selected, candidate)
        metadata = _metadata_score(candidate)
        recommendation_score = round(
            name_score * 0.3
            + price_similarity * 0.25
            + price_value * 0.2
            + brand_score * 0.15
            + metadata * 0.1,
            2,
        )
        enriched = dict(candidate)
        enriched["name_similarity_score"] = round(name_score, 2)
        enriched["price_similarity_score"] = round(price_similarity, 2)
        enriched["price_value_score"] = round(price_value, 2)
        enriched["brand_match_score"] = round(brand_score, 2)
        enriched["similarity_breakdown"] = {
            "name": round(name_score, 2),
            "price": round(price_similarity, 2),
            "brand": round(brand_score, 2),
        }
        enriched["metadata_score"] = round(metadata, 2)
        enriched["recommendation_score"] = recommendation_score
        enriched["recommendation_reason"] = _candidate_reason(enriched)
        scored.append(enriched)

    return sorted(scored, key=lambda item: item["recommendation_score"], reverse=True)


def _analysis_criteria() -> list[dict[str, Any]]:
    return [
        {"name": "상품명 유사도", "weight": 30, "description": "검색어/모델명 토큰이 얼마나 겹치는지"},
        {"name": "가격대 유사도", "weight": 25, "description": "선택 상품과 비슷한 가격대인지"},
        {"name": "가격 매력도", "weight": 20, "description": "같은 검색 결과 안에서 상대적으로 저렴한지"},
        {"name": "브랜드 일치", "weight": 15, "description": "브랜드 또는 제조사가 같은지"},
        {"name": "정보 완성도", "weight": 10, "description": "이미지/설명/판매처 정보가 충분한지"},
    ]


def _tokenize(value: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(value) if len(token) >= 2}


def _name_similarity_score(left: str, right: str) -> float:
    left_tokens = _tokenize(left)
    right_tokens = _tokenize(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens) * 100


def _price_similarity_score(left_price: Any, right_price: Any) -> float:
    if not left_price or not right_price:
        return 40.0
    left = max(float(left_price), 1.0)
    right = max(float(right_price), 1.0)
    diff_ratio = abs(left - right) / left
    return max(0.0, 100 - min(diff_ratio * 100, 100))


def _brand_match_score(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_brand = (left.get("brand") or left.get("maker") or "").strip().lower()
    right_brand = (right.get("brand") or right.get("maker") or "").strip().lower()
    if not left_brand or not right_brand:
        return 35.0
    return 100.0 if left_brand == right_brand else 0.0


def _metadata_score(product: dict[str, Any]) -> float:
    score = 0.0
    if product.get("image_url"):
        score += 25
    if product.get("description"):
        score += 25
    if product.get("brand") or product.get("maker"):
        score += 20
    if product.get("mall_name"):
        score += 15
    if product.get("link"):
        score += 15
    return score


def _price_anchor_score(selected: dict[str, Any], candidates: list[dict[str, Any]]) -> float:
    prices = [float(product.get("latest_price") or 0) for product in [selected, *candidates]]
    if not any(prices):
        return 50.0
    return _normalize(prices, "lower_better")[0]


def _candidate_reason(candidate: dict[str, Any]) -> str:
    return (
        f"추천 점수 {candidate['recommendation_score']}점입니다. "
        f"상품명 유사도 {candidate['name_similarity_score']}점, "
        f"가격대 유사도 {candidate['price_similarity_score']}점, "
        f"가격 매력도 {candidate['price_value_score']}점을 반영했습니다."
    )


def _lowest_price_winner(products: list[dict[str, Any]]) -> str:
    priced = [product for product in products if product.get("latest_price") is not None]
    if not priced:
        return "확인 불가"
    return min(priced, key=lambda product: int(product["latest_price"]))["name"]


def build_compare_payload(product_ids: list[int], user_priority: str | None = None) -> dict[str, Any]:
    products = []
    category_id = None
    category_name = None
    for product_id in product_ids:
        product = db.get_product_with_specs(product_id)
        if not product:
            raise ValueError(f"product {product_id}를 찾을 수 없습니다.")
        category_id = product["category_id"]
        category_name = product["category_name"]
        products.append(product)

    return {
        "category_id": category_id,
        "category": category_name,
        "products": products,
        "user_priority": user_priority or "균형",
    }


def recompute_category_recommendations() -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    for category in db.get_categories():
        scores = compute_category_scores(category["id"])
        if not scores["products"]:
            continue

        by_id = {product["id"]: product for product in scores["products"]}
        best_value = by_id[scores["best_value_product_id"]]
        best_performance = by_id[scores["best_performance_product_id"]]
        best_value_reason = (
            f"{best_value['name']}는 성능 점수 {best_value['performance_score']}점 대비 "
            f"현재가 {best_value['latest_price']:,}원으로 가성비 점수가 가장 높습니다."
        )
        best_performance_reason = (
            f"{best_performance['name']}는 핵심 스펙 가중합산 기준 "
            f"성능 점수 {best_performance['performance_score']}점으로 가장 앞섭니다."
        )
        recommendation_id = db.upsert_category_recommendation(
            category_id=category["id"],
            best_value_product_id=best_value["id"],
            best_value_score=best_value["value_score"],
            best_value_reason=best_value_reason,
            best_performance_product_id=best_performance["id"],
            best_performance_score=best_performance["performance_score"],
            best_performance_reason=best_performance_reason,
            llm_model="code-fallback",
        )
        recommendations.append(
            {
                "id": recommendation_id,
                "category_id": category["id"],
                "scores": scores,
                "best_value": best_value,
                "best_performance": best_performance,
            }
        )
    return recommendations


def check_price_alerts() -> list[dict[str, Any]]:
    triggered: list[dict[str, Any]] = []
    for alert in db.get_open_alerts():
        latest_price = alert.get("latest_price")
        if latest_price is not None and int(latest_price) <= int(alert["target_price"]):
            db.mark_alert_triggered(alert["id"], int(latest_price))
            triggered.append(alert)
    return triggered
