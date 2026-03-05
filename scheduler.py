from __future__ import annotations

from datetime import date, datetime
from typing import Dict, Any

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dateutil.relativedelta import relativedelta

from config import get_settings
from database import get_all_subscriptions, update_subscription_field


PERIODICITY_TO_DELTA: Dict[str, relativedelta] = {
    "1_month": relativedelta(months=1),
    "3_months": relativedelta(months=3),
    "6_months": relativedelta(months=6),
    "1_year": relativedelta(years=1),
}


async def _process_subscription(bot: Bot, sub: Dict[str, Any]) -> None:
    settings = get_settings()
    group_chat_id = settings.group_chat_id

    sub_id = sub["id"]
    service_name = sub["service_name"]
    amount = sub["amount"]
    periodicity = sub["periodicity"]

    try:
        next_payment = date.fromisoformat(sub["next_payment_date"])
    except ValueError:
        # Неверный формат даты — пропускаем запись.
        return

    today = date.today()
    days_diff = (next_payment - today).days

    if days_diff == 3:
        text = (
            f"⚠️ Напоминание: Через 3 дня ({next_payment:%Y-%m-%d}) "
            f"списание за <b>{service_name}</b> - <b>{amount:.2f}</b>"
        )
        await bot.send_message(chat_id=group_chat_id, text=text)
    elif days_diff == 1:
        text = (
            f"🚨 ВНИМАНИЕ: Завтра ({next_payment:%Y-%m-%d}) "
            f"списание за <b>{service_name}</b> - <b>{amount:.2f}</b>"
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


def setup_scheduler(scheduler: AsyncIOScheduler, bot: Bot) -> None:
    """
    Регистрирует ежедневное задание в 10:00.
    """
    # Время можно скорректировать под ваш часовой пояс, по умолчанию APScheduler
    # использует локальный timezone или указанный при создании.
    scheduler.add_job(
        check_subscriptions_and_notify,
        "cron",
        hour=10,
        minute=0,
        args=[bot],
        id="subscriptions_notifier",
        replace_existing=True,
    )
    scheduler.start()

