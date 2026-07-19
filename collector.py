from __future__ import annotations

import html
import os
import re
import time
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

import db
from product_classifier import classify_search_item

NAVER_SHOP_ENDPOINT = "https://openapi.naver.com/v1/search/shop.json"
TAG_RE = re.compile(r"<[^>]+>")
DEFAULT_HOT_QUERIES = ["샴푸", "바디워시", "로션", "폼클렌징"]
COSMETIC_CATALOG_DISPLAY = 100
COSMETIC_KEYWORDS = ("샴푸", "바디워시", "로션", "폼클렌징", "폼클렌저", "화장품")
IMAGE_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
IMAGE_SRC_RE = re.compile(
    r"(?:src|data-src|data-original|data-lazy-src)=[\"']([^\"']+)",
    re.IGNORECASE,
)
IMAGE_SRCSET_RE = re.compile(r"(?:srcset|data-srcset)=[\"']([^\"']+)", re.IGNORECASE)
IMAGE_SIZE_RE = re.compile(r"(?:width|height)=[\"']?(\d+)", re.IGNORECASE)
IMAGE_WIDTH_RE = re.compile(r"\bwidth=[\"']?(\d+)", re.IGNORECASE)
IMAGE_HEIGHT_RE = re.compile(r"\bheight=[\"']?(\d+)", re.IGNORECASE)
META_TAG_RE = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
META_ATTR_RE = re.compile(r"([\w:-]+)\s*=\s*([\"'])(.*?)\2", re.IGNORECASE | re.DOTALL)
DETAIL_REDIRECT_LIMIT = 3
SHOP_REQUEST_MAX_RETRIES = 3
SHOP_REQUEST_BACKOFF_SECONDS = 0.5


def _credentials() -> tuple[str | None, str | None]:
    return os.getenv("NAVER_CLIENT_ID"), os.getenv("NAVER_CLIENT_SECRET")


def has_naver_credentials() -> bool:
    client_id, client_secret = _credentials()
    return bool(client_id and client_secret)


def check_naver_api_connection(query: str = "무선이어폰") -> dict[str, Any]:
    if not has_naver_credentials():
        return {
            "connected": False,
            "status": "missing_credentials",
            "message": "NAVER_CLIENT_ID 또는 NAVER_CLIENT_SECRET이 없습니다.",
        }
    try:
        items = search_shop(query, display=3)
        return {
            "connected": True,
            "status": "ok",
            "query": query,
            "result_count": len(items),
            "has_image": bool(items and items[0].get("image")),
            "sample_title": items[0].get("title") if items else None,
        }
    except Exception as exc:
        return {
            "connected": False,
            "status": "request_failed",
            "message": str(exc),
            "error_type": type(exc).__name__,
        }


def clean_title(value: str) -> str:
    return html.unescape(TAG_RE.sub("", value)).strip()


def search_shop(query: str, display: int = 20, start: int = 1, sort: str = "sim") -> list[dict[str, Any]]:
    client_id, client_secret = _credentials()
    if not client_id or not client_secret:
        raise RuntimeError("NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET 설정이 필요합니다.")

    request_args = {
        "params": {"query": query, "display": display, "start": start, "sort": sort},
        "headers": {
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        },
        "timeout": 15,
    }
    for attempt in range(SHOP_REQUEST_MAX_RETRIES + 1):
        try:
            response = requests.get(NAVER_SHOP_ENDPOINT, **request_args)
            if (
                response.status_code == 429 or response.status_code >= 500
            ) and attempt < SHOP_REQUEST_MAX_RETRIES:
                time.sleep(SHOP_REQUEST_BACKOFF_SECONDS * (2**attempt))
                continue
            response.raise_for_status()
            break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if attempt >= SHOP_REQUEST_MAX_RETRIES:
                raise
            time.sleep(SHOP_REQUEST_BACKOFF_SECONDS * (2**attempt))
    else:
        raise RuntimeError("네이버 쇼핑 검색 요청 재시도 횟수를 초과했습니다.")

    items = response.json().get("items", [])
    cleaned_items: list[dict[str, Any]] = []
    for item in items:
        item = dict(item)
        item["title"] = clean_title(item.get("title", ""))
        cleaned_items.append(item)
    return cleaned_items


