from __future__ import annotations

import json
import os
from time import perf_counter
from typing import Any

from flask import Flask, jsonify, redirect, render_template, request, url_for
from requests import RequestException

import analysis
import db
import db_coder_agent
from antigravity_cli import recommend_products
from collector import (
    check_naver_api_connection,
    collect_cosmetic_catalog,
    collect_hot_products,
    collect_prices_for_all_products,
    collect_products_for_category,
    collect_products_for_search,
)
from llm_agent import run_llm_task


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_AS_ASCII"] = False
    db.init_db(seed=True)
    _ensure_recommendations()
    _ensure_hot_products()

    @app.template_filter("money")
    def money(value: Any) -> str:
        if value is None:
            return "확인 불가"
        return f"{int(value):,}원"

    @app.template_filter("json_attr")
    def json_attr(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    @app.route("/")
    def index() -> str:
        categories = db.get_categories()
        recommendations = {
            category["id"]: db.get_category_recommendation(category["id"]) for category in categories
        }
        return render_template(
            "index.html",
            categories=categories,
            recommendations=recommendations,
            counts=db.get_counts(),
            recent_reports=db.get_recent_reports(),
            hot_products=db.list_hot_products(limit=8),
        )

    @app.route("/search")
    def search_page() -> str:
        query = request.args.get("q", "").strip()
        products: list[dict[str, Any]] = []
        search_meta: dict[str, Any] | None = None
        error = None
        took_ms = None
        if query:
            started_at = perf_counter()
            try:
                include_accessories = request.args.get("include_accessories") == "1"
                search_meta = collect_products_for_search(
                    query,
                    display=20,
                    include_accessories=include_accessories,
                )
                products = [
                    product
                    for product_id in search_meta["product_ids"]
                    if (product := db.get_product(product_id))
                ]
                took_ms = round((perf_counter() - started_at) * 1000, 2)
            except Exception as exc:
                error = str(exc)
        return render_template(
            "search_results.html",
            query=query,
            products=products,
            search_meta=search_meta,
            error=error,
            took_ms=took_ms,
            include_accessories=request.args.get("include_accessories") == "1",
        )

    @app.route("/analyze", methods=["POST"])
    def analyze_form():
        product_id = request.form.get("product_id", type=int)
        if not product_id:
            return redirect(url_for("index"))
        result = _create_analysis_report(product_id)
        return redirect(url_for("analysis_page", report_id=result["report_id"]))

    @app.route("/analysis/<int:report_id>")
    def analysis_page(report_id: int) -> str:
        report = db.get_comparison_report(report_id)
        if not report:
            return render_template("not_found.html", message="분석 리포트를 찾을 수 없습니다."), 404
        return render_template("product_analysis.html", report=report, result=report["report_json"])

    @app.route("/categories/<int:category_id>")
    def category_page(category_id: int) -> str:
        category = db.get_category(category_id)
        if not category:
            return render_template("not_found.html", message="카테고리를 찾을 수 없습니다."), 404
        scores = analysis.compute_category_scores(category_id)
        recommendation = db.get_category_recommendation(category_id)
        return render_template(
            "category.html",
            category=category,
            products=db.get_products(category_id),
            scores=scores,
            recommendation=recommendation,
        )

    @app.route("/products/<int:product_id>")
    def product_detail_page(product_id: int) -> str:
        product = db.get_product_with_specs(product_id)
        if not product:
            return render_template("not_found.html", message="상품을 찾을 수 없습니다."), 404
        history = db.get_price_history(product_id, days=90)
        stats = analysis.compute_price_stats(product_id, days=90)
        timing = analysis.buy_timing_from_stats(stats)
        alerts = db.list_alerts(limit=20, product_id=product_id)
        return render_template(
            "product_detail.html",
            product=product,
            history=history,
            stats=stats,
            timing=timing,
            alerts=alerts,
        )

    @app.route("/reports/<int:report_id>")
    def report_page(report_id: int) -> str:
        report = db.get_comparison_report(report_id)
        if not report:
            return render_template("not_found.html", message="리포트를 찾을 수 없습니다."), 404
        products = [db.get_product_with_specs(product_id) for product_id in report["product_ids"]]
        return render_template(
            "compare_report.html",
            report=report,
            products=[product for product in products if product],
        )

    @app.route("/admin")
    def admin_dashboard() -> str:
        return render_template(
            "admin_dashboard.html",
            runs=db.list_pipeline_runs(limit=30),
            alerts=db.list_alerts(limit=10),
            alert_events=db.list_alert_events(limit=10),
            feedback_summary=db.feedback_summary(),
        )

    @app.route("/api/categories")
    def api_categories():
        return jsonify(db.get_categories())

    @app.route("/api/products")
    def api_products():
        category_id = request.args.get("category_id", type=int)
        return jsonify(db.get_products(category_id))

    @app.route("/api/search")
    def api_search():
        query = request.args.get("q", "").strip()
        if not query:
            return jsonify({"error": "검색어 q가 필요합니다."}), 400
        started_at = perf_counter()
        search_meta = collect_products_for_search(
            query,
            display=request.args.get("display", 20, type=int),
            include_accessories=request.args.get("include_accessories") == "1",
        )
        products = [
            product for product_id in search_meta["product_ids"] if (product := db.get_product(product_id))
        ]
        took_ms = round((perf_counter() - started_at) * 1000, 2)
        return jsonify(
            {
                "search": search_meta,
                "products": products,
                "took_ms": took_ms,
                "accessory_count": search_meta.get("accessory_count", 0),
            }
        )

    @app.route("/api/hot-products")
    def api_hot_products():
        refresh = request.args.get("refresh") == "1"
        if refresh:
            collect_hot_products()
        return jsonify({"products": db.list_hot_products(limit=request.args.get("limit", 8, type=int))})

    @app.route("/api/recommend", methods=["GET", "POST"])
    def api_recommend():
        payload = request.args if request.method == "GET" else (request.get_json(silent=True) or request.form)
        skin_type = str(payload.get("skin_type") or "").strip().lower() or None
        hair_type = str(payload.get("hair_type") or "").strip().lower() or None
        try:
            skin_conditions = _parse_skin_conditions(payload)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        if not skin_type and not hair_type and not skin_conditions:
            return jsonify({"error": "skin_type 또는 hair_type 중 하나를 입력하세요."}), 400
        if skin_type not in {None, "dry", "oily", "sensitive"}:
            return jsonify({"error": "skin_type은 dry, oily, sensitive 중 하나여야 합니다."}), 400
        if hair_type not in {None, "dry", "oily"}:
            return jsonify({"error": "hair_type은 dry, oily 중 하나여야 합니다."}), 400
        raw_limit = payload.get("limit", "20")
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            return jsonify({"error": "limit은 1 이상 100 이하의 정수여야 합니다."}), 400
        if not 1 <= limit <= 100:
            return jsonify({"error": "limit은 1 이상 100 이하의 정수여야 합니다."}), 400
        recommendations = recommend_products(skin_type=skin_type, hair_type=hair_type)
        recommendations = analysis.apply_skin_condition_scores(
            recommendations,
            skin_conditions,
            require_condition_match=not skin_type and not hair_type,
        )[:limit]
        return jsonify(
            {
                "skin_type": skin_type,
                "hair_type": hair_type,
                "skin_conditions": skin_conditions,
                "recommendations": recommendations,
                "count": len(recommendations),
                "engine": "antigravity_rules",
                "disclaimer": (
                    "이 추천은 상품명과 설명을 활용한 화장품 선택 보조 정보이며 "
                    "의료적 진단이 아닙니다."
                ),
            }
        )

    @app.route("/api/analyze", methods=["POST"])
    def api_analyze():
        payload = request.get_json(silent=True) or request.form
        product_id = int(payload["product_id"])
        return jsonify(_create_analysis_report(product_id))

    @app.route("/api/products/<int:product_id>/price-history")
    def api_price_history(product_id: int):
        days = request.args.get("days", default=90, type=int)
        return jsonify(db.get_price_history(product_id, days=days))

    @app.route("/api/compare", methods=["POST"])
    def api_compare():
        payload = request.get_json(silent=True) or request.form.to_dict(flat=False)
        product_ids = _coerce_product_ids(payload.get("product_ids") or payload.get("product_ids[]"))
        if not product_ids and payload.get("category_id"):
            category_id = int(_first(payload["category_id"]))
            product_ids = [product["id"] for product in db.get_products(category_id)[:3]]
        if len(product_ids) < 2:
            return jsonify({"error": "비교할 상품을 2개 이상 선택하세요."}), 400

        user_priority = _first(payload.get("user_priority")) or None
        compare_input = analysis.build_compare_payload(product_ids, user_priority)
        result = run_llm_task("compare", compare_input, persist=True)
        return jsonify(result)

    @app.route("/compare", methods=["POST"])
    def compare_form():
        try:
            product_ids = _coerce_product_ids(request.form.getlist("product_ids"))
        except (TypeError, ValueError):
            product_ids = []
        if len(product_ids) < 2:
            category_id = request.form.get("category_id", type=int)
            target = (
                url_for("category_page", category_id=category_id, error="select_more")
                if category_id is not None and db.get_category(category_id)
                else url_for("index", error="select_more")
            )
            return redirect(target)
        compare_input = analysis.build_compare_payload(
            product_ids,
            request.form.get("user_priority") or None,
        )
        result = run_llm_task("compare", compare_input, persist=True)
        return redirect(url_for("report_page", report_id=result["report_id"]))

    @app.route("/api/products/<int:product_id>/buy-timing")
    def api_buy_timing(product_id: int):
        days = request.args.get("days", default=90, type=int)
        stats = analysis.compute_price_stats(product_id, days=days)
        result = run_llm_task("buy_timing", stats, persist=False)
        return jsonify({"stats": stats, "timing": result})

    @app.route("/api/categories/<int:category_id>/best-picks")
    def api_best_picks(category_id: int):
        scores = analysis.compute_category_scores(category_id)
        result = run_llm_task("best_pick", scores, persist=True)
        recommendation = db.get_category_recommendation(category_id)
        return jsonify({"scores": scores, "recommendation": recommendation, "reason": result})

    @app.route("/api/alerts", methods=["POST"])
    def api_alerts():
        payload = request.get_json(silent=True) or request.form
        product_id = int(payload["product_id"])
        target_price = int(payload["target_price"])
        alert_id = db.create_alert(product_id, target_price)
        return jsonify({"id": alert_id, "product_id": product_id, "target_price": target_price}), 201

    @app.route("/alerts", methods=["POST"])
    def alert_form():
        payload = request.form
        product_id = int(payload["product_id"])
        target_price = int(payload["target_price"])
        db.create_alert(product_id, target_price)
        return redirect(url_for("product_detail_page", product_id=product_id))

    @app.route("/api/alerts")
    def api_alert_list():
        raw_product_id = request.args.get("product_id")
        product_id = request.args.get("product_id", type=int)
        if raw_product_id is not None and product_id is None:
            return jsonify({"error": "product_id는 정수여야 합니다."}), 400
        limit = request.args.get("limit", default=30, type=int)
        if limit is None or limit < 1:
            return jsonify({"error": "limit은 1 이상의 정수여야 합니다."}), 400
        return jsonify(
            {
                "alerts": db.list_alerts(
                    limit=limit,
                    product_id=product_id,
                ),
                "events": db.list_alert_events(limit=30),
            }
        )

    @app.route("/api/alerts/<int:alert_id>/cancel", methods=["POST"])
    def api_alert_cancel(alert_id: int):
        alert = db.cancel_alert(alert_id)
        if not alert:
            return jsonify({"error": "가격 알림을 찾을 수 없습니다."}), 404
        cancellation_performed = alert.pop("cancellation_performed", False)
        if alert["triggered"]:
            return jsonify({"error": "이미 발송된 가격 알림은 취소할 수 없습니다."}), 400
        if cancellation_performed:
            return jsonify({"alert": alert})
        return jsonify({"error": "이미 취소된 가격 알림입니다."}), 400

    @app.route("/api/alerts/check", methods=["POST"])
    def api_alert_check():
        triggered = analysis.check_price_alerts()
        return jsonify({"triggered": triggered, "count": len(triggered)})

    @app.route("/api/collect", methods=["POST"])
    def api_collect():
        raw_category_id = request.args.get("category_id")
        category_id = request.args.get("category_id", type=int)
        if raw_category_id is not None and category_id is None:
            return jsonify({"error": "category_id는 정수여야 합니다."}), 400
        if category_id is not None:
            if not db.get_category(category_id):
                return jsonify({"error": "수집할 카테고리를 찾을 수 없습니다."}), 404
            product_ids = collect_products_for_category(category_id)
            return jsonify({"collected_product_ids": product_ids})
        prices = collect_prices_for_all_products()
        cosmetic_products = collect_cosmetic_catalog()
        collection_summary = db.get_collection_summary(
            [product["id"] for product in cosmetic_products]
        )
        target_per_category = 100
        required_categories = ("화장품", "클렌징폼", "로션")
        target_met = all(
            collection_summary["category_counts"].get(category, 0) >= target_per_category
            for category in required_categories
        )
        analysis.recompute_category_recommendations()
        return jsonify(
            {
                "prices": prices,
                "hot_products": cosmetic_products[:8],
                "collected_count": len(cosmetic_products),
                "price_segments": collection_summary["price_segments"],
                "category_counts": collection_summary["category_counts"],
                "review_count": collection_summary["review_count"],
                "target_per_category": target_per_category,
                "target_met": target_met,
                "review_collection": (
                    "public_product_data_or_naver_blog_excerpts"
                    if collection_summary["review_count"]
                    else "no_public_reviews_found"
                ),
            }
        )

    @app.route("/api/feedback", methods=["POST"])
    def api_feedback():
        payload = request.get_json(silent=True) or request.form
        feedback_id = db.create_feedback(
            target_type=str(payload["target_type"]),
            target_id=int(payload["target_id"]),
            is_helpful=str(payload["is_helpful"]).lower() in {"1", "true", "yes", "y"},
            comment=payload.get("comment"),
        )
        return jsonify({"id": feedback_id}), 201

    @app.route("/api/admin/pipeline-runs")
    def api_pipeline_runs():
        limit = request.args.get("limit", default=30, type=int)
        return jsonify(db.list_pipeline_runs(limit=limit))

    @app.route("/api/admin/api-status")
    def api_status():
        query = request.args.get("query", default="무선이어폰")
        return jsonify({"naver_search_shop": check_naver_api_connection(query=query)})

    @app.route("/api/admin/feedback")
    def api_admin_feedback():
        limit = request.args.get("limit", default=30, type=int)
        return jsonify({"summary": db.feedback_summary(), "items": db.list_feedback(limit=limit)})

    @app.route("/api/admin/query", methods=["POST"])
    def api_admin_query():
        payload = request.get_json(silent=True) or request.form
        question = str(payload.get("question", "")).strip()
        if not question:
            return jsonify({"error": "질문 question이 필요합니다."}), 400
        try:
            return jsonify(db_coder_agent.answer_question(question))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    return app


def _ensure_recommendations() -> None:
    categories = db.get_categories()
    if categories and not any(db.get_category_recommendation(category["id"]) for category in categories):
        analysis.recompute_category_recommendations()


def _ensure_hot_products() -> None:
    if len(db.hot_product_queries_today()) < 3:
        try:
            collect_hot_products()
        except RequestException:
            # 외부 API 장애가 앱 시작 자체를 막지 않도록 기존 로컬 데이터를 사용한다.
            return


def _create_analysis_report(product_id: int) -> dict[str, Any]:
    result = analysis.analyze_selected_product(product_id)
    selected = result["selected_product"]
    recommended_ids = [int(item["id"]) for item in result.get("recommendations", [])]
    product_ids = [int(selected["id"]), *recommended_ids]
    report_id = db.create_comparison_report(
        category_id=int(selected["category_id"]),
        product_ids=product_ids,
        user_priority="auto_product_analysis",
        llm_model="code-ai-analysis",
        report=result,
    )
    result["report_id"] = report_id
    return result


def _coerce_product_ids(value: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [int(item) for item in parsed]
        except json.JSONDecodeError:
            return [int(part) for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        return [int(_first(item)) for item in value if str(_first(item)).strip()]
    return [int(value)]


def _first(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _parse_skin_conditions(payload: Any) -> list[str]:
    if hasattr(payload, "getlist"):
        raw_values = payload.getlist("skin_conditions")
    else:
        raw_value = payload.get("skin_conditions")
        raw_values = raw_value if isinstance(raw_value, list) else [raw_value]

    normalized: list[str] = []
    for raw_value in raw_values:
        if raw_value is None:
            continue
        for value in str(raw_value).split(","):
            condition = value.strip().lower()
            if condition and condition not in normalized:
                normalized.append(condition)

    unsupported = [
        condition for condition in normalized if condition not in analysis.SKIN_CONDITION_RULES
    ]
    if unsupported:
        raise ValueError(f"지원하지 않는 피부 상태입니다: {', '.join(unsupported)}")
    if len(normalized) > 5:
        raise ValueError("skin_conditions는 최대 5개까지 선택할 수 있습니다.")
    return normalized


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8400"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
