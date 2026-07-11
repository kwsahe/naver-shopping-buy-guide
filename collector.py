from __future__ import annotations

import html
import os
import re
from datetime import datetime
from typing import Any

import requests

import db
from product_classifier import classify_search_item

NAVER_SHOP_ENDPOINT = "https://openapi.naver.com/v1/search/shop.json"
TAG_RE = re.compile(r"<[^>]+>")
DEFAULT_HOT_QUERIES = ["무선이어폰", "노트북", "스마트워치", "아이폰", "태블릿"]


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
        raise RuntimeError("NAVER_CLIENT_ID and NAVER_CLIENT_SECRET are required")

    response = requests.get(
        NAVER_SHOP_ENDPOINT,
        params={"query": query, "display": display, "start": start, "sort": sort},
        headers={
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        },
        timeout=15,
    )
    response.raise_for_status()
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
        local_products = db.get_products(category_id)
        if not include_accessories:
            local_products = [
                product
                for product in local_products
                if product.get("product_type") in {None, "main_product"}
            ]
        return {
            "category_id": category_id,
            "query": query,
            "used_query": query,
            "product_ids": [product["id"] for product in local_products],
            "excluded_product_ids": [],
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
        "source": "naver",
    }


def collect_products_for_category(category_id: int, query: str | None = None, display: int = 20) -> list[int]:
    category = db.get_category(category_id)
    if not category:
        raise ValueError(f"category {category_id} not found")

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
    return db.get_products_by_ids(hot_product_ids)


def _enrich_search_item(
    query: str,
    used_query: str,
    item: dict[str, Any],
    rank: int,
    display: int,
) -> dict[str, Any]:
    classification = classify_search_item(query, item, rank=rank)
    hot_score = _hot_score(item, classification, rank, display)
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
    }


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
