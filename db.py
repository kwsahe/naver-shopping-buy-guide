from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is present in normal installs
    load_dotenv = None

if load_dotenv:
    load_dotenv()

DEFAULT_DB_PATH = Path("data/app.db")
SPEC_DIR = Path("data/specs")


def get_db_path() -> Path:
    return Path(os.getenv("DB_PATH", str(DEFAULT_DB_PATH)))


def _ensure_db_parent() -> None:
    get_db_path().parent.mkdir(parents=True, exist_ok=True)


def connect_db(readonly: bool = False) -> sqlite3.Connection:
    db_path = get_db_path()
    if readonly:
        uri_path = db_path.resolve().as_posix()
        conn = sqlite3.connect(f"file:{uri_path}?mode=ro", uri=True)
    else:
        _ensure_db_parent()
        conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    naver_category_code TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER REFERENCES categories(id),
    naver_product_id TEXT UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    brand TEXT,
    maker TEXT,
    mall_name TEXT,
    link TEXT,
    image_url TEXT,
    promo_image TEXT,
    product_type TEXT DEFAULT 'main_product',
    classification_score REAL,
    classification_reason TEXT,
    search_query TEXT,
    search_rank INTEGER,
    hot_score REAL,
    hot_reason TEXT,
    hot_updated_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS specs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER REFERENCES products(id),
    spec_key TEXT NOT NULL,
    spec_value TEXT NOT NULL,
    source TEXT,
    curated_at TEXT,
    UNIQUE(product_id, spec_key)
);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER REFERENCES products(id),
    price INTEGER NOT NULL,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS product_collection_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    search_query TEXT NOT NULL,
    sort_mode TEXT NOT NULL,
    search_rank INTEGER NOT NULL,
    price_segment TEXT NOT NULL,
    popularity_score REAL,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product_id, search_query, sort_mode)
);

CREATE TABLE IF NOT EXISTS product_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    external_review_id TEXT NOT NULL,
    author TEXT,
    rating REAL,
    content TEXT NOT NULL,
    source_url TEXT,
    source_kind TEXT NOT NULL DEFAULT 'structured_product_page',
    reviewed_at TEXT,
    collected_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product_id, external_review_id)
);

CREATE TABLE IF NOT EXISTS comparison_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER REFERENCES categories(id),
    product_ids TEXT,
    user_priority TEXT,
    llm_model TEXT,
    report_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS price_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER REFERENCES products(id),
    target_price INTEGER NOT NULL,
    triggered INTEGER DEFAULT 0,
    triggered_at TEXT,
    cancelled INTEGER DEFAULT 0,
    cancelled_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alert_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id INTEGER REFERENCES price_alerts(id),
    product_id INTEGER REFERENCES products(id),
    target_price INTEGER NOT NULL,
    actual_price INTEGER NOT NULL,
    message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS category_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER REFERENCES categories(id) UNIQUE,
    best_value_product_id INTEGER REFERENCES products(id),
    best_value_score REAL,
    best_value_reason TEXT,
    best_performance_product_id INTEGER REFERENCES products(id),
    best_performance_score REAL,
    best_performance_reason TEXT,
    llm_model TEXT,
    generated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type TEXT NOT NULL,
    status TEXT NOT NULL,
    items_processed INTEGER,
    error_message TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    is_helpful INTEGER NOT NULL,
    comment TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def init_db(seed: bool = True) -> None:
    with connect_db() as conn:
        conn.executescript(SCHEMA_SQL)
        _migrate_db(conn)
    if seed:
        seed_demo_data()


