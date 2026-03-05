from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def confirm_start_mock(mock_type: str):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Boshlash", callback_data=f"start_mock:{mock_type}"))
    kb.add(InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_mock"))
    return kb


def stop_mock_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⏹ Mockni to'xtatish", callback_data="stop_mock"))
    return kb


def premium_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("💎 Premium narxini ko'rish", callback_data="show_premium_price"))
    kb.add(InlineKeyboardButton("📸 To'lov screenshotini yuborish", callback_data="send_payment"))
    return kb


def admin_confirm_premium(user_id: int):
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("✅ Ha, ochish", callback_data=f"confirm_premium:{user_id}"),
        InlineKeyboardButton("❌ Yo'q", callback_data="cancel_premium")
    )
    return kb
