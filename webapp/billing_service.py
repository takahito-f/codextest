from __future__ import annotations

from datetime import datetime as dt
from decimal import Decimal
from typing import Any, Dict, List, Tuple

try:  # pragma: no cover - module availability checked at runtime
    from sqlalchemy import func, select
    from database import session_scope
    from models import KakinJouhou, TouchakuKanri

    SQLALCHEMY_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - fallback for environments without SQLAlchemy
    SQLALCHEMY_AVAILABLE = False
    func = select = None  # type: ignore
    session_scope = None  # type: ignore


_fallback_kakin: List[Dict[str, Any]] = []
_fallback_touchaku: List[Dict[str, Any]] = []


def query_billing(
    operator_id: str,
    billing_month: str,
    sort: str,
    order: str,
    page: int,
    per_page: int,
) -> Tuple[List[Dict[str, Any]], int]:
    if SQLALCHEMY_AVAILABLE:
        return _query_billing_sqlalchemy(operator_id, billing_month, sort, order, page, per_page)
    return _query_billing_fallback(operator_id, billing_month, sort, order, page, per_page)


def _query_billing_sqlalchemy(
    operator_id: str,
    billing_month: str,
    sort: str,
    order: str,
    page: int,
    per_page: int,
) -> Tuple[List[Dict[str, Any]], int]:
    offset = max(page - 1, 0) * per_page

    with session_scope() as session:
        kakin = KakinJouhou
        touchaku_alias = TouchakuKanri

        stmt = (
            select(
                kakin.jigyosha_id.label("jigyosha_id"),
                kakin.kakin_getsu.label("kakin_getsu"),
                func.sum(kakin.seikyuu_kingaku).label("total_amount"),
                func.max(touchaku_alias.juryo_nichiji).label("latest_received"),
                func.max(touchaku_alias.status).label("status"),
                func.max(touchaku_alias.error_message).label("error_message"),
            )
            .join(
                touchaku_alias,
                (touchaku_alias.jigyosha_id == kakin.jigyosha_id)
                & (touchaku_alias.kakin_getsu == kakin.kakin_getsu),
                isouter=True,
            )
            .where(kakin.kakin_getsu == billing_month)
            .group_by(kakin.jigyosha_id, kakin.kakin_getsu)
        )

        if operator_id:
            stmt = stmt.where(kakin.jigyosha_id == operator_id.ljust(15)[:15])

        subquery = stmt.subquery()

        sort_map = {
            "juryo_nichiji": "latest_received",
            "jigyosha_id": "jigyosha_id",
            "kakin_getsu": "kakin_getsu",
            "total_amount": "total_amount",
        }
        sort_key = sort_map.get(sort, "latest_received")
        sort_column = getattr(subquery.c, sort_key)
        order_clause = sort_column.desc() if order.lower() == "desc" else sort_column.asc()

        count_stmt = select(func.count()).select_from(subquery)
        total = session.execute(count_stmt).scalar_one()

        sorted_stmt = select(subquery).order_by(order_clause)
        rows = session.execute(sorted_stmt.offset(offset).limit(per_page)).mappings().all()

    results = []
    for row in rows:
        total_amount = row["total_amount"]
        if isinstance(total_amount, Decimal):
            total_amount = int(total_amount)
        results.append(
            {
                "jigyosha_id": (row["jigyosha_id"] or "").strip(),
                "kakin_getsu": (row["kakin_getsu"] or "").strip(),
                "total_amount": total_amount,
                "latest_received": row["latest_received"],
                "status": int(row["status"]) if row["status"] is not None else None,
                "error_message": row["error_message"],
            }
        )

    return results, total


def _query_billing_fallback(
    operator_id: str,
    billing_month: str,
    sort: str,
    order: str,
    page: int,
    per_page: int,
) -> Tuple[List[Dict[str, Any]], int]:
    filtered = [
        row
        for row in _fallback_kakin
        if row["kakin_getsu"] == billing_month
        and (not operator_id or row["jigyosha_id"].strip() == operator_id)
    ]

    grouped: Dict[str, Dict[str, Any]] = {}
    for row in filtered:
        key = row["jigyosha_id"].strip()
        entry = grouped.setdefault(
            key,
            {
                "jigyosha_id": key,
                "kakin_getsu": billing_month,
                "total_amount": 0,
                "latest_received": None,
                "status": None,
                "error_message": None,
            },
        )
        entry["total_amount"] += int(row["seikyuu_kingaku"])

    for record in _fallback_touchaku:
        if record["kakin_getsu"] != billing_month:
            continue
        key = record["jigyosha_id"].strip()
        if operator_id and key != operator_id:
            continue
        if key not in grouped:
            grouped[key] = {
                "jigyosha_id": key,
                "kakin_getsu": billing_month,
                "total_amount": 0,
                "latest_received": record["juryo_nichiji"],
                "status": record.get("status"),
                "error_message": record.get("error_message"),
            }
        else:
            current = grouped[key]
            if not current["latest_received"] or current["latest_received"] < record["juryo_nichiji"]:
                current["latest_received"] = record["juryo_nichiji"]
                current["status"] = record.get("status")
                current["error_message"] = record.get("error_message")

    results = list(grouped.values())

    sort_map = {
        "juryo_nichiji": "latest_received",
        "jigyosha_id": "jigyosha_id",
        "kakin_getsu": "kakin_getsu",
        "total_amount": "total_amount",
    }
    sort_key = sort_map.get(sort, "latest_received")
    reverse = order.lower() == "desc"
    def key_func(row: Dict[str, Any]):
        value = row.get(sort_key)
        if value is None:
            if sort_key == "latest_received":
                return dt.min
            if sort_key == "total_amount":
                return 0
            return ""
        return value

    results.sort(key=key_func, reverse=reverse)

    total = len(results)
    offset = max(page - 1, 0) * per_page
    paged = results[offset : offset + per_page]

    return paged, total


def _fallback_reset() -> None:
    _fallback_kakin.clear()
    _fallback_touchaku.clear()


def _fallback_add_kakin(record: Dict[str, Any]) -> None:
    _fallback_kakin.append(record)


def _fallback_add_touchaku(record: Dict[str, Any]) -> None:
    _fallback_touchaku.append(record)


def mask(value: str) -> str:
    if not value:
        return ""
    return value[:2] + "**"
