from aiogram import types
from loader import dp
from utils.db_api.crud import get_user, get_user_mocks, get_tense_stats_summary
from services.drf_client import get_bot_statistics, get_webapp_url
from services.ai_service import analyze_statistics

TENSE_DISPLAY = {
    "present_simple": "Present Simple",
    "present_continuous": "Present Continuous",
    "past_simple": "Past Simple",
    "past_perfect": "Past Perfect",
    "future_simple": "Future Simple",
    "present_perfect": "Present Perfect",
    "conditional": "Conditional",
}


def tense_progress_bar(accuracy: int, width: int = 10) -> str:
    filled = round(accuracy / 10)
    empty = width - filled
    return "█" * filled + "░" * empty


@dp.message_handler(text="📈 Statistika")
@dp.message_handler(text="📊 My Progress")
async def show_statistics(message: types.Message):
    await message.answer(
        "📊 <b>My Progress</b>\n\n"
        "To see your full progress and statistics:\n\n"
        "1️⃣ Press the <b>🌐 Web App</b> button at the bottom of the screen\n"
        "2️⃣ Then tap <b>My Progress</b> inside the app\n\n"
        "There you'll find:\n"
        "• Grammar tense statistics\n"
        "• IELTS / CEFR history\n"
        "• AI analysis and tips"
    )
    return

    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Foydalanuvchi topilmadi.")
        return

    # Parallel: mahalliy DB + DRF + tense stats (30 kun) + bugungi tense
    import asyncio
    ielts_mocks, cefr_mocks, drf, tense_summary, today_tense = await asyncio.gather(
        get_user_mocks(message.from_user.id, "ielts", 5),
        get_user_mocks(message.from_user.id, "cefr", 5),
        get_bot_statistics(message.from_user.id),
        get_tense_stats_summary(message.from_user.id, days=30),
        get_tense_stats_summary(message.from_user.id, days=1),
    )

    # ─── Sarlavha ──────────────────────────────────────────
    text = "📈 <b>Sizning statistikangiz</b>\n\n"
    text += f"👤 <b>{user.full_name}</b>\n"
    text += f"📅 Ro'yxatdan: {user.created_at.strftime('%d.%m.%Y')}\n"

    if user.is_premium:
        exp = user.premium_expires.strftime('%d.%m.%Y') if user.premium_expires else "∞"
        text += f"💎 <b>PREMIUM</b> (tugash: {exp})\n"
    else:
        try:
            from services.drf_client import get_free_limits
            limits = await get_free_limits()
            free_limit = limits.get("free_mocks_limit", 2)
        except Exception:
            from data.config import FREE_MOCK_LIMIT
            free_limit = FREE_MOCK_LIMIT
        remaining = max(0, free_limit - (user.free_mocks_used or 0))
        text += f"🆓 Bepul mock: <b>{remaining} ta</b> qoldi\n"

    # ─── Umumiy raqamlar ───────────────────────────────────
    total = drf.get("total_mocks", user.total_mocks or 0)
    total_ai = drf.get("total_ai_chats", 0)
    text += f"\n🎯 <b>Jami mock testlar: {total}</b>"
    text += f"  |  🤖 AI suhbat: {total_ai}\n"

    # ─── IELTS tarixi ──────────────────────────────────────
    ielts_hist = drf.get("ielts_history", [])
    if ielts_hist:
        text += "\n📝 <b>IELTS natijalari:</b>\n"
        for h in ielts_hist[-5:]:
            text += f"  • Band <b>{h['band']}</b> ({h['date']})\n"

        imp = drf.get("ielts_improvement")
        if imp is not None:
            if imp > 0:
                text += f"  📈 <b>+{imp} band</b> o'sish (birinchi vs so'nggi)\n"
            elif imp < 0:
                text += f"  📉 <b>{imp} band</b> kamayish\n"
            else:
                text += f"  ➡️ O'zgarishsiz\n"
    elif ielts_mocks:
        text += "\n📝 <b>IELTS oxirgi natijalar:</b>\n"
        for m in ielts_mocks:
            date = m.completed_at.strftime('%d.%m') if m.completed_at else "—"
            text += f"  • Band <b>{m.score}</b> ({date})\n"

    # ─── CEFR tarixi ───────────────────────────────────────
    cefr_hist = drf.get("cefr_history", [])
    if cefr_hist:
        text += "\n📊 <b>CEFR natijalari:</b>\n"
        for h in cefr_hist[-5:]:
            text += f"  • <b>{h['level']}</b> — {h['score']}/75 ({h['date']})\n"

        imp = drf.get("cefr_improvement")
        if imp is not None:
            if imp > 0:
                text += f"  📈 <b>+{imp} ball</b> o'sish\n"
            elif imp < 0:
                text += f"  📉 <b>{imp} ball</b> kamayish\n"
            else:
                text += f"  ➡️ O'zgarishsiz\n"
    elif cefr_mocks:
        text += "\n📊 <b>CEFR oxirgi natijalar:</b>\n"
        for m in cefr_mocks:
            date = m.completed_at.strftime('%d.%m') if m.completed_at else "—"
            text += f"  • <b>{m.cefr_level}</b> — {int(m.score or 0)}/75 ({date})\n"

    # ─── Zaif qismlar (IELTS sub-scores) ──────────────────
    weak = drf.get("weak_areas", [])
    if weak:
        text += "\n⚠️ <b>Yaxshilash kerak bo'lgan qismlar:</b>\n"
        for w in weak:
            text += f"  • {w['skill']} — o'rtacha: <b>{w['avg']}</b>\n"

    # ─── Ko'p ishlatiladigan so'zlar ───────────────────────
    top_words = drf.get("top_words", [])
    if top_words:
        text += "\n💬 <b>Ko'p ishlatiladigan so'zlar:</b>\n"
        for i, w in enumerate(top_words[:6], 1):
            text += f"  {i}. <i>{w['word']}</i> ({w['count']} marta)\n"

    # ─── Grammatika statistikasi (zamonlar) ───────────────
    if today_tense:
        text += "\n📊 <b>Bugungi zamon aniqligi:</b>\n"
        for tense_key, display_name in TENSE_DISPLAY.items():
            if tense_key in today_tense:
                v = today_tense[tense_key]
                acc = v.get("accuracy", 0)
                usage = v.get("usage", 0)
                bar = tense_progress_bar(acc)
                text += f"  {display_name:<22} {bar} {acc}% <i>({usage}x)</i>\n"

    if tense_summary:
        text += "\n📈 <b>Grammatika (30 kunlik o'rtacha):</b>\n"
        for tense_key, display_name in TENSE_DISPLAY.items():
            if tense_key in tense_summary:
                v = tense_summary[tense_key]
                acc = v.get("accuracy", 0)
                bar = tense_progress_bar(acc)
                # Bugungi vs 30 kunlik farq
                today_acc = today_tense.get(tense_key, {}).get("accuracy", 0) if today_tense else 0
                diff = round(today_acc - acc, 0)
                diff_str = (f" <b>+{int(diff)}%</b>" if diff > 0 else f" <b>{int(diff)}%</b>") if diff != 0 and today_tense else ""
                text += f"  {display_name:<22} {bar} {acc}%{diff_str}\n"
    elif not today_tense:
        text += "\n📊 <i>Tense statistikasi yo'q — AI Chat bilan gaplashing!</i>\n"

    # ─── Referal ──────────────────────────────────────────
    text += f"\n🔗 <b>Referal:</b> <code>{user.referral_code or '—'}</code>"
    text += f" | 👥 {user.referral_count or 0} ta taklif\n"

    await message.answer(text)

    # ─── AI tahlil (alohida xabar) ─────────────────────────
    if drf and (drf.get("total_mocks", 0) > 0 or drf.get("total_ai_chats", 0) > 0):
        await message.answer("⏳ AI tahlil tayyorlanmoqda...")
        analysis = await analyze_statistics(drf)
        if analysis:
            await message.answer(
                "🤖 <b>Shaxsiy tahlil:</b>\n\n" + analysis
            )