def _migrate_db(conn: sqlite3.Connection) -> None:
    product_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(products)").fetchall()
    }
    if "description" not in product_columns:
        conn.execute("ALTER TABLE products ADD COLUMN description TEXT")
    product_migrations = {
        "product_type": "ALTER TABLE products ADD COLUMN product_type TEXT DEFAULT 'main_product'",
        "classification_score": "ALTER TABLE products ADD COLUMN classification_score REAL",
        "classification_reason": "ALTER TABLE products ADD COLUMN classification_reason TEXT",
        "search_query": "ALTER TABLE products ADD COLUMN search_query TEXT",
        "search_rank": "ALTER TABLE products ADD COLUMN search_rank INTEGER",
        "hot_score": "ALTER TABLE products ADD COLUMN hot_score REAL",
        "hot_reason": "ALTER TABLE products ADD COLUMN hot_reason TEXT",
        "hot_updated_at": "ALTER TABLE products ADD COLUMN hot_updated_at TEXT",
        "promo_image": "ALTER TABLE products ADD COLUMN promo_image TEXT",
    }
    for column, sql in product_migrations.items():
        if column not in product_columns:
            conn.execute(sql)
    alert_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(price_alerts)").fetchall()
    }
    if "triggered_at" not in alert_columns:
        conn.execute("ALTER TABLE price_alerts ADD COLUMN triggered_at TEXT")
    if "cancelled" not in alert_columns:
        conn.execute("ALTER TABLE price_alerts ADD COLUMN cancelled INTEGER DEFAULT 0")
    if "cancelled_at" not in alert_columns:
        conn.execute("ALTER TABLE price_alerts ADD COLUMN cancelled_at TEXT")
    review_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(product_reviews)").fetchall()
    }
    if "source_kind" not in review_columns:
        conn.execute(
            "ALTER TABLE product_reviews "
            "ADD COLUMN source_kind TEXT NOT NULL DEFAULT 'structured_product_page'"
        )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [row_to_dict(row) or {} for row in rows]


def load_spec_files(spec_dir: Path = SPEC_DIR) -> list[dict[str, Any]]:
    if not spec_dir.exists():
        return []
    specs: list[dict[str, Any]] = []
    for path in sorted(spec_dir.glob("*.json")):
        specs.append(json.loads(path.read_text(encoding="utf-8")))
    return specs


def _encode_spec_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def seed_demo_data() -> None:
    spec_files = load_spec_files()
    if not spec_files:
        return

    with connect_db() as conn:
        for category_spec in spec_files:
            category_name = category_spec["category"]
            category_id = conn.execute(
                """
                INSERT INTO categories (name)
                VALUES (?)
                ON CONFLICT(name) DO UPDATE SET name = excluded.name
                RETURNING id
                """,
                (category_name,),
            ).fetchone()["id"]

            score_keys = set(category_spec.get("score_weights", {}).keys())
            for product in category_spec.get("products", []):
                product_id = conn.execute(
                    """
                    INSERT INTO products (
                        category_id, naver_product_id, name, description, brand, maker,
                        mall_name, link, image_url, product_type, classification_score,
                        classification_reason, search_query, search_rank, hot_score, hot_reason,
                        hot_updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(naver_product_id) DO UPDATE SET
                        category_id = excluded.category_id,
                        name = excluded.name,
                        description = excluded.description,
                        brand = excluded.brand,
                        maker = excluded.maker,
                        mall_name = excluded.mall_name,
                        link = excluded.link,
                        image_url = excluded.image_url,
                        product_type = excluded.product_type,
                        classification_score = excluded.classification_score,
                        classification_reason = excluded.classification_reason,
                        search_query = excluded.search_query,
                        search_rank = excluded.search_rank,
                        hot_score = excluded.hot_score,
                        hot_reason = excluded.hot_reason,
                        hot_updated_at = excluded.hot_updated_at
                    RETURNING id
                    """,
                    (
                        category_id,
                        product["product_id"],
                        product["name"],
                        product.get("description") or build_product_description(product),
                        product.get("brand"),
                        product.get("maker"),
                        product.get("mall_name"),
                        product.get("link"),
                        product.get("image_url", ""),
                        product.get("product_type", "main_product"),
                        product.get("classification_score", 100),
                        product.get("classification_reason", "수동 큐레이션 본품 데이터"),
                        product.get("search_query") or category_name,
                        product.get("search_rank"),
                        product.get("hot_score"),
                        product.get("hot_reason"),
                        product.get("hot_updated_at"),
                    ),
                ).fetchone()["id"]

                for key in score_keys:
                    if key not in product:
                        continue
                    conn.execute(
                        """
                        INSERT INTO specs (product_id, spec_key, spec_value, source, curated_at)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(product_id, spec_key) DO UPDATE SET
                            spec_value = excluded.spec_value,
                            source = excluded.source,
                            curated_at = excluded.curated_at
                        """,
                        (
                            product_id,
                            key,
                            _encode_spec_value(product[key]),
                            product.get("source"),
                            product.get("curated_at"),
                        ),
                    )

                price_count = conn.execute(
                    "SELECT COUNT(*) AS count FROM price_history WHERE product_id = ?",
                    (product_id,),
                ).fetchone()["count"]
                if price_count == 0:
                    _insert_demo_price_history(conn, product_id, int(product["base_price"]))


