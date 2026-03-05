from __future__ import annotations

from typing import Optional

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import is_admin
from database import (
    add_subscription,
    delete_subscription,
    get_all_subscriptions,
    get_subscription,
    update_subscription_field,
)

router = Router()


class AddSubscriptionStates(StatesGroup):
    service_name = State()
    amount = State()
    currency = State()
    next_payment_date = State()
    periodicity = State()


class EditSubscriptionStates(StatesGroup):
    choosing_subscription = State()
    choosing_field = State()
    editing_value = State()


class DeleteSubscriptionStates(StatesGroup):
    choosing_subscription = State()
    confirming = State()


MAIN_MENU_KB = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📋 Показать подписки"),
        ],
        [
            KeyboardButton(text="➕ Добавить подписку"),
            KeyboardButton(text="🔁 Изменить подписку"),
        ],
        [
            KeyboardButton(text="❌ Удалить подписку"),
        ],
    ],
    resize_keyboard=True,
)


def _admin_only_message(message: Message) -> bool:
    return is_admin(message.from_user.id) if message.from_user else False


def _admin_only_callback(callback: CallbackQuery) -> bool:
    return is_admin(callback.from_user.id) if callback.from_user else False


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if not _admin_only_message(message):
        return
    await message.answer(
        "👋 Привет! Я бот для учёта подписок и напоминаний о списаниях.\n\n"
        "Используй кнопки ниже для управления подписками.",
        reply_markup=MAIN_MENU_KB,
    )


@router.message(F.text == "📋 Показать подписки")
async def show_subscriptions(message: Message) -> None:
    if not _admin_only_message(message):
        return

    from datetime import date

    subscriptions = await get_all_subscriptions()
    if not subscriptions:
        await message.answer("Пока нет ни одной подписки.")
        return

    lines = ["📋 <b>Список подписок</b>:"]
    today = date.today()
    for sub in subscriptions:
        try:
            next_payment_dt = date.fromisoformat(sub["next_payment_date"])
        except ValueError:
            next_payment_dt = None

        days_left = None if not next_payment_dt else (next_payment_dt - today).days
        days_left_display = "—" if days_left is None else str(max(days_left, 0))

        period_human = {
            "1_month": "1 месяц",
            "3_months": "3 месяца",
            "6_months": "6 месяцев",
            "1_year": "1 год",
        }.get(sub["periodicity"], sub["periodicity"])

        date_human = sub["next_payment_date"]
        if next_payment_dt:
            date_human = next_payment_dt.strftime("%d-%m-%Y")

        date_prefix = ""
        if days_left == 7:
            date_prefix = "⚠️ "

        currency = sub.get("currency") or "RUB"
        lines.append(
            f"\n<b>ID:</b> {sub['id']}\n"
            f"<b>Сервис:</b> {sub['service_name']}\n"
            f"<b>Сумма:</b> {sub['amount']:.2f} {currency}\n"
            f"<b>До списания:</b> {days_left_display} дней\n"
            f"<b>Следующее списание:</b> {date_prefix}{date_human}\n"
            f"<b>Периодичность:</b> {period_human}"
        )

    await message.answer("\n".join(lines))


# --------- ДОБАВЛЕНИЕ ПОДПИСКИ ----------


