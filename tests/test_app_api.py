from __future__ import annotations

import collector
import db


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setattr(collector, "has_naver_credentials", lambda: False)
    from app import create_app

    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_search_response_has_timing_and_accessory_count(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/search?q=무선 이어폰")
    body = response.get_json()

    assert response.status_code == 200
    assert "took_ms" in body
    assert isinstance(body["took_ms"], int | float)
    assert body["took_ms"] >= 0
    assert "accessory_count" in body
    assert isinstance(body["accessory_count"], int)
    assert body["accessory_count"] >= 0
    assert body["accessory_count"] == body["search"]["accessory_count"]
    assert "all_product_ids" in body["search"]
    assert "excluded_count" in body["search"]


def test_compare_form_redirects_with_error(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    category_id = db.get_categories()[0]["id"]

    response = client.post("/compare", data={"category_id": category_id, "product_ids": "broken"})

    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/categories/{category_id}?error=select_more")


def test_compare_form_redirects_to_index_on_missing_category(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    # category_id가 없거나 파싱 실패 시 메인 페이지로 에러 파라미터를 들고 리다이렉트되는지 검증
    response = client.post("/compare", data={"product_ids": "broken"})

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/?error=select_more")


def test_alert_filter_and_cancel(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    products = db.get_products()
    alert_id = db.create_alert(products[0]["id"], 1000)
    db.create_alert(products[1]["id"], 2000)

    listed = client.get(f"/api/alerts?product_id={products[0]['id']}").get_json()
    cancelled = client.post(f"/api/alerts/{alert_id}/cancel")

    assert [alert["id"] for alert in listed["alerts"]] == [alert_id]
    assert cancelled.status_code == 200
    assert cancelled.get_json()["alert"]["cancelled"] == 1
    assert client.post(f"/api/alerts/{alert_id}/cancel").status_code == 400
    assert client.post("/api/alerts/999999/cancel").status_code == 404


def test_alert_isolation_and_db_state(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    products = db.get_products()
    p0_id = products[0]["id"]
    p1_id = products[1]["id"]

    alert0_id = db.create_alert(p0_id, 1000)
    alert1_id = db.create_alert(p1_id, 2000)

    # 격리 검증: p0_id로만 조회 시 alert0_id만 나오고 alert1_id는 조회되지 않아야 함
    res0 = client.get(f"/api/alerts?product_id={p0_id}").get_json()
    alert_ids = [a["id"] for a in res0["alerts"]]
    assert alert0_id in alert_ids
    assert alert1_id not in alert_ids

    # 취소 시 DB get_open_alerts() 목록에서 제외 상태 확인
    client.post(f"/api/alerts/{alert0_id}/cancel")
    open_alerts = db.get_open_alerts()
    open_alert_ids = [a["id"] for a in open_alerts]
    assert alert0_id not in open_alert_ids
    assert alert1_id in open_alert_ids


def test_compare_form_error_renders_notice_banner(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    category_id = db.get_categories()[0]["id"]

    # 잘못된 데이터로 POST 후 리다이렉트 경로를 따라가서 HTML 확인
    response = client.post(
        "/compare",
        data={"category_id": category_id, "product_ids": "broken"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    html_content = response.get_data(as_text=True)
    assert "비교할 상품을 2개 이상 선택하세요." in html_content


def test_compare_form_missing_category_renders_notice_banner(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    # category_id가 유실되었을 때 메인 페이지(/)로 리다이렉트되어 에러 배너가 나타나는지 확인
    response = client.post("/compare", data={"product_ids": "broken"}, follow_redirects=True)

    assert response.status_code == 200
    html_content = response.get_data(as_text=True)
    assert "비교할 상품을 2개 이상 선택하세요." in html_content


def test_search_delay_badge_rendering(tmp_path, monkeypatch) -> None:
    import time

    from collector import collect_products_for_search as original_collect

    client = _client(tmp_path, monkeypatch)

    # collect_products_for_search 호출 시 강제로 1.3초 지연을 유발
    def mock_collect(*args, **kwargs):
        time.sleep(1.3)
        return original_collect(*args, **kwargs)

    monkeypatch.setattr("app.collect_products_for_search", mock_collect)

    response = client.get("/search?q=무선 이어폰")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "응답 지연 감지" in html


def test_search_no_delay_badge_rendering(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.get("/search?q=무선 이어폰")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "응답 지연 감지" not in html


def test_collect_response_reports_verified_catalog_targets(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    import app

    products = [{"id": product_id} for product_id in range(1, 7)]
    monkeypatch.setattr(app, "collect_prices_for_all_products", lambda: [])
    monkeypatch.setattr(app, "collect_cosmetic_catalog", lambda: products)
    monkeypatch.setattr(
        app.db,
        "get_collection_summary",
        lambda product_ids: {
            "price_segments": {"고가": 100, "저가": 100, "검색 상위": 100},
            "category_counts": {"화장품": 100, "클렌징폼": 101, "로션": 102},
            "review_count": 12,
        },
    )
    monkeypatch.setattr(
        app.analysis,
        "recompute_category_recommendations",
        lambda: None,
    )

    response = client.post("/api/collect")
    body = response.get_json()

    assert response.status_code == 200
    assert body["target_met"] is True
    assert body["target_per_category"] == 100
    assert body["review_count"] == 12
    assert body["review_collection"] == "public_product_data_or_naver_blog_excerpts"
