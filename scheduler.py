from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from apscheduler.schedulers.blocking import BlockingScheduler

import db
from analysis import check_price_alerts, recompute_category_recommendations
from collector import collect_hot_products, collect_prices_for_all_products
from llm_agent import generate_best_pick_reasons

scheduler = BlockingScheduler(timezone="Asia/Seoul")


def _run_with_logging(run_type: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    started_at = datetime.now().isoformat(timespec="seconds")
    try:
        result = fn(*args, **kwargs)
        db.record_pipeline_run(
            run_type,
            "success",
            started_at,
            items_processed=_items_processed(result),
        )
        return result
    except Exception as exc:
        db.record_pipeline_run(run_type, "failed", started_at, error_message=str(exc))
        raise


def _items_processed(result: Any) -> int:
    if result is None:
        return 0
    if isinstance(result, list | tuple | set | dict):
        return len(result)
    return 1


def run_daily_pipeline_once() -> dict[str, Any]:
    db.init_db(seed=True)
    prices = _run_with_logging("price_collection", collect_prices_for_all_products)
    alerts = _run_with_logging("alert_check", check_price_alerts)
    hot_products = _run_with_logging("hot_product_collection", collect_hot_products)
    scores = _run_with_logging("best_pick_recompute", recompute_category_recommendations)
    reasons = _run_with_logging("best_pick_reason_generation", generate_best_pick_reasons, scores)
    return {
        "prices": prices,
        "alerts": alerts,
        "hot_products": hot_products,
        "scores": scores,
        "reasons": reasons,
    }


@scheduler.scheduled_job("cron", hour=9, minute=0)
def daily_price_collection() -> None:
    run_daily_pipeline_once()


if __name__ == "__main__":
    db.init_db(seed=True)
    scheduler.start()
