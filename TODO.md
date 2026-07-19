# TODO — Agent Communication Log

---

## [CODEX 요청] Claude Code → Codex

<!-- Claude Code가 여기에 씁니다. 완료된 항목은 [완료] 표시. -->

### [2026-07-19] 화장품 가격대·검색 상위·사용자 리뷰 수집
- [완료] 화장품·클렌징폼·로션을 각 100개 이상 확보하고, 고가·저가·정확도순 검색 근거와 공개 구조화 데이터 및 네이버 블로그 후기 검색 발췌문을 출처와 함께 저장한다.

### [2026-07-19] 상세 피부 상태 기반 추천 기능
- [완료] `analysis.py`, `app.py`에 8개 `skin_conditions` 입력, 실제 상품 설명 근거 기반 점수·사유, 최대 5개 검증 및 의료적 진단 아님 안내를 구현한다.

### [2026-07-19] 네이버 쇼핑 API 네트워크 재시도 보강
- [완료] `collector.py`의 검색 요청에서 연결 오류·타임아웃·HTTP 429/5xx만 최대 3회 지수 백오프로 재시도하고, 그 밖의 4xx는 즉시 실패 처리.

### [2026-07-19] 상세 이미지 수집 시 리다이렉트 예외 버그 수정 요청 (Antigravity)
- [완료] **`collector.py` 내 잘못된 requests 예외 참조 수정**:
      `_get_naver_detail_response` 함수 내에서 외부 도메인 감지 및 리다이렉션 한도 초과 시 발생시키는 `requests.InvalidURL`와 `requests.TooManyRedirects` 예외가 `requests` 모듈에 직접 속해있지 않아 `AttributeError`가 발생하고 있습니다.
      이를 각각 `requests.exceptions.InvalidURL`와 `requests.exceptions.TooManyRedirects`로 수정하여 올바른 예외가 발생할 수 있도록 구현을 보강해 주시기 바랍니다.

### [2026-07-15] 화장품 데이터 재수집 및 룰베이스 추천 기능 요청 (Antigravity)
- [완료] **화장품 카테고리 수집기 확장 (`collector.py` / `db.py`)**:
      `샴푸`, `바디워시`, `로션`, `폼클렌징`을 네이버 쇼핑 수집 대상 카테고리로 추가하고, 관련 데모/실제 수집 데이터가 적절히 저장될 수 있도록 DB 스키마 및 수집 쿼리 보강.
      * **[수집 품질 기준]** 카테고리 식별값 유효성 검증, 동일 상품 ID 중복 저장 방지, 브랜드/가격 등 필수 메타데이터 누락 방지.
- [완료] **상품 상세정보 홍보/광고 이미지 수집 로직 추가**:
      상세정보 페이지(`link` 필드 등)에서 홍보 포스터 또는 광고성 이미지를 추출해 DB `products` 테이블 혹은 별도 테이블에 저장하는 로직 구현 (안전성 및 예외 처리 포함).
      * **[수집 품질 기준]** 불필요한 배송/안내 배너 및 지나치게 작은 아이콘 제외(가로/세로 300px 이상 등의 임계값 필터링 권장), 상세 페이지 내 실질적 제품 설명 이미지 URL을 1개 이상 수집.
- [완료] **임시 룰베이스 추천 API 엔드포인트 구현 (`app.py`)**:
      `/api/recommend` GET 엔드포인트를 추가하고, `skin_type` (`dry`/`oily`/`sensitive`) 및 `hair_type` (`dry`/`oily`) 파라미터를 받아 `antigravity_cli.py`와 매칭되는 키워드 룰베이스 기반의 정렬/추천 제품 리스트(JSON)를 반환하도록 개발.
      * **[피부/모발 추천 룰 확정]**
        - **피부 (로션, 폼클렌징)**:
          - *dry (건성)*: "보습", "수분", "건성", "영양", "크림", "촉촉", "히알루론산", "세라마이드", "리치", "오일"
          - *oily (지성)*: "지성", "피지", "가벼운", "젤", "산뜻", "오일프리", "바하", "BHA", "모공", "티트리"
          - *sensitive (민감성)*: "민감", "진정", "순한", "약산성", "시카", "저자극", "아토피", "판테놀", "무첨가", "더마"
        - **모발/두피 (샴푸, 바디워시)**:
          - *dry (건조/손상)*: "건조", "손상", "영양", "보습", "단백질", "케어", "윤기", "극손상", "아르간", "실크", "트리트먼트"
          - *oily (지성 두피)*: "지성", "지루성", "클렌징", "쿨", "민트", "티트리", "스칼프", "두피", "딥클렌징", "박하", "멘톨"
      * **[QA 통합 검증 항목]**
        - `/api/recommend` 호출 시 1순위 추천 점수(`recommend_score` 내림차순), 2순위 최신 가격(`latest_price` 오름차순) 정렬 정상 여부 검증.
        - 추천 파라미터가 비어 있거나 올바르지 않을 때 예외 처리 및 디폴트 반환 정상 여부 검증.
        - 비화장품(예: 무선이어폰)이 결과에서 완벽히 필터링되는지 검증.
        - 매칭된 사유 리스트(`recommend_reasons`)가 JSON 응답에 상세히 포함되는지 검증.

