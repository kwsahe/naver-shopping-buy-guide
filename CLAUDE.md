# CLAUDE.md — 네이버쇼핑 경쟁 상품 비교 & 구매 가이드 자동화

> 이 문서는 Claude Code가 이 프로젝트를 실제로 구현할 때 읽는 설계 문서다.
> [[06-ideas/자동화 프로그램|아이디어 원본]]에서 스코프를 확정한 뒤 작성됨.
> 작업 시작 전 이 문서 전체를 먼저 읽고, Phase 순서대로 진행할 것.
>
> **레포명(예정)**: `naver-shopping-buy-guide`
> **GitHub Description**: 네이버쇼핑 API로 경쟁 상품을 비교·추천하고, 가격 추이 기반 매수 타이밍까지 안내하는 LLM 구매 가이드 자동화

---

## 0. 프로젝트 개요

### 목적
특정 상품 카테고리(예: 무선 이어폰, 캠핑 텐트)의 경쟁 상품들을 네이버쇼핑 공식 API로 수집해, 기능별 우위를 비교·추천하고 가격 변동을 주기적으로 추적해 "지금 사도 되는지"까지 조언하는 자동화 프로그램.

### 문제 정의
- 소비자는 같은 카테고리 안에서도 어떤 상품이 스펙 대비 나은지 판단하기 어렵다 (스펙표가 제조사마다 표기 방식이 다름)
- 가격은 계속 변하는데, 지금이 "쌀 때"인지 "비쌀 때"인지 알 방법이 마땅치 않다 (다나와/에누리도 현재가 비교는 해주지만 "사도 되는 시점"까지는 조언하지 않음)
- 기존 가격비교 서비스는 정적 비교표만 제공, LLM 기반의 자연어 추천 근거는 제공하지 않는다

### 핵심 가치 제안
1. **기능별 비교 + 추천 이유**: "A 제품이 배터리는 낫지만 B가 가성비 우위" 같은 자연어 근거 제시
2. **가격 추이 기반 매수 타이밍 판단**: 단순 현재가 비교가 아니라 "최근 N일간 이 정도면 저점 구간"까지 판단
3. **카테고리별 자동 베스트픽 추천**: 사용자가 상품을 직접 고르지 않아도, 카테고리 안에서 "가성비 최고"와 "성능 최고" 상품을 자동으로 뽑아 이유와 함께 제시
4. **완전히 합법적인 데이터 파이프라인**: 크롤링/우회 없이 공식 API만 사용

### 대상 사용자
- 실사용: 특정 카테고리 구매를 고민 중인 일반 소비자 (본인이 직접 사용 가능한 데모)
- 포트폴리오 심사자: 데이터 엔지니어링(수집/적재/스케줄링) + AI(LLM 비교·추천) + 풀스택(대시보드)을 한 프로젝트에서 확인

### 이 프로젝트로 보여주려는 역량
| 역량        | 어디서 드러나는가                         |
| --------- | --------------------------------- |
| 데이터 엔지니어링 | API 자동 수집, 시계열 DB 설계, 스케줄러 파이프라인  |
| LLM 활용    | 구조화된 비교 리포트 생성, 가격 추이 기반 판단       |
| 풀스택       | Flask 백엔드 + 대시보드 프론트엔드            |
| 프로덕트 감각   | 다나와/에누리 대비 차별화 지점(매수 타이밍)을 스스로 정의 |
| 운영/배포 능력  | 파이프라인 관찰성(16절), 사용자 피드백 루프(17절), CI/CD(18절), Docker Compose 배포(19절) — 다른 3개 프로젝트에는 없는 차별화 포인트 |

---

## 1. 사용자 시나리오

### 시나리오 1 — 카테고리 비교
1. 사용자가 "무선 이어폰"을 검색
2. 시스템이 등록된 경쟁 상품 목록을 카드/표로 보여줌 (가격, 판매처, 브랜드)
3. "AI 비교 리포트 생성" 클릭 → LLM이 기능별 우위와 추천 이유를 문단으로 생성
4. 사용자가 예산/우선순위(배터리 vs 음질 vs 가격)를 입력하면 그 조건에 맞춰 리포트가 재생성됨

### 시나리오 2 — 가격 추이 확인
1. 특정 상품 상세 페이지 진입
2. 최근 30/90일 가격 추이 그래프 표시
3. LLM이 "현재가는 최근 90일 중 하위 20% 구간이라 매수 적기로 판단됨" 같은 코멘트 생성
4. 근거로 사용된 실제 통계(최고가/최저가/평균가/현재가 백분위)를 함께 표시 (LLM이 숫자를 지어내지 않도록 코드에서 계산한 값을 프롬프트에 주입)

### 시나리오 3 — 가격 알림 등록 (확장 기능, Phase 5)
1. 사용자가 특정 상품에 "목표가" 등록
2. 스케줄러가 매일 가격을 체크하다가 목표가 이하로 떨어지면 알림 생성 (이메일/파일 로그, 추후 슬랙 등 확장)

### 시나리오 4 — 카테고리 베스트픽 자동 추천
1. 사용자가 카테고리 화면에 진입 (상품을 직접 고르지 않아도 됨)
2. "이 카테고리 추천" 카드에 **가성비 최고 상품**과 **성능 최고 상품**이 각각 배지로 표시됨
3. 각 배지를 누르면 "왜 이 상품이 뽑혔는지"에 대한 LLM의 자연어 설명이 펼쳐짐 (근거가 된 스펙/가격 수치 함께 표시)
4. 이 추천은 매일 가격 수집 직후 자동 갱신되므로, 가격이 바뀌면 가성비 최고 상품도 바뀔 수 있음

---

## 2. 시스템 아키텍처

