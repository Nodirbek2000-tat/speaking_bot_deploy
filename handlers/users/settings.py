import json
import logging
from aiogram import types
from aiogram.dispatcher import FSMContext

from loader import dp
from states.mock_states import SettingsStates
from keyboards.default.main_menu import main_menu
from keyboards.inline.settings_kb import (
    settings_main_kb, reminder_days_kb, reminder_hour_kb,
    reminder_minute_kb, reminder_list_kb, DAYS_UZ
)
from utils.db_api.crud import save_reminder, get_user_reminders, delete_reminder

logger = logging.getLogger(__name__)


@dp.message_handler(commands=["settings"])
@dp.message_handler(text="⚙️ Sozlamalar")
async def settings_menu(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer(
        "⚙️ <b>Sozlamalar</b>\n\n"
        "Bu yerda eslatma qo'shishingiz mumkin.\n"
        "Belgilangan vaqtda bot sizga o'qish eslatmasi yuboradi! 🔔",
        reply_markup=settings_main_kb()
    )


@dp.callback_query_handler(text="reminder_add")
@dp.callback_query_handler(text="reminder_add", state="*")
async def start_add_reminder(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(selected_days=[])
    await call.message.answer(
        "📅 <b>Eslatma kunlarini tanlang</b>\n\n"
        "Qaysi kunlarda eslatma olishni xohlaysiz?\n"
        "<i>(Bir necha kunni tanlashingiz mumkin)</i>",
        reply_markup=reminder_days_kb([])
    )
    await SettingsStates.reminder_days.set()
    await call.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("rem_day:"), state=SettingsStates.reminder_days)
async def toggle_reminder_day(call: types.CallbackQuery, state: FSMContext):
    day_num = int(call.data.split(":")[1])
    data = await state.get_data()
    selected = data.get("selected_days", [])

    if day_num in selected:
        selected.remove(day_num)
    else:
        selected.append(day_num)

    await state.update_data(selected_days=selected)
    await call.message.edit_reply_markup(reminder_days_kb(selected))
    await call.answer()


@dp.callback_query_handler(text="rem_days_done", state=SettingsStates.reminder_days)
async def days_done(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_days", [])

    if not selected:
        await call.answer("❗ Kamida bitta kun tanlang!", show_alert=True)
        return

    day_names = " ".join(DAYS_UZ.get(d, str(d)) for d in sorted(selected))
    await call.message.answer(
        f"✅ Kunlar tanlandi: <b>{day_names}</b>\n\n"
        f"🕐 Endi soatni tanlang:",
        reply_markup=reminder_hour_kb()
    )
    await SettingsStates.reminder_hour.set()
    await call.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("rem_hour:"), state=SettingsStates.reminder_hour)
async def set_reminder_hour(call: types.CallbackQuery, state: FSMContext):
    hour = int(call.data.split(":")[1])
    await state.update_data(reminder_hour=hour)
    await call.message.answer(
        f"⏰ Soat: <b>{hour:02d}:xx</b>\n\n"
        f"🕐 Endi daqiqani tanlang:",
        reply_markup=reminder_minute_kb()
    )
    await SettingsStates.reminder_minute.set()
    await call.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("rem_min:"), state=SettingsStates.reminder_minute)
async def set_reminder_minute(call: types.CallbackQuery, state: FSMContext):
    minute = int(call.data.split(":")[1])
    data = await state.get_data()
    selected_days = data.get("selected_days", [])
    hour = data.get("reminder_hour", 9)

    # Saqlash
    reminder = await save_reminder(
        user_id=call.from_user.id,
        days_of_week=sorted(selected_days),
        hour=hour,
        minute=minute
    )

    # Scheduler ga qo'shish
    try:
        from utils.scheduler import schedule_one_reminder
        schedule_one_reminder(reminder)
    except Exception as e:
        logger.warning(f"Schedule reminder error: {e}")

    day_names = " ".join(DAYS_UZ.get(d, str(d)) for d in sorted(selected_days))
    await call.message.answer(
        f"✅ <b>Eslatma saqlandi!</b>\n\n"
        f"📅 Kunlar: <b>{day_names}</b>\n"
        f"⏰ Vaqt: <b>{hour:02d}:{minute:02d}</b>\n\n"
        f"Har belgilangan vaqtda o'qish eslatmasi olasiz! 🔔",
        reply_markup=main_menu()
    )
    await state.finish()
    await call.answer()


@dp.callback_query_handler(text="rem_cancel", state="*")
async def cancel_reminder(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await call.message.answer("❌ Bekor qilindi.", reply_markup=main_menu())
    await call.answer()


@dp.callback_query_handler(text="reminder_list")
@dp.callback_query_handler(text="reminder_list", state="*")
async def show_reminder_list(call: types.CallbackQuery, state: FSMContext):
    reminders = await get_user_reminders(call.from_user.id)
    if not reminders:
        await call.message.answer(
            "📭 Sizda hali eslatma yo'q.\n"
            "Qo'shish uchun '🔔 Eslatma qo'shish' tugmasini bosing.",
            reply_markup=settings_main_kb()
        )
        await call.answer()
        return

    await call.message.answer(
        f"🔔 <b>Sizning eslatmalaringiz</b> ({len(reminders)} ta):\n\n"
        "O'chirish uchun eslatmaga bosing:",
        reply_markup=reminder_list_kb(reminders)
    )
    await call.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("rem_delete:"))
async def delete_reminder_cb(call: types.CallbackQuery):
    reminder_id = int(call.data.split(":")[1])

    # Scheduler dan o'chirish
    try:
        from utils.scheduler import remove_reminder_job
        remove_reminder_job(reminder_id)
    except Exception as e:
        logger.warning(f"Remove reminder job error: {e}")

    success = await delete_reminder(reminder_id)
    if success:
        await call.answer("✅ Eslatma o'chirildi!", show_alert=False)
        # Ro'yxatni yangilash
        reminders = await get_user_reminders(call.from_user.id)
        if reminders:
            await call.message.edit_reply_markup(reminder_list_kb(reminders))
        else:
            await call.message.edit_text(
                "📭 Barcha eslatmalar o'chirildi.",
                reply_markup=settings_main_kb()
            )
    else:
        await call.answer("❌ Xato yuz berdi")


@dp.callback_query_handler(text="settings_back")
async def settings_back(call: types.CallbackQuery):
    await call.message.edit_text(
        "⚙️ <b>Sozlamalar</b>\n\n"
        "Bu yerda eslatma qo'shishingiz mumkin.\n"
        "Belgilangan vaqtda bot sizga o'qish eslatmasi yuboradi! 🔔",
        reply_markup=settings_main_kb()
    )
    await call.answer()
