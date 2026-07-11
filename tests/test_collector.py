from __future__ import annotations

import collector
import db


def test_collect_products_for_search_filters_accessories(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))
    db.init_db(seed=False)
    monkeypatch.setattr(collector, "has_naver_credentials", lambda: True)
    monkeypatch.setattr(
        collector,
        "search_shop_with_retry",
        lambda query, display=20, sort="sim": (
            query,
            [
                {
                    "productId": "main-1",
                    "title": "QCY 무선 이어폰 본품",
                    "lprice": "29900",
                    "image": "https://example.com/main.jpg",
                    "mallName": "Demo",
                },
                {
                    "productId": "case-1",
                    "title": "무선 이어폰 실리콘 케이스 커버",
                    "lprice": "9900",
                    "image": "https://example.com/case.jpg",
                    "mallName": "Demo",
                },
            ],
        ),
    )

    result = collector.collect_products_for_search("무선이어폰", display=2)

    assert len(result["product_ids"]) == 1
    assert len(result["excluded_product_ids"]) == 1
    product = db.get_product(result["product_ids"][0])
    assert product["product_type"] == "main_product"