```text
[네이버 검색 API - 쇼핑]        [네이버 데이터랩 API]
        │                              │
        ▼                              ▼
 ┌─────────────────────────────────────────┐
 │  collector.py (수집 계층)                 │
 │  - 상품 검색/수집                          │
 │  - 카테고리 트렌드 수집                     │
 │  - 스펙 큐레이션 데이터 병합 (수동 JSON)      │
 └───────────────┬───────────────────────────┘
                 ▼
 ┌─────────────────────────────────────────┐
 │  scheduler.py (APScheduler)               │
 │  - 매일 정해진 시각에 가격 재수집             │
 │  - price_history 테이블에 적재              │
 └───────────────┬───────────────────────────┘
                 ▼
 ┌─────────────────────────────────────────┐
 │  DB (SQLite → 필요시 PostgreSQL)           │
 │  categories / products / specs /          │
 │  price_history / comparison_reports /     │
 │  category_recommendations                 │
 └───────────────┬───────────────────────────┘
                 ▼
 ┌─────────────────────────────────────────┐
 │  analysis.py                              │
 │  - 가격 통계 계산 (최고/최저/평균/백분위)      │
 │  - 스펙 정규화 및 비교표 생성                 │
 │  - 카테고리별 성능 점수/가성비 점수 계산       │
 │    (O2O demand-score 가중합산 방식 재사용)   │
 └───────────────┬───────────────────────────┘
                 ▼
 ┌─────────────────────────────────────────┐
 │  llm_agent.py — LangGraph StateGraph       │
 │  InputValidation → ScoreCompute →          │
 │  PromptRouter → LLMCall ⇄ JSONValidation   │
 │  (검증 실패 시 LLMCall로 재시도) → Persist    │
 │  * 세 작업(비교/매수타이밍/베스트픽) 공유        │
 └───────────────┬───────────────────────────┘
                 ▼
 ┌─────────────────────────────────────────┐
 │  Flask 백엔드 (app.py) + 대시보드            │
 │  - REST API                               │
 │  - 비교 테이블 / 가격 추이 그래프              │
 └─────────────────────────────────────────┘
```

---

## 3. 기술 스택 총정리

| 분야 | 선택 | 비고 |
|---|---|---|
| 데이터 수집 | 네이버 검색 API(쇼핑), 네이버 데이터랩 API | 공식 API, 크롤링 없음 |
| 백엔드 | Flask (O2O 프로젝트와 동일 스택) | 기존 코드 재사용 용이 |
| DB | SQLite(MVP) → PostgreSQL(확장 시) | 시계열 데이터 늘어나면 이전 |
| 스케줄러 | APScheduler (Python 프로세스 내 실행) 또는 Windows 작업 스케줄러 | cron 대체 (Windows 환경) |
| LLM | EXAONE-3.5-7.8B-Instruct (Colab Pro, 운영) / EXAONE-3.5-2.4B-Instruct (Ollama, 로컬 개발) | 4번 섹션에서 상세 |
| LLM 오케스트레이션 | LangGraph (`langgraph` 패키지) | 비교/매수타이밍/베스트픽 3개 작업이 공유하는 "생성→검증→재시도" 흐름을 StateGraph로 formalize. 4.8절 참고 |
| DB Coder 에이전트 | LangGraph + `sqlparse` (SQL 검증) | 자연어→SQL 읽기 전용 분석 에이전트, 관리자 전용. 4.9절 참고 |
| 프론트엔드 | Flask 템플릿(Jinja2) + Chart.js (가격 추이 그래프) | O2O 프로젝트 패턴 재사용 |
| 시각화 | Chart.js 또는 Plotly | 가격 추이, 비교 레이더 차트 |
| 관찰성 | `pipeline_runs` 테이블 + 관리자 대시보드 | 다른 3개 프로젝트에 없는 차별화 포인트. 16절 |
| CI/CD | GitHub Actions (`ruff` + `pytest`) | push/PR마다 자동 실행. 18절 |
| 배포 | Docker Compose (app + scheduler 2개 서비스) | 레포 클론 후 한 줄 실행 가능. 19절 |

---

## 4. LLM 모델 추천

### 4.1 요구사항 정리
1. **한국어 카피 품질**: 소비자 대상 구매 가이드 문구를 자연스럽게 생성해야 함
2. **구조화된 출력 준수**: 비교표/추천 이유를 JSON 스키마에 맞춰 안정적으로 반환해야 함 (프론트엔드가 파싱해야 하므로)
3. **적당한 추론력**: 여러 상품의 스펙을 비교해 우선순위를 매기는 정도의 추론이면 충분 — 복잡한 수학 계산은 코드에서 미리 끝내고 LLM에는 요약된 숫자만 준다 (LLM이 직접 산술하게 하지 않는다)
4. **인프라 제약**: 개인 포트폴리오 프로젝트, RTX 3050(VRAM 4GB) 로컬 또는 Colab Pro 사용 가능

### 4.2 후보 비교

| 모델 | 실행 위치 | 장점 | 단점 |
|---|---|---|---|
| **EXAONE-3.5-7.8B-Instruct** | Colab Pro | LG AI연구원의 한국어 특화 모델. k-safety-law-rag에서 이미 비교 테스트한 이력이 있고 **Colab 서빙 노트북(`exaone_colab_pro_server.ipynb`)도 이미 만들어져 있어 그대로 재사용 가능**. 완전 무료(오픈 가중치) | Colab 세션 유지 필요, 과거 VL/법령판단 태스크 비교에서 Qwen에 근소하게 밀렸던 이력(이번 비교·카피 생성 태스크에서는 재검증 가치 있음) |
| **EXAONE-3.5-2.4B-Instruct** | Ollama 로컬 | 로컬 GPU에서 가볍게 실행 가능(설치 시 최신 태그 확인: `ollama pull exaone3.5:2.4b`), 완전 무료 | 7.8B 대비 비교 근거의 디테일·일관성이 떨어질 수 있음 |
| ~~Qwen2.5-14B-Instruct / Qwen2.5:3b~~ | ~~Colab Pro / Ollama~~ | k-safety-law-rag·O2O에서 이미 검증됨 | 이번 프로젝트는 EXAONE으로 진행하기로 확정 (다른 모델도 써보고 싶다는 요청 반영) |
| ~~Solar Pro / Solar Mini (Upstage)~~ | ~~API~~ | 한국 기업의 한국어 특화 모델 | 무료 체험 종료(2026-03-02) 이후 API 유료 전환, 오픈 가중치판(Solar-Open-100B)은 102B라 Colab Pro로 자체 호스팅하기엔 과함 → 기각 |

### 4.3 최종 추천 — EXAONE 이원화 전략
Qwen 계열을 계속 쓰기보다 이번 프로젝트에서는 **EXAONE-3.5 계열로 진행**하기로 확정했다 (다른 모델도 실제로 써보고 싶다는 요청 반영). 기존 두 프로젝트에서 검증한 "작은 모델로 반복 → 큰 모델로 확정" 이원화 패턴은 그대로 유지한다.

- **로컬 개발/반복 테스트 단계**: `EXAONE-3.5-2.4B-Instruct` (Ollama, 로컬 GPU) — 프롬프트를 빠르게 여러 번 고쳐가며 검증할 때 사용. 비용 없음, 응답 빠름.
- **최종 데모/운영 단계**: `EXAONE-3.5-7.8B-Instruct` (Colab Pro) — k-safety-law-rag의 `exaone_colab_pro_server.ipynb`를 그대로 복사해와서 붙이면 새로 구축할 필요가 없다.

두 단계 모두 완전 무료(오픈 가중치, 자체 호스팅)라서 API 과금 걱정 없이 진행할 수 있다.

