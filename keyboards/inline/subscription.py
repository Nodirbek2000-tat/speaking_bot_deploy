from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from data.config import CHANNEL_LINK


def subscribe_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=CHANNEL_LINK))
    kb.add(InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub"))
    return kb
