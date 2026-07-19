#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from typing import Any

import db

TYPE_LABELS = {
    "dry": "건성/건조",
    "oily": "지성",
    "sensitive": "민감성",
}

COSMETIC_CATEGORIES = (
    "샴푸",
    "바디워시",
    "로션",
    "폼클렌징",
    "폼클렌저",
    "화장품",
    "shampoo",
    "bodywash",
    "lotion",
    "cleansing",
)
SKIN_CATEGORIES = (
    "바디워시",
    "로션",
    "폼클렌징",
    "폼클렌저",
    "bodywash",
    "body wash",
    "lotion",
    "cleansing",
)
HAIR_CATEGORIES = ("샴푸", "shampoo")


def recommend_products(skin_type: str | None, hair_type: str | None) -> list[dict[str, Any]]:
    """피부 및 모발 상태에 기반한 룰베이스 추천 로직을 수행합니다."""
    products = db.get_products()
    recommendations: list[dict[str, Any]] = []

    # 룰 매칭 키워드 정의
    rules = {
        "skin": {
            "dry": ["보습", "수분", "건성", "영양", "크림", "촉촉", "히알루론산"],
            "oily": ["지성", "피지", "가벼운", "젤", "산뜻", "오일프리", "세범"],
            "sensitive": [
                "민감",
                "진정",
                "순한",
                "약산성",
                "시카",
                "저자극",
                "아토피",
                "무향",
            ],
        },
        "hair": {
            "dry": ["건조", "손상", "영양", "보습", "단백질", "케어", "윤기", "아르간"],
            "oily": [
                "지성",
                "지루성",
                "클렌징",
                "쿨",
                "민트",
                "티트리",
                "스칼프",
                "두피",
                "딥클렌징",
            ],
        },
    }

    for product in products:
        category_name = product.get("category_name", "").lower()
        name = product.get("name", "")
        description = product.get("description", "") or ""
        text_to_search = (name + " " + description).lower()

        score = 0.0
        matched_reasons = []

        # 화장품 카테고리 여부 판단 (샴푸, 바디워시, 로션, 폼클렌징 등)
        is_cosmetic = any(category in category_name for category in COSMETIC_CATEGORIES)

        if not is_cosmetic:
            continue

        # 피부 타입 매칭 (로션, 폼클렌징 등의 스킨케어 제품 위주)
        if skin_type and any(category in category_name for category in SKIN_CATEGORIES):
            score += 0.5
            keywords = rules["skin"].get(skin_type, [])
            matches = [kw for kw in keywords if kw in text_to_search]
            if matches:
                score += len(matches) * 1.5
                matched_reasons.append(
                    f"{TYPE_LABELS[skin_type]} 피부에 맞는 표현이 확인되었습니다: {', '.join(matches)}"
                )
            else:
                matched_reasons.append(
                    f"{TYPE_LABELS[skin_type]} 피부용 제품군에서 확인한 추천 후보입니다."
                )

        # 모발 타입 매칭 (샴푸, 바디워시 등의 헤어/바디 제품 위주)
        if hair_type and any(category in category_name for category in HAIR_CATEGORIES):
            score += 0.5
            keywords = rules["hair"].get(hair_type, [])
            matches = [kw for kw in keywords if kw in text_to_search]
            if matches:
                score += len(matches) * 1.5
                matched_reasons.append(
                    f"{TYPE_LABELS[hair_type]} 두피·모발에 맞는 표현이 확인되었습니다: "
                    f"{', '.join(matches)}"
                )
            else:
                matched_reasons.append(
                    f"{TYPE_LABELS[hair_type]} 두피·모발용 제품군에서 확인한 추천 후보입니다."
                )

        # 추천 점수가 부여되었거나 타입이 지정되지 않은 경우 후보군에 포함
        if score > 0 or (not skin_type and not hair_type):
            product_copy = dict(product)
            product_copy["recommend_score"] = score
            product_copy["recommend_reasons"] = matched_reasons
            recommendations.append(product_copy)

    # 점수 높은 순, 가격 낮은 순으로 정렬
    recommendations.sort(
        key=lambda item: (
            -item.get("recommend_score", 0.0),
            item.get("latest_price") or float("inf"),
        )
    )
    return recommendations


def main() -> None:
    parser = argparse.ArgumentParser(description="Antigravity 임시 화장품 추천 CLI 도구")
    parser.add_argument(
        "--skin",
        choices=["dry", "oily", "sensitive"],
        help="피부 타입을 입력하세요 (dry: 건성, oily: 지성, sensitive: 민감성)",
    )
    parser.add_argument(
        "--hair",
        choices=["dry", "oily"],
        help="모발 타입을 입력하세요 (dry: 건조/손상, oily: 지성)",
    )

    args = parser.parse_args()

    try:
        results = recommend_products(args.skin, args.hair)
    except Exception as e:
        print(f"오류가 발생했습니다: {e}", file=sys.stderr)
        sys.exit(1)

    print("=" * 60)
    print(" [Antigravity 화장품 맞춤 추천 결과]")
    print(
        " 입력 조건 - "
        f"피부 타입: {TYPE_LABELS.get(args.skin, '미지정')}, "
        f"모발 타입: {TYPE_LABELS.get(args.hair, '미지정')}"
    )
    print("=" * 60)

    if not results:
        print("조건에 부합하는 추천 상품이 존재하지 않거나 데이터베이스가 비어 있습니다.")
        return

    for idx, item in enumerate(results[:5], 1):
        price_str = f"{item['latest_price']:,}원" if item.get("latest_price") is not None else "가격 정보 없음"
        print(f"{idx}. [{item['category_name']}] {item['name']}")
        print(f"   - 브랜드/제조사: {item.get('brand') or '알 수 없음'} / {item.get('maker') or '알 수 없음'}")
        print(f"   - 가격: {price_str}")
        if item.get("recommend_reasons"):
            print("   - 추천 사유:")
            for reason in item["recommend_reasons"]:
                print(f"     * {reason}")
        print("-" * 60)


if __name__ == "__main__":
    main()