> ⚠️ 참고: 이 추천은 그동안 프로젝트에서 실제로 검증된 모델 기준이다. 실제 구현 시점에 더 최신/더 나은 한국어 모델(EXAONE 4.0 등 후속 버전 포함)이 나와 있을 수 있으니, Hugging Face/Ollama에서 "한국어 성능 + 구조화 출력" 기준으로 한 번 더 최신 정보를 확인하고 시작할 것.

### 4.4 프롬프트 설계 원칙
1. **숫자는 코드에서 계산, LLM은 해석만**: 최고가/최저가/평균가/현재가 백분위는 Python으로 미리 계산해서 프롬프트에 숫자로 넣는다. LLM에게 "계산해줘"라고 시키지 않는다 (환각 위험).
2. **JSON 스키마 강제**: 응답 형식을 예시와 함께 명시하고, 응답 후 `json.loads()` 검증 실패 시 재시도 로직을 둔다 (k-safety-law-rag의 JSON 검증 패턴 재사용).
3. **비교 근거는 입력된 스펙 범위 내에서만**: 스펙표에 없는 값은 "확인 불가"로 표시하도록 지시 — 스펙 환각 방지 (k-safety-law-rag의 "검색 결과 외 조항 언급 금지" 규칙과 동일한 사상).
4. **사용자 우선순위 반영**: "배터리 중시" 같은 사용자 입력이 있으면 그 축을 기준으로 재정렬해서 비교하도록 시스템 프롬프트에 명시.

### 4.5 프롬프트 예시 (기능 비교)
```text
[시스템]
당신은 전자상거래 상품 비교 전문가입니다. 아래 스펙표에 없는 정보는
추측하지 말고 "확인 불가"로 표시하세요. 사용자가 우선순위를 지정하면
그 기준으로 비교 순서를 재정렬하세요.

[스펙 데이터]
{
  "products": [
    {"name": "A", "price": 89000, "battery_hours": 8, "weight_g": 5.2, "anc": true},
    {"name": "B", "price": 65000, "battery_hours": 6, "weight_g": 4.8, "anc": false}
  ]
}

[사용자 우선순위]
배터리 지속시간

[출력 형식(JSON)]
{
  "ranking": ["A", "B"],
  "reason": "...",
  "feature_comparison": [
    {"feature": "battery_hours", "winner": "A", "detail": "..."}
  ]
}
```

### 4.6 프롬프트 예시 (매수 타이밍 판단)
```text
[시스템]
당신은 가격 분석가입니다. 아래 통계는 이미 계산되어 있으니
그대로 인용하고 새로운 숫자를 만들어내지 마세요.

[가격 통계 (코드에서 미리 계산)]
{
  "current_price": 79000,
  "min_90d": 72000,
  "max_90d": 95000,
  "avg_90d": 84000,
  "percentile_rank": 18
}

[출력 형식(JSON)]
{
  "verdict": "buy_now | wait | neutral",
  "reason": "현재가는 최근 90일 중 하위 18% 구간으로 상대적 저점입니다."
}
```

### 4.7 프롬프트 예시 (카테고리 베스트픽 추천)
```text
[시스템]
당신은 상품 추천 전문가입니다. 아래 성능 점수/가성비 점수는 이미 계산되어
있으니 그대로 인용하고, 점수를 직접 계산하거나 새로운 숫자를 만들어내지
마세요. 각 베스트픽이 왜 선정됐는지 스펙과 가격을 근거로 설명하세요.

[카테고리 점수 데이터 (코드에서 미리 계산, analysis.py)]
{
  "category": "무선 이어폰",
  "products": [
    {"name": "A", "price": 89000, "performance_score": 82, "value_score": 71,
     "battery_hours": 8, "anc": true, "weight_g": 5.2},
    {"name": "B", "price": 65000, "performance_score": 68, "value_score": 79,
     "battery_hours": 6, "anc": false, "weight_g": 4.8}
  ],
  "best_performance_candidate": "A",
  "best_value_candidate": "B"
}

[출력 형식(JSON)]
{
  "best_performance": {"product": "A", "reason": "..."},
  "best_value": {"product": "B", "reason": "..."}
}
```

### 4.8 LangGraph 기반 실행 파이프라인
비교/매수타이밍/베스트픽 세 작업 모두 "프롬프트 조립 → LLM 호출 → JSON 검증 → 실패 시 재시도 → 저장"이라는 동일한 흐름을 공유한다. 이 공통 흐름을 함수 3벌로 중복 구현하는 대신, LangGraph의 `StateGraph`로 한 번만 구현하고 `task_type`으로 분기한다.

> k-safety-law-rag에서는 동일한 개념을 위해 `langgraph` 패키지 없이 자체 경량 그래프 모듈(`question_graph.py`)을 만들었다. 이번에는 실제 `langgraph` 라이브러리를 사용해 두 접근을 실제로 비교해본다 (의존성 없는 자체 구현 vs 라이브러리 사용).

**State 정의**
```python
from typing import TypedDict, Literal, Optional

class LLMTaskState(TypedDict):
    task_type: Literal["compare", "buy_timing", "best_pick"]
    input_data: dict                 # analysis.py가 계산한 점수/통계/스펙
    prompt: Optional[str]
    raw_response: Optional[str]
    parsed_response: Optional[dict]
    validation_error: Optional[str]
    retry_count: int
    max_retries: int                 # 기본값 2
    result: Optional[dict]           # 최종 검증된 결과
```

**노드 구성**
| 노드 | 역할 |
|---|---|
| `input_validation_node` | `category_id`/`product_ids`가 실제 DB에 존재하는지 확인. 실패 시 즉시 종료 |
| `score_compute_node` | `analysis.py` 호출 — `task_type`에 필요한 가격 통계/성능·가성비 점수만 계산 |
| `prompt_router_node` | `task_type`에 따라 4.5/4.6/4.7 중 해당 프롬프트 템플릿을 조립 |
| `llm_call_node` | EXAONE 모델 호출, `raw_response`에 저장 |
| `json_validation_node` | 스키마 검증. 성공 시 `result` 채움, 실패 시 `validation_error` + `retry_count += 1` |
| `persist_node` | `task_type`에 맞는 테이블(comparison_reports / category_recommendations 등)에 저장 |