def search_shop_with_retry(query: str, display: int = 20, sort: str = "sim") -> tuple[str, list[dict[str, Any]]]:
    search_query = query.strip()
    if not search_query:
        raise ValueError("검색어를 입력하세요.")
    items = search_shop(search_query, display=display, sort=sort)
    compact_query = search_query.replace(" ", "")
    if not items and compact_query != search_query:
        return compact_query, search_shop(compact_query, display=display, sort=sort)
    return search_query, items


def collect_products_for_search(
    query: str,
    display: int = 20,
    include_accessories: bool = False,
) -> dict[str, Any]:
    category_id = db.get_or_create_category(query)
    if not has_naver_credentials():
        all_local_products = db.get_products(category_id)
        local_products = all_local_products
        if not include_accessories:
            local_products = [
                product
                for product in local_products
                if product.get("product_type") in {None, "main_product"}
            ]
        accessory_ids = [
            product["id"] for product in all_local_products if product.get("product_type") == "accessory"
        ]
        return {
            "category_id": category_id,
            "query": query,
            "used_query": query,
            "product_ids": [product["id"] for product in local_products],
            "all_product_ids": [product["id"] for product in all_local_products],
            "excluded_product_ids": accessory_ids if not include_accessories else [],
            "excluded_count": len(accessory_ids),
            "accessory_count": len(accessory_ids),
            "source": "local",
        }

    used_query, items = search_shop_with_retry(query, display=display)
    product_ids: list[int] = []
    excluded_product_ids: list[int] = []
    for rank, item in enumerate(items, start=1):
        if not item.get("productId") or not item.get("lprice"):
            continue
        item.update(_enrich_search_item(query, used_query, item, rank, display))
        product_ids.append(db.upsert_product_from_naver(category_id, item))
        if item["product_type"] != "main_product":
            excluded_product_ids.append(product_ids[-1])
    visible_product_ids = product_ids if include_accessories else [
        product_id for product_id in product_ids if product_id not in set(excluded_product_ids)
    ]
    return {
        "category_id": category_id,
        "query": query,
        "used_query": used_query,
        "product_ids": visible_product_ids,
        "all_product_ids": product_ids,
        "excluded_product_ids": excluded_product_ids,
        "excluded_count": len(excluded_product_ids),
        "accessory_count": len(excluded_product_ids),
        "source": "naver",
    }


def collect_products_for_category(category_id: int, query: str | None = None, display: int = 20) -> list[int]:
    category = db.get_category(category_id)
    if not category:
        raise ValueError(f"category {category_id}를 찾을 수 없습니다.")

    if not has_naver_credentials():
        return [product["id"] for product in db.get_products(category_id)]

    collected_ids: list[int] = []
    _, items = search_shop_with_retry(query or category["name"], display=display)

    for rank, item in enumerate(items, start=1):
        if not item.get("productId") or not item.get("lprice"):
            continue
        item.update(_enrich_search_item(query or category["name"], query or category["name"], item, rank, display))
        product_id = db.upsert_product_from_naver(category_id, item)
        if item["product_type"] == "main_product":
            collected_ids.append(product_id)
    return collected_ids


def collect_prices_for_all_products() -> list[dict[str, Any]]:
    if not has_naver_credentials():
        return _collect_demo_prices()

    collected: list[dict[str, Any]] = []
    for product in db.get_products():
        matches = search_shop(product["name"], display=10)
        match = next(
            (
                item
                for item in matches
                if str(item.get("productId")) == str(product.get("naver_product_id"))
            ),
            matches[0] if matches else None,
        )
        if not match or not match.get("lprice"):
            continue
        match.update(
            _enrich_search_item(
                product.get("search_query") or product["name"],
                product.get("search_query") or product["name"],
                match,
                int(product.get("search_rank") or 10),
                10,
            )
        )
        price = int(match["lprice"])
        db.update_product_metadata_from_naver(product["id"], match)
        db.add_price(product["id"], price)
        collected.append(
            {
                "product_id": product["id"],
                "price": price,
                "image_url": match.get("image"),
                "description": db.build_product_description(match),
                "source": "naver",
            }
        )
    return collected


