import asyncio
import logging
from io import BytesIO
from aiogram import types
from aiogram.dispatcher import FSMContext

from loader import dp
from states.mock_states import SpeakingChat
from keyboards.default.main_menu import main_menu
from services.ai_service import chat_with_coach, text_to_speech, analyze_tenses, analyze_speaking_session
from services.stt_service import voice_to_text
from utils.db_api.crud import log_activity, update_tense_stats
from services.drf_client import sync_tense_stats

logger = logging.getLogger(__name__)

COACH_PROFILES = {
    "male": {
        "name": "Alex",
        "voice": "echo",
        "system_prompt": (
            "You are Alex, a friendly and engaging male English speaking coach. "
            "Your job is to have a NATURAL CONVERSATION with the user. "
            "ALWAYS respond directly to what the user just said — ask follow-up questions, "
            "show interest, add your own thoughts. Do NOT just give generic encouragement. "
            "If user makes grammar mistakes, fix them naturally within your reply (not as a list). "
            "Keep responses to 2-3 sentences. If user speaks Uzbek, reply in English and "
            "gently encourage them to try in English."
        ),
        "greeting": "Hi! I'm Alex, your English speaking coach. What would you like to talk about today? 😊",
    },
    "female": {
        "name": "Emma",
        "voice": "nova",
        "system_prompt": (
            "You are Emma, a friendly and engaging female English speaking coach. "
            "Your job is to have a NATURAL CONVERSATION with the user. "
            "ALWAYS respond directly to what the user just said — ask follow-up questions, "
            "show interest, add your own thoughts. Do NOT just give generic encouragement. "
            "If user makes grammar mistakes, fix them naturally within your reply (not as a list). "
            "Keep responses to 2-3 sentences. If user speaks Uzbek, reply in English and "
            "gently encourage them to try in English."
        ),
        "greeting": "Hello! I'm Emma, your English speaking coach. What shall we talk about today? 😊",
    },
}


@dp.message_handler(text="🤖 AI Chat")
async def ai_chat_start(message: types.Message):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("👨 Male (Alex)", callback_data="gender:male"),
        types.InlineKeyboardButton("👩 Female (Emma)", callback_data="gender:female"),
    )
    await message.answer(
        "🤖 <b>AI Coach</b> bilan suhbat\n\n"
        "Qaysi coach bilan gaplashmoqchisiz?",
        reply_markup=kb
    )
    await SpeakingChat.selecting_gender.set()


@dp.callback_query_handler(lambda c: c.data.startswith("gender:"), state=SpeakingChat.selecting_gender)
async def gender_selected(call: types.CallbackQuery, state: FSMContext):
    gender = call.data.split(":")[1]
    profile = COACH_PROFILES.get(gender, COACH_PROFILES["male"])

    await state.update_data(
        gender=gender,
        history=[{"role": "system", "content": profile["system_prompt"]}],
        transcripts=[],
    )

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("❌ Suhbatni tugatish")

    await call.message.edit_reply_markup()
    await call.message.answer(
        f"🤖 <b>AI Coach {profile['name']}</b> bilan suhbat boshlandi!\n\n"
        "🎙 <b>Faqat ovozli xabar bilan gaplashing!</b>\n"
        f"{profile['name']} xatolaringizni natural ravishda to'g'rilaydi.\n\n"
        "❌ Chiqish uchun: <b>Suhbatni tugatish</b>",
        reply_markup=kb
    )

    greeting = profile["greeting"]
    await call.message.answer(greeting)

    audio_bytes = await text_to_speech(greeting, voice=profile["voice"])
    if audio_bytes:
        buf = BytesIO(audio_bytes)
        buf.name = "coach.ogg"
        await call.message.answer_voice(types.InputFile(buf))

    await SpeakingChat.chatting.set()
    await log_activity(call.from_user.id, ai_chat=True)
    await call.answer()


@dp.message_handler(
    state=SpeakingChat.chatting,
    content_types=[types.ContentType.TEXT, types.ContentType.VOICE]
)
async def ai_chat_message(message: types.Message, state: FSMContext):
    data = await state.get_data()
    gender = data.get("gender", "male")
    profile = COACH_PROFILES.get(gender, COACH_PROFILES["male"])

    # Suhbatni tugatish
    if message.content_type == types.ContentType.TEXT and message.text in ["❌ Suhbatni tugatish", "/start"]:
        transcripts = data.get("transcripts", [])
        await state.finish()
        await message.answer(
            "Suhbat tugadi. Yaxshi ish qildingiz! 👏",
            reply_markup=main_menu()
        )

        # Sessiya oxirida AI tahlil (inglizcha)
        if transcripts:
            await message.answer("⏳ <i>Analyzing your speaking session...</i>")
            try:
                analysis = await analyze_speaking_session(transcripts)
                if analysis:
                    await message.answer(
                        "📊 <b>Session Analysis</b>\n\n" + analysis
                    )
            except Exception as e:
                logger.warning(f"Session analysis error: {e}")
        return

    # Matn yuborganda eslatma
    if message.content_type == types.ContentType.TEXT:
        await message.answer(
            "🎙 Iltimos, <b>ovozli xabar</b> yuboring!\n"
            "<i>Speaking amaliyoti uchun gapirib javob bering.</i>"
        )
        return

    # Ovozni matnga aylantirish
    await message.bot.send_chat_action(message.chat.id, "typing")
    transcript = await voice_to_text(message.voice, message.bot)
    if not transcript:
        await message.answer("❌ Ovozni tanib bo'lmadi. Iltimos qaytadan yuboring:")
        return

    # Tarixga qo'shish
    history = data.get("history", [{"role": "system", "content": profile["system_prompt"]}])
    transcripts = data.get("transcripts", [])
    history.append({"role": "user", "content": transcript})
    transcripts.append(transcript)

    await message.bot.send_chat_action(message.chat.id, "typing")

    # Parallel: AI coach javob + zamonlar tahlili
    reply, tense_data = await asyncio.gather(
        chat_with_coach(history),
        analyze_tenses(transcript)
    )

    # Zamonlar statistikasini yangilash + DRF ga sync
    if tense_data:
        try:
            await update_tense_stats(message.from_user.id, tense_data)
        except Exception as e:
            logger.warning(f"Tense stats update error: {e}")
        try:
            await sync_tense_stats(message.from_user.id, tense_data)
        except Exception as e:
            logger.warning(f"Tense stats DRF sync error: {e}")

    history.append({"role": "assistant", "content": reply})
    if len(history) > 20:
        history = [history[0]] + history[-18:]

    await state.update_data(history=history, transcripts=transcripts)

    # Coach javobini matn + ovoz ko'rinishida yuborish
    await message.answer(f"🤖 <b>{profile['name']}:</b>\n{reply}")

    audio_bytes = await text_to_speech(reply, voice=profile["voice"])
    if audio_bytes:
        buf = BytesIO(audio_bytes)
        buf.name = "coach.ogg"
        await message.answer_voice(types.InputFile(buf))
