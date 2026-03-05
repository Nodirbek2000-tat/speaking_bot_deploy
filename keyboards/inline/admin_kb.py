from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def admin_panel_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("👤 Premium berish", callback_data="admin_give_premium"),
        InlineKeyboardButton("📝 IELTS savol qo'sh", callback_data="admin_add_ielts"),
        InlineKeyboardButton("📊 CEFR savol qo'sh", callback_data="admin_add_cefr"),
        InlineKeyboardButton("📚 So'zlar JSON", callback_data="admin_add_words"),
        InlineKeyboardButton("📋 IELTS savollar", callback_data="admin_list_ielts"),
        InlineKeyboardButton("📋 CEFR savollar", callback_data="admin_list_cefr"),
        InlineKeyboardButton("📣 Xabar yuborish", callback_data="admin_broadcast"),
        InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"),
    )
    return kb


def ielts_part_kb():
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton("Part 1", callback_data="ielts_part:1"),
        InlineKeyboardButton("Part 2", callback_data="ielts_part:2"),
        InlineKeyboardButton("Part 3", callback_data="ielts_part:3"),
    )
    return kb


def cefr_part_select_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("Part 1", callback_data="cefr_part:1"),
        InlineKeyboardButton("Part 2 (rasm)", callback_data="cefr_part:2"),
        InlineKeyboardButton("Part 3 (compare)", callback_data="cefr_part:3"),
        InlineKeyboardButton("Part 4 (discussion)", callback_data="cefr_part:4"),
    )
    return kb


def confirm_premium_kb(user_id: int):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_prem:{user_id}"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_prem"),
    )
    return kb