def collect_hot_products(
    queries: list[str] | None = None,
    display_per_query: int = 10,
) -> list[dict[str, Any]]:
    if not has_naver_credentials():
        return db.list_hot_products(limit=8)

    hot_product_ids: list[int] = []
    for query in queries or DEFAULT_HOT_QUERIES:
        category_id = db.get_or_create_category(query)
        used_query, items = search_shop_with_retry(query, display=display_per_query)
        for rank, item in enumerate(items, start=1):
            if not item.get("productId") or not item.get("lprice"):
                continue
            item.update(_enrich_search_item(query, used_query, item, rank, display_per_query))
            product_id = db.upsert_product_from_naver(category_id, item)
            if item["product_type"] == "main_product":
                hot_product_ids.append(product_id)
    # 한 상품이 여러 검색어에 노출되더라도 재수집 건수에는 한 번만 반영합니다.
    unique_product_ids = list(dict.fromkeys(hot_product_ids))
    return db.get_products_by_ids(unique_product_ids)


def collect_cosmetic_catalog(
    queries: list[str] | None = None,
    display_per_query: int = COSMETIC_CATALOG_DISPLAY,
) -> list[dict[str, Any]]:
    """주요 화장품 카테고리를 넓은 범위로 다시 수집해 기존 상품을 갱신합니다."""
    if not 1 <= display_per_query <= 100:
        raise ValueError("카테고리별 수집 개수는 1 이상 100 이하여야 합니다.")
    return collect_hot_products(
        queries=queries or DEFAULT_HOT_QUERIES,
        display_per_query=display_per_query,
    )


def _enrich_search_item(
    query: str,
    used_query: str,
    item: dict[str, Any],
    rank: int,
    display: int,
) -> dict[str, Any]:
    classification = classify_search_item(query, item, rank=rank)
    hot_score = _hot_score(item, classification, rank, display)
    promo_image = None
    detail_description = None
    if _is_cosmetic_query(query):
        promo_image, detail_description = _extract_product_detail(item.get("link"))
    return {
        **classification,
        "search_query": used_query,
        "search_rank": rank,
        "hot_score": hot_score,
        "hot_reason": (
            f"검색 순위 {rank}위, 본품 분류 점수 {classification['classification_score']}점, "
            "이미지/가격 메타데이터를 반영한 공식 API 기반 핫스코어입니다."
        ),
        "hot_updated_at": datetime.now().isoformat(timespec="seconds"),
        "promo_image": promo_image or item.get("image"),
        "detail_description": detail_description,
    }


def _is_cosmetic_query(query: str) -> bool:
    normalized = query.replace(" ", "").lower()
    return any(keyword in normalized for keyword in COSMETIC_KEYWORDS)


def _extract_promo_image(product_url: str | None) -> str | None:
    """네이버 상품 상세 HTML에서 충분히 큰 홍보 이미지를 안전하게 추출합니다."""
    promo_image, _ = _extract_product_detail(product_url)
    return promo_image


def _extract_product_detail(product_url: str | None) -> tuple[str | None, str | None]:
    """네이버 상세 페이지에서 대표 홍보 이미지와 설명 메타데이터를 추출합니다."""
    if not product_url:
        return None, None
    if not _is_allowed_naver_url(product_url):
        return None, None
    try:
        response = _get_naver_detail_response(product_url)
        response.raise_for_status()
    except requests.RequestException:
        return None, None

    metadata: dict[str, str] = {}
    for tag in META_TAG_RE.findall(response.text):
        attributes = {
            key.lower(): html.unescape(value).strip()
            for key, _, value in META_ATTR_RE.findall(tag)
        }
        key = (attributes.get("property") or attributes.get("name") or "").lower()
        content = attributes.get("content")
        if key and content:
            metadata[key] = content

    fallback_image = None
    for key in ("og:image", "twitter:image", "twitter:image:src"):
        candidate = urljoin(product_url, metadata.get(key, ""))
        if candidate.startswith("https://"):
            fallback_image = candidate
            break

    detail_description = metadata.get("og:description") or metadata.get("description")
    if detail_description:
        detail_description = clean_title(detail_description)[:1000] or None

    candidates: list[tuple[int, str]] = []
    for tag in IMAGE_TAG_RE.findall(response.text):
        sizes = [int(value) for value in IMAGE_SIZE_RE.findall(tag)]
        if sizes and min(sizes) < 300:
            continue
        width_match = IMAGE_WIDTH_RE.search(tag)
        height_match = IMAGE_HEIGHT_RE.search(tag)
        width = int(width_match.group(1)) if width_match else 0
        height = int(height_match.group(1)) if height_match else 0
        match = IMAGE_SRC_RE.search(tag)
        if match:
            candidate = urljoin(product_url, html.unescape(match.group(1)))
            candidates.append((_detail_image_score(candidate, width, height), candidate))
        srcset_match = IMAGE_SRCSET_RE.search(tag)
        if srcset_match:
            srcset = html.unescape(srcset_match.group(1))
            for source in srcset.split(","):
                if not source.strip():
                    continue
                candidate = urljoin(product_url, source.strip().split()[0])
                candidates.append((_detail_image_score(candidate, width, height), candidate))
    useful_candidates = [item for item in candidates if _is_useful_detail_image(item[1])]
    fallback_candidate = (1 if fallback_image else -1, fallback_image)
    promo_image = max([*useful_candidates, fallback_candidate], key=lambda item: item[0])[1]
    return promo_image, detail_description


