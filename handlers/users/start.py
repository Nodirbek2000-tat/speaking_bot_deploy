import logging
from aiogram import types
from aiogram.dispatcher import FSMContext

from loader import dp, bot
from utils.db_api.crud import get_or_create_user, save_phone_number
from keyboards.default.main_menu import main_menu
from states.mock_states import PhoneRequest
from services.drf_client import sync_user_phone, log_bot_activity
from data.config import BOT_USERNAME

logger = logging.getLogger(__name__)

WEBAPP_URL = None  # import from config


@dp.message_handler(commands=['start'], state='*')
async def start_handler(message: types.Message, state: FSMContext):
    await state.finish()

    args = message.get_args()
    ref_code = None

    # Web App premium deep link
    if args and args.startswith('buy_premium'):
        try:
            plan_id_str = args.split('_')[-1]
            plan_id = int(plan_id_str)
        except (ValueError, IndexError):
            plan_id = 1
        from handlers.users.premium import premium_info
        # Avval user yaratamiz
        user = await get_or_create_user(
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
            ref_code=None,
        )
        try:
            await log_bot_activity(
                telegram_id=message.from_user.id,
                full_name=message.from_user.full_name,
                username=message.from_user.username or '',
                activity_type='start',
                data={'first_name': message.from_user.first_name or ''}
            )
        except Exception:
            pass
        await premium_info(message)
        return

    if args and args.startswith('ref_'):
        ref_code = args[4:]

    user = await get_or_create_user(
        telegram_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username,
        ref_code=ref_code,
    )

    # ── DRF backend ga user sync qilish ──────────────────────────────────────
    try:
        await log_bot_activity(
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username or '',
            activity_type='start',
            data={
                'ref_code': ref_code or '',
                'first_name': message.from_user.first_name or '',
                'last_name': message.from_user.last_name or '',
            }
        )
    except Exception as e:
        logger.warning(f"DRF sync error on /start: {e}")

    # ── Telefon raqami yo'q bo'lsa → so'rash (majburiy) ──────────────────────
    if not user.phone_number:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        kb.add(types.KeyboardButton("📱 Telefon raqamni ulashish", request_contact=True))
        await message.answer(
            "👋 <b>Xush kelibsiz, Speaking Bot ga!</b>\n\n"
            "🔐 Botdan foydalanish uchun <b>telefon raqamingizni</b> ulashing.\n\n"
            "Bu faqat bir marta so'raladi va xavfsiz saqlanadi. 🔒",
            reply_markup=kb
        )
        await PhoneRequest.waiting_phone.set()
        return

    # ── Telefon bor → to'g'ridan menyu ───────────────────────────────────────
    await _welcome_user(message, user)


@dp.message_handler(content_types=types.ContentType.CONTACT, state=PhoneRequest.waiting_phone)
async def process_phone_contact(message: types.Message, state: FSMContext):
    """Foydalanuvchi o'zining kontaktini yuborgan"""
    contact = message.contact

    # Faqat o'zining raqamini qabul qilish
    if contact.user_id != message.from_user.id:
        await message.answer("⚠️ Iltimos, <b>o'zingizning</b> telefon raqamingizni ulashing.")
        return

    phone = contact.phone_number
    # +998... formatiga o'tkazish
    if not phone.startswith('+'):
        phone = '+' + phone

    # ── Lokal DB ga saqlash ───────────────────────────────────────────────────
    await save_phone_number(message.from_user.id, phone)

    # ── Django backend ga sync qilish ─────────────────────────────────────────
    try:
        await sync_user_phone(
            telegram_id=message.from_user.id,
            phone=phone,
            username=message.from_user.username or '',
            full_name=message.from_user.full_name,
            first_name=message.from_user.first_name or '',
            last_name=message.from_user.last_name or '',
        )
        logger.info(f"Phone synced to backend: {message.from_user.id}")
    except Exception as e:
        logger.warning(f"Phone sync error: {e}")

    await state.finish()

    # User ni qayta olib xush kelibsiz deyish
    from utils.db_api.crud import get_user
    user = await get_user(message.from_user.id)
    await _welcome_user(message, user)


@dp.message_handler(state=PhoneRequest.waiting_phone, content_types=types.ContentType.ANY)
async def phone_request_fallback(message: types.Message):
    """Telefon o'rniga boshqa narsa yuborganda"""
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(types.KeyboardButton("📱 Telefon raqamni ulashish", request_contact=True))
    await message.answer(
        "❗ Iltimos, pastdagi tugmani bosib telefon raqamingizni ulashing.\n\n"
        "Bunsiz botdan foydalana olmaysiz.",
        reply_markup=kb
    )


async def _welcome_user(message: types.Message, user):
    """Asosiy menyu ko'rsatish"""
    from data.config import WEBAPP_URL

    name = user.full_name.split()[0] if user.full_name else "Do'st"
    premium_text = "💎 Premium foydalanuvchi sifatida xush kelibsiz!" if user.is_premium else ""

    text = (
        f"👋 <b>Salom, {name}!</b>\n\n"
        f"🎤 <b>Speaking Bot</b> — ingliz tili gaplashish ko'nikmangizni oshiring!\n\n"
        f"📝 IELTS & CEFR mock testlar\n"
        f"🤖 AI Coach bilan amaliyot\n"
        f"🌐 Web App — full featured\n"
    )
    if premium_text:
        text += f"\n{premium_text}"

    await message.answer(text, reply_markup=main_menu(
        is_premium=user.is_premium,
        webapp_url=WEBAPP_URL,
    ))