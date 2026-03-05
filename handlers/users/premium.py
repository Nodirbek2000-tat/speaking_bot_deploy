import logging
from aiogram import types
from aiogram.dispatcher import FSMContext
from loader import dp, bot
from utils.db_api.crud import get_user
from data.config import OWNER_USERNAME, ADMINS, PAYMENT_CHANNEL, BOT_USERNAME
from keyboards.default.main_menu import main_menu
from keyboards.inline.premium_kb import channel_confirm_kb
from states.mock_states import PremiumPurchase
from services.drf_client import log_bot_activity, get_payment_card_info, create_premium_request_drf

logger = logging.getLogger(__name__)


@dp.message_handler(commands=["premium"])
@dp.message_handler(text="💎 Premium")
async def premium_info(message: types.Message):
    user = await get_user(message.from_user.id)

    if user and user.is_premium:
        exp = user.premium_expires.strftime('%d.%m.%Y') if user.premium_expires else "∞"
        await message.answer(
            f"💎 <b>Siz PREMIUM foydalanuvchisiz!</b>\n\n"
            f"✅ Cheksiz IELTS va CEFR mock\n"
            f"✅ Cheksiz AI suhbat\n"
            f"✅ Barcha funksiyalar ochiq\n\n"
            f"📅 Tugash sanasi: <b>{exp}</b>"
        )
        return

    # DRF dan karta va narx olish
    card_data = await get_payment_card_info()
    plan = card_data.get("plan") or {}
    card = card_data.get("card") or {}
    price_uzs = plan.get("price_uzs", 0)
    plan_id = plan.get("id", 1)
    price_text = f"{int(price_uzs):,} so'm".replace(",", " ") if price_uzs else "99 000 so'm"

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        f"📅 1 oy — {price_text}",
        callback_data=f"buy_premium:{plan_id}"
    ))

    await message.answer(
        "💎 <b>PREMIUM</b>\n\n"
        "<b>Premium imkoniyatlari:</b>\n"
        "✅ Cheksiz IELTS va CEFR mock testlar\n"
        "✅ Cheksiz AI suhbat\n"
        "✅ Batafsil tahlil va hisobotlar\n"
        "✅ Ovozli savollar va javoblar\n\n"
        f"<b>💰 1 oylik Premium — {price_text}</b>\n\n"
        "Sotib olish uchun tugmani bosing 👇",
        reply_markup=kb
    )


@dp.callback_query_handler(lambda c: c.data.startswith("buy_premium:"))
async def buy_premium_plan(call: types.CallbackQuery, state: FSMContext):
    plan_id_str = call.data.split(":")[1]
    try:
        plan_id = int(plan_id_str)
    except ValueError:
        await call.answer("Noto'g'ri reja!")
        return

    # DRF dan karta ma'lumotlarini olish
    card_data = await get_payment_card_info()
    plan = card_data.get("plan") or {}
    card = card_data.get("card") or {}

    price_uzs = plan.get("price_uzs", 0)
    price_text = f"{int(price_uzs):,} so'm".replace(",", " ") if price_uzs else "99 000 so'm"
    card_number = card.get("number", "—")
    card_owner = card.get("owner", "—")
    card_bank = card.get("bank", "")

    await state.update_data(plan_id=plan_id, price_uzs=price_uzs)

    bank_line = f"\n🏦 Bank: {card_bank}" if card_bank else ""

    await call.message.answer(
        f"💎 <b>1 oylik Premium — {price_text}</b>\n\n"
        f"<b>To'lov yo'riqnomasi:</b>\n\n"
        f"💳 Karta: <code>{card_number}</code>\n"
        f"👤 Egasi: {card_owner}{bank_line}\n"
        f"💰 Summa: <b>{price_text}</b>\n\n"
        f"<b>To'lovdan keyin:</b>\n"
        f"📸 To'lov cheki (screenshot) rasmini yuboring.\n\n"
        f"✅ Admin 1-2 soat ichida premiumingizni faollashtiradi!\n\n"
        f"<i>Savollar uchun: {OWNER_USERNAME}</i>"
    )
    await call.message.answer("📸 To'lov cheki rasmini yuboring:")
    await PremiumPurchase.waiting_receipt.set()
    await call.answer()


@dp.message_handler(state=PremiumPurchase.waiting_receipt, content_types=[types.ContentType.PHOTO, types.ContentType.TEXT])
async def process_receipt(message: types.Message, state: FSMContext):
    if message.text and message.text in ["❌", "/start"]:
        await state.finish()
        await message.answer("Bekor qilindi.", reply_markup=main_menu())
        return

    if message.content_type != types.ContentType.PHOTO:
        await message.answer("📸 Iltimos, to'lov cheki rasmini yuboring!")
        return

    data = await state.get_data()
    plan_id = data.get("plan_id", 1)
    price_uzs = data.get("price_uzs", 0)
    price_text = f"{int(price_uzs):,} so'm".replace(",", " ") if price_uzs else "Premium"

    photo = message.photo[-1]
    file_id = photo.file_id

    user = await get_user(message.from_user.id)
    username = f"@{message.from_user.username}" if message.from_user.username else str(message.from_user.id)

    caption = (
        f"💰 <b>Yangi Premium So'rov!</b>\n\n"
        f"👤 <b>Foydalanuvchi:</b> {message.from_user.full_name}\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"📱 Username: {username}\n"
        f"📅 Reja: <b>1 oy — {price_text}</b>\n\n"
        f"📸 Chek rasmi yuqorida\n\n"
        f"Tasdiqlash yoki rad etish uchun tugmalardan foydalaning:"
    )

    confirm_kb = channel_confirm_kb(message.from_user.id, str(plan_id))

    # 1. PAYMENT_CHANNEL ga yuborish
    channel_sent = False
    if PAYMENT_CHANNEL:
        try:
            await bot.send_photo(
                chat_id=PAYMENT_CHANNEL,
                photo=file_id,
                caption=caption,
                reply_markup=confirm_kb
            )
            channel_sent = True
        except Exception as e:
            logger.warning(f"Payment channel send error: {e}")

    # 2. Agar kanal yo'q bo'lsa — adminlarga yuborish
    if not channel_sent:
        for admin_id in ADMINS:
            try:
                await bot.send_photo(
                    chat_id=int(admin_id),
                    photo=file_id,
                    caption=caption,
                    reply_markup=confirm_kb
                )
            except Exception as e:
                logger.warning(f"Admin notify error: {e}")

    # 3. DRF ga PremiumPurchase yaratish
    try:
        drf_result = await create_premium_request_drf(
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username or "",
            receipt_file_id=file_id,
            plan_id=plan_id
        )
        logger.info(f"DRF premium request: {drf_result}")
    except Exception as e:
        logger.warning(f"DRF premium request error: {e}")

    # 4. Bot activity log
    await log_bot_activity(
        telegram_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username or "",
        activity_type="premium_request",
        data={
            "plan_id": plan_id,
            "price_uzs": price_uzs,
            "file_id": file_id,
        }
    )

    await message.answer(
        "✅ <b>So'rovingiz qabul qilindi!</b>\n\n"
        "📸 Chekingiz adminlarga yuborildi.\n"
        "⏳ Tez orada (1-2 soat ichida) premiumingiz faollashadi.\n\n"
        f"Savollar uchun: {OWNER_USERNAME}",
        reply_markup=main_menu()
    )
    await state.finish()