**그래프 연결 (설계 스케치)**
```python
# llm_agent.py
from langgraph.graph import StateGraph, END

graph = StateGraph(LLMTaskState)
graph.add_node("input_validation", input_validation_node)
graph.add_node("score_compute", score_compute_node)
graph.add_node("prompt_router", prompt_router_node)
graph.add_node("llm_call", llm_call_node)
graph.add_node("json_validation", json_validation_node)
graph.add_node("persist", persist_node)

graph.set_entry_point("input_validation")
graph.add_edge("input_validation", "score_compute")
graph.add_edge("score_compute", "prompt_router")
graph.add_edge("prompt_router", "llm_call")
graph.add_edge("llm_call", "json_validation")

def _route_after_validation(state: LLMTaskState) -> str:
    if state["validation_error"] and state["retry_count"] < state["max_retries"]:
        return "retry"
    return "done"

graph.add_conditional_edges(
    "json_validation",
    _route_after_validation,
    {"retry": "llm_call", "done": "persist"},
)
graph.add_edge("persist", END)

llm_pipeline = graph.compile()

# 호출 예시
# llm_pipeline.invoke({"task_type": "best_pick", "input_data": scores, "retry_count": 0, "max_retries": 2, ...})
```

- 재시도 횟수(`max_retries`)를 초과하고도 검증에 실패하면 `result`에 "확인 불가" 수준의 안전한 fallback 메시지를 채워서 종료한다 (조용히 실패하지 않고, 프론트에는 "AI 응답 생성에 실패했습니다" 같은 명확한 상태를 보여준다).
- 세 작업의 차이는 오직 `prompt_router_node`의 분기와 `persist_node`의 저장 테이블뿐이라, 새 LLM 작업 유형이 추가돼도 그래프 구조를 그대로 재사용할 수 있다.

### 4.9 DB Coder 에이전트 (읽기 전용 자연어 분석, 관리자용)
자연어 질문("지난주 대비 이번주 평균가가 오른 상품 알려줘")을 SQL로 변환해 실행하는 별도 에이전트. **DB 관리(스키마 변경/데이터 수정)까지 자동화하지 않고, 조회(SELECT)만 허용한다** — LLM이 환각으로 `DELETE`/`DROP TABLE` 같은 쿼리를 생성해 실제로 실행되는 사고를 원천 차단하기 위해서다.

**State 정의**
```python
class DBCoderState(TypedDict):
    nl_question: str
    schema_context: str          # 6번 섹션 스키마를 문자열로 주입
    generated_sql: Optional[str]
    validation_error: Optional[str]
    query_result: Optional[list]
    answer: Optional[str]        # 결과를 자연어로 요약
    retry_count: int
    max_retries: int
```

**노드 구성 및 안전장치**
| 노드 | 역할 | 안전장치 |
|---|---|---|
| `sql_generation_node` | DB 스키마를 컨텍스트로 주고 LLM이 SQL 생성 | 시스템 프롬프트에 "SELECT 문만 작성" 명시 |
| `sql_validation_node` | `sqlparse`로 파싱해 키워드 화이트리스트 검증 (`SELECT`/`WITH`/`FROM`/`WHERE`/`JOIN`/`GROUP BY`/`ORDER BY`/`LIMIT`만 허용) | `INSERT`/`UPDATE`/`DELETE`/`DROP`/`ALTER`/`CREATE`가 하나라도 포함되면 즉시 거부, 재시도 없이 종료 |
| `sql_execution_node` | 검증 통과한 쿼리만 실행 | **DB 연결 자체를 읽기 전용으로 오픈** (SQLite URI `file:app.db?mode=ro`) — 애플리케이션 로직뿐 아니라 연결 단계에서도 쓰기를 물리적으로 차단하는 이중 안전장치 |
| `result_formatting_node` | 조회 결과를 자연어로 요약 | 결과에 없는 값은 언급하지 않도록 지시 |

- 이 에이전트는 `/api/admin/query` 같은 **관리자 전용/로컬 전용 엔드포인트**로만 노출한다. 일반 사용자에게 개방하지 않는다.
- `sql_validation_node`에서 거부된 경우는 4.8의 재시도 루프와 달리 **재시도하지 않고 즉시 거부**한다 (위험 쿼리를 다르게 표현해 우회 생성하는 것을 막기 위함).

---

## 5. 데이터 소스 & API 연동 상세

### 5.1 네이버 검색 API — 쇼핑
- **가입/발급**: developers.naver.com → 애플리케이션 등록 → "검색" API 사용 설정 → Client ID/Secret 발급
- **엔드포인트**: `GET https://openapi.naver.com/v1/search/shop.json`
- **주요 파라미터**: `query`(검색어), `display`(결과 수, 최대 100), `start`(페이지), `sort`(sim/date/asc/dsc)
- **주요 응답 필드**:

| 필드 | 설명 |
|---|---|
| `title` | 상품명 (HTML 태그 포함될 수 있음, 파싱 필요) |
| `link` | 상품 상세 페이지 링크 |
| `image` | 상품 이미지 URL |
| `lprice` / `hprice` | 최저가 / 최고가 |
| `mallName` | 판매처명 |
| `productId` | 네이버쇼핑 상품 ID |
| `productType` | 상품 유형 코드 (1: 일반상품, 2: 유사상품 등) |
| `brand` / `maker` | 브랜드 / 제조사 |
| `category1~4` | 카테고리 계층 |

> ⚠️ 이 API는 **상세 스펙(배터리, 무게 등)을 제공하지 않는다.** 이게 이 프로젝트의 핵심 병목이며, MVP에서는 스펙을 수동 큐레이션 JSON으로 별도 관리한다 (5.3 참고).
> ⚠️ 일일 호출 한도가 있다 — 정확한 쿼터는 발급 시점에 개발자센터에서 반드시 재확인할 것 (문서상 수치를 임의로 단정하지 않는다).

### 5.2 네이버 데이터랩 API — 쇼핑인사이트
- **엔드포인트**: `POST https://openapi.naver.com/v1/datalab/shopping/categories` 등
- **용도**: 카테고리별 검색 트렌드 지수, 연령대/성별 관심도 비율
- **주의**: 카테고리 코드가 네이버쇼핑 자체 분류 체계를 따르므로, 사용하려는 카테고리의 코드를 먼저 조회해야 함

### 5.3 MVP 스펙 큐레이션 데이터
API가 주지 않는 스펙 정보는 수동으로 관리한다. `score_weights`는 카테고리 베스트픽 추천(6번/8번 섹션)에서 성능/가성비 점수를 계산할 때 사용하는 가중치이며, 카테고리마다 의미 있는 스펙이 다르므로 카테고리별로 직접 정의한다.

```json
// data/specs/무선이어폰.json
{
  "category": "무선 이어폰",
  "score_weights": {
    "battery_hours": {"weight": 0.4, "direction": "higher_better"},
    "anc":           {"weight": 0.3, "direction": "boolean_bonus"},
    "weight_g":       {"weight": 0.3, "direction": "lower_better"}
  },
  "products": [
    {
      "product_id": "네이버쇼핑_productId와_매칭",
      "name": "상품명",
      "battery_hours": 8,
      "anc": true,
      "weight_g": 5.2,
      "water_resistant": "IPX4",
      "source": "제조사 공식 페이지 (URL)",
      "curated_at": "2026-07-09"
    }
  ]
}
```