def _insert_demo_price_history(conn: sqlite3.Connection, product_id: int, base_price: int) -> None:
    now = datetime.now()
    for days_ago in range(44, -1, -1):
        drift = (days_ago - 22) * 90
        weekly_wave = ((days_ago % 7) - 3) * 550
        price = max(1000, int(base_price + drift + weekly_wave))
        collected_at = (now - timedelta(days=days_ago)).isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO price_history (product_id, price, collected_at) VALUES (?, ?, ?)",
            (product_id, price, collected_at),
        )


def get_counts() -> dict[str, int]:
    with connect_db() as conn:
        return {
            "categories": conn.execute("SELECT COUNT(*) AS count FROM categories").fetchone()["count"],
            "products": conn.execute("SELECT COUNT(*) AS count FROM products").fetchone()["count"],
            "reports": conn.execute("SELECT COUNT(*) AS count FROM comparison_reports").fetchone()[
                "count"
            ],
            "pipeline_runs": conn.execute("SELECT COUNT(*) AS count FROM pipeline_runs").fetchone()[
                "count"
            ],
        }


def get_categories() -> list[dict[str, Any]]:
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT c.*,
                   COUNT(p.id) AS product_count
            FROM categories c
            LEFT JOIN products p ON p.category_id = c.id
            GROUP BY c.id
            ORDER BY c.name
            """
        ).fetchall()
        return rows_to_dicts(rows)


def get_category(category_id: int) -> dict[str, Any] | None:
    with connect_db() as conn:
        return row_to_dict(
            conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
        )


def get_category_by_name(name: str) -> dict[str, Any] | None:
    with connect_db() as conn:
        return row_to_dict(conn.execute("SELECT * FROM categories WHERE name = ?", (name,)).fetchone())


def get_or_create_category(name: str, naver_category_code: str | None = None) -> int:
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("category 이름이 필요합니다.")
    with connect_db() as conn:
        row = conn.execute(
            """
            INSERT INTO categories (name, naver_category_code)
            VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET
                naver_category_code = COALESCE(excluded.naver_category_code, categories.naver_category_code)
            RETURNING id
            """,
            (normalized_name, naver_category_code),
        ).fetchone()
        return int(row["id"])


def get_products(category_id: int | None = None) -> list[dict[str, Any]]:
    params: tuple[Any, ...] = ()
    where = ""
    if category_id is not None:
        where = "WHERE p.category_id = ?"
        params = (category_id,)

    with connect_db() as conn:
        rows = conn.execute(
            f"""
            SELECT p.*,
                   c.name AS category_name,
                   (
                       SELECT ph.price
                       FROM price_history ph
                       WHERE ph.product_id = p.id
                       ORDER BY ph.collected_at DESC, ph.id DESC
                       LIMIT 1
                   ) AS latest_price
            FROM products p
            JOIN categories c ON c.id = p.category_id
            {where}
            ORDER BY latest_price ASC, p.name
            """,
            params,
        ).fetchall()
        return rows_to_dicts(rows)


def get_products_by_ids(product_ids: list[int]) -> list[dict[str, Any]]:
    if not product_ids:
        return []
    placeholders = ",".join("?" for _ in product_ids)
    order_case = " ".join(f"WHEN {product_id} THEN {index}" for index, product_id in enumerate(product_ids))
    with connect_db() as conn:
        rows = conn.execute(
            f"""
            SELECT p.*,
                   c.name AS category_name,
                   (
                       SELECT ph.price
                       FROM price_history ph
                       WHERE ph.product_id = p.id
                       ORDER BY ph.collected_at DESC, ph.id DESC
                       LIMIT 1
                   ) AS latest_price
            FROM products p
            JOIN categories c ON c.id = p.category_id
            WHERE p.id IN ({placeholders})
            ORDER BY CASE p.id {order_case} END
            """,
            tuple(product_ids),
        ).fetchall()
        return rows_to_dicts(rows)


def list_hot_products(limit: int = 8) -> list[dict[str, Any]]:
    today_prefix = datetime.now().date().isoformat()
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT p.*,
                   c.name AS category_name,
                   (
                       SELECT ph.price
                       FROM price_history ph
                       WHERE ph.product_id = p.id
                       ORDER BY ph.collected_at DESC, ph.id DESC
                       LIMIT 1
                   ) AS latest_price
            FROM products p
            JOIN categories c ON c.id = p.category_id
            WHERE COALESCE(p.product_type, 'main_product') = 'main_product'
              AND p.hot_score IS NOT NULL
              AND p.hot_updated_at LIKE ?
            ORDER BY p.hot_score DESC, p.search_rank ASC, p.id DESC
            LIMIT ?
            """,
            (f"{today_prefix}%", limit),
        ).fetchall()
        hot_products = rows_to_dicts(rows)
        if hot_products:
            return hot_products
        fallback_rows = conn.execute(
            """
            SELECT p.*,
                   c.name AS category_name,
                   (
                       SELECT ph.price
                       FROM price_history ph
                       WHERE ph.product_id = p.id
                       ORDER BY ph.collected_at DESC, ph.id DESC
                       LIMIT 1
                   ) AS latest_price
            FROM products p
            JOIN categories c ON c.id = p.category_id
            WHERE COALESCE(p.product_type, 'main_product') = 'main_product'
            ORDER BY COALESCE(p.hot_score, 0) DESC, p.created_at DESC, p.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return rows_to_dicts(fallback_rows)


def hot_product_queries_today() -> list[str]:
    today_prefix = datetime.now().date().isoformat()
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT search_query
            FROM products
            WHERE COALESCE(product_type, 'main_product') = 'main_product'
              AND hot_score IS NOT NULL
              AND hot_updated_at LIKE ?
              AND search_query IS NOT NULL
            ORDER BY search_query
            """,
            (f"{today_prefix}%",),
        ).fetchall()
        return [row["search_query"] for row in rows]