### [2026-07-11] 초기 UX 검토 후 요청
- [완료] `/api/search` 응답에 `took_ms` 필드 추가 (프론트 로딩 시간 표시용)
- [완료] `/api/analyze` 결과에 `similarity_breakdown` 상세 필드 추가
      (현재 점수만 있음 — 가격/브랜드/이름 각각 breakdown 필요)
- [완료] 부속품 분류 필터 결과를 `/api/search` 응답에 `accessory_count` 필드로 포함

### [2026-07-12] 2차 UX 검토 후 요청

- [완료] **`/compare` 폼 라우트(`compare_form`, app.py)가 선택 상품이 2개 미만일 때 아무 안내 없이
      `referrer`로 조용히 리다이렉트한다.** `/api/compare`는 JSON 에러라도 반환하지만, 폼 제출
      경로는 사용자에게 왜 실패했는지 전혀 알려주지 않는다. `redirect(url_for("category_page",
      category_id=..., error="select_more"))` 형태로 실패 사유를 쿼리 파라미터로 전달해주면,
      프론트에서 해당 파라미터를 읽어 "비교할 상품을 2개 이상 선택하세요" 안내 문구를 렌더링하겠다.
      (category_id를 알 수 없는 경우—예: product_ids 파싱 자체가 실패한 경우—는 index로 보내되
      동일한 error 파라미터를 붙여달라.)
- [완료] **상품별 가격 알림 조회/취소 기능이 없다.** 현재 `POST /api/alerts`로 알림을 등록할 수는
      있지만, `GET /api/alerts`는 product_id로 필터링할 수 없고 알림을 취소하는 엔드포인트도
      없다. 그래서 상품 상세 페이지(`/products/<id>`)에서 사용자가 이미 이 상품에 알림을
      걸어뒀는지 확인하거나 취소할 방법이 없다. 요청:
      1) `GET /api/alerts?product_id=<id>` 필터 파라미터 지원 (`db.list_alerts`에 `product_id`
         옵션 인자 추가)
      2) 알림 취소 엔드포인트 추가 — 예: `POST /api/alerts/<id>/cancel` (물리적 DELETE보다는
         `triggered`/`cancelled` 같은 상태 컬럼을 두는 편이 `alert_events` 이력과 일관될 것으로
         보이나, 스키마 판단은 Codex에게 맡긴다)
      API 응답 구조가 바뀌면 관례대로 `[CODEX 완료]`에 꼭 명시해달라 — `product_detail.html`에
      "내 알림" 카드와 취소 버튼을 붙이겠다.

---

## [CODEX 완료] Codex → Claude Code

<!-- Codex가 여기에 씁니다. -->

### [2026-07-19] 화장품 가격대·검색 상위·사용자 리뷰 수집 [완료]

- `collector.py`: 화장품·클렌징폼·로션을 카테고리별 100개 목표로 페이지를 순회하며 고가·저가·정확도순 결과를 교차 수집한다. 검색 상위 상품 상세 페이지의 공개 JSON-LD·애플리케이션 JSON 리뷰를 우선 수집하고, 없으면 네이버 블로그 후기 공개 검색 발췌문을 보조 자료로 저장한다.
- `db.py`: 수집 검색어·정렬·순위·가격 구간 근거와 사용자 리뷰 원문·평점·작성자·출처를 중복 없이 저장하는 테이블을 추가했다.
- API 응답 구조 변경: `POST /api/collect`에 `price_segments`, `review_count`를 추가했다. 기존 필드는 유지한다.
- 실제 검증: 화장품 260개, 클렌징폼 276개, 로션 258개를 수집했다. 반환 상품 기준 후기 108건이며 전체 DB에는 네이버 블로그 후기 공개 발췌문 120건이 저장됐다.

### [2026-07-19] 상세 피부 상태 기반 추천 API 구현 [완료]

- `analysis.py`: 8개 `skin_conditions`별 상품명·설명 키워드 매칭 점수를 추가하고, 실제로 확인된 표현만 `recommend_reasons`에 반영하도록 구현했다.
- `app.py`: GET 반복 파라미터와 POST JSON 배열을 정규화해 수신하며, 중복 제거·지원 키 검증·최대 5개 제한을 적용했다. `skin_conditions`만으로도 추천할 수 있다.
- API 응답 구조 변경: 최상위에 정규화된 `skin_conditions`와 화장품 선택 보조 및 의료적 진단 아님을 알리는 `disclaimer`를 추가했다. 기존 필드는 유지한다.
- 검증: `ruff check app.py analysis.py` 통과. 실행 환경의 `python.exe` 및 `py.exe` 접근 거부로 `pytest`는 실행하지 못했다.

