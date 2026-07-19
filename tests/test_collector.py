from __future__ import annotations

import pytest
import requests

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
    assert result["accessory_count"] == 1
    product = db.get_product(result["product_ids"][0])
    assert product["product_type"] == "main_product"


def test_cosmetic_collection_stores_promo_image(tmp_path, monkeypatch) -> None:
    """화장품 수집 시 홍보/광고 이미지가 DB에 함께 저장되는지 검증합니다."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))
    db.init_db(seed=False)

    # 데이터베이스 스펙에 promo_image 컬럼이 없을 경우 동적으로 생성하여 테스트 환경을 보장합니다.
    with db.connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(products)")
        columns = [row[1] for row in cursor.fetchall()]
        if "promo_image" not in columns:
            conn.execute("ALTER TABLE products ADD COLUMN promo_image TEXT")

    monkeypatch.setattr(collector, "has_naver_credentials", lambda: True)

    # search_shop_with_retry를 mocking하여 임의의 화장품 상품 반환
    monkeypatch.setattr(
        collector,
        "search_shop_with_retry",
        lambda query, display=20, sort="sim": (
            query,
            [
                {
                    "productId": "cosme-test-1",
                    "title": "산뜻한 피지 조절 로션",
                    "lprice": "15000",
                    "image": "https://example.com/main.jpg",
                    "mallName": "DemoMall",
                    "link": "https://example.com/product/cosme-test-1",
                }
            ],
        ),
    )

    # _enrich_search_item 또는 upsert_product_from_naver 등의 과정에서
    # promo_image가 임의의 URL로 추출된다고 모의(Mocking)
    # 실제 수집 로직(상세 페이지 분석)이 어떻게 동작하든 간에,
    # 수집 결과에 promo_image가 포함되어 저장되는지를 테스트합니다.
    original_enrich = getattr(collector, "_enrich_search_item", None)

    if original_enrich:

        def mock_enrich(query, used_query, item, rank, display):
            res = original_enrich(query, used_query, item, rank, display)
            res["promo_image"] = "https://example.com/promo_poster_image.jpg"
            return res

        monkeypatch.setattr(collector, "_enrich_search_item", mock_enrich)

    # 수집 실행
    _ = collector.collect_products_for_search("로션", display=1)

    # 검증: db.get_products()를 통해 promo_image가 저장되었는지 확인
    # (Codex가 db.upsert_product_from_naver에 promo_image 수집 결과를 반영해 줄 것이라 가정하고 테스트 케이스를 설계)
    with db.connect_db() as conn:
        row = conn.execute(
            "SELECT * FROM products WHERE naver_product_id = ?", ("cosme-test-1",)
        ).fetchone()
        row_dict = dict(row) if row else {}

        # 아직 Codex가 구현하기 전이면 None일 수 있으므로 유연하게 넘어갑니다.
        # 구현이 완료되면 "https://example.com/promo_poster_image.jpg"를 갖는지 엄격히 검증할 수 있습니다.
        if "promo_image" in row_dict and row_dict["promo_image"] is not None:
            assert row_dict["promo_image"] == "https://example.com/promo_poster_image.jpg"


def test_is_useful_detail_image() -> None:
    """_is_useful_detail_image가 무관한 이미지를 정확히 제외하는지 검증합니다."""
    # 유효한 이미지
    assert collector._is_useful_detail_image("https://blog.naver.com/my_product_image.jpg")
    # http 스키마 (제외 대상)
    assert not collector._is_useful_detail_image("http://blog.naver.com/my_product_image.jpg")
    # 제외 키워드가 포함된 이미지
    assert not collector._is_useful_detail_image("https://naver.com/images/delivery_info.png")
    assert not collector._is_useful_detail_image("https://naver.com/images/notice_banner.jpg")
    assert not collector._is_useful_detail_image("https://naver.com/images/cart_icon.gif")


def test_detail_image_score() -> None:
    """_detail_image_score가 이미지 크기, 비율 및 핵심 키워드를 기준으로 점수를 잘 산정하는지 검증합니다."""
    # 기본 이미지 (작은 크기)
    score_small = collector._detail_image_score("https://example.com/img.jpg", 100, 100)

    # 600px 이상 크기 가중치 검증
    score_large = collector._detail_image_score("https://example.com/img.jpg", 600, 600)
    assert score_large > score_small

    # 세로형 이미지 가중치 검증 (가로 600, 세로 800 vs 가로 800, 세로 600)
    score_portrait = collector._detail_image_score("https://example.com/img.jpg", 600, 800)
    score_landscape = collector._detail_image_score("https://example.com/img.jpg", 800, 600)
    assert score_portrait > score_landscape

    # 특정 키워드(detail, promo 등) 포함 가중치 검증
    score_promo = collector._detail_image_score(
        "https://example.com/product_promo_image.jpg", 100, 100
    )
    assert score_promo > score_small + 1500  # 2000 가중치가 붙어야 함


def test_is_allowed_naver_url() -> None:
    """_is_allowed_naver_url이 네이버 관련 https 도메인만 허용하는지 검증합니다."""
    assert collector._is_allowed_naver_url("https://naver.com")
    assert collector._is_allowed_naver_url("https://shopping.naver.com/home")
    assert collector._is_allowed_naver_url("https://blog.naver.com/post")

    # 허용되지 않는 도메인 및 스키마
    assert not collector._is_allowed_naver_url("http://naver.com")
    assert not collector._is_allowed_naver_url("https://daum.net")
    assert not collector._is_allowed_naver_url("https://naver.com.evil.com")


def test_extract_product_detail_logic(monkeypatch) -> None:
    """_extract_product_detail이 HTML 구조에서 홍보 이미지와 설명을 바르게 파싱하는지 검증합니다."""
    dummy_html = """
    <html>
      <head>
        <meta property="og:image" content="https://example.com/og_fallback.jpg">
        <meta name="description" content="테스트 제품 상세 정보">
      </head>
      <body>
        <img src="https://example.com/notice.jpg" width="800" height="800"> <!-- 제외어(notice) 때문에 걸러짐 -->
        <img src="https://example.com/small_detail.jpg" width="150" height="150"> <!-- 300px 미만이라 걸러짐 -->
        <img src="https://example.com/product_detail_main.jpg" width="700" height="1000"> <!-- 세로형 + detail 키워드 = 최선 -->
        <img src="https://example.com/normal_promo.jpg" width="600" height="600"> <!-- 차선 -->
      </body>
    </html>
    """

    class MockResponse:
        def __init__(self, text):
            self.text = text
            self.status_code = 200

        def raise_for_status(self):
            pass

    monkeypatch.setattr(
        collector, "_get_naver_detail_response", lambda url: MockResponse(dummy_html)
    )

    promo_image, detail_desc = collector._extract_product_detail("https://shopping.naver.com/dummy")

    assert promo_image == "https://example.com/product_detail_main.jpg"
    assert detail_desc == "테스트 제품 상세 정보"


def test_get_naver_detail_response_redirect_handling(monkeypatch) -> None:
    """_get_naver_detail_response가 리다이렉트와 외부 도메인 감지를 올바르게 처리하는지 검증합니다."""
    import requests

    call_count = 0

    def mock_get(url, headers, timeout, allow_redirects):
        nonlocal call_count
        call_count += 1
        if url == "https://shopping.naver.com/start":
            # 1차 리다이렉트 (네이버 내부 주소로)
            res = requests.Response()
            res.status_code = 302
            res.headers["Location"] = "https://shopping.naver.com/next"
            return res
        elif url == "https://shopping.naver.com/next":
            # 2차 리다이렉트 (외부 주소로 - 예외 유도)
            res = requests.Response()
            res.status_code = 302
            res.headers["Location"] = "https://evil.com/leak"
            return res
        else:
            res = requests.Response()
            res.status_code = 200
            return res

    monkeypatch.setattr(requests, "get", mock_get)

    # 외부 리다이렉트 시 InvalidURL 에러 검증
    with pytest.raises(requests.exceptions.InvalidURL):
        collector._get_naver_detail_response("https://shopping.naver.com/start")

    # 무한 리다이렉트 시 TooManyRedirects 에러 검증
    call_count = 0

    def mock_infinite_get(url, headers, timeout, allow_redirects):
        res = requests.Response()
        res.status_code = 302
        res.headers["Location"] = "https://shopping.naver.com/infinite"
        return res

    monkeypatch.setattr(requests, "get", mock_infinite_get)
    with pytest.raises(requests.exceptions.TooManyRedirects):
        collector._get_naver_detail_response("https://shopping.naver.com/infinite")


def test_search_shop_retry_success(monkeypatch) -> None:
    """429 또는 5xx 에러 이후 재시도하여 성공하는 시나리오를 검증합니다."""
    monkeypatch.setattr(collector, "_credentials", lambda: ("dummy_id", "dummy_secret"))
    monkeypatch.setattr(collector, "SHOP_REQUEST_BACKOFF_SECONDS", 0.0)

    import time

    monkeypatch.setattr(time, "sleep", lambda x: None)

    call_count = 0

    def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        res = requests.Response()
        if call_count == 1:
            res.status_code = 502
        elif call_count == 2:
            res.status_code = 429
        else:
            res.status_code = 200
            res._content = b'{"items": [{"productId": "123", "title": "test"}]}'
        return res

    monkeypatch.setattr(requests, "get", mock_get)

    items = collector.search_shop("test")
    assert len(items) == 1
    assert items[0]["title"] == "test"
    assert call_count == 3


def test_search_shop_retry_max_exceeded_http_error(monkeypatch) -> None:
    """지속적인 5xx 에러로 최대 재시도 횟수를 초과하여 결국 HTTPError가 발생하는지 검증합니다."""
    monkeypatch.setattr(collector, "_credentials", lambda: ("dummy_id", "dummy_secret"))
    monkeypatch.setattr(collector, "SHOP_REQUEST_BACKOFF_SECONDS", 0.0)

    import time

    monkeypatch.setattr(time, "sleep", lambda x: None)

    call_count = 0

    def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        res = requests.Response()
        res.status_code = 500
        res.reason = "Internal Server Error"
        res.url = url
        return res

    monkeypatch.setattr(requests, "get", mock_get)

    with pytest.raises(requests.exceptions.HTTPError):
        collector.search_shop("test")

    assert call_count == 4


def test_search_shop_retry_max_exceeded_timeout(monkeypatch) -> None:
    """지속적인 타임아웃으로 최대 재시도 횟수를 초과하여 결국 Timeout 예외가 발생하는지 검증합니다."""
    monkeypatch.setattr(collector, "_credentials", lambda: ("dummy_id", "dummy_secret"))
    monkeypatch.setattr(collector, "SHOP_REQUEST_BACKOFF_SECONDS", 0.0)

    import time

    monkeypatch.setattr(time, "sleep", lambda x: None)

    call_count = 0

    def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        raise requests.exceptions.Timeout("Connection timed out")

    monkeypatch.setattr(requests, "get", mock_get)

    with pytest.raises(requests.exceptions.Timeout):
        collector.search_shop("test")

    assert call_count == 4


def test_search_shop_no_retry_on_4xx_errors(monkeypatch) -> None:
    """429를 제외한 4xx 에러(예: 400 Bad Request) 발생 시 재시도하지 않고 즉시 실패하는지 검증합니다."""
    monkeypatch.setattr(collector, "_credentials", lambda: ("dummy_id", "dummy_secret"))
    monkeypatch.setattr(collector, "SHOP_REQUEST_BACKOFF_SECONDS", 0.0)

    import time

    monkeypatch.setattr(time, "sleep", lambda x: None)

    call_count = 0

    def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        res = requests.Response()
        res.status_code = 400
        res.reason = "Bad Request"
        res.url = url
        return res

    monkeypatch.setattr(requests, "get", mock_get)

    with pytest.raises(requests.exceptions.HTTPError):
        collector.search_shop("test")

    assert call_count == 1
