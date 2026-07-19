# Agent Roles — naver-shopping-buy-guide

## Claude Code (UX Agent)

**담당 파일:** `templates/`, `static/`

**작업 순서:**
1. `TODO.md`의 `[CODEX 완료]` 섹션을 읽는다
2. 완료된 백엔드 변경사항을 프론트에 반영한다 (`templates/`, `static/`)
3. 앱을 사용자 관점에서 검토해 UX 문제나 개선 아이디어를 찾는다
4. 새로운 백엔드 요청을 `[CODEX 요청]`에 추가한다
5. 이번 라운드 작업 내용을 `[검증 결과]`에 요약한다

**규칙:**
- 백엔드 파일(`app.py`, `analysis.py`, `db.py` 등)은 절대 수정하지 않는다
- 백엔드가 필요한 작업은 반드시 `[CODEX 요청]`으로 위임한다
- 할 일이 없으면 `[검증 결과]`에 `대기 중 — 추가 요청 없음` 기록

---

## Codex (Feature Agent)

**담당 파일:** `app.py`, `analysis.py`, `collector.py`, `db.py`, `llm_agent.py`, `product_classifier.py`, `scheduler.py`

**작업 순서:**
1. `TODO.md`의 `[CODEX 요청]` 섹션에서 미완료 항목을 읽는다
2. 요청된 기능을 백엔드 파일에 구현한다
3. 완료된 항목에 `[완료]` 표시를 추가한다
4. 구현 내용을 `[CODEX 완료]`에 날짜와 함께 요약한다

**규칙:**
- `templates/`, `static/` 파일은 수정하지 않는다 (프론트는 Claude Code 담당)
- API 응답 구조가 바뀌면 `[CODEX 완료]`에 반드시 명시한다
- 할 일이 없으면 `[CODEX 완료]`에 `대기 중 — 구현할 요청 없음` 기록

---

## Antigravity (QA & Usability Agent)

**담당 역할:** 테스트 환경 정상화, QA 및 사용성 크로스 검증

**작업 순서:**
1. `TODO.md`의 `[CODEX 완료]` 및 `[검증 결과]`를 검토한다.
2. `tests/` 디렉토리 내 테스트 검증 및 pytest, ruff 등 린터/테스터 환경을 관리한다.
3. UI/UX 검증(모바일 반응성, 크로스 브라우징, 접근성)을 수행하고 개선점을 제시한다.
4. 검증 결과 및 발견된 이슈를 `TODO.md`의 `[검증 결과]` 섹션에 요약 기록한다.

**규칙:**
- 테스트 코드(`tests/`) 및 개발 환경 설정 파일은 수정/추가할 수 있다.
- 프로덕션 코드(프론트, 백엔드)는 직접 수정하지 않고, 검증 과정에서 찾은 버그나 개선사항은 `TODO.md`를 통해 Codex(백엔드) 또는 Claude Code(프론트)에게 전달하여 반영한다.

---

## 소통 채널: TODO.md

```
[CODEX 요청]   ← Claude Code 또는 Antigravity가 작성
[CODEX 완료]   ← Codex가 작성
[검증 결과]    ← Claude Code 또는 Antigravity가 작성
```

- 모든 항목에 날짜(`YYYY-MM-DD`) 기록
- 완료된 항목은 삭제하지 말고 `[완료]` 표시
- 라운드가 쌓일수록 히스토리가 된다
