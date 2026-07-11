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