def get_product(product_id: int) -> dict[str, Any] | None:
    with connect_db() as conn:
        row = conn.execute(
            """
            SELECT p.*,
                   c.name AS category_name,
                   (
                       SELECT ph.price
                       FROM price_history ph
                       WHERE ph.product_id = p.id
                       ORDER BY ph.collected_at DESC, ph.id DESC
                       LIMIT 1
                   ) AS latest_price
            FROM products p
            JOIN categories c ON c.id = p.category_id
            WHERE p.id = ?
            """,
            (product_id,),
        ).fetchone()
        return row_to_dict(row)


def get_specs_map(product_id: int) -> dict[str, Any]:
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT spec_key, spec_value FROM specs WHERE product_id = ?",
            (product_id,),
        ).fetchall()
    return {row["spec_key"]: parse_spec_value(row["spec_value"]) for row in rows}


def parse_spec_value(value: str) -> Any:
    lower = value.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def get_product_with_specs(product_id: int) -> dict[str, Any] | None:
    product = get_product(product_id)
    if not product:
        return None
    product.update(get_specs_map(product_id))
    return product


def get_price_history(product_id: int, days: int = 90) -> list[dict[str, Any]]:
    threshold = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT id, product_id, price, collected_at
            FROM price_history
            WHERE product_id = ? AND collected_at >= ?
            ORDER BY collected_at ASC, id ASC
            """,
            (product_id, threshold),
        ).fetchall()
        return rows_to_dicts(rows)


def add_price(product_id: int, price: int, collected_at: str | None = None) -> None:
    with connect_db() as conn:
        conn.execute(
            "INSERT INTO price_history (product_id, price, collected_at) VALUES (?, ?, ?)",
            (product_id, int(price), collected_at or datetime.now().isoformat(timespec="seconds")),
        )


def upsert_collection_evidence(
    product_id: int,
    search_query: str,
    sort_mode: str,
    search_rank: int,
    price_segment: str,
    popularity_score: float | None,
) -> None:
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO product_collection_evidence (
                product_id, search_query, sort_mode, search_rank, price_segment,
                popularity_score, collected_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(product_id, search_query, sort_mode) DO UPDATE SET
                search_rank = excluded.search_rank,
                price_segment = excluded.price_segment,
                popularity_score = excluded.popularity_score,
                collected_at = excluded.collected_at
            """,
            (
                product_id,
                search_query,
                sort_mode,
                int(search_rank),
                price_segment,
                popularity_score,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )


