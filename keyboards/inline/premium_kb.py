from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def channel_confirm_kb(user_id: int, plan_key: str):
    """Premium tasdiqlash kanalida ko'rsatiladigan admin tugmalari"""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.row(
        InlineKeyboardButton(
            "✅ Tasdiqlash",
            callback_data=f"channel_confirm_premium:{user_id}:{plan_key}"
        ),
        InlineKeyboardButton(
            "❌ Rad etish",
            callback_data=f"channel_reject_premium:{user_id}"
        )
    )
    return kb