이 파일은 카테고리를 추가할 때마다 수동으로 채워야 하는 유일한 비자동화 지점이며, 이후 Phase에서 카탈로그 상세 페이지 파싱으로 자동화할 수 있는 확장 여지를 남겨둔다.

### 5.4 성능 점수 / 가성비 점수 계산 방식
O2O-Demand-Forecasting-Solution의 `calculate_demand_score()`(Min-Max 정규화 + 가중합산) 패턴을 그대로 재사용한다.

1. `score_weights`에 정의된 각 스펙 값을 카테고리 내 상품군 기준으로 Min-Max 정규화(0~100). `direction`이 `lower_better`면 정규화 전에 역수 처리, `boolean_bonus`면 true/false를 100/0으로 매핑.
2. **성능 점수(performance_score)** = 정규화된 스펙 점수의 가중합산 (가격 반영 안 함)
3. **가성비 점수(value_score)** = `performance_score / normalized_price` 형태로 계산 (가격이 낮을수록, 성능이 높을수록 점수가 올라가도록 정규화된 가격의 역수를 곱하는 방식)
4. 두 점수 모두 **코드에서 계산 완료 후** LLM에는 결과값만 전달한다 (4.4의 "숫자는 코드에서 계산" 원칙과 동일).

---

## 6. 데이터베이스 스키마 설계

```sql
CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    naver_category_code TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER REFERENCES categories(id),
    naver_product_id TEXT UNIQUE,
    name TEXT NOT NULL,
    brand TEXT,
    maker TEXT,
    mall_name TEXT,
    link TEXT,
    image_url TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE specs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER REFERENCES products(id),
    spec_key TEXT NOT NULL,      -- 예: battery_hours, weight_g, anc
    spec_value TEXT NOT NULL,
    source TEXT,                 -- 큐레이션 출처
    curated_at TEXT
);

CREATE TABLE price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER REFERENCES products(id),
    price INTEGER NOT NULL,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE comparison_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER REFERENCES categories(id),
    product_ids TEXT,            -- JSON 배열
    user_priority TEXT,           -- 예: "battery_hours"
    llm_model TEXT,
    report_json TEXT,            -- LLM 응답 원문(JSON)
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE price_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER REFERENCES products(id),
    target_price INTEGER NOT NULL,
    triggered INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 카테고리별 가성비/성능 베스트픽 (스케줄러가 매일 가격 수집 후 갱신)
CREATE TABLE category_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER REFERENCES categories(id),
    best_value_product_id INTEGER REFERENCES products(id),
    best_value_score REAL,
    best_value_reason TEXT,          -- LLM 생성 설명
    best_performance_product_id INTEGER REFERENCES products(id),
    best_performance_score REAL,
    best_performance_reason TEXT,     -- LLM 생성 설명
    llm_model TEXT,
    generated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 파이프라인 실행 이력 (관찰성, 16절)
CREATE TABLE pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type TEXT NOT NULL,          -- 'price_collection' | 'best_pick_recompute' | 'alert_check'
    status TEXT NOT NULL,            -- 'success' | 'failed'
    items_processed INTEGER,
    error_message TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT
);

-- 사용자 피드백 (17절)
CREATE TABLE feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL,       -- 'comparison_report' | 'best_pick' | 'buy_timing'
    target_id INTEGER NOT NULL,      -- 해당 테이블의 row id
    is_helpful INTEGER NOT NULL,     -- 1 = 도움됨, 0 = 도움 안 됨
    comment TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

---

## 7. 스케줄러 설계

```python
# scheduler.py (설계 스케치)
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from collector import collect_prices_for_all_products
from analysis import check_price_alerts, recompute_category_recommendations
from llm_agent import generate_best_pick_reasons
from db import record_pipeline_run

scheduler = BlockingScheduler(timezone="Asia/Seoul")

def _run_with_logging(run_type: str, fn, *args, **kwargs):
    """모든 스케줄 작업을 pipeline_runs에 기록하는 공통 래퍼 (16절 관찰성)"""
    started_at = datetime.now().isoformat()
    try:
        result = fn(*args, **kwargs)
        record_pipeline_run(run_type, "success", started_at, items_processed=len(result or []))
        return result
    except Exception as e:
        record_pipeline_run(run_type, "failed", started_at, error_message=str(e))
        raise  # 로깅 후에도 예외는 그대로 올려서 알림/재시도 로직이 인지하게 한다

@scheduler.scheduled_job("cron", hour=9, minute=0)
def daily_price_collection():
    _run_with_logging("price_collection", collect_prices_for_all_products)
    _run_with_logging("alert_check", check_price_alerts)
    scores = _run_with_logging("best_pick_recompute", recompute_category_recommendations)
    generate_best_pick_reasons(scores)         # LLM 설명 생성 후 category_recommendations upsert

if __name__ == "__main__":
    scheduler.start()
