import json
from io import BytesIO
from aiogram import types
from aiogram.dispatcher import FSMContext

from loader import dp
from states.mock_states import VocabSearch, WordDiscuss, VocabPractice
from utils.db_api.crud import save_word, get_saved_words, get_random_words, log_activity
from keyboards.default.main_menu import main_menu, back_menu
from keyboards.inline.vocab_kb import word_actions_kb, saved_words_nav_kb, word_discuss_kb, vocab_quiz_kb
from services.ai_service import lookup_word_ai, discuss_word_with_coach, text_to_speech
from services.drf_client import fetch_vocab_words, log_bot_activity


@dp.message_handler(text="📚 Lug'at")
async def vocab_menu(message: types.Message):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🔍 So'z qidirish", callback_data="vocab_search"),
        types.InlineKeyboardButton("🔖 Saqlangan so'zlar", callback_data="vocab_saved"),
        types.InlineKeyboardButton("💪 Mashq qilish", callback_data="vocab_practice"),
    )
    await message.answer(
        "📚 <b>Lug'at</b>\n\n"
        "So'zni qidiring — inglizcha ta'rif, o'zbekcha tarjima,\n"
        "sinonimlar va 5 ta akademik misol jumlalar ko'rasiz!\n\n"
        "🗣 AI bilan muhokama tugmasi ham mavjud.",
        reply_markup=kb
    )