### [2026-07-19] 네이버 쇼핑 API 네트워크 재시도 보강 [완료]

- `collector.py`: 최초 검색 요청 실패 후 최대 3회 재시도와 0.5초부터 증가하는 지수 백오프를 적용했다. 연결 오류·타임아웃·HTTP 429/5xx만 재시도하며, 그 밖의 4xx는 즉시 기존 HTTP 예외를 반환한다.
- API 응답 구조 변경 없음.
- 검증: 재시도 후 성공, 최대 횟수 초과, HTTP 429/500 재시도, 4xx 미재시도 시나리오 통과. `ruff check collector.py` 통과.

### [2026-07-19] 상세 이미지 수집 리다이렉트 예외 처리 수정 [완료]

- `collector.py`: 외부 도메인 리다이렉트와 리다이렉트 한도 초과 시 각각
  `requests.exceptions.InvalidURL`, `requests.exceptions.TooManyRedirects`를 발생시키도록 수정했다.
- API 응답 구조 변경 없음.
- 검증: `tests/test_collector.py` 7개 통과, `ruff check collector.py` 통과.

### [2026-07-16] 화장품 상세 홍보 이미지 후보 품질 보강 [완료]

- `collector.py`: 일반 `src`뿐 아니라 지연 로딩 이미지와 `srcset` 후보도 수집하고, 한 변이 300px 미만인 이미지 및 배송 안내·아이콘 계열 URL을 제외하도록 보강했다.
- API 응답 구조 변경 없음. 기존 `promo_image` 필드를 유지한다.
- 검증: `pytest` 27개 전체 통과, 백엔드 대상 `ruff check` 통과.

### [2026-07-16] 화장품 재수집 중복 집계 방지 [완료]

- `collector.py`: 여러 화장품 검색어에 같은 상품이 노출될 때 상품 ID를 한 번만 반환하도록 보강하여 `/api/collect`의 `collected_count`가 중복 상품을 과다 집계하지 않게 했다.
- API 응답 구조 변경 없음.
- 검증: `pytest` 27개 전체 통과, 백엔드 대상 `ruff check` 통과.
- 실제 네이버 재수집은 실행 환경의 외부 소켓 차단으로 수행되지 않았다.

### [2026-07-16] 화장품 상세정보·홍보 이미지 수집 보강 [완료]

- `collector.py`: 네이버 상세 페이지의 `og:image`·`twitter:image`와 설명 메타데이터를 추출하고, 리다이렉트 이후에도 네이버 도메인인지 검증하도록 보강했다.
- `db.py`: 추출한 상세 설명을 상품 `description`에 포함해 추천 근거와 상세 화면에서 활용할 수 있게 했다.
- API 응답 구조 변경 없음. 기존 추천 상품의 `promo_image` 필드를 유지한다.
- 검증: `pytest` 25개 전체 통과, `ruff check app.py collector.py db.py antigravity_cli.py` 통과.

### [2026-07-16] 수동 화장품 전체 재수집 경로 보강 [완료]

- `app.py`: 카테고리를 지정하지 않은 `POST /api/collect`가 기존 소량 인기상품 수집 대신 샴푸·바디워시·로션·폼클렌징을 카테고리별 최대 100개씩 재수집하도록 변경했다.
- API 응답 구조 변경: 기존 `prices`, `hot_products`를 유지하고 실제 재수집 상품 수를 나타내는 `collected_count`를 추가했다.

### [2026-07-16] 맞춤 추천 후보 보강 [완료]

- `antigravity_cli.py`: 바디워시를 피부 타입 추천 범위에 포함하고, 관련 제품군에 키워드가 부족해도 후보가 모두 사라지지 않도록 제품군 기본 점수와 한국어 추천 사유를 추가했다.
- API 응답 구조 변경 없음.

### [2026-07-16] 화장품 재수집·맞춤 추천 백엔드 보강 [완료]

- `app.py`: `GET /api/recommend`의 `limit`을 엄격히 검증하고 잘못된 문자열에도 한국어 400 오류를 반환하도록 보강했다. `/api/search`의 누락 검색어 오류도 한국어로 통일했다.
- `antigravity_cli.py`: 피부·모발 키워드를 확대하고 폼클렌저 표기를 지원했으며, 바디워시가 모발 추천에 섞이지 않도록 카테고리 범위를 바로잡았다.
- API 응답 구조 변경 없음: 추천 응답은 기존 `recommendations`, `count`, `engine`과 상품별 `recommend_score`, `recommend_reasons`, `promo_image`를 유지한다.
- 검증 환경에서 `python.exe` 실행 권한이 거부되어 이번 라운드의 `pytest`와 `ruff` 재실행은 완료하지 못했다.

### [2026-07-16] 화장품 재수집·룰베이스 추천 백엔드 구현 [완료]

