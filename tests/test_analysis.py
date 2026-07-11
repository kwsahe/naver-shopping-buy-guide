from __future__ import annotations

import os

import analysis
import db


def test_calculate_price_statistics_percentile() -> None:
    stats = analysis.calculate_price_statistics([100, 120, 140, 160, 120])

    assert stats["current_price"] == 120
    assert stats["min_price"] == 100
    assert stats["max_price"] == 160
    assert stats["avg_price"] == 128.0
    assert stats["percentile_rank"] == 40.0


def test_calculate_product_scores_respects_directions() -> None:
    products = [
        {"name": "Heavy Long", "battery_hours": 10, "anc": True, "weight_g": 7, "latest_price": 100000},
        {"name": "Light Short", "battery_hours": 5, "anc": False, "weight_g": 3, "latest_price": 50000},
    ]
    weights = {
        "battery_hours": {"weight": 0.4, "direction": "higher_better"},
        "anc": {"weight": 0.2, "direction": "boolean_bonus"},
        "weight_g": {"weight": 0.4, "direction": "lower_better"},
    }

    scores = analysis.calculate_product_scores(products, weights)

    assert scores[0]["spec_score_breakdown"]["battery_hours"] == 100
    assert scores[1]["spec_score_breakdown"]["weight_g"] == 100
    assert scores[0]["performance_score"] == 60
    assert scores[1]["performance_score"] == 40
    assert scores[1]["value_score"] > scores[0]["value_score"]


def test_compute_category_scores_from_seed_data(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))
    db.init_db(seed=True)

    category = db.get_categories()[0]
    scores = analysis.compute_category_scores(category["id"])

    assert scores["category"] == "무선 이어폰"
    assert len(scores["products"]) >= 5
    assert scores["best_performance_candidate"]
    assert scores["best_value_candidate"]


def test_check_price_alerts_triggers(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))
    db.init_db(seed=True)
    product = db.get_products()[0]
    alert_id = db.create_alert(product["id"], int(product["latest_price"]) + 1)

    triggered = analysis.check_price_alerts()

    assert triggered[0]["id"] == alert_id


def test_db_path_env_is_respected(tmp_path, monkeypatch) -> None:
    target = tmp_path / "custom.db"
    monkeypatch.setenv("DB_PATH", str(target))
    db.init_db(seed=True)

    assert os.path.exists(target)


def test_naver_product_upsert_saves_image_and_description(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))
    db.init_db(seed=True)
    category = db.get_categories()[0]

    product_id = db.upsert_product_from_naver(
        category["id"],
        {
            "productId": "naver-demo-1",
            "title": "테스트 이어폰",
            "brand": "테스트브랜드",
            "maker": "테스트메이커",
            "mallName": "테스트몰",
            "link": "https://example.com/product",
            "image": "https://example.com/product.jpg",
            "lprice": "12345",
            "category1": "디지털",
            "category2": "음향기기",
        },
    )

    product = db.get_product(product_id)

    assert product["image_url"] == "https://example.com/product.jpg"
    assert "테스트브랜드" in product["description"]
    assert "12,345원" in product["description"]


def test_analyze_selected_product_recommends_candidates(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))
    db.init_db(seed=True)
    category = db.get_categories()[0]
    products = db.get_products(category["id"])

    result = analysis.analyze_selected_product(products[0]["id"], limit=3)

    assert result["selected_product"]["id"] == products[0]["id"]
    assert result["recommendations"]
    assert result["recommendations"][0]["recommendation_score"] >= 0
    assert result["scoring_criteria"][0]["weight"] == 30
    assert result["feature_comparison"]
