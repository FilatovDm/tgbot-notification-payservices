from __future__ import annotations

import aiosqlite
from typing import Any, Dict, List, Optional

DB_PATH = "subscriptions.db"

DEFAULT_CURRENCY = "RUB"
USD_SERVICES = {"HeyGen", "Make"}


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
                currency TEXT NOT NULL DEFAULT 'RUB',
                next_payment_date TEXT NOT NULL, -- формат YYYY-MM-DD
                periodicity TEXT NOT NULL,       -- '1_month', '3_months', '6_months', '1_year'
                auto_renew INTEGER NOT NULL DEFAULT 0 -- 0/1: автопродление
            )
            """
        )
        await db.commit()

        # Миграция для существующих БД: добавляем колонку currency при необходимости.
        cursor = await db.execute("PRAGMA table_info(subscriptions)")
        columns = {row[1] for row in await cursor.fetchall()}  # row[1] = name

        # Миграция для существующих БД: добавляем колонку currency при необходимости.
        currency_added = False
        if "currency" not in columns:
            await db.execute(
                "ALTER TABLE subscriptions ADD COLUMN currency TEXT NOT NULL DEFAULT 'RUB'"
            )
            currency_added = True
            await db.commit()

        # Заполняем валюту для старых записей при первой миграции.
        if currency_added:
            await db.execute(
                "UPDATE subscriptions SET currency = ?",
                (DEFAULT_CURRENCY,),
            )
            await db.execute(
                "UPDATE subscriptions SET currency = 'USD' WHERE service_name IN ('HeyGen', 'Make')"
            )
            await db.commit()

        # Миграция для существующих БД: добавляем колонку auto_renew при необходимости.
        if "auto_renew" not in columns:
            await db.execute(
                "ALTER TABLE subscriptions ADD COLUMN auto_renew INTEGER NOT NULL DEFAULT 0"
            )
            await db.commit()


async def add_subscription(
    service_name: str,
    amount: float,
    currency: str,
    next_payment_date: str,
    periodicity: str,
    auto_renew: bool = False,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO subscriptions (service_name, amount, currency, next_payment_date, periodicity, auto_renew)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (service_name, amount, currency, next_payment_date, periodicity, int(auto_renew)),
        )
        await db.commit()
        return cursor.lastrowid


async def get_all_subscriptions() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id,
                   service_name,
                   amount,
                   currency,
                   next_payment_date,
                   periodicity,
                   auto_renew
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
            SELECT id,
                   service_name,
                   amount,
                   currency,
                   next_payment_date,
                   periodicity,
                   auto_renew
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
    if field not in {
        "service_name",
        "amount",
        "currency",
        "next_payment_date",
        "periodicity",
        "auto_renew",
    }:
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