def upsert_product_reviews(product_id: int, reviews: list[dict[str, Any]]) -> int:
    if not reviews:
        return 0
    with connect_db() as conn:
        before = conn.total_changes
        for review in reviews:
            conn.execute(
                """
                INSERT INTO product_reviews (
                    product_id, external_review_id, author, rating, content,
                    source_url, source_kind, reviewed_at, collected_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_id, external_review_id) DO UPDATE SET
                    author = excluded.author,
                    rating = excluded.rating,
                    content = excluded.content,
                    source_url = excluded.source_url,
                    source_kind = excluded.source_kind,
                    reviewed_at = excluded.reviewed_at,
                    collected_at = excluded.collected_at
                """,
                (
                    product_id,
                    review["external_review_id"],
                    review.get("author"),
                    review.get("rating"),
                    review["content"],
                    review.get("source_url"),
                    review.get("source_kind", "structured_product_page"),
                    review.get("reviewed_at"),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
        return conn.total_changes - before


def list_product_reviews(product_id: int, limit: int = 10) -> list[dict[str, Any]]:
    if not isinstance(product_id, int) or isinstance(product_id, bool) or product_id < 1:
        raise ValueError("product_id는 1 이상의 정수여야 합니다.")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ValueError("limit는 1 이상 100 이하의 정수여야 합니다.")

    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT author, rating, content, source_url, source_kind, reviewed_at
            FROM product_reviews
            WHERE product_id = ?
            ORDER BY
                CASE WHEN reviewed_at IS NULL OR reviewed_at = '' THEN 1 ELSE 0 END,
                reviewed_at DESC,
                collected_at DESC,
                id DESC
            LIMIT ?
            """,
            (product_id, limit),
        ).fetchall()
        return rows_to_dicts(rows)


def get_collection_summary(product_ids: list[int] | None = None) -> dict[str, Any]:
    if product_ids == []:
        return {"price_segments": {}, "category_counts": {}, "review_count": 0}
    where = ""
    params: tuple[Any, ...] = ()
    if product_ids is not None:
        placeholders = ",".join("?" for _ in product_ids)
        where = f"WHERE product_id IN ({placeholders})"
        params = tuple(product_ids)
    with connect_db() as conn:
        evidence_rows = conn.execute(
            f"""
            SELECT price_segment, COUNT(DISTINCT product_id) AS product_count
            FROM product_collection_evidence
            {where}
            GROUP BY price_segment
            """,
            params,
        ).fetchall()
        review_count = conn.execute(
            f"SELECT COUNT(*) AS count FROM product_reviews {where}",
            params,
        ).fetchone()["count"]
        category_rows = conn.execute(
            f"""
            SELECT categories.name, COUNT(DISTINCT products.id) AS product_count
            FROM products
            JOIN categories ON categories.id = products.category_id
            {"WHERE products.id IN (" + ",".join("?" for _ in product_ids) + ")" if product_ids else ""}
            GROUP BY categories.id, categories.name
            """,
            params,
        ).fetchall()
    return {
        "price_segments": {
            row["price_segment"]: row["product_count"] for row in evidence_rows
        },
        "category_counts": {
            row["name"]: row["product_count"] for row in category_rows
        },
        "review_count": int(review_count),
    }


def upsert_product_from_naver(category_id: int, item: dict[str, Any]) -> int:
    with connect_db() as conn:
        row = conn.execute(
            """
            INSERT INTO products (
                category_id, naver_product_id, name, description, brand, maker,
                mall_name, link, image_url, product_type, classification_score,
                classification_reason, search_query, search_rank, hot_score, hot_reason,
                hot_updated_at, promo_image
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(naver_product_id) DO UPDATE SET
                category_id = excluded.category_id,
                name = excluded.name,
                description = excluded.description,
                brand = excluded.brand,
                maker = excluded.maker,
                mall_name = excluded.mall_name,
                link = excluded.link,
                image_url = excluded.image_url,
                product_type = excluded.product_type,
                classification_score = excluded.classification_score,
                classification_reason = excluded.classification_reason,
                search_query = excluded.search_query,
                search_rank = excluded.search_rank,
                hot_score = excluded.hot_score,
                hot_reason = excluded.hot_reason,
                hot_updated_at = excluded.hot_updated_at,
                promo_image = COALESCE(excluded.promo_image, products.promo_image)
            RETURNING id
            """,
            (
                category_id,
                item["productId"],
                item["title"],
                build_product_description(item),
                item.get("brand"),
                item.get("maker"),
                item.get("mallName"),
                item.get("link"),
                item.get("image"),
                item.get("product_type", "main_product"),
                item.get("classification_score"),
                item.get("classification_reason"),
                item.get("search_query"),
                item.get("search_rank"),
                item.get("hot_score"),
                item.get("hot_reason"),
                item.get("hot_updated_at"),
                item.get("promo_image"),
            ),
        ).fetchone()
        product_id = int(row["id"])
        try:
            price = int(item.get("lprice") or 0)
        except (TypeError, ValueError):
            price = 0
        if price > 0:
            conn.execute(
                "INSERT INTO price_history (product_id, price) VALUES (?, ?)",
                (product_id, price),
            )
    upsert_product_reviews(product_id, item.get("reviews") or [])
    return product_id


def update_product_metadata_from_naver(product_id: int, item: dict[str, Any]) -> None:
    with connect_db() as conn:
        conn.execute(
            """
            UPDATE products
            SET name = ?,
                description = ?,
                brand = ?,
                maker = ?,
                mall_name = ?,
                link = ?,
                image_url = ?,
                product_type = COALESCE(?, product_type),
                classification_score = COALESCE(?, classification_score),
                classification_reason = COALESCE(?, classification_reason),
                search_query = COALESCE(?, search_query),
                search_rank = COALESCE(?, search_rank),
                hot_score = COALESCE(?, hot_score),
                hot_reason = COALESCE(?, hot_reason),
                hot_updated_at = COALESCE(?, hot_updated_at),
                promo_image = COALESCE(?, promo_image)
            WHERE id = ?
            """,
            (
                item.get("title"),
                build_product_description(item),
                item.get("brand"),
                item.get("maker"),
                item.get("mallName"),
                item.get("link"),
                item.get("image"),
                item.get("product_type"),
                item.get("classification_score"),
                item.get("classification_reason"),
                item.get("search_query"),
                item.get("search_rank"),
                item.get("hot_score"),
                item.get("hot_reason"),
                item.get("hot_updated_at"),
                item.get("promo_image"),
                product_id,
            ),
        )


def build_product_description(source: dict[str, Any]) -> str:
    name = source.get("title") or source.get("name") or "상품명 확인 불가"
    brand = source.get("brand") or source.get("maker") or "브랜드 확인 불가"
    mall = source.get("mallName") or source.get("mall_name") or "판매처 확인 불가"
    price = source.get("lprice") or source.get("base_price")
    category_parts = [
        source.get("category1"),
        source.get("category2"),
        source.get("category3"),
        source.get("category4"),
    ]
    category_path = " > ".join(str(part) for part in category_parts if part)
    fragments = [f"{name}은(는) {brand}의 상품입니다.", f"판매처: {mall}."]
    detail_description = str(source.get("detail_description") or "").strip()
    if detail_description:
        fragments.append(f"상품 상세정보: {detail_description}")
    if price:
        fragments.append(f"수집 최저가는 {int(price):,}원입니다.")
    if category_path:
        fragments.append(f"네이버쇼핑 분류: {category_path}.")
    if source.get("source"):
        fragments.append(f"스펙 출처: {source['source']}.")
    return " ".join(fragments)


def create_comparison_report(
    category_id: int,
    product_ids: list[int],
    user_priority: str | None,
    llm_model: str,
    report: dict[str, Any],
) -> int:
    with connect_db() as conn:
        row = conn.execute(
            """
            INSERT INTO comparison_reports (
                category_id, product_ids, user_priority, llm_model, report_json
            )
            VALUES (?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                category_id,
                json.dumps(product_ids, ensure_ascii=False),
                user_priority,
                llm_model,
                json.dumps(report, ensure_ascii=False),
            ),
        ).fetchone()
        return int(row["id"])


def get_comparison_report(report_id: int) -> dict[str, Any] | None:
    with connect_db() as conn:
        row = conn.execute(
            """
            SELECT cr.*, c.name AS category_name
            FROM comparison_reports cr
            JOIN categories c ON c.id = cr.category_id
            WHERE cr.id = ?
            """,
            (report_id,),
        ).fetchone()
    report = row_to_dict(row)
    if report:
        report["product_ids"] = json.loads(report["product_ids"] or "[]")
        report["report_json"] = json.loads(report["report_json"] or "{}")
    return report


def upsert_category_recommendation(
    category_id: int,
    best_value_product_id: int,
    best_value_score: float,
    best_value_reason: str,
    best_performance_product_id: int,
    best_performance_score: float,
    best_performance_reason: str,
    llm_model: str,
) -> int:
    with connect_db() as conn:
        row = conn.execute(
            """
            INSERT INTO category_recommendations (
                category_id,
                best_value_product_id,
                best_value_score,
                best_value_reason,
                best_performance_product_id,
                best_performance_score,
                best_performance_reason,
                llm_model,
                generated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(category_id) DO UPDATE SET
                best_value_product_id = excluded.best_value_product_id,
                best_value_score = excluded.best_value_score,
                best_value_reason = excluded.best_value_reason,
                best_performance_product_id = excluded.best_performance_product_id,
                best_performance_score = excluded.best_performance_score,
                best_performance_reason = excluded.best_performance_reason,
                llm_model = excluded.llm_model,
                generated_at = excluded.generated_at
            RETURNING id
            """,
            (
                category_id,
                best_value_product_id,
                float(best_value_score),
                best_value_reason,
                best_performance_product_id,
                float(best_performance_score),
                best_performance_reason,
                llm_model,
                datetime.now().isoformat(timespec="seconds"),
            ),
        ).fetchone()
        return int(row["id"])


def get_category_recommendation(category_id: int) -> dict[str, Any] | None:
    with connect_db() as conn:
        row = conn.execute(
            """
            SELECT r.*,
                   bv.name AS best_value_name,
                   bv.image_url AS best_value_image_url,
                   bp.name AS best_performance_name,
                   bp.image_url AS best_performance_image_url
            FROM category_recommendations r
            LEFT JOIN products bv ON bv.id = r.best_value_product_id
            LEFT JOIN products bp ON bp.id = r.best_performance_product_id
            WHERE r.category_id = ?
            """,
            (category_id,),
        ).fetchone()
        return row_to_dict(row)


def create_alert(product_id: int, target_price: int) -> int:
    with connect_db() as conn:
        row = conn.execute(
            """
            INSERT INTO price_alerts (product_id, target_price)
            VALUES (?, ?)
            RETURNING id
            """,
            (product_id, target_price),
        ).fetchone()
        return int(row["id"])


def mark_alert_triggered(alert_id: int, actual_price: int | None = None) -> None:
    with connect_db() as conn:
        alert = conn.execute(
            """
            SELECT a.*, p.name AS product_name
            FROM price_alerts a
            JOIN products p ON p.id = a.product_id
            WHERE a.id = ?
            """,
            (alert_id,),
        ).fetchone()
        if not alert:
            return
        triggered_at = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "UPDATE price_alerts SET triggered = 1, triggered_at = ? WHERE id = ?",
            (triggered_at, alert_id),
        )
        if actual_price is not None:
            message = (
                f"{alert['product_name']} 가격이 목표가 {int(alert['target_price']):,}원 이하인 "
                f"{int(actual_price):,}원에 도달했습니다."
            )
            conn.execute(
                """
                INSERT INTO alert_events (
                    alert_id, product_id, target_price, actual_price, message, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    alert_id,
                    alert["product_id"],
                    alert["target_price"],
                    int(actual_price),
                    message,
                    triggered_at,
                ),
            )


def get_open_alerts() -> list[dict[str, Any]]:
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT a.*, p.name AS product_name,
                   (
                       SELECT ph.price
                       FROM price_history ph
                       WHERE ph.product_id = a.product_id
                       ORDER BY ph.collected_at DESC, ph.id DESC
                       LIMIT 1
                   ) AS latest_price
            FROM price_alerts a
            JOIN products p ON p.id = a.product_id
              WHERE a.triggered = 0 AND a.cancelled = 0
            ORDER BY a.created_at DESC
            """
        ).fetchall()
        return rows_to_dicts(rows)


def list_alerts(limit: int = 30, product_id: int | None = None) -> list[dict[str, Any]]:
    with connect_db() as conn:
        where_clause = "WHERE a.product_id = ?" if product_id is not None else ""
        params: tuple[Any, ...] = (product_id, limit) if product_id is not None else (limit,)
        rows = conn.execute(
            f"""
              SELECT a.*, p.name AS product_name,
                   (
                       SELECT ph.price
                       FROM price_history ph
                       WHERE ph.product_id = a.product_id
                       ORDER BY ph.collected_at DESC, ph.id DESC
                       LIMIT 1
                   ) AS latest_price
              FROM price_alerts a
              JOIN products p ON p.id = a.product_id
              {where_clause}
              ORDER BY a.created_at DESC, a.id DESC
              LIMIT ?
            """,
            params,
        ).fetchall()
        return rows_to_dicts(rows)


def cancel_alert(alert_id: int) -> dict[str, Any] | None:
    with connect_db() as conn:
        alert = conn.execute("SELECT * FROM price_alerts WHERE id = ?", (alert_id,)).fetchone()
        if not alert:
            return None
        if alert["triggered"] or alert["cancelled"]:
            result = row_to_dict(alert) or {}
            result["cancellation_performed"] = False
            return result
        cancelled_at = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "UPDATE price_alerts SET cancelled = 1, cancelled_at = ? WHERE id = ?",
            (cancelled_at, alert_id),
        )
        result = row_to_dict(
            conn.execute("SELECT * FROM price_alerts WHERE id = ?", (alert_id,)).fetchone()
        ) or {}
        result["cancellation_performed"] = True
        return result