```

- 실패 시 로깅 후 다음 주기에 재시도 (k-safety-law-rag의 명확한 오류 메시지 출력 패턴 재사용)
- Windows 환경이므로 상시 프로세스 대신 **Windows 작업 스케줄러**로 스크립트를 매일 1회 실행하는 방식도 대안으로 고려 (`_system/scripts/daily_note_gen.py`와 동일한 방식)
- 모든 작업이 `_run_with_logging()`을 거치므로 실행 이력이 자동으로 `pipeline_runs`에 쌓인다 (16절)

---

## 8. 백엔드 API 설계

| 메서드 | 경로 | 설명 |
|---|---|---|
| `GET` | `/api/categories` | 등록된 카테고리 목록 |
| `GET` | `/api/products?category_id=` | 카테고리별 상품 목록 (가격/판매처 포함) |
| `GET` | `/api/products/{id}/price-history?days=90` | 가격 추이 조회 |
| `POST` | `/api/compare` | 상품 ID 목록 + 사용자 우선순위 → LLM 비교 리포트 생성 |
| `GET` | `/api/products/{id}/buy-timing` | 매수 타이밍 판단 조회 |
| `GET` | `/api/categories/{id}/best-picks` | 카테고리 내 가성비/성능 최고 상품 + LLM 추천 이유 조회 (스케줄러가 미리 계산해둔 값을 반환) |
| `POST` | `/api/alerts` | 가격 알림 등록 |
| `POST` | `/api/collect` | 수동 재수집 트리거 (관리자용) |
| `POST` | `/api/feedback` | 리포트/베스트픽/매수타이밍 결과에 대한 도움됨 여부 피드백 등록 (17절) |
| `GET` | `/api/admin/pipeline-runs` | 최근 파이프라인 실행 이력 조회 (16절, 관리자용) |
| `POST` | `/api/admin/query` | DB Coder 에이전트(4.9)에 자연어 질의 — 읽기 전용, 관리자 전용 |
| `GET` | `/health` | 서버 상태 확인 |

---

## 9. 프론트엔드/대시보드 설계 (반응형)

### 9.1 디자인 참고
[Figma — E-Wallet Mobile App Design (Community)](https://www.figma.com/design/vivRVoOQdzK93K8rLh15RO/-Preview-Only----E-Wallet-Mobile-App-Design--Community-)을 비주얼 레퍼런스로 참고한다.

> ⚠️ 현재는 **디자인 방향성만** 반영된 상태다. Figma MCP 도구가 데스크톱 앱에서 실제 레이어가 선택된 상태여야 상세 정보(색상 토큰, 컴포넌트 구조, 정확한 spacing)를 가져올 수 있어서, 아직 실제 파일 내용은 추출하지 못했다. 이후 진행 시:
> 1. Figma 데스크톱 앱에서 이 Community 파일을 본인 계정으로 Duplicate
> 2. 참고하고 싶은 화면 프레임을 선택 → 우클릭 → "Copy link to selection"
> 3. 그 node-specific 링크를 다시 전달하면, 실제 색상/타이포/컴포넌트를 이 섹션에 반영해 갱신할 것.
>
> 그 전까지는 e-wallet류 모바일 앱 UI에서 흔히 쓰이는 일반적인 디자인 패턴(카드 기반 요약 섹션, 리스트형 아이템, 하단 고정 네비게이션, 여백이 넉넉한 미니멀 톤)을 참고 방향으로만 잡아둔다. **정확한 색상/폰트 값을 임의로 지어내 코드에 반영하지 않는다.**

### 9.2 반응형 전략
- 모바일 우선(mobile-first) CSS로 작성 — 작은 화면 기준 스타일을 기본으로 하고 `min-width` 미디어 쿼리로 태블릿/데스크톱 레이아웃을 확장한다
- 브레이크포인트: `~480px`(모바일) / `481~768px`(태블릿) / `769px~`(데스크톱)
- 레이아웃은 flexbox/grid 기반 카드 그리드 — 모바일에서는 1열 스택, 데스크톱에서는 2~3열 그리드로 전환
- 내비게이션은 모바일에서 하단 고정 탭바, 데스크톱에서는 상단 내비게이션으로 전환

### 9.3 화면 구성 (카드 기반 UI)
- **홈/카테고리 선택**: 상단 "요약 카드"(등록 카테고리 수, 최근 비교 리포트 수 등 — wallet 앱의 잔액 카드 자리에 대응) + "이 카테고리 추천" 카드(가성비 최고/성능 최고 배지, 탭하면 LLM 추천 이유 펼침) + 하단 카테고리 리스트 카드
- **비교 화면**: 상품을 리스트/거래내역 카드 스타일로 나열(가격/판매처) + "우선순위 선택" 필터 + "AI 비교 리포트 생성" 버튼
- **상품 상세 화면**: 가격 추이 라인 차트(Chart.js) + 매수 타이밍 코멘트를 인사이트 카드 형태로 배치
- **비교 리포트 화면**: 기능별 승자 표 + LLM 생성 추천 문단을 카드 섹션으로 분리
- **모든 LLM 결과 카드 공통**: 하단에 "도움됐어요 👍 / 아니요 👎" 버튼 → `POST /api/feedback` 호출 (17절)
- **관리자 화면(비공개 경로)**: 최근 파이프라인 실행 이력(16절, 성공/실패 배지 + 소요시간) + DB Coder 자연어 질의창(4.9절) — 일반 사용자 내비게이션에는 노출하지 않는다

### 9.4 기술 스택
Flask + Jinja2 템플릿을 유지하되(별도 SPA 프레임워크 도입은 이 스코프에서 불필요 — O2O 프로젝트와 동일 스택 재사용 원칙), CSS는 모바일 우선 반응형으로 새로 작성한다. O2O-Demand-Forecasting-Solution의 대시보드 UI 패턴(KPI 카드, 차트, 랭킹 테이블)을 반응형 그리드로 재구성해 재사용하면 개발 속도를 아낄 수 있다.

---

## 10. 폴더 구조 제안

```text
naver-shopping-guide/
├── .env.example
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml                # 18절: push/PR 시 테스트+lint 자동 실행
├── Dockerfile                     # 19절
├── docker-compose.yml             # 19절: app + scheduler 서비스 묶음
├── requirements.txt
├── app.py                     # Flask 서버
├── collector.py                # 네이버 API 수집 모듈
├── scheduler.py                 # 가격 주기 수집 + pipeline_runs 로깅
├── analysis.py                  # 가격 통계/스펙 비교 계산
├── llm_agent.py                  # LangGraph StateGraph — 프롬프트 조립/모델 호출/JSON 검증/재시도/저장
├── db_coder_agent.py              # 4.9절: 읽기 전용 자연어→SQL 에이전트
├── db.py                         # DB 연결 및 스키마 초기화, record_pipeline_run()
├── data/
│   └── specs/                    # 카테고리별 수동 스펙 큐레이션 JSON
├── templates/
│   ├── index.html
│   ├── category.html
│   ├── product_detail.html
│   ├── compare_report.html
│   └── admin_dashboard.html       # 16절: 파이프라인 실행 이력 + DB Coder 질의창
├── static/
├── notebooks/
│   └── exaone35_7_8b_colab_server.ipynb   # k-safety-law-rag의 exaone_colab_pro_server.ipynb 재사용/복사
└── tests/
    ├── test_analysis.py
    └── test_llm_agent.py          # 13절: LangGraph 재시도/fallback 케이스
```

---

## 11. 환경 변수

```env
# .env.example
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=

LLM_PROVIDER=local_ollama          # local_ollama | remote_openai
LLM_MODEL=exaone3.5:2.4b           # 운영 전환 시 LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct
LLM_API_BASE=http://localhost:11434
LLM_API_KEY=dummy

