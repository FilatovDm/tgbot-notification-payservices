from __future__ import annotations

from datetime import date, timedelta, timezone
from typing import Any, Dict

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from zoneinfo import ZoneInfo

from config import get_settings
from database import get_all_subscriptions, update_subscription_field
from dateutil.relativedelta import relativedelta


PERIODICITY_TO_DELTA: Dict[str, relativedelta] = {
    "1_month": relativedelta(months=1),
    "3_months": relativedelta(months=3),
    "6_months": relativedelta(months=6),
    "1_year": relativedelta(years=1),
}

NOTIFY_DAYS = (3, 2, 1, 0)


async def _process_subscription(bot: Bot, sub: Dict[str, Any]) -> None:
    settings = get_settings()
    group_chat_id = settings.group_chat_id

    sub_id = sub["id"]
    service_name = sub["service_name"]
    amount = sub["amount"]
    currency = sub.get("currency") or "RUB"
    periodicity = sub["periodicity"]

    try:
        next_payment = date.fromisoformat(sub["next_payment_date"])
    except ValueError:
        # Неверный формат даты — пропускаем запись.
        return

    today = date.today()
    days_diff = (next_payment - today).days

    payment_date_human = next_payment.strftime("%d-%m-%Y")

    if days_diff in NOTIFY_DAYS:
        if days_diff == 3:
            prefix = "⚠️ Напоминание: Через 3 дня"
        elif days_diff == 2:
            prefix = "⚠️ Напоминание: Через 2 дня"
        elif days_diff == 1:
            prefix = "🚨 ВНИМАНИЕ: Завтра"
        else:
            prefix = "💳 Сегодня"

        text = (
            f"{prefix} ({payment_date_human}) списание за <b>{service_name}</b> - "
            f"<b>{amount:.2f} {currency}</b>"
        )
        await bot.send_message(chat_id=group_chat_id, text=text)

    # Если дата наступила или прошла — переносим на следующий период.
    if next_payment <= today:
        delta = PERIODICITY_TO_DELTA.get(periodicity)
        if not delta:
            return

        new_date = next_payment
        # Гарантируем, что новая дата строго > today.
        while new_date <= today:
            new_date = new_date + delta

        await update_subscription_field(
            subscription_id=sub_id,
            field="next_payment_date",
            value=new_date.strftime("%Y-%m-%d"),
        )


async def check_subscriptions_and_notify(bot: Bot) -> None:
    """
    Основной джоб для APScheduler.
    """
    subscriptions = await get_all_subscriptions()
    for sub in subscriptions:
        await _process_subscription(bot, sub)


def _get_moscow_tzinfo():
    # На Windows может отсутствовать IANA tz database, поэтому есть fallback на фиксированный UTC+3.
    try:
        return ZoneInfo("Europe/Moscow")
    except Exception:
        return timezone(timedelta(hours=3))


def setup_scheduler(scheduler: AsyncIOScheduler, bot: Bot) -> None:
    """
    Регистрирует ежедневное задание в 10:00 по МСК.
    """
    msk = _get_moscow_tzinfo()
    scheduler.add_job(
        check_subscriptions_and_notify,
        "cron",
        hour=10,
        minute=0,
        timezone=msk,
        args=[bot],
        id="subscriptions_notifier",
        replace_existing=True,
    )
    scheduler.start()