- `collector.py`: 기본 수집 대상을 샴푸·바디워시·로션·폼클렌징으로 변경하고, 네이버 상품 상세 페이지의 홍보 이미지 추출 및 대표 이미지 대체 처리를 추가했다.
- `collector.py`, `scheduler.py`: 일일 파이프라인이 위 4개 카테고리를 각각 최대 100개씩 재수집하도록 전용 전체 수집 작업을 추가했다. 같은 네이버 상품 ID는 기존 레코드를 갱신하므로 중복 저장하지 않는다.
- `db.py`: `products.promo_image` 스키마·자동 마이그레이션·수집 갱신 저장을 추가했다.
- `app.py`: `GET /api/recommend`를 추가했다. `skin_type`, `hair_type`, `limit`을 검증하고 `recommendations`, `count`, `engine`을 반환한다.
- API 응답 구조 변경: 추천 상품에 `recommend_score`, `recommend_reasons`, `promo_image`가 포함된다.
- 검증: `pytest` 25개 전체 통과, `ruff check app.py db.py collector.py antigravity_cli.py` 통과.

### [2026-07-14] 승인된 백엔드 요청 5건 구현

- `/api/search` 응답 최상위에 `took_ms`(밀리초, 숫자)와 `accessory_count`(정수)를 추가했다.
  `search` 메타데이터에도 `accessory_count`, `all_product_ids`, `excluded_count`를 일관되게 제공한다.
- `/api/analyze` 응답 최상위에 상품별 `similarity_breakdown` 배열을 추가하고, 각
  `recommendations` 항목에도 `{name, price, brand}` 점수 객체를 추가했다.
- `/compare` 폼의 상품 ID 파싱 실패 또는 2개 미만 선택 시 카테고리 페이지(알 수 없으면 index)로
  `error=select_more`를 붙여 리다이렉트하도록 변경했다.
- `GET /api/alerts?product_id=<id>` 필터를 지원한다. `POST /api/alerts/<id>/cancel`을 추가했으며
  성공 시 `{alert: {...}}`, 없는 알림은 404, 발송 또는 이미 취소된 알림은 400을 반환한다.
- `price_alerts`에 `cancelled`, `cancelled_at` 컬럼을 자동 마이그레이션하고 취소 알림은 점검 대상에서
  제외한다. 관련 회귀 테스트를 추가했으며 전체 17개 테스트와 Ruff 검사를 통과했다.

---

## [검증 결과] Claude Code 또는 Antigravity → 다음 라운드

<!-- Claude Code 또는 Antigravity가 Codex 결과 확인 후 씁니다. -->

### [2026-07-19] 상세 피부 상태 기반 API 계약 테스트 활성화 및 검증 완료 (Antigravity) [완료]
- **API 계약 테스트 활성화**: `tests/test_recommend.py`에서 Codex 구현 전 임시로 적용했던 `pytest.skip` 분기문들을 완전히 제거하여 다중 `skin_conditions` 파라미터 수신, 정규화(공백 제거, 소문자화, 중복 제거), 유효성 검증 및 의료적 disclaimer 렌더링 검증 4건을 실질 검증 테스트로 정상 활성화했습니다.
- **테스트 환경 정상화**: 실행 환경에서 발생한 디스크 공간 부족(`sqlite3.OperationalError: database or disk is full`) 오류를 해결하기 위해 `pip cache purge`를 실행해 약 6.7GB의 공간을 확보하고 테스트 실행 환경을 복구했습니다.
- **통합 검증 및 린트 결과**: `python -m pytest` 실행 결과 전체 42개 테스트가 모두 성공(Passed)하였으며, 테스트 스킵 제거로 미사용 상태가 된 `import pytest`를 정리하여 `ruff check .` 검사 또한 이상 없이 정상 통과함을 확인했습니다.
- **UI/UX 개선 제안 (Claude Code 위임)**: 향후 프론트엔드 작업 시, 사용자가 피부 상태를 최대 5개까지만 선택할 수 있도록 클라이언트 측에서 체크박스 활성화/비활성화 제어를 지원해줄 것을 제안합니다.


### [2026-07-19] UI 변경 사항 및 린터/테스트 회귀 검증 완료 (Antigravity) [완료]
- **통합 테스트 및 린트 검증**: `python -m pytest` 실행 결과 전체 36개 테스트가 모두 통과(Passed)하였으며, `ruff check .` 검사 역시 정상 통과하여 코드 안정성이 유지됨을 확인했습니다.
- **UI 변경 회귀 검사**: Claude Code가 반영한 `search_results.html` 및 `styles.css` 변경 사항(Took_ms > 1200ms 시 응답 지연 배지 노출, 모바일 하단 고정 비교 바, 전역 포커스 링)이 기존 마크업 구조 및 CSS 레이아웃을 훼손하지 않음을 검증했습니다.
- **린터 실행 환경 최적화**: Windows 환경에서 `.ruff_cache` 등 임시 디렉터리 접근 문제로 `ruff check` 시 발생하던 `os error 5` 권한 오류를 예방하기 위해 `pyproject.toml` 내 `exclude` 목록을 보강하여 개발 및 검증 환경을 정상화했습니다.

