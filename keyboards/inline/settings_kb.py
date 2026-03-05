from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

DAYS_UZ = {0: "Du", 1: "Se", 2: "Ch", 3: "Pa", 4: "Ju", 5: "Sh", 6: "Ya"}


def settings_main_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🔔 Eslatma qo'shish", callback_data="reminder_add"),
        InlineKeyboardButton("📋 Mening eslatmalarim", callback_data="reminder_list"),
    )
    return kb


def reminder_days_kb(selected: list = None):
    """Hafta kunlarini tanlash (ko'p tanlov)"""
    selected = selected or []
    kb = InlineKeyboardMarkup(row_width=4)
    row = []
    for day_num, day_name in DAYS_UZ.items():
        check = "✅" if day_num in selected else ""
        row.append(
            InlineKeyboardButton(
                f"{check}{day_name}",
                callback_data=f"rem_day:{day_num}"
            )
        )
    # 4 ta + 3 ta qator
    kb.row(*row[:4])
    kb.row(*row[4:])
    kb.add(InlineKeyboardButton("✅ Davom etish", callback_data="rem_days_done"))
    kb.add(InlineKeyboardButton("❌ Bekor qilish", callback_data="rem_cancel"))
    return kb


def reminder_hour_kb():
    """Soat tanlash (1-24)"""
    kb = InlineKeyboardMarkup(row_width=6)
    buttons = []
    for h in range(6, 24):
        buttons.append(InlineKeyboardButton(f"{h:02d}", callback_data=f"rem_hour:{h}"))
    # 6 ta bir qatorda
    for i in range(0, len(buttons), 6):
        kb.row(*buttons[i:i+6])
    kb.add(InlineKeyboardButton("❌ Bekor qilish", callback_data="rem_cancel"))
    return kb


def reminder_minute_kb():
    """Daqiqa tanlash"""
    kb = InlineKeyboardMarkup(row_width=3)
    minutes = [0, 10, 15, 20, 30, 45]
    buttons = [
        InlineKeyboardButton(f"{m:02d}", callback_data=f"rem_min:{m}")
        for m in minutes
    ]
    kb.row(*buttons[:3])
    kb.row(*buttons[3:])
    kb.add(InlineKeyboardButton("❌ Bekor qilish", callback_data="rem_cancel"))
    return kb


def reminder_list_kb(reminders: list):
    """Mavjud eslatmalar ro'yxati"""
    kb = InlineKeyboardMarkup(row_width=1)
    for r in reminders:
        import json
        days = json.loads(r.days_of_week or "[]")
        day_names = " ".join(DAYS_UZ.get(d, str(d)) for d in days)
        label = f"🔔 {day_names} — {r.hour:02d}:{r.minute:02d}"
        kb.add(InlineKeyboardButton(
            f"🗑 {label}",
            callback_data=f"rem_delete:{r.id}"
        ))
    kb.add(InlineKeyboardButton("➕ Yangi eslatma", callback_data="reminder_add"))
    kb.add(InlineKeyboardButton("🔙 Orqaga", callback_data="settings_back"))
    return kb
