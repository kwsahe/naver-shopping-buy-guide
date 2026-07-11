from __future__ import annotations

import re
from typing import Any

import sqlparse

import db

BLOCKED_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "REPLACE",
    "TRUNCATE",
    "VACUUM",
    "ATTACH",
    "DETACH",
    "PRAGMA",
}


def generate_sql_from_question(question: str) -> str:
    lowered = question.lower()
    if "pipeline" in lowered or "파이프라인" in question or "실행" in question:
        return """
        SELECT run_type, status, items_processed, error_message, started_at, finished_at
        FROM pipeline_runs
        ORDER BY started_at DESC, id DESC
        LIMIT 20
        """
    if "feedback" in lowered or "피드백" in question or "도움" in question:
        return """
        SELECT target_type, is_helpful, COUNT(*) AS count
        FROM feedback
        GROUP BY target_type, is_helpful
        ORDER BY target_type, is_helpful DESC
        LIMIT 50
        """
    if "가격" in question or "price" in lowered:
        return """
        SELECT p.name, c.name AS category_name, latest.price AS latest_price, latest.collected_at
        FROM products p
        JOIN categories c ON c.id = p.category_id
        JOIN (
            SELECT ph.product_id, ph.price, ph.collected_at
            FROM price_history ph
            JOIN (
                SELECT product_id, MAX(collected_at) AS collected_at
                FROM price_history
                GROUP BY product_id
            ) recent
              ON recent.product_id = ph.product_id
             AND recent.collected_at = ph.collected_at
        ) latest ON latest.product_id = p.id
        ORDER BY latest.price ASC
        LIMIT 20
        """
    return """
    SELECT c.name AS category_name, COUNT(p.id) AS product_count
    FROM categories c
    LEFT JOIN products p ON p.category_id = c.id
    GROUP BY c.id
    ORDER BY c.name
    LIMIT 20
    """


def validate_readonly_sql(sql: str) -> str:
    stripped = sqlparse.format(sql, strip_comments=True).strip()
    if not stripped:
        raise ValueError("SQL is empty")

    statements = [statement for statement in sqlparse.parse(stripped) if statement.tokens]
    if len(statements) != 1:
        raise ValueError("Only one SELECT statement is allowed")

    first_type = statements[0].get_type()
    upper = stripped.upper()
    if first_type != "SELECT" and not upper.startswith("WITH "):
        raise ValueError("Only SELECT or WITH queries are allowed")

    tokens = set(re.findall(r"\b[A-Z_]+\b", upper))
    blocked = sorted(tokens & BLOCKED_KEYWORDS)
    if blocked:
        raise ValueError(f"Blocked SQL keyword: {', '.join(blocked)}")

    return stripped


def answer_question(question: str) -> dict[str, Any]:
    db.init_db(seed=True)
    generated_sql = generate_sql_from_question(question)
    validated_sql = validate_readonly_sql(generated_sql)
    rows = db.execute_readonly_query(validated_sql)
    return {
        "question": question,
        "schema_context": db.schema_context(),
        "generated_sql": validated_sql,
        "rows": rows,
        "answer": _summarize_rows(rows),
    }


def _summarize_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "조회 결과가 없습니다."
    return f"{len(rows)}개의 행을 찾았습니다. 첫 번째 결과는 {rows[0]} 입니다."
