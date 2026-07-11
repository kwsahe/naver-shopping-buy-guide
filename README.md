# Naver Shopping Buy Guide

네이버쇼핑 공식 API로 경쟁 상품을 수집하고, 수동 큐레이션 스펙과 가격 이력을 기반으로 비교 리포트, 베스트픽, 매수 타이밍을 제공하는 Flask 기반 구매 가이드 데모입니다.

## 빠른 시작

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

브라우저에서 `http://localhost:8400`을 열면 됩니다. 네이버 API 키가 없어도 `data/specs/wireless_earbuds.json` 데모 데이터로 동작합니다.

## 주요 사용자 흐름

1. 홈에서 검색어를 입력합니다. 예: `무선이어폰`
2. 네이버쇼핑 API 검색 결과에서 상품을 하나 선택합니다.
3. `상품 분석` 버튼을 누릅니다.
4. 선택 상품 기준으로 비교 후보 상품, 추천 점수, 가격/브랜드/상품명 유사도 점수를 확인합니다.

현재 LLM 실호출은 보류되어 있으며, 분석은 설명 가능한 코드 기반 점수화 엔진으로 동작합니다. 이후 `LLM_ENABLED=1`로 전환하면 LLM 호출 구간을 붙일 수 있습니다.

검색 결과는 케이스, 필름, 충전기, 이어팁 같은 부속품을 자동 분류해 기본 결과에서 제외합니다. 필요하면 검색 결과 화면의 `부속품 포함 보기`로 전체 결과를 확인할 수 있습니다.

홈 대시보드의 `오늘의 핫상품`은 네이버 공식 검색 API에서 수집한 검색 순위, 본품 분류 점수, 이미지/가격 메타데이터를 합산한 핫스코어 기반으로 자동 회전 표시됩니다. 네이버 검색 API는 제품별 실제 조회수/구매수를 제공하지 않으므로, 현재 카드는 공식 API 데이터 기반의 대체 지표입니다.

## 환경 변수

- `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`: 네이버 검색 API 키
- `LLM_ENABLED`: 기본값 `0`. LLM 연결 보류 중에는 꺼둡니다.
- `LLM_PROVIDER`: `disabled`, `local_ollama`, `remote_openai`, `mock`
- `LLM_MODEL`: 기본값 `exaone3.5:2.4b`
- `LLM_API_BASE`: Ollama 기본값 `http://localhost:11434`
- `DB_PATH`: SQLite 경로, 기본값 `data/app.db`

## 주요 명령

```bash
python db.py                  # DB 초기화와 데모 데이터 시드
python scheduler.py           # APScheduler 상시 실행
python -m pytest tests/ -v    # 테스트 실행
ruff check .                  # 린트
docker compose up             # Flask + scheduler 실행
```

## API

- `GET /api/categories`
- `GET /api/search?q=무선이어폰`
- `POST /api/analyze`
- `GET /api/hot-products?refresh=1`
- `GET /api/products?category_id=1`
- `GET /api/products/1/price-history?days=90`
- `POST /api/compare`
- `GET /api/products/1/buy-timing`
- `GET /api/categories/1/best-picks`
- `POST /api/alerts`
- `GET /api/alerts`
- `POST /api/alerts/check`
- `POST /api/feedback`
- `GET /api/admin/api-status`
- `GET /api/admin/pipeline-runs`
- `GET /api/admin/feedback`
- `POST /api/admin/query`
- `GET /health`