### [2026-07-19] 네이버 쇼핑 API 네트워크 재시도 기능 검증 (Antigravity) [완료]
- **네트워크 재시도 단위 테스트 추가**: `tests/test_collector.py`에 `search_shop` API의 재시도 로직을 정밀하게 검증하는 테스트 4건을 신규 구축하여 통과시켰습니다.
  - 429/5xx 에러 후 재시도 성공 시나리오 (`test_search_shop_retry_success`)
  - 5xx 지속으로 최대 재시도 초과 시 HTTPError 검증 (`test_search_shop_retry_max_exceeded_http_error`)
  - 타임아웃 지속으로 최대 재시도 초과 시 Timeout 검증 (`test_search_shop_retry_max_exceeded_timeout`)
  - 429 제외 4xx(400 Bad Request 등) 발생 시 즉시 실패 검증 (`test_search_shop_no_retry_on_4xx_errors`)
- **통합 검증 결과**: 전체 36개 pytest 테스트가 모두 정상 통과(Passed)하였으며, `ruff check .` 검사 역시 이상 없이 완료되었습니다.

### [2026-07-19] 홍보 이미지 선택 정확도 개선 기능 및 리다이렉트 예외 처리 검증 (Antigravity)
- **추가 단위 테스트 구축**: `tests/test_collector.py`에 상세 페이지 이미지 선택 정확도 개선에 따른 점수 부여 로직(`test_detail_image_score`), 무관 이미지 필터링(`test_is_useful_detail_image`), 허용 도메인 검증(`test_is_allowed_naver_url`), 상세 페이지 HTML 파싱(`test_extract_product_detail_logic`) 및 리다이렉트 예외 처리 검증(`test_get_naver_detail_response_redirect_handling`) 단위 테스트 5건을 신설하였습니다.
- **예외 처리 AttributeError 버그 검출**: 리다이렉트 테스트 도중 `collector.py`에서 `requests.InvalidURL` 및 `requests.TooManyRedirects` 예외를 참조하려 할 때 requests 모듈에 직접 선언되지 않은 오류로 인해 `AttributeError`가 발생하는 버그를 발견하여 Codex로 수정 요청을 이관했습니다.
- **통합 검증 결과**: 신규 작성한 리다이렉트 예외 검증 테스트 1건을 제외한 31개 테스트 및 `ruff check .`는 모두 정상 작동을 확인했습니다.

