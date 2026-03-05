"""
handlers/users/mock_ielts.py
IELTS Mock — yangilangan versiya (aiogram 2.x uchun):
  - Part 1: birinchi savol "Can you tell me your name?" (intro), keyin 5-6 ta oddiy savol
  - Part 2: Cue card (admin qo'shgan)
  - Part 3: Part 2 ga bog'liq follow-up savollar (admin qo'shgan)
"""
import asyncio
import io
import json
import logging
import random

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text

# DIQQAT: dp ni o'zingizning loyihangizdagi asosiy fayldan import qilasiz (odatda loader.py da bo'ladi)
from loader import dp

from keyboards.inline.mock_kb import (
    ielts_start_kb, ielts_next_kb, ielts_part2_kb,
    ielts_finish_kb, main_menu_kb,
)
from keyboards.default.main_menu import main_menu
from services.drf_client import (
    get_ielts_questions,
    save_ielts_session,
    get_user_profile,
)
from services.ai_service import text_to_speech
from services.openai_service import transcribe_audio, analyze_ielts_speaking
from states.mock_states import IELTSMock
from utils.db_api.crud import get_user

logger = logging.getLogger(__name__)

# ── Sozlamalar ────────────────────────────────────────────────────────────────
PART1_QUESTIONS_COUNT = 6   # Intro dan keyin nechta savol (jami 7 = 1 intro + 6)
PART3_QUESTIONS_COUNT = 4   # Part 3 dan nechta savol

PART1_INTRO = "Can you tell me your full name, please?"
PART1_INTRO_FOLLOWUP = "And where are you from?"


# ─── /ielts yoki "IELTS Mock" tugmasi ────────────────────────────────────────

@dp.message_handler(text=["📝 IELTS Mock", "/ielts"], state="*")
async def start_ielts(message: types.Message, state: FSMContext):
    await state.finish()

    user = await get_user(message.from_user.id)
    profile = await get_user_profile(message.from_user.id)

    # Free limit tekshirish
    if profile and not profile.get('has_premium'):
        ielts_count = profile.get('ielts_count', 0)
        free_limit = profile.get('free_ielts_limit', 2)
        if ielts_count >= free_limit:
            await message.answer(
                "⚠️ <b>Bepul IELTS Mock limitingiz tugadi!</b>\n\n"
                f"Siz allaqachon {ielts_count} ta mock test topshirdingiz.\n"
                "Davom etish uchun Premium oling 💎",
                parse_mode="HTML",
                reply_markup=main_menu_kb()
            )
            return

    await message.answer(
        "🎓 <b>IELTS Speaking Mock Test</b>\n\n"
        "📋 <b>Test 3 qismdan iborat:</b>\n"
        "• <b>Part 1</b> — Kirish va oddiy savollar (1-2 daqiqa)\n"
        "• <b>Part 2</b> — Cue card mavzu (1-2 daqiqa)\n"
        "• <b>Part 3</b> — Mavzuga oid chuqurroq savollar (3-4 daqiqa)\n\n"
        "🎙 Har bir savolga <b>ovozli xabar</b> orqali javob bering.\n"
        "⏱ Taxminiy vaqt: <b>10-15 daqiqa</b>\n\n"
        "Boshlashga tayyormisiz?",
        parse_mode="HTML",
        reply_markup=ielts_start_kb()
    )


