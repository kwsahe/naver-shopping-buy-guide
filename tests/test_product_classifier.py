from __future__ import annotations

from product_classifier import classify_search_item


def test_classifier_marks_accessory_for_product_search() -> None:
    result = classify_search_item(
        "무선이어폰",
        {"title": "무선 이어폰 실리콘 케이스 커버", "lprice": "9900", "image": "x"},
        rank=1,
    )

    assert result["product_type"] == "accessory"
    assert result["classification_score"] < 55
    assert "부속품" in result["classification_reason"]


def test_classifier_keeps_main_product() -> None:
    result = classify_search_item(
        "무선이어폰",
        {"title": "QCY 블루투스 무선 이어폰 본품", "lprice": "29900", "image": "x"},
        rank=1,
    )

    assert result["product_type"] == "main_product"
    assert result["classification_score"] >= 55


def test_classifier_rejects_accessory_with_high_query_overlap() -> None:
    # 쿼리가 "에어팟 프로"이고 상품명이 "에어팟 프로 가죽 케이스 키링 세트"일 때,
    # 겹치는 단어(에어팟, 프로)가 많아 점수가 크게 가산되어도 부속품 키워드(케이스, 키링) 등으로 인해
    # accessory(score < 55)로 제대로 분류되어야 함.
    result = classify_search_item(
        "에어팟 프로",
        {
            "title": "에어팟 프로 가죽 케이스 키링 세트",
            "lprice": "15000",
            "image": "https://example.com/img.jpg",
        },
        rank=1,
    )

    assert result["product_type"] == "accessory"
    assert result["classification_score"] < 55