def list_alert_events(limit: int = 30) -> list[dict[str, Any]]:
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT e.*, p.name AS product_name
            FROM alert_events e
            JOIN products p ON p.id = e.product_id
            ORDER BY e.created_at DESC, e.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return rows_to_dicts(rows)


def create_feedback(
    target_type: str,
    target_id: int,
    is_helpful: bool,
    comment: str | None = None,
) -> int:
    with connect_db() as conn:
        row = conn.execute(
            """
            INSERT INTO feedback (target_type, target_id, is_helpful, comment)
            VALUES (?, ?, ?, ?)
            RETURNING id
            """,
            (target_type, target_id, 1 if is_helpful else 0, comment),
        ).fetchone()
        return int(row["id"])


def feedback_summary() -> list[dict[str, Any]]:
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT target_type,
                   SUM(CASE WHEN is_helpful = 1 THEN 1 ELSE 0 END) AS helpful_count,
                   SUM(CASE WHEN is_helpful = 0 THEN 1 ELSE 0 END) AS not_helpful_count,
                   COUNT(*) AS total_count
            FROM feedback
            GROUP BY target_type
            ORDER BY target_type
            """
        ).fetchall()
        return rows_to_dicts(rows)


def list_feedback(limit: int = 30) -> list[dict[str, Any]]:
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM feedback
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return rows_to_dicts(rows)


def record_pipeline_run(
    run_type: str,
    status: str,
    started_at: str,
    items_processed: int | None = None,
    error_message: str | None = None,
) -> int:
    with connect_db() as conn:
        row = conn.execute(
            """
            INSERT INTO pipeline_runs (
                run_type, status, items_processed, error_message, started_at, finished_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                run_type,
                status,
                items_processed,
                error_message,
                started_at,
                datetime.now().isoformat(timespec="seconds"),
            ),
        ).fetchone()
        return int(row["id"])


