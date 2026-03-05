from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def word_actions_kb(word: str, is_saved: bool = False):
    kb = InlineKeyboardMarkup(row_width=2)
    if not is_saved:
        kb.add(InlineKeyboardButton("🔖 Saqlash", callback_data=f"save_word:{word}"))
    else:
        kb.add(InlineKeyboardButton("✅ Saqlangan", callback_data="already_saved"))
    kb.row(
        InlineKeyboardButton("🗣 AI bilan muhokama", callback_data=f"discuss_word:{word}"),
        InlineKeyboardButton("💪 Mashq qilish", callback_data="vocab_practice"),
    )
    kb.add(InlineKeyboardButton("🔍 Boshqa so'z", callback_data="search_another"))
    return kb


def word_discuss_kb(word: str):
    """So'z muhokamasi davomida ko'rsatiladigan klaviatura"""
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🔙 So'z kartasiga qaytish", callback_data=f"back_to_word:{word}"))
    return kb


def saved_words_nav_kb(index: int, total: int, word: str):
    kb = InlineKeyboardMarkup(row_width=3)
    row = []
    if index > 0:
        row.append(InlineKeyboardButton("⬅️", callback_data=f"saved_nav:{index-1}"))
    row.append(InlineKeyboardButton(f"{index+1}/{total}", callback_data="saved_count"))
    if index < total - 1:
        row.append(InlineKeyboardButton("➡️", callback_data=f"saved_nav:{index+1}"))
    kb.row(*row)
    kb.add(InlineKeyboardButton("🗑 O'chirish", callback_data=f"del_word:{word}:{index}"))
    return kb


def vocab_quiz_kb(index: int, total: int):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🔊 Yana eshitish", callback_data=f"quiz_replay:{index}"),
        InlineKeyboardButton("➡️ Keyingisi", callback_data=f"quiz_next:{index}"),
    )
    kb.add(InlineKeyboardButton("❌ Mashqni tugatish", callback_data="quiz_stop"))
    return kb
