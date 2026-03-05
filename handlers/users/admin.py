import asyncio
import logging
from aiogram import types
from aiogram.dispatcher import FSMContext

from loader import dp, bot
from data.config import ADMINS, DRF_URL
from states.mock_states import AdminStates
from utils.db_api.crud import get_user, activate_premium, get_all_users
from keyboards.inline.mock_keyboards import admin_confirm_premium
from keyboards.default.main_menu import main_menu
from services.drf_client import (
    get_global_stats, get_required_channels, add_required_channel,
    remove_required_channel, set_channel_bot_admin, cancel_user_premium,
    get_app_settings, update_app_settings
)

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return str(user_id) in ADMINS


# ─── ADMIN PANEL ──────────────────────────────────────────────────────────────

@dp.message_handler(commands=["admin"])
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    stats = await get_global_stats()
    channels = await get_required_channels()
    settings = await get_app_settings()

    active_channels = [c for c in channels if c.get('is_active')]
    ch_list = ""
    for ch in active_channels[:5]:
        admin_icon = "✅" if ch.get('is_bot_admin') else "⚠️"
        ch_list += f"  {admin_icon} @{ch['channel_username']}\n"
    if not ch_list:
        ch_list = "  <i>Yo'q</i>\n"

    await message.answer(
        "🔐 <b>Admin Panel</b>\n\n"

        "📊 <b>Statistika:</b>\n"
        f"  👥 Jami users: <b>{stats.get('total_users', '?')}</b>\n"
        f"  💎 Premium: <b>{stats.get('premium_users', '?')}</b>\n"
        f"  🆓 Bepul: <b>{stats.get('free_users', '?')}</b>\n"
        f"  🟢 Bugun faol: <b>{stats.get('today_active', '?')}</b>\n"
        f"  📞 Bugun suhbatlar: <b>{stats.get('today_calls', '?')}</b>\n"
        f"  📞 Jami suhbatlar: <b>{stats.get('total_calls', '?')}</b>\n\n"

        "⚙️ <b>Sozlamalar:</b>\n"
        f"  🆓 Bepul qo'ng'iroqlar: <b>{settings.get('free_calls_limit', '?')}</b>\n"
        f"  🎁 Referal uchun: <b>{settings.get('referrals_for_premium', '?')}</b> ta\n"
        f"  📅 Referal premium: <b>{settings.get('referral_premium_days', '?')}</b> kun\n\n"

        "📡 <b>Kanallar:</b>\n"
        f"{ch_list}\n"

        "📋 <b>Buyruqlar:</b>\n"
        "/stats — batafsil statistika\n"
        "/channels — kanallarni boshqarish\n"
        "/give_premium — premium berish\n"
        "/cancel_premium — premiumni bekor qilish\n"
        "/set_free_limit &lt;n&gt; — bepul qo'ng'iroq limiti\n"
        "/set_ref_count &lt;n&gt; — referal soni\n"
        "/broadcast — hammaga xabar yuborish\n"
        "/web_app — Web App URL"
    )


# ─── STATS ────────────────────────────────────────────────────────────────────

