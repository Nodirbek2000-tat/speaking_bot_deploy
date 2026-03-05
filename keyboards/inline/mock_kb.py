# keyboards/inline/mock_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# ── IELTS Mock Test boshlash tugmasi ─────────────────────────────
def ielts_start_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("▶️ Boshlash", callback_data="ielts_start"))
    return kb


# ── Part 1 / Part 2 / Part 3 keyingi savol tugmasi ─────────────
def ielts_next_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📝 Keyingi savol", callback_data="ielts_next"))
    return kb


# ── Part 2 cue card tugmasi (tayyor bo‘lgach) ─────────────────
def ielts_part2_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Tayyor", callback_data="ielts_part2_done"))
    return kb


# ── IELTS Mock test tugatish / finish tugmasi ─────────────────
def ielts_finish_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🏠 Asosiy menyu", callback_data="main_menu"))
    return kb


# ── Asosiy menyu uchun tugmalar ────────────────────────────────
def main_menu_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📝 IELTS Mock", callback_data="ielts_start"))
    kb.add(InlineKeyboardButton("⚡ Boshqa xizmatlar", callback_data="other_services"))
    return kb