@dp.callback_query_handler(text="ielts_start", state="*")
async def ielts_begin(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.delete()

    # Savollarni backenddan olish
    msg = await call.message.answer("⏳ Savollar yuklanmoqda...")

    questions = await get_ielts_questions()
    if not questions:
        await msg.edit_text(
            "⚠️ Savollar topilmadi. Admin hali savollar qo'shmagan.\n"
            "Keyinroq urinib ko'ring.",
            reply_markup=main_menu_kb()
        )
        return

    # Savollarni qismlarga ajratish
    part1_intro = [q for q in questions if q['part'] == 1 and q.get('is_intro')]
    part1_regular = [q for q in questions if q['part'] == 1 and not q.get('is_intro')]
    part2_questions = [q for q in questions if q['part'] == 2]
    part3_questions = [q for q in questions if q['part'] == 3]

    # Part 1: intro + random 5-6 ta savol
    selected_part1 = []
    if part1_intro:
        selected_part1.append(random.choice(part1_intro))
    elif part1_regular:
        # Intro yo'q bo'lsa, default qo'yamiz
        selected_part1.append({
            'id': 0,
            'part': 1,
            'question': PART1_INTRO,
            'is_intro': True
        })

    regular_count = min(PART1_QUESTIONS_COUNT, len(part1_regular))
    selected_part1 += random.sample(part1_regular, regular_count) if len(part1_regular) >= regular_count else part1_regular

    # Part 2: bitta random cue card
    selected_part2 = random.choice(part2_questions) if part2_questions else None

    # Part 3: Part 2 ga bog'liq savollar (yoki random)
    selected_part3 = []
    if selected_part2:
        linked_p3 = [q for q in part3_questions if q.get('related_part2') == selected_part2['id']]
        if linked_p3:
            count = min(PART3_QUESTIONS_COUNT, len(linked_p3))
            selected_part3 = random.sample(linked_p3, count)
        else:
            # Bog'liq savol yo'q — random olamiz
            count = min(PART3_QUESTIONS_COUNT, len(part3_questions))
            selected_part3 = random.sample(part3_questions, count) if len(part3_questions) >= count else part3_questions
    else:
        count = min(PART3_QUESTIONS_COUNT, len(part3_questions))
        selected_part3 = random.sample(part3_questions, count) if len(part3_questions) >= count else part3_questions

    # State ga saqlash
    await state.update_data(
        part1_questions=[q['id'] for q in selected_part1],
        part1_texts=[q['question'] for q in selected_part1],
        part2_question=selected_part2,
        part3_questions=[q['id'] for q in selected_part3],
        part3_texts=[q['question'] for q in selected_part3],
        current_part=1,
        current_index=0,
        answers=[],  # {'question_id': x, 'transcript': '...'}
    )

    await msg.delete()

    # Bekor qilish tugmasi bilan reply keyboard
    cancel_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    cancel_kb.add(types.KeyboardButton("❌ Bekor qilish"))
    await call.message.answer(
        "🎙 Mock test boshlandi! Bekor qilish uchun quyidagi tugmani bosing.",
        reply_markup=cancel_kb
    )

    await IELTSMock.part1.set()
    await ask_part1_question(call.message, state, question_index=0)


# ─── Part 1 ───────────────────────────────────────────────────────────────────

async def ask_part1_question(message: types.Message, state: FSMContext, question_index: int):
    data = await state.get_data()
    texts = data['part1_texts']
    total = len(texts)

    if question_index >= total:
        # Part 1 tugadi → Part 2 ga o'tish
        await transition_to_part2(message, state)
        return

    question_text = texts[question_index]
    is_intro = question_index == 0

    if is_intro:
        header = "👋 <b>Part 1 — Kirish</b>"
        footer = "\n\n🎙 Ovozli xabar yuboring."
    else:
        header = f"📌 <b>Part 1</b> — Savol {question_index}/{total - 1}"
        footer = "\n\n🎙 Ovozli xabar yuboring."

    await message.answer(
        f"{header}\n\n"
        f"❓ {question_text}"
        f"{footer}",
        parse_mode="HTML",
    )
    await _send_question_voice(message, question_text)
    await state.update_data(current_index=question_index)


@dp.message_handler(state=IELTSMock.part1, content_types=types.ContentType.VOICE)
async def handle_part1_voice(message: types.Message, state: FSMContext):
    data = await state.get_data()
    index = data.get('current_index', 0)
    texts = data.get('part1_texts', [])
    question_ids = data.get('part1_questions', [])
    answers = data.get('answers', [])

    # Audio transcribe
    transcript = await _transcribe_voice(message)
    if transcript:
        await message.answer(f"✍️ <i>Siz dedingiz:</i> {transcript}", parse_mode="HTML")

    # Javobni saqlash (question_text va part ham bilan)
    q_id = question_ids[index] if index < len(question_ids) else 0
    answers.append({
        'question_id': q_id,
        'question_text': texts[index],
        'part': 1,
        'transcript': transcript,
    })
    await state.update_data(answers=answers)

    next_index = index + 1

    if next_index >= len(texts):
        # Part 1 tugadi
        await message.answer("✅ Part 1 tugadi! Part 2 ga o'tamiz...")
        await asyncio.sleep(1)
        await transition_to_part2(message, state)
    else:
        await ask_part1_question(message, state, next_index)


@dp.message_handler(
    text=["❌ Bekor qilish", "/start"],
    state=[IELTSMock.part1, IELTSMock.part2, IELTSMock.part3]
)
async def cancel_ielts(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer(
        "❌ IELTS Mock bekor qilindi.",
        reply_markup=main_menu()
    )


@dp.message_handler(state=IELTSMock.part1, content_types=types.ContentType.ANY)
async def part1_not_voice(message: types.Message):
    await message.answer("🎙 Iltimos, <b>ovozli xabar</b> yuboring.", parse_mode="HTML")


# ─── Part 2 ───────────────────────────────────────────────────────────────────

async def transition_to_part2(message: types.Message, state: FSMContext):
    data = await state.get_data()
    part2 = data.get('part2_question')

    if not part2:
        # Part 2 yo'q — Part 3 ga o'tish
        await transition_to_part3(message, state)
        return

    await IELTSMock.part2.set()

    cue_card = part2.get('cue_card_points') or []
    cue_text = ""
    if cue_card:
        cue_text = "\n" + "\n".join(f"  {p}" for p in cue_card)

    await message.answer(
        "📋 <b>Part 2 — Cue Card</b>\n\n"
        f"❓ <b>{part2['question']}</b>"
        f"{cue_text}\n\n"
        "⏱ <b>1 daqiqa</b> o'ylab, keyin <b>1-2 daqiqa</b> gapiring.\n"
        "🎙 Tayyor bo'lgach ovozli xabar yuboring.",
        parse_mode="HTML",
        reply_markup=ielts_part2_kb()
    )
    await _send_question_voice(message, part2['question'])


@dp.message_handler(state=IELTSMock.part2, content_types=types.ContentType.VOICE)
async def handle_part2_voice(message: types.Message, state: FSMContext):
    data = await state.get_data()
    part2 = data.get('part2_question', {})
    answers = data.get('answers', [])

    transcript = await _transcribe_voice(message)
    if transcript:
        await message.answer(f"✍️ <i>Siz dedingiz:</i> {transcript}", parse_mode="HTML")

    answers.append({
        'question_id': part2.get('id', 0),
        'question_text': part2.get('question', ''),
        'part': 2,
        'transcript': transcript,
    })
    await state.update_data(answers=answers)

    await message.answer("✅ Part 2 qabul qilindi! Part 3 ga o'tamiz...")
    await asyncio.sleep(1)
    await transition_to_part3(message, state)


@dp.message_handler(state=IELTSMock.part2, content_types=types.ContentType.ANY)
async def part2_not_voice(message: types.Message):
    await message.answer("🎙 Iltimos, <b>ovozli xabar</b> yuboring.", parse_mode="HTML")


# ─── Part 3 ───────────────────────────────────────────────────────────────────

async def transition_to_part3(message: types.Message, state: FSMContext):
    data = await state.get_data()
    part3_texts = data.get('part3_texts', [])

    if not part3_texts:
        await finish_ielts(message, state)
        return

    await IELTSMock.part3.set()
    await state.update_data(current_index=0)

    await message.answer(
        "💬 <b>Part 3 — Muhokama</b>\n\n"
        "Bu qismda mavzuga oid chuqurroq savollar beriladi.\n"
        "Har bir savolga to'liq javob bering.",
        parse_mode="HTML"
    )
    await asyncio.sleep(1)
    await ask_part3_question(message, state, 0)


async def ask_part3_question(message: types.Message, state: FSMContext, index: int):
    data = await state.get_data()
    texts = data.get('part3_texts', [])
    total = len(texts)

    if index >= total:
        await finish_ielts(message, state)
        return

    await message.answer(
        f"💬 <b>Part 3</b> — Savol {index + 1}/{total}\n\n"
        f"❓ {texts[index]}\n\n"
        "🎙 Ovozli xabar yuboring.",
        parse_mode="HTML"
    )
    await _send_question_voice(message, texts[index])
    await state.update_data(current_index=index)


@dp.message_handler(state=IELTSMock.part3, content_types=types.ContentType.VOICE)
async def handle_part3_voice(message: types.Message, state: FSMContext):
    data = await state.get_data()
    index = data.get('current_index', 0)
    texts = data.get('part3_texts', [])
    question_ids = data.get('part3_questions', [])
    answers = data.get('answers', [])

    transcript = await _transcribe_voice(message)
    if transcript:
        await message.answer(f"✍️ <i>Siz dedingiz:</i> {transcript}", parse_mode="HTML")

    q_id = question_ids[index] if index < len(question_ids) else 0
    answers.append({
        'question_id': q_id,
        'question_text': texts[index],
        'part': 3,
        'transcript': transcript,
    })
    await state.update_data(answers=answers)

    next_index = index + 1
    if next_index >= len(texts):
        await finish_ielts(message, state)
    else:
        await ask_part3_question(message, state, next_index)


@dp.message_handler(state=IELTSMock.part3, content_types=types.ContentType.ANY)
async def part3_not_voice(message: types.Message):
    await message.answer("🎙 Iltimos, <b>ovozli xabar</b> yuboring.", parse_mode="HTML")


# ─── Finish & AI Tahlil ───────────────────────────────────────────────────────

async def finish_ielts(message: types.Message, state: FSMContext):
    data = await state.get_data()
    answers = data.get('answers', [])

    if not answers:
        await message.answer(
            "⚠️ Hech qanday javob topilmadi.",
            reply_markup=main_menu_kb()
        )
        await state.finish()
        return

    processing_msg = await message.answer(
        "⏳ <b>Natijalar hisoblanmoqda...</b>\n\n"
        "🤖 AI javoblaringizni tahlil qilmoqda...\n"
        "Bu 20-30 soniya olishi mumkin.",
        parse_mode="HTML"
    )

    # Barcha transcriptlarni Q+A format bilan birlashtirish
    full_transcript = "\n\n".join([
        f"[Part {a.get('part', '?')}] Q: {a.get('question_text', f'Question {i+1}')}\nA: {a.get('transcript', '(no answer)')}"
        for i, a in enumerate(answers)
    ])

    # AI tahlil
    result = await analyze_ielts_speaking(full_transcript)

    if not result:
        await processing_msg.edit_text(
            "⚠️ Tahlil qilishda xato yuz berdi. Keyinroq urinib ko'ring.",
            reply_markup=main_menu_kb()
        )
        await state.finish()
        return

    band = result.get('overall_band', 5.0)
    band = min(9.0, round(band + 0.5, 1))   # +0.5 bonus
    sub = result.get('sub_scores', {})
    strengths = result.get('strengths', [])
    improvements = result.get('improvements', [])

    # Backendga saqlash
    user = await get_user(message.from_user.id)
    await save_ielts_session(
        telegram_id=message.from_user.id,
        band=band,
        sub_scores=sub,
        feedback=result,
        answers=answers,
    )

    await processing_msg.delete()

    # Band rang
    band_emoji = "🏆" if band >= 7 else "✅" if band >= 5.5 else "📈"

    # Sub scores matni
    sub_text = ""
    if sub:
        sub_text = (
            f"\n\n📊 <b>Sub-scores:</b>\n"
            f"• Fluency & Coherence: <b>{sub.get('fluency', '—')}</b>\n"
            f"• Lexical Resource: <b>{sub.get('lexical', '—')}</b>\n"
            f"• Grammar: <b>{sub.get('grammar', '—')}</b>\n"
            f"• Pronunciation: <b>{sub.get('pronunciation', '—')}</b>"
        )

    strengths_text = ""
    if strengths:
        strengths_text = "\n\n✅ <b>Kuchli tomonlar:</b>\n" + "\n".join(f"• {s}" for s in strengths[:3])

    improvements_text = ""
    if improvements:
        improvements_text = "\n\n📈 <b>Yaxshilash kerak:</b>\n" + "\n".join(f"• {i}" for i in improvements[:3])

    await message.answer(
        f"{band_emoji} <b>IELTS Speaking Mock natijasi</b>\n\n"
        f"🎯 Umumiy band: <b>{band}/9.0</b>"
        f"{sub_text}"
        f"{strengths_text}"
        f"{improvements_text}\n\n"
        f"📱 Batafsil tahlil uchun Web App → My Progress",
        parse_mode="HTML",
        reply_markup=ielts_finish_kb()
    )

    await state.finish()


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _transcribe_voice(message: types.Message) -> str:
    """Voice xabarni matnga o'girish"""
    try:
        file_info = await message.bot.get_file(message.voice.file_id)
        file_url = f"https://api.telegram.org/file/bot{message.bot.token}/{file_info.file_path}"
        transcript = await transcribe_audio(file_url)
        return transcript or ""
    except Exception as e:
        logger.error(f"Transcribe error: {e}")
        return ""


async def _send_question_voice(message: types.Message, text: str):
    """Savolni TTS orqali ovozli xabar sifatida yuborish"""
    try:
        audio = await text_to_speech(text, voice="alloy")
        if audio:
            await message.answer_voice(
                types.InputFile(io.BytesIO(audio), filename="question.ogg")
            )
    except Exception as e:
        logger.error(f"TTS send error: {e}")