def _detail_image_score(url: str, width: int, height: int) -> int:
    """상품 설명·프로모션에 가까운 큰 이미지를 대표 홍보 이미지로 우선합니다."""
    normalized = url.lower()
    score = min(max(width, height), 4000)
    if width >= 600:
        score += 600
    if height >= 600:
        score += 600
    if height > width > 0:
        score += 500
    if any(marker in normalized for marker in ("detail", "description", "content", "promo")):
        score += 2000
    return score


def _is_useful_detail_image(url: str) -> bool:
    """배송 안내·아이콘처럼 제품 홍보와 무관한 이미지를 후보에서 제외합니다."""
    if not url.startswith("https://"):
        return False
    normalized = url.lower()
    excluded_markers = ("delivery", "shipping", "notice", "icon", "sprite", "spacer")
    return not any(marker in normalized for marker in excluded_markers)


def _get_naver_detail_response(product_url: str) -> requests.Response:
    """허용된 네이버 주소만 직접 따라가 외부 리다이렉트 요청을 차단합니다."""
    current_url = product_url
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ShoppingGuideBot/1.0)"}
    for redirect_count in range(DETAIL_REDIRECT_LIMIT + 1):
        response = requests.get(current_url, headers=headers, timeout=8, allow_redirects=False)
        if not response.is_redirect:
            return response
        if redirect_count == DETAIL_REDIRECT_LIMIT:
            raise requests.exceptions.TooManyRedirects("상품 상세 페이지의 리다이렉트가 너무 많습니다.")
        location = response.headers.get("Location")
        next_url = urljoin(current_url, location or "")
        if not location or not _is_allowed_naver_url(next_url):
            raise requests.exceptions.InvalidURL("네이버 외부 주소로의 리다이렉트는 허용되지 않습니다.")
        current_url = next_url
    raise requests.exceptions.TooManyRedirects("상품 상세 페이지의 리다이렉트가 너무 많습니다.")


def _is_allowed_naver_url(url: str) -> bool:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (hostname == "naver.com" or hostname.endswith(".naver.com"))


def _hot_score(
    item: dict[str, Any],
    classification: dict[str, Any],
    rank: int,
    display: int,
) -> float:
    rank_score = max(0.0, (display - rank + 1) / max(display, 1) * 60)
    classification_score = float(classification["classification_score"]) * 0.25
    metadata_score = 0
    if item.get("image"):
        metadata_score += 8
    if item.get("lprice"):
        metadata_score += 7
    if item.get("mallName"):
        metadata_score += 5
    accessory_penalty = 25 if classification["product_type"] != "main_product" else 0
    score = rank_score + classification_score + metadata_score - accessory_penalty
    return round(max(0.0, min(100.0, score)), 2)


def _collect_demo_prices() -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    today_factor = (datetime.now().toordinal() % 9) - 4
    for product in db.get_products():
        latest_price = int(product.get("latest_price") or 0)
        if latest_price <= 0:
            continue
        product_factor = (int(product["id"]) % 5) - 2
        next_price = max(1000, latest_price + (today_factor + product_factor) * 180)
        db.add_price(product["id"], next_price)
        collected.append({"product_id": product["id"], "price": next_price, "source": "demo"})
    return collected


if __name__ == "__main__":
    db.init_db(seed=True)
    collected_prices = collect_prices_for_all_products()
    print(f"Collected {len(collected_prices)} prices")
