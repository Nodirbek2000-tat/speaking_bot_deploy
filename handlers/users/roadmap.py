import asyncio
from aiogram import types
from loader import dp
from utils.db_api.crud import get_user, get_user_mocks, get_tense_stats_summary
from services.ai_service import generate_roadmap
from services.drf_client import get_bot_statistics


@dp.message_handler(text="🗺 Roadmap")
async def show_roadmap(message: types.Message):
    user = await get_user(message.from_user.id)

    # Parallel: mock tarixi + DRF statistika + tense stats
    (ielts_mocks, cefr_mocks), drf_stats, tense_stats = await asyncio.gather(
        asyncio.gather(
            get_user_mocks(message.from_user.id, "ielts", 1),
            get_user_mocks(message.from_user.id, "cefr", 1),
        ),
        get_bot_statistics(message.from_user.id),
        get_tense_stats_summary(message.from_user.id),
    )

    last_ielts = ielts_mocks[0].score if ielts_mocks else None
    last_cefr_score = cefr_mocks[0].score if cefr_mocks else None
    last_cefr_level = cefr_mocks[0].cefr_level if cefr_mocks else None

    top_words = drf_stats.get("top_words", []) if drf_stats else []
    ielts_improvement = drf_stats.get("ielts_improvement") if drf_stats else None
    cefr_improvement = drf_stats.get("cefr_improvement") if drf_stats else None

    await message.answer(
        "🗺 <b>Shaxsiy Roadmapingiz tayyorlanmoqda...</b>\n"
        "Bu 10-15 soniya olishi mumkin ⏳"
    )

    roadmap = await generate_roadmap(
        ielts_band=last_ielts,
        cefr_score=last_cefr_score,
        cefr_level=last_cefr_level,
        total_mocks=user.total_mocks if user else 0,
        top_words=[w["word"] for w in top_words[:5]],
        ielts_improvement=ielts_improvement,
        cefr_improvement=cefr_improvement,
        tense_stats=tense_stats,
    )

    await message.answer(f"🗺 <b>Sizning Shaxsiy English Roadmapingiz</b>\n\n{roadmap}")