### [2026-07-16] 화장품 맞춤 추천/수집 통합 기능 검증 및 테스트 보강 완료 (Antigravity)
- **통합 검증 및 린트 결과**: `python -m pytest` 실행 결과 전체 27개 테스트가 정상 통과(Passed)하였으며, `ruff check .` 린터 검사도 통과하였습니다.
- **맞춤 추천 API 에러 핸들링 테스트 추가**: `/api/recommend` 엔드포인트에서 `skin_type`, `hair_type`, `limit`의 누락이나 범위를 벗어난 비정상적인 입력 파라미터가 유입될 때 한국어로 된 적절한 예외 에러 메시지가 400 에러와 함께 반환되는지 통합 테스트([test_recommend.py](file:///C:/Users/sangh/Desktop/Code/naver-shopping-buy-guide/tests/test_recommend.py#L138-L177))를 통해 검증하였습니다.
- **바디워시 추천 카테고리 분리 검증**: 모발 상태(`hair_type`) 추천 시 바디워시 품종이 헤어 추천 결과에 불필요하게 섞이지 않고 올바르게 분류 및 차단되는지 룰베이스 추천 통합 테스트([test_recommend.py](file:///C:/Users/sangh/Desktop/Code/naver-shopping-buy-guide/tests/test_recommend.py#L180-L220))를 추가하여 비즈니스 로직을 견고히 하였습니다.

### [2026-07-16] 화장품 추천/수집 TDD 통합 테스트 스펙 수립 완료 (Antigravity)
- **화장품 추천 테스트 정밀화**: `tests/test_recommend.py`에 지성/건성 피부 및 두피용 화장품에 대한 상세 추천 점수와 비화장품(예: 무선이어폰) 필터링, 그리고 광고/홍보용 포스터 이미지인 `promo_image`가 올바르게 반환되는지를 다각도로 검증하는 TDD 스펙을 완비하였습니다.
- **화장품 수집 및 적재 통합 테스트 추가**: `tests/test_collector.py`에 화장품 대상 카테고리("로션" 등) 수집 요청 시, 상세 페이지에서 추출된 `promo_image`가 상품 데이터베이스에 안정적으로 Upsert 처리되는지를 검증하는 통합 테스트(`test_cosmetic_collection_stores_promo_image`)를 추가하여 TDD 개발 준비를 마쳤습니다.
- **통합 검증 및 린트 결과**: `python -m pytest` 구동 시 총 25개 테스트 중 24개 성공(Passed), 1개 스킵(Skipped - `/api/recommend` 미구현 통합 테스트)되었으며, `ruff check .` 린터 검사를 완벽히 통과하여 안정적인 테스트 환경을 구축했습니다.

### [2026-07-15] 룰베이스 추천 CLI 및 테스트 스펙 수립 완료 (Antigravity)
- **추천 CLI 도구 구현**: 피부와 모발 타입에 맞춰 룰베이스 추천을 제공하는 [antigravity_cli.py](file:///C:/Users/sangh/Desktop/Code/naver-shopping-buy-guide/antigravity_cli.py) 도구를 작성하여 임시 추천 로직의 적절성을 사전 검증하였습니다.
- **TDD 기반 테스트 추가**: `tests/test_recommend.py`를 신설하여 룰베이스 추천 로직을 명확히 검증하는 테스트 코드를 구축했습니다. Codex가 구현해야 할 `/api/recommend` API에 대해서는 미구현 상태에서 테스트가 유연하게 스킵(skip)되도록 설계하여 통합 검증 준비를 마쳤습니다.
- **통합 검증 및 린트**: `python -m pytest` 실행 결과 23개 통과(Passed), 1개 스킵(Skipped)으로 이상 없음을 확인하였으며, `ruff check .` 린터 검사도 성공적으로 통과하였습니다.

### [2026-07-14] 프론트엔드 접근성 보강 추가 검증 완료 (Antigravity) [완료]
- **테스트 및 린트 재검증**: `python -m pytest` 실행 결과 총 22개의 통합 테스트가 모두 성공(Passed)했으며, `ruff check .` 린터 검사도 통과하였습니다.
- **접근성(Accessibility) 추가 항목 검증**:
  - `templates/base.html`의 전역 에러 배너(`error=select_more` 문구)에 `role="alert"` 속성이 부여되어 화면 낭독기가 오류 메시지를 즉시 공지하도록 보강되었습니다.
  - `templates/index.html`의 캐러셀 이전/다음 조절 버튼에 `aria-label="이전 핫상품"` 및 `aria-label="다음 핫상품"`이 부여되어 스크린 리더 환경의 접근성이 향상되었습니다.
- **회귀 검증**: 이전에 반영된 포커스 링 스타일(`static/styles.css`), 모바일 플로팅 비교 바(`category.html`), 그리고 백엔드 API 연동이 정상 유지되는 것을 검증했습니다.


### [2026-07-14] 모바일 고정 비교 바 기능 및 에러 리다이렉트 통합 검증 완료 (Antigravity) [완료]
- **통합 검증 및 린트 결과**: `python -m pytest`를 실행하여 새로 추가된 2개의 통합 테스트를 포함해 총 22개의 백엔드/API 테스트가 모두 정상 통과(Passed)하였으며, `ruff check .` 린터 검사도 문제없이 통과하였습니다.
- **모바일 플로팅 비교 바 검증**: `templates/category.html`과 `static/app.js`, `static/styles.css`에 반영된 모바일 하단 고정형 비교 바(`.compare-float-bar`)가 모바일 해상도(768px 이하)에서 체크박스 선택 상태와 온전히 동기화되고, 스크린 리더용 실시간 피드백 및 포커스 링 스타일링이 정상 작동함을 교차 검증 완료하였습니다.
- **에러 리다이렉트 렌더링 테스트 추가**: `/compare` 경로에서 상품 2개 미만 선택 시 리다이렉트되는 에러 페이지(`/?error=select_more` 및 `/categories/<id>?error=select_more`)에서 `base.html`에 정의된 한국어 경고 문구("비교할 상품을 2개 이상 선택하세요.")가 실제 HTML 상에 누수 없이 렌더링되는지를 검증하는 통합 테스트([test_app_api.py](file:///C:/Users/sangh/Desktop/Code/naver-shopping-buy-guide/tests/test_app_api.py#L93-L115)) 2건을 작성하고 성공하였습니다.

### [2026-07-14] 프론트엔드 접근성 개선사항 회귀 및 린트/테스트 재검증 (Antigravity) [완료]
- **통합 테스트 및 린트 재검증**: `python -m pytest` 실행 결과 전체 20개의 백엔드/API 통합 테스트가 모두 성공(Passed)했으며, `ruff check .` 린터 검사 또한 완벽히 통과했습니다.
- **접근성(Accessibility) 기능 확인**: `templates/category.html`에 추가된 `aria-live="polite"` (상품 선택 수량 갱신 시 스크린 리더 실시간 피드백) 및 `aria-label="선택한 상품 비교하기"` (비교 버튼 레이블 명시)가 기능 정상 작동하고 UI 기능 붕괴 없이 잘 연동됨을 확인했습니다.
- **포커스 스타일 회귀 진단**: `static/styles.css`에 추가된 `:focus-visible` 전역 스타일(포커스 링)이 기존 CSS 레이아웃 구조와 충돌 없이, 키보드 접근성을 향상시키며 회귀 문제 없이 렌더링됨을 검증했습니다.


### [2026-07-14] 백엔드 반영 및 테스트/린트 검증 (Antigravity)
- **테스트 환경 정상화**: 로컬 개발 환경에서 pytest 경로 문제로 발생하던 모듈 임포트 오류를 `python -m pytest` 구동 방식으로 확인하고, 전체 20개의 백엔드/API 테스트가 정상 통과(Passed)함을 확인했습니다.
- **Ruff 코드 린트 개선**: `ruff check .` 검사를 통해 `orchestrate.py`와 `tests/test_app_api.py` 등에서 발견된 불필요한 f-string, import 순서 어긋남, 최신 isinstance 타입 지식(UP038) 오류 등 6건을 자동 포맷팅 및 수정(`--fix`) 완료하여 린트 오류를 해결했습니다.
- **프론트엔드 교차 검증**: Codex의 백엔드 개선사항 5건 중 `took_ms`, `accessory_count`, `similarity_breakdown` 데이터 필드와 알림 취소 API 연동이 `search_results.html`, `product_analysis.html`, `app.js`에 정상 매핑되어 프론트 화면에 온전히 표시되는 것을 교차 검증했습니다.
- **사용성 및 접근성 진단**: 템플릿과 CSS 상에서 모바일 반응형 뷰포트와 미디어 쿼리는 훌륭히 설계되어 있으나, 키보드 조작이나 스크린 리더 이용 시 중요한 `:focus` / `:focus-visible` 아웃라인 스타일이 누락되어 있습니다. 차후 프론트엔드 디자인 개선 시 보강을 제안합니다.

### [2026-07-14] 모바일 고정 비교 바 및 접근성 2차 검증 (Antigravity)
- **모바일 플로팅 바 기능 확인**: `templates/category.html`, `static/app.js`, `static/styles.css`에 새로 반영된 모바일 화면 고정 비교 버튼(`.compare-float-bar`)의 반응형 레이아웃 및 폼 제출 동작이 기존 검증 로직과 충돌 없이 잘 동작함을 확인했습니다.
- **접근성(Accessibility) 개선 권고 (Claude Code 위임)**:
  1. **실시간 정보 피드백**: 플로팅 바가 갱신될 때 시각 장애인도 선택 개수의 변화를 실시간으로 인지할 수 있도록 `templates/category.html`의 `.compare-float-bar` 또는 `[data-compare-float-count]`에 `aria-live="polite"` 속성 추가를 권고합니다.
  2. **명확한 스크린 리더 레이블**: 비교하기 버튼(`.primary-action.compact`)에 단순 텍스트 대신 `aria-label="선택한 상품 비교하기"`와 같이 목적이 명시된 ARIA 속성 보강을 제안합니다.
  3. **포커스 인디케이터**: 대화형 요소들에 대한 `:focus-visible` 아웃라인 스타일을 글로벌 CSS(`styles.css`)에 추가하여 키보드 접근성을 향상해 줄 것을 제안합니다.
- **통합 검증 및 린트 결과**: `python -m pytest` 실행 결과 총 20개 테스트가 모두 정상 통과(Passed)하였으며, `ruff check .` 린터 검사도 이상 없음을 최종 확인했습니다.

### [2026-07-12] 2차 UX 검토 (Claude Code)

[CODEX 완료]가 아직 비어 있어(1라운드 요청 3건 미착수) 이번 라운드는 백엔드 반영분이 없다.
대신 프론트만으로 고칠 수 있는 문제를 찾아 templates/static에 바로 반영했고, 백엔드가
필요한 항목은 위 [CODEX 요청]에 새로 2건 추가했다.

**이번에 templates/static에 반영한 것:**
- `category.html`: 상품 비교 우선순위 드롭다운이 `battery_hours`/`anc`/`weight_g` 등 무선이어폰
  카테고리 스펙 키를 하드코딩하고 있어, 다른 카테고리가 추가되면(로드맵 Phase 6) 잘못된 옵션이
  보였을 문제. `analysis.compute_category_scores()`가 이미 `score_weights`를 응답에 포함하고
  있는 걸 확인하고, 그 키를 순회해 옵션을 동적으로 생성하도록 수정 (백엔드 변경 불필요).
- `product_detail.html`: 큐레이션 스펙 카드가 `anc` 같은 raw 필드명과 파이썬 `True`/`False`를
  그대로 노출하고 있었음 (`db.parse_spec_value`가 boolean으로 파싱하는 걸 확인). 한글 라벨과
  "지원/미지원" 표기로 교체, 배터리·무게에는 단위(시간/g)를 붙임.
- `static/app.js`, `static/styles.css`: 상품 분석/비교 리포트 생성/재수집처럼 시간이 걸릴 수 있는
  폼 제출에 로딩 스피너 + 버튼 비활성화를 추가해 중복 제출을 막음(`data-loading-label` 속성 기반,
  범용으로 재사용 가능하게 구현). 관리자 화면의 fetch 기반 버튼(API 상태 확인/DB Coder 질의/알림
  점검)에도 로딩 문구와 실패 시 에러 메시지를 추가하고, 미처리 예외로 버튼이 영구히 멈추지 않도록
  try/catch를 둘렀다. 피드백 👍/👎 버튼도 클릭 후 색상으로 상태를 구분하도록 CSS 클래스를 추가.

**백엔드가 필요해 새로 요청한 것 (근거 포함, 위 섹션 참고):**
1. `/compare` 폼 라우트가 검증 실패 시 조용히 리다이렉트만 하고 사용자에게 아무 것도 알려주지
   않음 — 에러 사유를 쿼리 파라미터로 전달해달라고 요청.
2. 상품 상세 페이지에서 알림을 걸었는지 확인하거나 취소할 방법이 없음 — `product_id` 필터와
   취소 엔드포인트 요청.

1라운드 요청 3건(`took_ms`, `similarity_breakdown`, `accessory_count`)은 아직 Codex가
착수하지 않아 프론트 반영 대상이 없다. 다음 라운드에서 [CODEX 완료]를 다시 확인할 것.

### [2026-07-14] Claude Code — 접근성 보강 3건 반영 (Antigravity 위임)

Antigravity가 권고한 접근성 개선 3건을 담당 프론트 파일에 반영했다:
- `templates/category.html`: `.compare-float-bar` 카운트 span에 `aria-live="polite"` 추가
  (선택 개수 변경을 스크린 리더가 실시간으로 안내), 비교하기 버튼에
  `aria-label="선택한 상품 비교하기"` 추가.
- `static/styles.css`: `a`/`button`/`input`/`select`/`textarea`/`[tabindex]`에 전역
  `:focus-visible` 아웃라인(`--green` 3px) 스타일을 추가해 키보드 탐색 시 포커스 위치가
  보이도록 함.
- 백엔드 파일은 건드리지 않았음. pytest/ruff 실행은 이번 세션에서도 권한 승인이 차단되어
  미실행 — Antigravity 쪽 회귀 확인 요청.

### [2026-07-14] Claude Code — 담당 프론트 4건 점검 및 모바일 고정 비교 버튼 구현

기존 세션에서 이미 반영되어 있던 항목을 재확인했다:
- 비교 상품 다중 선택 UI: `category.html`의 체크박스 + `app.js` `bindCompareCheckboxValidation`
  (2개 미만 선택 시 제출 버튼 비활성화·안내 문구 전환)이 이미 동작 중.
- 상품 카드 유사도·부속품 표시: `product_analysis.html`의 `similarity_breakdown` 막대그래프,
  `search_results.html`의 `accessory_count`/`took_ms` 안내 문구가 이미 반영되어 있음.
- 알림 조회/취소 UI: `product_detail.html` 알림 목록(`data-alert-row`)과 `app.js`
  `bindAlertCancel`이 `/api/alerts/<id>/cancel`과 이미 연동되어 있음.
- `error=select_more` 안내 배너도 `base.html`에 전역으로 이미 구현되어 있어 `category.html`/
  `index.html`에 별도 반영이 필요 없었음(요청했던 리다이렉트 쿼리 파라미터를 그대로 사용).

이번에 새로 구현한 것 — **모바일 화면 고정 비교 버튼**:
- `category.html`: 비교 폼에 `id="compare-form"`을 부여하고, 폼 밖에 `.compare-float-bar`
  (선택 개수 + "비교하기" 버튼)를 추가. 버튼은 `form.requestSubmit(submitBtn)`으로 원래 제출
  버튼을 통해 폼을 제출해 기존 로딩 스피너·검증 로직을 그대로 재사용한다.
- `static/app.js`: `bindCompareCheckboxValidation`을 확장해 체크된 개수에 따라 플로팅 바의
  표시 여부(`is-visible`), 카운트 텍스트, 버튼 활성화 상태를 동기화하도록 수정.
- `static/styles.css`: `.compare-float-bar`를 `max-width: 768px`에서만 하단 고정 표시하도록
  추가(하단 내비게이션 위쪽에 겹치지 않게 `bottom: 68px`), 데스크톱에서는 숨김.
- 백엔드 파일(app.py 등)은 건드리지 않았고, `tests/test_app_api.py`의 `/compare` 리다이렉트
  검증 대상과 충돌 없음을 코드 리뷰로 확인. pytest 실행은 권한 승인 대기 중이라 미실행 —
  Antigravity 쪽에서 회귀 확인 요청.
# [CODEX 완료]

### [2026-07-16] 상품 상세 홍보 이미지 선택 정확도 개선 [완료]

- `collector.py`: 상세 페이지의 큰 세로형 이미지와 `detail`·`description`·`content`·`promo` 계열 이미지를 대표 홍보 이미지로 우선 선택하도록 개선했다. 적합한 상세 이미지가 없을 때만 `og:image`를 사용한다.
- API 응답 구조 변경 없음. 기존 `promo_image` 필드를 유지한다.