@dp.callback_query_handler(text="vocab_search")
async def start_word_search(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("🔍 Qidirmoqchi bo'lgan so'zingizni yozing:", reply_markup=back_menu())
    await VocabSearch.waiting_word.set()
    await call.answer()


@dp.message_handler(state=VocabSearch.waiting_word)
async def process_word_search(message: types.Message, state: FSMContext):
    if message.text == "🔙 Orqaga":
        await state.finish()
        await message.answer("Bosh menyu 👇", reply_markup=main_menu())
        return

    word = message.text.strip().lower()
    await message.answer(f"🔍 <b>{word}</b> so'zi qidirilmoqda...")

    data = await lookup_word_ai(word)
    if not data:
        await message.answer("❌ So'z topilmadi. Boshqa so'z kiriting.")
        return

    await state.update_data(current_word=data)
    await log_activity(message.from_user.id, word_looked=True)

    saved = await get_saved_words(message.from_user.id)
    is_saved = any(sw.word.lower() == word.lower() for sw in saved)

    text = format_word_card(data)
    await message.answer(text, reply_markup=word_actions_kb(word, is_saved))
    await VocabSearch.viewing_word.set()


def format_word_card(data: dict) -> str:
    word = data.get("word", "")
    level = data.get("level", "")
    definition = data.get("definition", "")
    translation = data.get("translation_uz", "")
    examples = data.get("examples", [])
    synonyms = data.get("synonyms", [])

    text = f"📖 <b>{word}</b>  <code>[{level}]</code>\n\n"
    text += f"📝 <b>Ta'rif:</b> {definition}\n\n"
    if translation:
        text += f"🇺🇿 <b>Tarjima:</b> {translation}\n\n"

    # Sinonimlar
    if synonyms:
        syn_parts = []
        for s in synonyms[:5]:
            if isinstance(s, dict):
                syn_parts.append(f"<i>{s.get('word', s)}</i>")
            else:
                syn_parts.append(f"<i>{s}</i>")
        text += f"🔄 <b>Sinonimlar:</b> {', '.join(syn_parts)}\n\n"

    text += "✍️ <b>Akademik misollar:</b>\n"
    for i, ex in enumerate(examples[:5], 1):
        text += f"{i}. <i>{ex}</i>\n"
    return text


@dp.callback_query_handler(lambda c: c.data.startswith("save_word:"), state=VocabSearch.viewing_word)
async def save_word_cb(call: types.CallbackQuery, state: FSMContext):
    word_text = call.data.split(":")[1]
    data_state = await state.get_data()
    word_data = data_state.get("current_word", {})

    saved = await save_word(
        user_id=call.from_user.id,
        word=word_data.get("word", word_text),
        definition=word_data.get("definition", ""),
        translation_uz=word_data.get("translation_uz", ""),
        examples=word_data.get("examples", [])
    )
    if saved:
        await call.answer("✅ So'z saqlandi!", show_alert=False)
        await call.message.edit_reply_markup(word_actions_kb(word_text, True))
    else:
        await call.answer("Bu so'z allaqachon saqlangan!", show_alert=False)


@dp.callback_query_handler(text="search_another", state=VocabSearch.viewing_word)
async def search_another(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("🔍 Yangi so'z kiriting:")
    await VocabSearch.waiting_word.set()
    await call.answer()


# ─── AI bilan muhokama ────────────────────────────────────────────────────────

@dp.callback_query_handler(lambda c: c.data.startswith("discuss_word:"), state=VocabSearch.viewing_word)
async def start_word_discussion(call: types.CallbackQuery, state: FSMContext):
    word = call.data.split(":", 1)[1]
    data_state = await state.get_data()
    word_data = data_state.get("current_word", {})

    await state.update_data(discuss_word=word, discuss_history=[], discuss_word_data=word_data)

    opening = (
        f"Let's talk about the word <b>'{word}'</b>! 🗣\n\n"
        f"I'll help you understand it better through conversation.\n\n"
        f"Try using <b>'{word}'</b> in a sentence — let's start! 💬\n\n"
        f"<i>(Suhbatni tugatish uchun pastdagi tugmani bosing)</i>"
    )
    await call.message.answer(opening, reply_markup=word_discuss_kb(word))
    await WordDiscuss.discussing.set()
    await call.answer()


@dp.message_handler(state=WordDiscuss.discussing,
                    content_types=[types.ContentType.TEXT, types.ContentType.VOICE])
async def word_discuss_message(message: types.Message, state: FSMContext):
    if message.content_type == types.ContentType.VOICE:
        from services.stt_service import voice_to_text
        transcript = await voice_to_text(message.voice, message.bot)
        if not transcript:
            await message.answer("❌ Ovoz tanilmadi. Matn yuboring.")
            return
        user_text = transcript
        await message.answer(f"🎙 <i>{transcript}</i>")
    else:
        user_text = message.text.strip()

    data_state = await state.get_data()
    word = data_state.get("discuss_word", "")
    history = data_state.get("discuss_history", [])

    history.append({"role": "user", "content": user_text})

    await message.bot.send_chat_action(message.chat.id, "typing")
    reply = await discuss_word_with_coach(word, history)

    history.append({"role": "assistant", "content": reply})
    if len(history) > 16:
        history = history[-16:]

    await state.update_data(discuss_history=history)
    await message.answer(f"🤖 <b>Alex:</b>\n{reply}", reply_markup=word_discuss_kb(word))


@dp.callback_query_handler(lambda c: c.data.startswith("back_to_word:"), state=WordDiscuss.discussing)
async def back_to_word_card(call: types.CallbackQuery, state: FSMContext):
    word = call.data.split(":", 1)[1]
    data_state = await state.get_data()
    word_data = data_state.get("discuss_word_data", {})

    if word_data:
        text = format_word_card(word_data)
        saved = await get_saved_words(call.from_user.id)
        is_saved = any(sw.word.lower() == word.lower() for sw in saved)
        await call.message.answer(text, reply_markup=word_actions_kb(word, is_saved))

    await state.update_data(discuss_word=None, discuss_history=[])
    await VocabSearch.viewing_word.set()
    await call.answer()


# ─── Saqlangan so'zlar ───────────────────────────────────────────────────────

@dp.callback_query_handler(text="vocab_saved")
async def show_saved_words(call: types.CallbackQuery, state: FSMContext):
    words = await get_saved_words(call.from_user.id)
    if not words:
        await call.message.answer(
            "📭 Hali saqlangan so'z yo'q.\n"
            "🔍 So'z qidirib saqlang!"
        )
        await call.answer()
        return

    saved_list = [
        {
            "word": w.word,
            "definition": w.definition,
            "translation_uz": w.translation_uz,
            "examples": json.loads(w.examples or "[]")
        }
        for w in words
    ]
    await state.update_data(saved_index=0, saved_words=saved_list)

    w_data = saved_list[0]
    text = format_word_card(w_data)
    await call.message.answer(text, reply_markup=saved_words_nav_kb(0, len(saved_list), w_data["word"]))
    await call.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("saved_nav:"))
async def nav_saved(call: types.CallbackQuery, state: FSMContext):
    index = int(call.data.split(":")[1])
    data_state = await state.get_data()
    saved_list = data_state.get("saved_words", [])
    if not saved_list or index >= len(saved_list):
        await call.answer("❌ Ro'yxat topilmadi")
        return
    w = saved_list[index]
    text = format_word_card(w)
    await call.message.edit_text(text, reply_markup=saved_words_nav_kb(index, len(saved_list), w["word"]))
    await call.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("del_word:"))