DB_PATH=data/app.db
PORT=8400
```

---

## 12. 개발 로드맵

### Phase 1 — 데이터 파이프라인 (MVP 기반)
- [ ] 네이버 검색 API / 데이터랩 API 키 발급
- [ ] `collector.py`: 카테고리 키워드로 경쟁 상품 수집
- [ ] DB 스키마 초기화 (`db.py`)
- [ ] 카테고리 1개 선정 후 스펙 큐레이션 JSON 작성 (제품 5~10개)

### Phase 2 — 가격 추적
- [ ] `price_history` 적재 로직 구현
- [ ] `scheduler.py` 구현 (일 1회 수집)
- [ ] 가격 통계 계산(`analysis.py`): 최고/최저/평균/백분위
- [ ] 카테고리별 성능 점수/가성비 점수 계산(`analysis.py`, 5.4 방식) 구현 + 단위 테스트

### Phase 3 — LLM 비교/추천
- [ ] `langgraph` 설치, `llm_agent.py`에 StateGraph 구축 (4.8절: input_validation→score_compute→prompt_router→llm_call⇄json_validation→persist)
- [ ] 기능 비교 프롬프트(4.5) + 매수 타이밍 판단 프롬프트(4.6) + 카테고리 베스트픽 프롬프트(4.7)를 `prompt_router_node`에 연결
- [ ] 재시도 초과 시 fallback 메시지 처리 확인
- [ ] 로컬 EXAONE-3.5-2.4B-Instruct로 그래프 전체 흐름 반복 검증

### Phase 4 — 백엔드/프론트엔드
- [ ] Flask REST API 구현 (8번 섹션 엔드포인트)
- [ ] Figma 파일 Duplicate 후 참고 화면 node 링크 확보 → 실제 색상/컴포넌트 토큰 반영해 9.1 갱신
- [ ] 모바일 우선 반응형 CSS 작성 (브레이크포인트 3단계)
- [ ] 대시보드 화면 4종(홈/카테고리, 비교, 상품상세, 비교리포트) 구현
- [ ] 가격 추이 차트 연동 (Chart.js, 반응형 리사이즈 확인)

### Phase 5 — 운영 모델 전환 & 알림 (확장)
- [ ] Colab Pro + EXAONE-3.5-7.8B-Instruct로 전환
- [ ] 가격 알림(`price_alerts`) 기능 구현
- [ ] 알림 발송 채널 연동 (이메일 우선, 이후 슬랙/텔레그램 확장 가능)

### Phase 6 — 스펙 자동화 & 카테고리 확장 (최종 완성 이후 과제)
- [ ] 카탈로그 상세 페이지에서 스펙 자동 파싱 검토 (크롤링이 아닌 공식 페이지 정적 파싱 범위 내에서, robots.txt 준수)
- [ ] 카테고리 2개 이상으로 확장
- [ ] 사용자 계정/찜 목록 기능
- [ ] DB Coder 에이전트(4.9) 구현 — `sqlparse` 검증 + 읽기전용 DB 연결 + 관리자 전용 엔드포인트

### Phase 7 — 운영 신뢰성 & 배포 (기업 포트폴리오 심사 대응)
> 우선순위: 관찰성·CI는 코드량 대비 효과가 커서 먼저, 피드백 루프·Docker는 그 다음으로 진행 추천 (자세한 내용은 16~19절)
- [ ] `pipeline_runs` 테이블 + `_run_with_logging()` 래퍼 구현, 관리자 대시보드에 실행 이력 노출 (16절)
- [ ] `.github/workflows/ci.yml` 작성 — push/PR마다 `ruff` + `pytest` 자동 실행 (18절)
- [ ] `feedback` 테이블 + 모든 LLM 결과 카드에 👍/👎 버튼 연결 (17절)
- [ ] `Dockerfile` + `docker-compose.yml` 작성, `docker compose up`으로 전체 스택 기동 확인 (19절)

---

## 13. 테스트 전략
- `analysis.py`의 통계 계산 함수는 알려진 입력값으로 단위 테스트 (평균/백분위 계산 정확성 검증 — LLM이 잘못된 숫자를 인용하지 않도록 원천 차단)
- `analysis.py`의 성능/가성비 점수 계산 함수도 알려진 스펙 조합으로 단위 테스트 (Min-Max 정규화, `lower_better`/`boolean_bonus` 방향성 처리가 의도대로 동작하는지 검증)
- `llm_agent.py`의 LangGraph 파이프라인은 (a) 첫 시도에 성공하는 케이스, (b) N번 실패 후 재시도로 성공하는 케이스, (c) `max_retries` 초과로 fallback되는 케이스 세 가지를 모두 단위 테스트
- API 엔드포인트는 실제 네이버 API 대신 mock 응답으로 통합 테스트
- 위 테스트는 로컬뿐 아니라 GitHub Actions CI(18절)에서 push/PR마다 자동 실행되며, 외부 API 키 없이도 통과해야 한다

---

## 14. 확장 방향 (최종 완성 이후)
- 스펙 자동 수집으로 큐레이션 병목 해소
- 카테고리 다변화 (가전, 캠핑용품 등)
- 가격 알림을 슬랙/텔레그램 봇으로 확장
- "이 카테고리 트렌드 브리핑"을 정기 자동 생성해 이메일로 발송 (데이터랩 API 활용)
- 여러 카테고리를 넘나드는 예산 배분 추천 (예: "이번 달 20만원으로 이어폰+케이스 중 뭘 살까")

---

## 15. Claude Code 작업 규칙 (이 프로젝트 전용)
1. 가격/통계 숫자는 반드시 코드에서 계산 후 LLM 프롬프트에 주입한다 — LLM이 직접 계산하게 하지 않는다.
2. 스펙 큐레이션 JSON에 없는 값은 LLM이 "확인 불가"로만 답하도록 시스템 프롬프트에 명시한다 (환각 방지).
3. 크롤링이 필요한 시점이 오면 반드시 먼저 사용자에게 확인 — robots.txt 준수, 요청 간격 확보 없이 진행하지 않는다.
4. 로컬 개발 중에는 `EXAONE-3.5-2.4B-Instruct`로 반복 검증하고, 데모/발표 직전에만 Colab `EXAONE-3.5-7.8B-Instruct`로 전환한다.
5. `.env`, `data/app.db`는 git에 커밋하지 않는다 (`.gitignore` 확인).
6. LLM 작업(비교/매수타이밍/베스트픽)을 새로 추가할 때는 `llm_agent.py`의 기존 함수 형태로 새로 짜지 말고, 4.8절의 LangGraph `prompt_router_node`/`persist_node`에 분기를 추가하는 방식으로 확장한다 (그래프 구조를 중복 구현하지 않는다).
7. DB Coder 에이전트(4.9)가 생성한 SQL은 반드시 읽기 전용 DB 연결 + 키워드 화이트리스트 검증을 통과한 것만 실행한다. DDL/DML 키워드가 포함되면 재시도 없이 즉시 거부하고, 절대 자동으로 쓰기 쿼리를 실행하지 않는다.
8. 스펙 데이터 확보를 위해 다나와/에누리 등 타 가격비교 서비스를 크롤링하지 않는다 — 이 프로젝트의 핵심 가치 제안(0번 섹션, "완전히 합법적인 데이터 파이프라인")과 정면으로 충돌하며, 스펙 비교 데이터는 해당 서비스들의 핵심 비즈니스 자산이라 법적 리스크가 일반 크롤링보다 크다. 스펙 자동화가 필요하면 제조사 공식 페이지 등 리스크가 낮은 대안을 먼저 사용자와 상의한다.
9. 스케줄러가 실행하는 모든 작업(가격수집/알림확인/베스트픽재계산)은 `_run_with_logging()` 래퍼를 거쳐 `pipeline_runs`에 기록되게 하고, 이 로깅을 우회하는 별도 실행 경로를 만들지 않는다 (16절).
10. `feedback` 테이블 데이터를 근거로 `score_weights`나 프롬프트를 자동으로 바꾸지 않는다 — 피드백은 어디까지나 사람이 검토해서 반영하는 참고 자료다 (17절).

---

## 16. 파이프라인 관찰성 (Observability)

### 왜 필요한가
스케줄러가 매일 자동으로 가격을 수집하고 베스트픽을 재계산하는데, 지금까지는 "성공했는지 실패했는지"를 확인할 방법이 없었다. 데이터 엔지니어링 역할에서 가장 중요한 것 중 하나가 "파이프라인이 조용히 실패하지 않게 만드는 것"이므로, 이 프로젝트에서 그 역량을 직접 보여주는 지점으로 삼는다.

### 설계
- `pipeline_runs` 테이블(6절)에 모든 스케줄 작업의 `run_type`, `status`, `items_processed`, `error_message`, 시작/종료 시각을 기록
- `scheduler.py`의 `_run_with_logging()` 래퍼(7절)가 모든 작업 실행을 감싸서, 개별 작업마다 로깅 코드를 중복 작성하지 않는다
- 관리자 화면(`admin_dashboard.html`)에서 최근 실행 이력을 리스트로 표시 — 성공은 초록 배지, 실패는 빨간 배지 + 에러 메시지
- `GET /api/admin/pipeline-runs`로 이력 조회 (8절)

### 확장 여지
- 연속 실패 N회 이상 시 이메일/슬랙으로 알림 (Phase 5의 알림 채널 재사용)
- 수집 성공률, 평균 소요시간 등 간단한 통계를 관리자 화면 상단에 요약 카드로 표시

---

## 17. 사용자 피드백 루프

### 왜 필요한가
LLM 기능(비교/매수타이밍/베스트픽)을 만드는 것과, 그게 실제로 쓸만한지 확인하는 것은 다른 문제다. "이 추천이 도움이 됐는가"를 데이터로 쌓아두면, AI 기능을 만들고 끝내는 게 아니라 개선 근거까지 갖추고 있다는 것을 보여줄 수 있다.

### 설계
- `feedback` 테이블(6절)에 `target_type`(comparison_report/best_pick/buy_timing), `target_id`, `is_helpful`(👍/👎), 선택적 `comment` 저장
- 모든 LLM 결과 카드(9.3절)에 "도움됐어요 👍 / 아니요 👎" 버튼 부착 → `POST /api/feedback`
- 이 데이터는 **자동으로 프롬프트나 `score_weights`를 바꾸는 데 쓰지 않는다** (작업 규칙 10). 사람이 주기적으로 `feedback` 테이블을 조회해서(관리자 화면 또는 DB Coder 에이전트로 "최근 도움 안 됐다는 피드백이 많은 카테고리는?" 같은 질문을 던져서) 프롬프트나 가중치를 수동으로 조정하는 근거로만 사용한다

### 포트폴리오 관점에서의 의미
"AI 기능을 만들었다"가 아니라 "AI 기능의 품질을 어떻게 측정하고 개선하는가"까지 설계했다는 것을 보여주는 지점 — 면접에서 "이 추천이 실제로 잘 맞았는지 어떻게 아세요?"라는 질문에 바로 답할 수 있다.

---

## 18. CI/CD 파이프라인

### 왜 필요한가
지금까지 만든 다른 3개 프로젝트(k-safety-law-rag, construction-vl-agent, O2O)에는 CI가 없다. push할 때마다 테스트가 자동으로 도는 것만으로도 "배포 파이프라인을 이해하고 있다"는 신호를 준다. 이 프로젝트에서 가장 적은 노력으로 가장 확실한 차별화를 만드는 지점이다.

### 설계 (`.github/workflows/ci.yml`)
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Lint (ruff)
        run: ruff check .
      - name: Run tests
        run: pytest tests/ -v
```

