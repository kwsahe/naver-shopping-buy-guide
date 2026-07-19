from __future__ import annotations

import antigravity_cli
import collector
import db


def _setup_cosmetic_demo_data(tmp_path, monkeypatch) -> None:
    """테스트를 위해 화장품 데모 데이터를 세팅합니다."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setattr(collector, "has_naver_credentials", lambda: False)
    db.init_db(seed=False)

    with db.connect_db() as conn:
        # 데이터베이스 스펙에 promo_image 컬럼이 없을 경우 동적으로 생성하여 테스트 환경을 보장합니다.
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(products)")
        columns = [row[1] for row in cursor.fetchall()]
        if "promo_image" not in columns:
            conn.execute("ALTER TABLE products ADD COLUMN promo_image TEXT")

        # 카테고리 등록
        lotion_cat_id = conn.execute(
            "INSERT INTO categories (name) VALUES (?) RETURNING id", ("로션",)
        ).fetchone()["id"]
        shampoo_cat_id = conn.execute(
            "INSERT INTO categories (name) VALUES (?) RETURNING id", ("샴푸",)
        ).fetchone()["id"]
        earphone_cat_id = conn.execute(
            "INSERT INTO categories (name) VALUES (?) RETURNING id", ("이어폰",)
        ).fetchone()["id"]

        # 상품 등록 (홍보 포스터 이미지인 promo_image 필드 추가 포함)
        # 1. 지성 피부용 로션
        conn.execute(
            """
            INSERT INTO products (category_id, naver_product_id, name, description, brand, maker, product_type, promo_image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lotion_cat_id,
                "cosme-1",
                "산뜻한 피지 조절 로션",
                "지성 피부를 위한 가벼운 오일프리 젤 제형 로션입니다.",
                "브랜드A",
                "제조사A",
                "main_product",
                "https://example.com/promo_lotion_oily.jpg",
            ),
        )
        # 2. 건성 피부용 로션
        conn.execute(
            """
            INSERT INTO products (category_id, naver_product_id, name, description, brand, maker, product_type, promo_image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lotion_cat_id,
                "cosme-2",
                "울트라 보습 크림 로션",
                "건성 피부에 깊은 수분과 영양을 공급하는 촉촉한 크림입니다.",
                "브랜드B",
                "제조사B",
                "main_product",
                "https://example.com/promo_lotion_dry.jpg",
            ),
        )
        # 3. 지성 두피용 샴푸
        conn.execute(
            """
            INSERT INTO products (category_id, naver_product_id, name, description, brand, maker, product_type, promo_image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                shampoo_cat_id,
                "cosme-3",
                "티트리 쿨 딥클렌징 샴푸",
                "지성 두피와 지루성 두피를 시원하게 스칼프 케어 해주는 샴푸입니다.",
                "브랜드C",
                "제조사C",
                "main_product",
                "https://example.com/promo_shampoo_oily.jpg",
            ),
        )
        # 4. 비화장품 (추천 로직에서 걸러져야 함)
        conn.execute(
            """
            INSERT INTO products (category_id, naver_product_id, name, description, brand, maker, product_type, promo_image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                earphone_cat_id,
                "earphone-1",
                "QCY 무선 이어폰 본품",
                "최고의 음질을 자랑하는 블루투스 무선 이어폰.",
                "QCY",
                "QCY",
                "main_product",
                None,
            ),
        )

        # 가격 이력 추가 (latest_price를 계산할 수 있도록)
        conn.execute("INSERT INTO price_history (product_id, price) VALUES (1, 15000)")
        conn.execute("INSERT INTO price_history (product_id, price) VALUES (2, 18000)")
        conn.execute("INSERT INTO price_history (product_id, price) VALUES (3, 12000)")
        conn.execute("INSERT INTO price_history (product_id, price) VALUES (4, 29900)")


def test_antigravity_cli_recommendation_logic(tmp_path, monkeypatch) -> None:
    """antigravity_cli.py의 룰베이스 추천 로직을 검증합니다."""
    _setup_cosmetic_demo_data(tmp_path, monkeypatch)

    # 1. 지성 피부 조건 추천 검증 (피지 조절 로션이 1위여야 함)
    oily_results = antigravity_cli.recommend_products(skin_type="oily", hair_type=None)
    assert len(oily_results) > 0
    assert "피지 조절 로션" in oily_results[0]["name"]
    assert oily_results[0]["recommend_score"] > 0
    # promo_image가 결과에 포함되는지 확인
    assert oily_results[0]["promo_image"] == "https://example.com/promo_lotion_oily.jpg"

    # 2. 건성 피부 조건 추천 검증 (울트라 보습 크림 로션이 1위여야 함)
    dry_results = antigravity_cli.recommend_products(skin_type="dry", hair_type=None)
    assert len(dry_results) > 0
    assert "보습 크림 로션" in dry_results[0]["name"]

    # 3. 지성 두피 조건 추천 검증 (티트리 쿨 딥클렌징 샴푸가 추천되어야 함)
    oily_hair_results = antigravity_cli.recommend_products(skin_type=None, hair_type="oily")
    assert len(oily_hair_results) > 0
    assert "티트리 쿨" in oily_hair_results[0]["name"]

    # 4. 비화장품 필터링 검증 (무선 이어폰이 추천 결과에 절대 포함되면 안 됨)
    all_results = antigravity_cli.recommend_products(skin_type="oily", hair_type="oily")
    for item in all_results:
        assert "이어폰" not in item["name"]


def test_api_recommend_endpoint_integration(tmp_path, monkeypatch) -> None:
    """
    Codex가 구현할 /api/recommend 엔드포인트를 검증합니다.
    구현 전(404 에러 시)에는 테스트를 유연하게 skip하며, 구현이 완료되면 통합 테스트로 작동합니다.
    """
    _setup_cosmetic_demo_data(tmp_path, monkeypatch)

    # app 생성
    from app import create_app

    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()

    response = client.get("/api/recommend?skin_type=oily")
    assert response.status_code == 200
    data = response.get_json()
    assert "recommendations" in data
    assert len(data["recommendations"]) > 0

    first_item = data["recommendations"][0]
    assert "피지 조절 로션" in first_item["name"]
    # 룰베이스 추천 점수, 추천 사유, 홍보 이미지가 반환 필드에 포함되는지 정밀 검증
    assert "recommend_score" in first_item
    assert "recommend_reasons" in first_item
    assert "promo_image" in first_item
    assert first_item["promo_image"] == "https://example.com/promo_lotion_oily.jpg"

    # 이어폰 등 비화장품이 결과에서 완전히 배제되었는지 검증
    for rec in data["recommendations"]:
        assert "이어폰" not in rec["name"]


def test_api_recommend_invalid_params(tmp_path, monkeypatch) -> None:
    """/api/recommend 엔드포인트의 입력값 검증과 한글 에러 응답을 테스트합니다."""
    _setup_cosmetic_demo_data(tmp_path, monkeypatch)
    from app import create_app

    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()

    # 1. skin_type과 hair_type이 둘 다 없을 때
    response = client.get("/api/recommend")
    assert response.status_code == 400
    assert response.get_json()["error"] == "skin_type 또는 hair_type 중 하나를 입력하세요."

    # 2. 잘못된 skin_type
    response = client.get("/api/recommend?skin_type=normal")
    assert response.status_code == 400
    assert response.get_json()["error"] == "skin_type은 dry, oily, sensitive 중 하나여야 합니다."

    # 3. 잘못된 hair_type
    response = client.get("/api/recommend?hair_type=normal")
    assert response.status_code == 400
    assert response.get_json()["error"] == "hair_type은 dry, oily 중 하나여야 합니다."

    # 4. 잘못된 limit (숫자가 아님)
    response = client.get("/api/recommend?skin_type=oily&limit=abc")
    assert response.status_code == 400
    assert response.get_json()["error"] == "limit은 1 이상 100 이하의 정수여야 합니다."

    # 5. 잘못된 limit 범위 초과 (1 미만)
    response = client.get("/api/recommend?skin_type=oily&limit=0")
    assert response.status_code == 400
    assert response.get_json()["error"] == "limit은 1 이상 100 이하의 정수여야 합니다."

    # 6. 잘못된 limit 범위 초과 (100 초과)
    response = client.get("/api/recommend?skin_type=oily&limit=101")
    assert response.status_code == 400
    assert response.get_json()["error"] == "limit은 1 이상 100 이하의 정수여야 합니다."


def test_antigravity_cli_hair_excludes_bodywash(tmp_path, monkeypatch) -> None:
    """hair_type 추천 시 바디워시가 헤어 추천 대상에서 올바르게 배제되는지 검증합니다."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "app.db"))
    db.init_db(seed=False)

    with db.connect_db() as conn:
        shampoo_cat_id = conn.execute(
            "INSERT INTO categories (name) VALUES (?) RETURNING id", ("샴푸",)
        ).fetchone()["id"]
        bodywash_cat_id = conn.execute(
            "INSERT INTO categories (name) VALUES (?) RETURNING id", ("바디워시",)
        ).fetchone()["id"]

        # 샴푸 등록
        conn.execute(
            """
            INSERT INTO products (category_id, naver_product_id, name, description, brand, maker, product_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                shampoo_cat_id,
                "shampoo-1",
                "건조한 모발 샴푸",
                "건조 모발용 샴푸",
                "브랜드A",
                "제조사A",
                "main_product",
            ),
        )
        # 바디워시 등록
        conn.execute(
            """
            INSERT INTO products (category_id, naver_product_id, name, description, brand, maker, product_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                bodywash_cat_id,
                "bodywash-1",
                "촉촉한 바디워시",
                "건조 피부용 바디워시",
                "브랜드B",
                "제조사B",
                "main_product",
            ),
        )

        conn.execute("INSERT INTO price_history (product_id, price) VALUES (1, 10000)")
        conn.execute("INSERT INTO price_history (product_id, price) VALUES (2, 12000)")

    # hair_type="dry"만 지정했을 때, 바디워시("건조 피부용 바디워시")가 "건조" 키워드를 가지고 있더라도
    # HAIR_CATEGORIES가 아니므로 추천 목록에서 제외되거나 점수가 부여되지 않아야 함.
    results = antigravity_cli.recommend_products(skin_type=None, hair_type="dry")

    # 샴푸만 추천되고 바디워시는 추천 목록에 없어야 함
    assert len(results) == 1
    assert "샴푸" in results[0]["name"]
    assert "바디워시" not in results[0]["name"]


def test_api_recommend_skin_conditions_repeated_params(tmp_path, monkeypatch) -> None:
    """GET 요청에서 skin_conditions 다중 반복 파라미터 수신을 검증합니다."""
    _setup_cosmetic_demo_data(tmp_path, monkeypatch)
    from app import create_app

    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()

    response = client.get("/api/recommend?skin_conditions=pore_wide&skin_conditions=oiliness")
    assert response.status_code == 200
    data = response.get_json()
    assert "recommendations" in data
    assert "skin_conditions" in data
    # 중복 제거 및 소문자화 등이 순서 유지하며 반영되었는지 검사
    assert data["skin_conditions"] == ["pore_wide", "oiliness"]


def test_api_recommend_skin_conditions_post_json(tmp_path, monkeypatch) -> None:
    """POST 요청에서 JSON 배열 형태로 skin_conditions 수신을 검증합니다."""
    _setup_cosmetic_demo_data(tmp_path, monkeypatch)
    from app import create_app

    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()

    response = client.post("/api/recommend", json={"skin_conditions": ["pore_wide", "oiliness"]})
    assert response.status_code == 200
    data = response.get_json()
    assert "recommendations" in data
    assert data["skin_conditions"] == ["pore_wide", "oiliness"]


def test_api_recommend_skin_conditions_validation(tmp_path, monkeypatch) -> None:
    """skin_conditions의 공백 제거, 소문자화, 중복 제거, 미지원 값 및 최대 개수 검증을 테스트합니다."""
    _setup_cosmetic_demo_data(tmp_path, monkeypatch)
    from app import create_app

    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()

    # 공백 제거, 소문자화, 중복 제거 검증
    response = client.get(
        "/api/recommend?skin_conditions= PORE_WIDE &skin_conditions=oiliness&skin_conditions=pore_wide"
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["skin_conditions"] == ["pore_wide", "oiliness"]

    # 미지원 값 포함 시 400 에러 검증
    response_invalid = client.get(
        "/api/recommend?skin_conditions=pore_wide&skin_conditions=invalid_condition"
    )
    assert response_invalid.status_code == 400
    assert "지원하지 않는" in response_invalid.get_json().get(
        "error", ""
    ) or "피부 상태" in response_invalid.get_json().get("error", "")

    # 최대 5개 초과 시 400 에러 검증
    # 후보: pore_wide, pore_clogged, oiliness, dry_tight, sensitive_redness, trouble_acne, flaky, pigmentation_dullness
    response_excessive = client.get(
        "/api/recommend?skin_conditions=pore_wide&skin_conditions=pore_clogged&skin_conditions=oiliness&skin_conditions=dry_tight&skin_conditions=sensitive_redness&skin_conditions=trouble_acne"
    )
    assert response_excessive.status_code == 400
    assert "5개" in response_excessive.get_json().get(
        "error", ""
    ) or "최대" in response_excessive.get_json().get("error", "")


def test_api_recommend_skin_conditions_reasons_and_disclaimer(tmp_path, monkeypatch) -> None:
    """추천 사유 생성 규칙(치료 보장 표현 금지) 및 의료적 진단 아님 안내문구가 포함되는지 검증합니다."""
    _setup_cosmetic_demo_data(tmp_path, monkeypatch)
    from app import create_app

    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()

    response = client.get("/api/recommend?skin_conditions=oiliness")
    assert response.status_code == 200
    data = response.get_json()

    # 1. 의료적 진단 아님 안내문구(disclaimer) 포함 여부 검증
    assert "disclaimer" in data
    assert "의료적 진단이 아닙니다" in data["disclaimer"]

    # 2. 추천 사유 검증 ("치료", "개선" 등 보장 문구 배제 및 "관련 표현이 확인됨" 등 매칭 근거 존재 시만 생성)
    recommendations = data["recommendations"]
    assert len(recommendations) > 0

    # "피지 조절 로션" (id: 1)은 "피지" 키워드가 있으므로 사유에 포함되어야 하고,
    # "울트라 보습 크림 로션" (id: 2)은 "피지" 키워드가 없으므로 사유가 없거나 점수가 0이어야 함 (혹은 추천 사유에 근거 없는 내용이 빠져야 함)
    for rec in recommendations:
        reasons = rec.get("recommend_reasons", [])
        if "피지 조절 로션" in rec["name"]:
            assert len(reasons) > 0
            for reason in reasons:
                assert "치료" not in reason
                assert "개선" not in reason
                assert "보장" not in reason
                assert "관련 표현" in reason or "확인됨" in reason
        else:
            # 매칭 키워드가 없는 상품은 사유가 없거나, "피지" 관련 매칭 근거가 적혀있으면 안됨.
            for reason in reasons:
                assert "피지" not in reason
