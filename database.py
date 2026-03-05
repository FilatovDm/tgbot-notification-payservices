from __future__ import annotations

import aiosqlite
from typing import Any, Dict, List, Optional

DB_PATH = "subscriptions.db"


async def init_db() -> None:
    """
    Инициализация БД и создание таблицы subscriptions при первом запуске.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_name TEXT NOT NULL,
                amount REAL NOT NULL,
                next_payment_date TEXT NOT NULL, -- формат YYYY-MM-DD
                periodicity TEXT NOT NULL        -- '1_month', '3_months', '6_months', '1_year'
            )
            """
        )
        await db.commit()


async def add_subscription(
    service_name: str,
    amount: float,
    next_payment_date: str,
    periodicity: str,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO subscriptions (service_name, amount, next_payment_date, periodicity)
            VALUES (?, ?, ?, ?)
            """,
            (service_name, amount, next_payment_date, periodicity),
        )
        await db.commit()
        return cursor.lastrowid


async def get_all_subscriptions() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, service_name, amount, next_payment_date, periodicity
            FROM subscriptions
            ORDER BY next_payment_date ASC
            """
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_subscription(subscription_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, service_name, amount, next_payment_date, periodicity
            FROM subscriptions
            WHERE id = ?
            """,
            (subscription_id,),
        )
        row = await cursor.fetchone()
    return dict(row) if row else None


async def update_subscription_field(
    subscription_id: int,
    field: str,
    value: Any,
) -> None:
    if field not in {"service_name", "amount", "next_payment_date", "periodicity"}:
        raise ValueError(f"Invalid field to update: {field}")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE subscriptions SET {field} = ? WHERE id = ?",
            (value, subscription_id),
        )
        await db.commit()


async def delete_subscription(subscription_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM subscriptions WHERE id = ?",
            (subscription_id,),
        )
        await db.commit()