@router.message(F.text == "➕ Добавить подписку")
async def add_subscription_start(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return

    await state.set_state(AddSubscriptionStates.service_name)
    await message.answer("Введите название сервиса:")


@router.message(AddSubscriptionStates.service_name)
async def add_subscription_service_name(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return

    await state.update_data(service_name=message.text.strip())
    await state.set_state(AddSubscriptionStates.amount)
    await message.answer("Введите сумму списания (число):")


@router.message(AddSubscriptionStates.amount)
async def add_subscription_amount(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return

    try:
        amount = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Некорректная сумма. Введите число, например: 199.99")
        return

    await state.update_data(amount=amount)
    await state.set_state(AddSubscriptionStates.currency)

    kb = InlineKeyboardBuilder()
    kb.button(text="RUB", callback_data="currency:RUB")
    kb.button(text="USD", callback_data="currency:USD")
    kb.adjust(2)
    await message.answer("Выберите валюту:", reply_markup=kb.as_markup())


@router.callback_query(AddSubscriptionStates.currency, F.data.startswith("currency:"))
async def add_subscription_currency(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        await callback.answer()
        return

    currency = callback.data.split(":", maxsplit=1)[1].upper()
    if currency not in {"RUB", "USD"}:
        await callback.answer("Неизвестная валюта", show_alert=True)
        return

    await state.update_data(currency=currency)
    await state.set_state(AddSubscriptionStates.next_payment_date)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Введите дату следующего списания в формате YYYY-MM-DD:")
    await callback.answer()


@router.message(AddSubscriptionStates.next_payment_date)
async def add_subscription_next_date(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return

    from datetime import datetime

    text = message.text.strip()
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        await message.answer("Некорректная дата. Укажите в формате YYYY-MM-DD, например: 2026-03-15")
        return

    await state.update_data(next_payment_date=text)
    await state.set_state(AddSubscriptionStates.periodicity)

    kb = InlineKeyboardBuilder()
    kb.button(text="1 месяц", callback_data="period:1_month")
    kb.button(text="3 месяца", callback_data="period:3_months")
    kb.button(text="6 месяцев", callback_data="period:6_months")
    kb.button(text="1 год", callback_data="period:1_year")
    kb.adjust(2, 2)

    await message.answer("Выберите периодичность:", reply_markup=kb.as_markup())


@router.callback_query(AddSubscriptionStates.periodicity, F.data.startswith("period:"))
async def add_subscription_periodicity(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        await callback.answer()
        return

    periodicity = callback.data.split(":", maxsplit=1)[1]
    data = await state.get_data()

    await add_subscription(
        service_name=data["service_name"],
        amount=data["amount"],
        currency=data["currency"],
        next_payment_date=data["next_payment_date"],
        periodicity=periodicity,
    )

    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("✅ Подписка успешно добавлена.", reply_markup=MAIN_MENU_KB)
    await callback.answer()


# --------- ИЗМЕНЕНИЕ ПОДПИСКИ ----------


async def _build_subscriptions_inline_kb(prefix: str) -> Optional[InlineKeyboardBuilder]:
    subscriptions = await get_all_subscriptions()
    if not subscriptions:
        return None

    kb = InlineKeyboardBuilder()
    for sub in subscriptions:
        text = f"{sub['id']}: {sub['service_name']} ({sub['next_payment_date']})"
        kb.button(text=text, callback_data=f"{prefix}:{sub['id']}")
    kb.adjust(1)
    return kb


@router.message(F.text == "🔁 Изменить подписку")
async def edit_subscription_start(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return

    kb = await _build_subscriptions_inline_kb(prefix="edit_sub")
    if not kb:
        await message.answer("Нет подписок для изменения.")
        return

    await state.set_state(EditSubscriptionStates.choosing_subscription)
    await message.answer("Выберите подписку для изменения:", reply_markup=kb.as_markup())


@router.callback_query(EditSubscriptionStates.choosing_subscription, F.data.startswith("edit_sub:"))
async def edit_subscription_choose(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        await callback.answer()
        return

    sub_id = int(callback.data.split(":", maxsplit=1)[1])
    sub = await get_subscription(sub_id)
    if not sub:
        await callback.answer("Подписка не найдена", show_alert=True)
        return

    await state.update_data(subscription_id=sub_id)
    await state.set_state(EditSubscriptionStates.choosing_field)

    kb = InlineKeyboardBuilder()
    kb.button(text="Название", callback_data="edit_field:service_name")
    kb.button(text="Сумма", callback_data="edit_field:amount")
    kb.button(text="Валюта", callback_data="edit_field:currency")
    kb.button(text="Дата", callback_data="edit_field:next_payment_date")
    kb.button(text="Периодичность", callback_data="edit_field:periodicity")
    kb.adjust(2, 2, 1)

    await callback.message.edit_text(
        f"Вы выбрали подписку:\n"
        f"<b>{sub['service_name']}</b> (ID: {sub['id']})\n\n"
        "Что хотите изменить?",
        reply_markup=kb.as_markup(),
    )
    await callback.answer()


@router.callback_query(EditSubscriptionStates.choosing_field, F.data.startswith("edit_field:"))
async def edit_subscription_choose_field(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        await callback.answer()
        return

    field = callback.data.split(":", maxsplit=1)[1]
    await state.update_data(field=field)

    if field == "periodicity":
        kb = InlineKeyboardBuilder()
        kb.button(text="1 месяц", callback_data="edit_period:1_month")
        kb.button(text="3 месяца", callback_data="edit_period:3_months")
        kb.button(text="6 месяцев", callback_data="edit_period:6_months")
        kb.button(text="1 год", callback_data="edit_period:1_year")
        kb.adjust(2, 2)
        await callback.message.edit_text("Выберите новую периодичность:", reply_markup=kb.as_markup())
    elif field == "currency":
        kb = InlineKeyboardBuilder()
        kb.button(text="RUB", callback_data="edit_currency:RUB")
        kb.button(text="USD", callback_data="edit_currency:USD")
        kb.adjust(2)
        await callback.message.edit_text("Выберите новую валюту:", reply_markup=kb.as_markup())
    else:
        await callback.message.edit_text(
            "Введите новое значение:\n"
            "- Для названия — текст\n"
            "- Для суммы — число\n"
            "- Для даты — формат YYYY-MM-DD"
        )
        await state.set_state(EditSubscriptionStates.editing_value)

    await callback.answer()


@router.callback_query(EditSubscriptionStates.choosing_field, F.data.startswith("edit_period:"))
async def edit_subscription_period(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        await callback.answer()
        return

    data = await state.get_data()
    sub_id = data.get("subscription_id")
    if sub_id is None:
        await callback.answer("Состояние устарело, начните заново.", show_alert=True)
        await state.clear()
        return

    periodicity = callback.data.split(":", maxsplit=1)[1]
    await update_subscription_field(subscription_id=sub_id, field="periodicity", value=periodicity)
    await state.clear()

    await callback.message.edit_text("✅ Периодичность обновлена.", reply_markup=None)
    await callback.answer()


@router.callback_query(EditSubscriptionStates.choosing_field, F.data.startswith("edit_currency:"))
async def edit_subscription_currency(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        await callback.answer()
        return

    data = await state.get_data()
    sub_id = data.get("subscription_id")
    if sub_id is None:
        await callback.answer("Состояние устарело, начните заново.", show_alert=True)
        await state.clear()
        return

    currency = callback.data.split(":", maxsplit=1)[1].upper()
    if currency not in {"RUB", "USD"}:
        await callback.answer("Неизвестная валюта", show_alert=True)
        return

    await update_subscription_field(subscription_id=sub_id, field="currency", value=currency)
    await state.clear()

    await callback.message.edit_text("✅ Валюта обновлена.", reply_markup=None)
    await callback.answer()


@router.message(EditSubscriptionStates.editing_value)
async def edit_subscription_apply_value(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return

    from datetime import datetime

    data = await state.get_data()
    sub_id = data.get("subscription_id")
    field = data.get("field")

    if sub_id is None or field is None:
        await message.answer("Состояние устарело, начните заново.")
        await state.clear()
        return

    value_raw = message.text.strip()
    value: object

    if field == "amount":
        try:
            value = float(value_raw.replace(",", "."))
        except ValueError:
            await message.answer("Некорректная сумма. Введите число, например: 199.99")
            return
    elif field == "next_payment_date":
        try:
            datetime.strptime(value_raw, "%Y-%m-%d")
        except ValueError:
            await message.answer("Некорректная дата. Укажите в формате YYYY-MM-DD, например: 2026-03-15")
            return
        value = value_raw
    else:
        value = value_raw

    await update_subscription_field(subscription_id=sub_id, field=field, value=value)
    await state.clear()
    await message.answer("✅ Подписка обновлена.", reply_markup=MAIN_MENU_KB)


# --------- УДАЛЕНИЕ ПОДПИСКИ ----------


@router.message(F.text == "❌ Удалить подписку")
async def delete_subscription_start(message: Message, state: FSMContext) -> None:
    if not _admin_only_message(message):
        return

    kb = await _build_subscriptions_inline_kb(prefix="del_sub")
    if not kb:
        await message.answer("Нет подписок для удаления.")
        return

    await state.set_state(DeleteSubscriptionStates.choosing_subscription)
    await message.answer("Выберите подписку для удаления:", reply_markup=kb.as_markup())


@router.callback_query(DeleteSubscriptionStates.choosing_subscription, F.data.startswith("del_sub:"))
async def delete_subscription_choose(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        await callback.answer()
        return

    sub_id = int(callback.data.split(":", maxsplit=1)[1])
    sub = await get_subscription(sub_id)
    if not sub:
        await callback.answer("Подписка не найдена", show_alert=True)
        return

    await state.update_data(subscription_id=sub_id)
    await state.set_state(DeleteSubscriptionStates.confirming)

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, удалить", callback_data="confirm_del:yes")
    kb.button(text="✖️ Отмена", callback_data="confirm_del:no")
    kb.adjust(2)

    await callback.message.edit_text(
        f"Вы уверены, что хотите удалить подписку:\n"
        f"<b>{sub['service_name']}</b> (ID: {sub['id']})?",
        reply_markup=kb.as_markup(),
    )
    await callback.answer()


@router.callback_query(DeleteSubscriptionStates.confirming, F.data.startswith("confirm_del:"))
async def delete_subscription_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    if not _admin_only_callback(callback):
        await callback.answer()
        return

    answer = callback.data.split(":", maxsplit=1)[1]
    data = await state.get_data()
    sub_id = data.get("subscription_id")

    if answer == "yes" and sub_id is not None:
        await delete_subscription(sub_id)
        await callback.message.edit_text("✅ Подписка удалена.")
    else:
        await callback.message.edit_text("Отмена удаления.")

    await state.clear()
    await callback.answer()