@dp.message_handler(commands=["stats"])
async def admin_stats(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    stats = await get_global_stats()
    users = await get_all_users()

    # Bot local stats
    premium_local = sum(1 for u in users if u.is_premium)

    await message.answer(
        "📊 <b>Batafsil Statistika</b>\n\n"
        f"<b>Web App (Django):</b>\n"
        f"  👥 Jami users: {stats.get('total_users', '?')}\n"
        f"  💎 Premium: {stats.get('premium_users', '?')}\n"
        f"  🟢 Bugun faol: {stats.get('today_active', '?')}\n"
        f"  📞 Jami suhbatlar: {stats.get('total_calls', '?')}\n"
        f"  📞 Bugun suhbatlar: {stats.get('today_calls', '?')}\n\n"
        f"<b>Telegram Bot (lokal):</b>\n"
        f"  👥 Jami: {len(users)}\n"
        f"  💎 Premium: {premium_local}\n"
        f"  🆓 Bepul: {len(users) - premium_local}"
    )


# ─── CHANNELS ─────────────────────────────────────────────────────────────────

@dp.message_handler(commands=["channels"])
async def admin_channels(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    channels = await get_required_channels()

    if not channels:
        await message.answer(
            "📡 <b>Majburiy Kanallar</b>\n\n"
            "Hozircha kanallar yo'q.\n\n"
            "<b>Qo'shish:</b>\n"
            "<code>/addchannel @username Kanal nomi</code>"
        )
        return

    text = "📡 <b>Majburiy Kanallar:</b>\n\n"
    for ch in channels:
        status = "✅ Faol" if ch.get('is_active') else "❌ Nofaol"
        bot_admin = "🤖 Bot admin" if ch.get('is_bot_admin') else "⚠️ Bot admin emas"
        text += (
            f"<b>{ch['channel_title']}</b>\n"
            f"  📎 @{ch['channel_username']}\n"
            f"  {status} · {bot_admin}\n\n"
        )

    text += (
        "<b>Boshqarish:</b>\n"
        "<code>/addchannel @username Kanal nomi</code>\n"
        "<code>/removechannel @username</code>\n"
        "<code>/checkbot @username</code> — bot admin ekanligini tekshir"
    )

    await message.answer(text)


@dp.message_handler(lambda msg: msg.text and msg.text.startswith("/addchannel"))
async def add_channel(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.strip().split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            "❌ Format: <code>/addchannel @username Kanal nomi</code>\n"
            "Misol: <code>/addchannel @my_channel English Practice</code>"
        )
        return

    username = parts[1].lstrip("@")
    title = parts[2]
    link = f"https://t.me/{username}"

    result = await add_required_channel(username, title, link)
    if result.get('ok'):
        created = result.get('created', True)
        action = "qo'shildi" if created else "yangilandi"
        await message.answer(
            f"✅ Kanal {action}!\n"
            f"📎 @{username} — <b>{title}</b>\n\n"
            f"⚠️ Eslatma: Bot kanalda admin bo'lishi uchun uni kanalga admin qiling!"
        )
    else:
        await message.answer("❌ Xato yuz berdi.")


@dp.message_handler(lambda msg: msg.text and msg.text.startswith("/removechannel"))
async def remove_channel(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("❌ Format: <code>/removechannel @username</code>")
        return

    username = parts[1].lstrip("@")
    result = await remove_required_channel(username)
    if result.get('ok'):
        await message.answer(f"✅ @{username} kanali o'chirildi.")
    else:
        await message.answer("❌ Xato yuz berdi.")


@dp.message_handler(lambda msg: msg.text and msg.text.startswith("/checkbot"))
async def check_bot_admin(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("❌ Format: <code>/checkbot @username</code>")
        return

    username = parts[1].lstrip("@")
    try:
        chat_member = await bot.get_chat_member(f"@{username}", (await bot.get_me()).id)
        is_bot_admin = chat_member.status in ['administrator', 'creator']
        await set_channel_bot_admin(username, is_bot_admin)

        if is_bot_admin:
            await message.answer(f"✅ Bot @{username} kanalida <b>admin</b>!")
        else:
            await message.answer(
                f"⚠️ Bot @{username} kanalida <b>admin emas</b>.\n"
                f"Botni kanalga admin qiling, so'ng qayta tekshiring."
            )
    except Exception as e:
        await set_channel_bot_admin(username, False)
        await message.answer(f"❌ Tekshirib bo'lmadi: {e}\nBot kanalda admin emas bo'lishi mumkin.")


# ─── SETTINGS ─────────────────────────────────────────────────────────────────

@dp.message_handler(lambda msg: msg.text and msg.text.startswith("/set_free_limit"))
async def set_free_limit(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("❌ Format: <code>/set_free_limit 3</code>")
        return
    try:
        n = int(parts[1])
        result = await update_app_settings(free_calls_limit=n)
        if result.get('ok'):
            await message.answer(f"✅ Bepul qo'ng'iroqlar limiti: <b>{n}</b> ga o'rnatildi.")
        else:
            await message.answer("❌ Xato.")
    except ValueError:
        await message.answer("❌ Raqam kiriting.")


@dp.message_handler(lambda msg: msg.text and msg.text.startswith("/set_ref_count"))
async def set_ref_count(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("❌ Format: <code>/set_ref_count 3</code>")
        return
    try:
        n = int(parts[1])
        result = await update_app_settings(referrals_for_premium=n)
        if result.get('ok'):
            await message.answer(f"✅ Premium uchun referal soni: <b>{n}</b> ga o'rnatildi.")
        else:
            await message.answer("❌ Xato.")
    except ValueError:
        await message.answer("❌ Raqam kiriting.")


@dp.message_handler(commands=["web_app"])
async def show_webapp_url(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    from data.config import WEBAPP_URL
    if WEBAPP_URL:
        await message.answer(f"🌐 Web App URL:\n<code>{WEBAPP_URL}</code>")
    else:
        await message.answer(
            "⚠️ WEBAPP_URL sozlanmagan.\n"
            ".env faylga qo'shing:\n<code>WEBAPP_URL=https://yourdomain.com/webapp/</code>"
        )


# ─── PREMIUM BERISH ───────────────────────────────────────────────────────────

@dp.message_handler(commands=["give_premium"])
async def admin_give_premium(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.set_state(AdminStates.waiting_user_id)
    await message.answer(
        "👤 Foydalanuvchi <b>Telegram ID</b>sini yuboring:\n"
        "<i>(ID ni bilish uchun /users buyrug'idan foydalaning)</i>"
    )


@dp.message_handler(state=AdminStates.waiting_user_id)
async def receive_user_id(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Noto'g'ri ID. Faqat raqam yuboring.")
        return

    user = await get_user(user_id)
    if not user:
        await message.answer(f"❌ ID: {user_id} — bu foydalanuvchi botda ro'yxatdan o'tmagan.")
        await state.finish()
        return

    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminStates.confirming_premium)

    username = user.username or "yo'q"
    premium_status = "✅ Ha" if user.is_premium else "❌ Yo'q"

    await message.answer(
        f"👤 Foydalanuvchi:\n"
        f"  Ismi: <b>{user.full_name}</b>\n"
        f"  Username: @{username}\n"
        f"  ID: <code>{user.telegram_id}</code>\n"
        f"  Premium: {premium_status}\n\n"
        f"<b>1 oylik premium ochasizmi?</b>",
        reply_markup=admin_confirm_premium(user_id)
    )


@dp.callback_query_handler(lambda c: c.data.startswith("confirm_premium:"), state=AdminStates.confirming_premium)
async def confirm_premium_activation(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return

    user_id = int(call.data.split(":")[1])
    success = await activate_premium(user_id, days=30)
    await state.finish()

    if success:
        await call.message.edit_text(
            f"✅ <b>Premium faollashtirildi!</b>\n"
            f"👤 User ID: <code>{user_id}</code>\n"
            f"⏰ 1 oylik premium berildi."
        )
        try:
            await call.bot.send_message(
                user_id,
                "🎉 <b>Tabriklaymiz!</b>\n\n"
                "💎 <b>Premium</b> hisobingizga qo'shildi!\n"
                "Endi siz cheksiz qo'ng'iroq qiling va o'sing! 🚀\n\n"
                "<i>Muddati: 30 kun</i>"
            )
        except Exception:
            pass
    else:
        await call.message.edit_text("❌ Xato yuz berdi.")


@dp.callback_query_handler(lambda c: c.data == "cancel_premium", state=AdminStates.confirming_premium)
async def cancel_premium_confirmation(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await call.message.edit_text("❌ Bekor qilindi.")


# ─── PREMIUM BEKOR QILISH ─────────────────────────────────────────────────────

@dp.message_handler(lambda msg: msg.text and msg.text.startswith("/cancel_premium"))
async def admin_cancel_premium(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("❌ Format: <code>/cancel_premium TELEGRAM_ID</code>")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Noto'g'ri ID.")
        return

    # Cancel in Django DB
    result = await cancel_user_premium(target_id)
    # Also cancel in local DB
    local_user = await get_user(target_id)
    if local_user:
        from utils.db_api.crud import deactivate_premium
        try:
            await deactivate_premium(target_id)
        except Exception:
            pass

    if result.get('ok'):
        username = result.get('username', str(target_id))
        await message.answer(f"✅ @{username} (<code>{target_id}</code>) premiumı bekor qilindi.")
        try:
            await bot.send_message(
                target_id,
                "ℹ️ Sizning premium obunangiz admin tomonidan bekor qilindi.\n"
                "Savollar bo'lsa /premium orqali murojaat qiling."
            )
        except Exception:
            pass
    else:
        await message.answer(f"❌ Xato: {result.get('error', 'User topilmadi')}")


# ─── USERS COUNT ──────────────────────────────────────────────────────────────

@dp.message_handler(commands=["users"])
async def admin_users_count(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    users = await get_all_users()
    premium_count = sum(1 for u in users if u.is_premium)

    await message.answer(
        f"📊 <b>Bot statistikasi:</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{len(users)}</b>\n"
        f"💎 Premium: <b>{premium_count}</b>\n"
        f"🆓 Bepul: <b>{len(users) - premium_count}</b>"
    )


# ─── PREMIUM TASDIQLASH (receipt orqali) ──────────────────────────────────────

PLAN_DAYS = {"1": 30, "3": 90, "12": 365}
PLAN_NAMES = {"1": "1 oy", "3": "3 oy", "12": "1 yil"}


@dp.message_handler(lambda msg: msg.text and msg.text.startswith("/grant_"))
async def grant_premium(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.strip().split("_")
    if len(parts) < 3:
        await message.answer("❌ Format: /grant_USERID_PLANKEY")
        return

    try:
        user_id = int(parts[1])
        plan_key = parts[2]
    except (ValueError, IndexError):
        await message.answer("❌ Noto'g'ri format. Misol: /grant_123456_1")
        return

    days = PLAN_DAYS.get(plan_key, 30)
    plan_name = PLAN_NAMES.get(plan_key, "1 oy")

    success = await activate_premium(user_id, days=days)
    if success:
        await message.answer(
            f"✅ <b>Premium faollashtirildi!</b>\n"
            f"👤 User ID: <code>{user_id}</code>\n"
            f"📅 Reja: {plan_name} ({days} kun)"
        )
        try:
            await bot.send_message(
                user_id,
                "🎉 <b>Tabriklaymiz!</b>\n\n"
                f"💎 <b>{plan_name} Premium</b> hisobingizga qo'shildi!\n"
                "Endi siz cheksiz qo'ng'iroq qiling va o'sing! 🚀",
                reply_markup=main_menu(is_premium=True)
            )
        except Exception as e:
            print(f"Grant notify error: {e}")
    else:
        await message.answer(f"❌ Xato: User ID {user_id} topilmadi.")


# ─── BROADCAST ────────────────────────────────────────────────────────────────

@dp.message_handler(commands=["broadcast"])
async def admin_broadcast_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.set_state(AdminStates.broadcast_message)
    await message.answer(
        "📢 <b>Broadcast</b>\n\n"
        "Barcha foydalanuvchilarga yuboriladigan xabarni yuboring.\n\n"
        "HTML formatlash qo'llab-quvvatlanadi:\n"
        "<code>&lt;b&gt;qalin&lt;/b&gt;</code> · <code>&lt;i&gt;kursiv&lt;/i&gt;</code> · "
        "<code>&lt;code&gt;kod&lt;/code&gt;</code>\n\n"
        "/cancel — bekor qilish"
    )


@dp.message_handler(commands=["cancel"], state=AdminStates.broadcast_message)
async def admin_broadcast_cancel(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.finish()
    await message.answer("❌ Broadcast bekor qilindi.")


@dp.message_handler(state=AdminStates.broadcast_message, content_types=types.ContentTypes.TEXT)
async def admin_broadcast_send(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.finish()
    text = message.text.strip()

    if text.startswith('/'):
        await message.answer("❌ Xabar oddiy matn bo'lishi kerak.")
        return

    all_users = await get_all_users()
    tg_users = [u for u in all_users if u.telegram_id]

    status_msg = await message.answer(
        f"⏳ Yuborilmoqda... 0 / {len(tg_users)}"
    )

    sent = failed = 0
    BATCH = 30  # har bir batch da 30 ta parallel

    async def send_one(u):
        try:
            await bot.send_message(u.telegram_id, text, parse_mode='HTML')
            return True
        except Exception:
            return False

    for i in range(0, len(tg_users), BATCH):
        batch = tg_users[i:i + BATCH]
        results = await asyncio.gather(*[send_one(u) for u in batch])
        sent += sum(results)
        failed += len(results) - sum(results)

        if i + BATCH < len(tg_users):
            try:
                await status_msg.edit_text(
                    f"⏳ Yuborilmoqda... {min(i + BATCH, len(tg_users))} / {len(tg_users)}"
                )
            except Exception:
                pass
        await asyncio.sleep(0.1)  # Telegram flood limit

    await status_msg.edit_text(
        f"✅ <b>Broadcast yakunlandi!</b>\n\n"
        f"📤 Yuborildi: <b>{sent}</b>\n"
        f"❌ Xato: <b>{failed}</b>\n"
        f"👥 Jami: <b>{len(tg_users)}</b>"
    )


# ─── KANAL ORQALI PREMIUM TASDIQLASH ─────────────────────────────────────────

PLAN_DAYS_CH = {"1": 30, "3": 90, "12": 365}
PLAN_NAMES_CH = {"1": "1 oy", "3": "3 oy", "12": "1 yil"}


@dp.callback_query_handler(lambda c: c.data.startswith("channel_confirm_premium:"))
async def channel_confirm_premium(call: types.CallbackQuery):
    """Admin kanalda ✅ Tasdiqlash tugmasini bosganda"""
    parts = call.data.split(":")
    if len(parts) < 3:
        await call.answer("Noto'g'ri format")
        return

    try:
        user_id = int(parts[1])
        plan_key = parts[2]
    except (ValueError, IndexError):
        await call.answer("Noto'g'ri format")
        return

    days = PLAN_DAYS_CH.get(plan_key, 30)
    plan_name = PLAN_NAMES_CH.get(plan_key, "1 oy")

    success = await activate_premium(user_id, days=days)
    if success:
        # Kanaldagi xabarni yangilash
        try:
            await call.message.edit_caption(
                call.message.caption + f"\n\n✅ <b>Tasdiqlandi!</b> Admin: {call.from_user.full_name}",
                reply_markup=None
            )
        except Exception:
            pass

        # Foydalanuvchiga xabar
        try:
            await bot.send_message(
                user_id,
                f"🎉 <b>Tabriklaymiz!</b>\n\n"
                f"💎 <b>{plan_name} Premium</b> hisobingizga qo'shildi!\n"
                f"Endi siz cheksiz qo'ng'iroq qiling va o'sing! 🚀",
                reply_markup=main_menu(is_premium=True)
            )
        except Exception as e:
            logger.warning(f"Premium notify error: {e}")
        await call.answer(f"✅ Premium faollashtirildi! User ID: {user_id}", show_alert=True)
    else:
        await call.answer("❌ Xato: foydalanuvchi topilmadi", show_alert=True)


@dp.callback_query_handler(lambda c: c.data.startswith("channel_reject_premium:"))
async def channel_reject_premium(call: types.CallbackQuery):
    """Admin kanalda ❌ Rad etish tugmasini bosganda"""
    parts = call.data.split(":")
    if len(parts) < 2:
        await call.answer("Noto'g'ri format")
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await call.answer("Noto'g'ri format")
        return

    try:
        await call.message.edit_caption(
            call.message.caption + f"\n\n❌ <b>Rad etildi.</b> Admin: {call.from_user.full_name}",
            reply_markup=None
        )
    except Exception:
        pass

    try:
        await bot.send_message(
            user_id,
            "❌ <b>Premium so'rovingiz rad etildi.</b>\n\n"
            "To'lov tasdiqlanmadi. Iltimos, to'g'ri chek yuboring yoki admin bilan bog'laning."
        )
    except Exception as e:
        logger.warning(f"Reject notify error: {e}")
    await call.answer("❌ Rad etildi", show_alert=True)


@dp.message_handler(lambda msg: msg.text and msg.text.startswith("/reject_"))
async def reject_premium(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.strip().split("_")
    if len(parts) < 2:
        await message.answer("❌ Format: /reject_USERID")
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Noto'g'ri format. Misol: /reject_123456")
        return

    await message.answer(
        f"❌ <b>So'rov rad etildi.</b>\n"
        f"👤 User ID: <code>{user_id}</code>"
    )
    try:
        await bot.send_message(
            user_id,
            "❌ <b>Premium so'rovingiz rad etildi.</b>\n\n"
            "To'lov tasdiqlanmadi. Iltimos, to'g'ri chek yuboring yoki admin bilan bog'laning.",
        )
    except Exception as e:
        print(f"Reject notify error: {e}")
