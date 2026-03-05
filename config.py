from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import List

import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_ids: List[int]
    group_chat_id: int


@lru_cache
def get_settings() -> Settings:
    """
    Загрузка настроек из .env.
    ADMIN_IDS парсится как список int, разделитель — запятая.
    """
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not set in .env")

    raw_admin_ids = os.getenv("ADMIN_IDS", "")
    admin_ids: List[int] = []
    for item in raw_admin_ids.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            admin_ids.append(int(item))
        except ValueError:
            raise RuntimeError(f"Invalid ADMIN_IDS value: {item!r}. Must be integer IDs separated by commas.")

    if not admin_ids:
        raise RuntimeError("ADMIN_IDS is empty or not set in .env")

    raw_group_chat_id = os.getenv("GROUP_CHAT_ID")
    if not raw_group_chat_id:
        raise RuntimeError("GROUP_CHAT_ID is not set in .env")

    try:
        group_chat_id = int(raw_group_chat_id)
    except ValueError:
        raise RuntimeError("GROUP_CHAT_ID must be an integer")

    return Settings(
        bot_token=bot_token,
        admin_ids=admin_ids,
        group_chat_id=group_chat_id,
    )


def is_admin(user_id: int) -> bool:
    """
    Проверка, является ли пользователь администратором.
    """
    settings = get_settings()
    return user_id in settings.admin_ids