- `test_analysis.py`(가격 통계/성능·가성비 점수 계산), `test_llm_agent.py`(LangGraph 재시도/fallback 케이스)가 이 워크플로우에서 자동 실행된다 (13절)
- 외부 API(네이버)나 실제 LLM 호출이 필요한 테스트는 CI에서 mock으로 대체 — 실제 API 키 없이도 CI가 통과해야 한다
- lint는 가볍게 `ruff` 하나만 사용 (별도 설정 파일 없이 기본 규칙으로 시작, 필요시 `pyproject.toml`에 규칙 추가)

---

## 19. 배포 (Docker Compose)

### 왜 필요한가
면접관이나 채용 담당자가 레포를 클론해서 직접 실행해볼 수 있으면 데모 신뢰도가 크게 올라간다. `.env`만 채우고 명령어 한 줄로 전체 스택(Flask + 스케줄러)이 뜨는 게 목표다.

### 설계
```dockerfile
# Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "app.py"]
```

```yaml
# docker-compose.yml
services:
  app:
    build: .
    ports:
      - "8400:8400"
    env_file: .env
    volumes:
      - ./data:/app/data      # SQLite 파일을 컨테이너 밖에 유지 (재시작해도 데이터 보존)
    command: python app.py

  scheduler:
    build: .
    env_file: .env
    volumes:
      - ./data:/app/data      # app과 동일한 DB 파일 공유
    command: python scheduler.py
```

- `app`(Flask 웹서버)과 `scheduler`(가격 수집 스케줄러)를 별도 컨테이너로 분리 — 웹서버가 재시작되어도 스케줄러 상태에 영향 없음
- 두 컨테이너가 `./data` 볼륨을 공유해 같은 SQLite 파일을 사용 (SQLite는 다중 프로세스 쓰기에 취약하므로, 트래픽이 늘면 PostgreSQL로 전환 시 이 문제도 함께 해소됨 — 3절에 이미 명시된 전환 계획)
- 실행: `docker compose up` 한 줄로 전체 스택 기동