def list_pipeline_runs(limit: int = 30) -> list[dict[str, Any]]:
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM pipeline_runs
            ORDER BY started_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return rows_to_dicts(rows)


def get_recent_reports(limit: int = 5) -> list[dict[str, Any]]:
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT cr.id, cr.user_priority, cr.created_at, c.name AS category_name
            FROM comparison_reports cr
            JOIN categories c ON c.id = cr.category_id
            ORDER BY cr.created_at DESC, cr.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return rows_to_dicts(rows)


def schema_context() -> str:
    return """
categories(id, name, naver_category_code, created_at)
products(id, category_id, naver_product_id, name, description, brand, maker, mall_name, link, image_url,
  product_type, classification_score, classification_reason, search_query, search_rank, hot_score,
  hot_reason, hot_updated_at, created_at)
specs(id, product_id, spec_key, spec_value, source, curated_at)
price_history(id, product_id, price, collected_at)
product_collection_evidence(id, product_id, search_query, sort_mode, search_rank, price_segment,
  popularity_score, collected_at)
product_reviews(id, product_id, external_review_id, author, rating, content, source_url, source_kind,
  reviewed_at, collected_at)
comparison_reports(id, category_id, product_ids, user_priority, llm_model, report_json, created_at)
  price_alerts(id, product_id, target_price, triggered, triggered_at, cancelled, cancelled_at, created_at)
alert_events(id, alert_id, product_id, target_price, actual_price, message, created_at)
category_recommendations(id, category_id, best_value_product_id, best_value_score, best_value_reason,
  best_performance_product_id, best_performance_score, best_performance_reason, llm_model, generated_at)
pipeline_runs(id, run_type, status, items_processed, error_message, started_at, finished_at)
feedback(id, target_type, target_id, is_helpful, comment, created_at)
""".strip()


def execute_readonly_query(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with connect_db(readonly=True) as conn:
        rows = conn.execute(sql, params).fetchall()
        return rows_to_dicts(rows)


if __name__ == "__main__":
    init_db(seed=True)
    print(f"Initialized {get_db_path()}")
