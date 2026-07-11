from __future__ import annotations

import json
import os
from typing import Any

from flask import Flask, jsonify, redirect, render_template, request, url_for

import analysis
import db
import db_coder_agent
from collector import (
    check_naver_api_connection,
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
        if query:
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
            except Exception as exc:
                error = str(exc)
        return render_template(
            "search_results.html",
            query=query,
            products=products,
            search_meta=search_meta,
            error=error,
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
        return render_template(
            "product_detail.html",
            product=product,
            history=history,
            stats=stats,
            timing=timing,
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
            return jsonify({"error": "q is required"}), 400
        search_meta = collect_products_for_search(
            query,
            display=request.args.get("display", 20, type=int),
            include_accessories=request.args.get("include_accessories") == "1",
        )
        products = [
            product for product_id in search_meta["product_ids"] if (product := db.get_product(product_id))
        ]
        return jsonify({"search": search_meta, "products": products})

    @app.route("/api/hot-products")
    def api_hot_products():
        refresh = request.args.get("refresh") == "1"
        if refresh:
            collect_hot_products()
        return jsonify({"products": db.list_hot_products(limit=request.args.get("limit", 8, type=int))})

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
        product_ids = _coerce_product_ids(request.form.getlist("product_ids"))
        if len(product_ids) < 2:
            return redirect(request.referrer or url_for("index"))
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
        return jsonify(
            {
                "alerts": db.list_alerts(limit=request.args.get("limit", default=30, type=int)),
                "events": db.list_alert_events(limit=30),
            }
        )

    @app.route("/api/alerts/check", methods=["POST"])
    def api_alert_check():
        triggered = analysis.check_price_alerts()
        return jsonify({"triggered": triggered, "count": len(triggered)})

    @app.route("/api/collect", methods=["POST"])
    def api_collect():
        category_id = request.args.get("category_id", type=int)
        if category_id:
            product_ids = collect_products_for_category(category_id)
            return jsonify({"collected_product_ids": product_ids})
        prices = collect_prices_for_all_products()
        hot_products = collect_hot_products()
        analysis.recompute_category_recommendations()
        return jsonify({"prices": prices, "hot_products": hot_products[:8]})

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
            return jsonify({"error": "question is required"}), 400
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
        collect_hot_products()


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


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8400"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
