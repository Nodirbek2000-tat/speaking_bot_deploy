import json
from aiogram import types
from aiogram.dispatcher import FSMContext

from loader import dp
from states.mock_states import CEFRMock
from utils.db_api.crud import (
    can_do_mock, increment_mock_count, create_mock_session,
    get_active_mock, update_mock_answer, complete_mock, log_activity
)
from keyboards.default.main_menu import main_menu
from services.ai_service import evaluate_cefr
from services.stt_service import voice_to_text
from services.drf_client import fetch_cefr_questions, log_bot_activity, save_cefr_result

PART_DESCRIPTIONS = {
    1: "📋 Part 1 — Umumiy savollar",
    2: "🖼 Part 2 — Rasmni tasvirlash (1-2 daqiqa gapiring)",
    3: "🔀 Part 3 — Rasmlarni solishtiring va muhokama qiling",
    4: "💬 Part 4 — Munozara savollari",
}


@dp.message_handler(text="📊 CEFR Mock")
async def cefr_mock_start(message: types.Message):
    ok = await can_do_mock(message.from_user.id)
    if not ok:
        await message.answer(
            "❌ <b>Bepul limitingiz tugadi!</b>\n\n"
            "💎 Premium sotib oling yoki do'stingizni taklif qiling!\n"
            "/premium",
            reply_markup=main_menu()
        )
        return

    q_data = await fetch_cefr_questions()
    if not q_data:
        await message.answer(
            "⚠️ Hozircha CEFR savollari yo'q.\n"
            "Admin qo'shadi. Keyinroq urinib ko'ring!"
        )
        return

    session = await create_mock_session(message.from_user.id, "cefr", q_data)
    await increment_mock_count(message.from_user.id)

    cancel_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    cancel_kb.add(types.KeyboardButton("❌ Bekor qilish"))

    await message.answer(
        "📊 <b>CEFR Speaking Mock Test</b>\n\n"
        "🎯 <b>Baholash tizimi:</b>\n"
        "• A1: 1–14 ball\n"
        "• A2: 15–34 ball\n"
        "• B1: 35–50 ball\n"
        "• B2: 51–65 ball\n"
        "• C1: 66–75 ball\n\n"
        f"Jami <b>{len(q_data)}</b> ta savol (4 qism)\n"
        "Har savolga matn yoki 🎙 ovoz bilan javob bering 👇",
        reply_markup=cancel_kb
    )
    await ask_cefr_question(message, q_data, 0)
    await CEFRMock.answering.set()


async def ask_cefr_question(message, questions: list, index: int):
    q = questions[index]
    part = q["part"]
    part_desc = PART_DESCRIPTIONS.get(part, f"Part {part}")

    text = f"<b>{part_desc}</b>\n"
    text += f"Savol {index + 1}/{len(questions)}\n\n"
    if q.get("instruction"):
        text += f"📌 <i>{q['instruction']}</i>\n\n"
    text += f"❓ <b>{q['question']}</b>\n\n"
    text += "✍️ Javobingizni yozing yoki 🎙 ovoz yuboring:"

    if q.get("image_file_id"):
        await message.answer_photo(q["image_file_id"], caption=text)
    else:
        await message.answer(text)


@dp.message_handler(
    state=CEFRMock.answering,
    content_types=[types.ContentType.TEXT, types.ContentType.VOICE]
)
async def cefr_answer(message: types.Message, state: FSMContext):
    if message.text in ["❌ Bekor qilish", "🔙 Orqaga", "/start"]:
        await state.finish()
        await message.answer("❌ CEFR Mock bekor qilindi.", reply_markup=main_menu())
        return

    ms = await get_active_mock(message.from_user.id)
    if not ms:
        await state.finish()
        return

    questions = json.loads(ms.questions)

    if message.voice:
        await message.answer("🎙 Ovoz tanilmoqda...")
        transcript = await voice_to_text(message.voice, message.bot)
        if not transcript:
            await message.answer("❌ Ovozni tanib bo'lmadi. Matn yozing:")
            return
        answer_text = transcript
        await message.answer(f"📝 <i>{transcript}</i>")
    else:
        answer_text = message.text
        transcript = message.text

    updated = await update_mock_answer(ms.id, transcript, answer_text)
    current = updated.current_question

    if current >= len(questions):
        await message.answer("⏳ Natijalar hisoblanmoqda... 15-20 soniya kuting.")
        transcripts = json.loads(updated.transcripts)
        result = await evaluate_cefr(questions, transcripts)

        score = result.get("score", 50)
        score = min(75, score + 4)   # +4 bonus
        # Level ni yangi score ga qarab qayta hisoblash
        if score <= 14:   level = "A1"
        elif score <= 34: level = "A2"
        elif score <= 50: level = "B1"
        elif score <= 65: level = "B2"
        else:             level = "C1"
        feedback = result.get("feedback", {})

        await complete_mock(ms.id, score, level, json.dumps(result, ensure_ascii=False))
        await log_activity(
            message.from_user.id,
            mock_done=True,
            cefr_score=score,
            cefr_level=level
        )
        # DRF ga natijani saqlash (statistikada ko'rinadi)
        await save_cefr_result(
            telegram_id=message.from_user.id,
            score=score,
            level=level,
            feedback=feedback,
        )
        await log_bot_activity(
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username or "",
            activity_type="cefr_mock",
            data={
                "score": score,
                "level": level,
                "questions_count": len(questions),
            }
        )

        level_emoji = {
            "A1": "🟤", "A2": "🔵", "B1": "🟢",
            "B2": "🟡", "C1": "🟠", "C2": "🔴"
        }.get(level, "⭐")

        text = "🎓 <b>CEFR Mock Natijasi</b>\n\n"
        text += f"{level_emoji} <b>Darajangiz: {level}</b>\n"
        text += f"📊 <b>Ball: {score}/75</b>\n\n"

        if feedback.get("summary"):
            text += f"📝 {feedback['summary']}\n\n"

        if feedback.get("strengths"):
            text += "✅ <b>Kuchli tomonlar:</b>\n"
            for s in feedback["strengths"][:3]:
                text += f"• {s}\n"
            text += "\n"

        if feedback.get("improvements"):
            text += "📈 <b>Yaxshilash kerak:</b>\n"
            for imp in feedback["improvements"][:3]:
                text += f"• {imp}\n"
            text += "\n"

        if feedback.get("errors"):
            text += "❌ <b>Xatolar:</b>\n"
            for e in feedback["errors"][:3]:
                text += f"• <s>{e.get('error', '')}</s> → <b>{e.get('correction', '')}</b>\n"

        await message.answer(text, reply_markup=main_menu())
        await state.finish()
    else:
        await ask_cefr_question(message, questions, current)