async def delete_saved_word(call: types.CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    word_text = parts[1]
    index = int(parts[2]) if len(parts) > 2 else 0

    from utils.db_api.database import async_session
    from utils.db_api.models import SavedWord
    from sqlalchemy import select
    async with async_session() as session:
        result = await session.execute(
            select(SavedWord).where(
                SavedWord.user_id == call.from_user.id,
                SavedWord.word == word_text
            )
        )
        sw = result.scalar_one_or_none()
        if sw:
            await session.delete(sw)
            await session.commit()

    data_state = await state.get_data()
    saved_list = data_state.get("saved_words", [])
    saved_list = [w for w in saved_list if w["word"] != word_text]
    await state.update_data(saved_words=saved_list)

    if not saved_list:
        await call.message.edit_text("📭 Saqlangan so'zlar yo'q.")
    else:
        new_index = min(index, len(saved_list) - 1)
        w = saved_list[new_index]
        text = format_word_card(w)
        await call.message.edit_text(text, reply_markup=saved_words_nav_kb(new_index, len(saved_list), w["word"]))
    await call.answer("🗑 O'chirildi!")


# ─── Mashq ────────────────────────────────────────────────────────────────────

@dp.callback_query_handler(text="vocab_practice")
async def vocab_practice(call: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(*[
        types.InlineKeyboardButton(l, callback_data=f"practice_level:{l}")
        for l in ["A1", "A2", "B1", "B2", "C1", "C2"]
    ])
    await call.message.answer("🎯 Qaysi darajadagi so'zlarni mashq qilasiz?", reply_markup=kb)
    await call.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("practice_level:"))
async def show_practice_words(call: types.CallbackQuery, state: FSMContext):
    level = call.data.split(":")[1]

    words = await fetch_vocab_words(level=level, telegram_id=call.from_user.id)

    if not words:
        local_words = await get_random_words(level=level, count=20)
        if not local_words:
            await call.message.answer(
                f"❌ {level} darajasidagi so'z yo'q.\n"
                "Admin tez orada qo'shadi!"
            )
            await call.answer()
            return
        words = [
            {
                "word": w.word,
                "level": w.level,
                "definition": w.definition,
                "translation_uz": w.translation_uz or "",
                "examples": json.loads(w.examples or "[]"),
            }
            for w in local_words
        ]

    words = words[:20]
    await state.update_data(quiz_words=words, quiz_index=0, quiz_level=level)
    await VocabPractice.quizzing.set()
    await call.answer()
    await send_quiz_word(call.message, words, 0)


async def send_quiz_word(message, words: list, index: int):
    """So'z kartasini matn + ovoz bilan yuborish"""
    if index >= len(words):
        await message.answer(
            "🎉 <b>Mashq tugadi!</b>\n\n"
            f"Jami <b>{len(words)}</b> ta so'zni o'rgandingiz! 💪",
            reply_markup=main_menu()
        )
        return

    w = words[index]
    word = w.get("word", "")
    level = w.get("level", "")
    definition = w.get("definition", "")
    translation = w.get("translation_uz", "")
    examples = w.get("examples", [])

    text = (
        f"📖 <b>{index + 1}/{len(words)}</b>  <code>[{level}]</code>\n\n"
        f"🔤 <b>{word}</b>\n\n"
        f"📝 {definition}\n"
    )
    if translation:
        text += f"🇺🇿 <i>{translation}</i>\n"
    if examples:
        text += f"\n✍️ <b>Misol:</b>\n<i>{examples[0]}</i>\n"

    await message.answer(text, reply_markup=vocab_quiz_kb(index, len(words)))

    # TTS — so'zni ovozda o'qib berish
    tts_text = f"{word}. {definition}"
    if examples:
        tts_text += f" Example: {examples[0]}"
    audio_bytes = await text_to_speech(tts_text)
    if audio_bytes:
        buf = BytesIO(audio_bytes)
        buf.name = "word.ogg"
        await message.answer_voice(types.InputFile(buf), caption=f"🔊 <b>{word}</b>")


@dp.callback_query_handler(lambda c: c.data.startswith("quiz_next:"), state=VocabPractice.quizzing)
async def quiz_next(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    words = data.get("quiz_words", [])
    index = int(call.data.split(":")[1]) + 1
    await state.update_data(quiz_index=index)
    await call.answer()
    if index >= len(words):
        await state.finish()
        await call.message.answer(
            "🎉 <b>Mashq tugadi!</b>\n\n"
            f"Jami <b>{len(words)}</b> ta so'zni o'rgandingiz! 💪",
            reply_markup=main_menu()
        )
    else:
        await send_quiz_word(call.message, words, index)


@dp.callback_query_handler(lambda c: c.data.startswith("quiz_replay:"), state=VocabPractice.quizzing)
async def quiz_replay(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    words = data.get("quiz_words", [])
    index = int(call.data.split(":")[1])
    await call.answer("🔊 Qayta o'qilyapti...")
    if index < len(words):
        w = words[index]
        word = w.get("word", "")
        definition = w.get("definition", "")
        examples = w.get("examples", [])
        tts_text = f"{word}. {definition}"
        if examples:
            tts_text += f" Example: {examples[0]}"
        audio_bytes = await text_to_speech(tts_text)
        if audio_bytes:
            buf = BytesIO(audio_bytes)
            buf.name = "word.ogg"
            await call.message.answer_voice(types.InputFile(buf), caption=f"🔊 <b>{word}</b>")


@dp.callback_query_handler(text="quiz_stop", state=VocabPractice.quizzing)
async def quiz_stop(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await call.message.answer("✅ Mashq to'xtatildi.", reply_markup=main_menu())
    await call.answer()
