from __future__ import annotations

import re
from typing import Any

TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")

ACCESSORY_KEYWORDS = {
    "케이스",
    "커버",
    "파우치",
    "가방",
    "보호필름",
    "필름",
    "강화유리",
    "스킨",
    "스티커",
    "거치대",
    "스탠드",
    "홀더",
    "충전기",
    "충전",
    "어댑터",
    "케이블",
    "젠더",
    "도킹",
    "독",
    "이어팁",
    "이어캡",
    "팁",
    "스트랩",
    "밴드",
    "리필",
    "부품",
    "배터리",
    "렌즈커버",
    "키스킨",
    "키캡",
    "마우스패드",
    "보호대",
    "필터",
    "리모컨",
}

MAIN_PRODUCT_HINTS = {
    "이어폰": {"이어폰", "버즈", "buds", "airpods", "에어팟", "헤드셋", "헤드폰"},
    "무선이어폰": {"이어폰", "버즈", "buds", "airpods", "에어팟"},
    "노트북": {"노트북", "북", "그램", "갤럭시북", "맥북", "laptop"},
    "아이폰": {"아이폰", "iphone", "자급제", "미개봉"},
    "스마트워치": {"워치", "watch", "갤럭시워치", "애플워치"},
    "태블릿": {"태블릿", "아이패드", "ipad", "갤럭시탭", "탭"},
}


def classify_search_item(query: str, item: dict[str, Any], rank: int | None = None) -> dict[str, Any]:
    title = str(item.get("title") or item.get("name") or "")
    category_text = " ".join(
        str(item.get(key) or "") for key in ("category1", "category2", "category3", "category4")
    )
    title_tokens = _tokens(title)
    query_tokens = _tokens(query)
    accessory_hits = sorted(keyword for keyword in ACCESSORY_KEYWORDS if keyword.lower() in title.lower())
    main_hits = sorted(_main_hints(query) & title_tokens)
    query_overlap = len(query_tokens & title_tokens)

    score = 52.0
    reasons: list[str] = []
    if query_overlap:
        score += min(query_overlap * 12, 24)
        reasons.append("검색어와 상품명 토큰이 겹침")
    if main_hits:
        score += min(len(main_hits) * 14, 28)
        reasons.append("본품 단서가 상품명에 있음")
    if accessory_hits:
        score -= min(len(accessory_hits) * 30, 70)
        reasons.append(f"부속품 키워드 감지: {', '.join(accessory_hits[:4])}")
    if "액세서리" in category_text or "주변기기" in category_text:
        score -= 25
        reasons.append("네이버 카테고리가 주변기기/액세서리 계열")
    if item.get("image"):
        score += 4
    if item.get("lprice"):
        score += 4
    if rank is not None and rank <= 5:
        score += 4

    score = max(0.0, min(100.0, score))
    product_type = "main_product" if score >= 55 else "accessory"
    if not reasons:
        reasons.append("가격/이미지/검색 순위 기반 기본 분류")
    return {
        "product_type": product_type,
        "classification_score": round(score, 2),
        "classification_reason": " · ".join(reasons),
    }


def _tokens(value: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(value) if len(token) >= 2}


def _main_hints(query: str) -> set[str]:
    query_no_space = query.replace(" ", "").lower()
    hints: set[str] = set()
    for key, values in MAIN_PRODUCT_HINTS.items():
        if key in query_no_space:
            hints |= {value.lower() for value in values}
    hints |= _tokens(query)
    return hints
