from aiogram import types
from loader import dp, bot
from utils.db_api.crud import get_user, get_user_mocks
from services.drf_client import get_bot_statistics, get_leaderboard
from services.ai_service import analyze_statistics


@dp.message_handler(text="📊 My Progress")
async def show_my_progress(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Please start the bot with /start first.")
        return

    await message.answer("⏳ Analyzing your progress...")

    ielts_mocks = await get_user_mocks(message.from_user.id, "ielts", 10)
    cefr_mocks = await get_user_mocks(message.from_user.id, "cefr", 10)
    drf = await get_bot_statistics(message.from_user.id)

    # ── Header ──────────────────────────────────────────────
    text = "📊 <b>My Progress Report</b>\n\n"
    text += f"👤 <b>{user.full_name}</b>\n"

    if user.is_premium:
        exp = user.premium_expires.strftime('%d.%m.%Y') if user.premium_expires else "∞"
        text += f"💎 Premium (expires: {exp})\n"
    else:
        from data.config import FREE_MOCK_LIMIT
        rem = max(0, FREE_MOCK_LIMIT - (user.free_mocks_used or 0))
        text += f"🆓 Free mocks left: <b>{rem}</b>\n"

    # ── IELTS trend ─────────────────────────────────────────
    ielts_hist = drf.get("ielts_history", [])
    if ielts_hist:
        text += "\n📝 <b>IELTS Speaking History:</b>\n"
        bands = [h['band'] for h in ielts_hist[-8:]]
        # Simple text chart
        for i, h in enumerate(ielts_hist[-8:]):
            bar = "█" * int(float(h['band']))
            text += f"  {h['date']}  Band <b>{h['band']}</b>  {bar}\n"
        if len(bands) >= 2:
            change = round(bands[-1] - bands[0], 1)
            emoji = "📈" if change > 0 else ("📉" if change < 0 else "➡️")
            text += f"  {emoji} Overall change: <b>{'+' if change>0 else ''}{change}</b>\n"
    elif ielts_mocks:
        text += "\n📝 <b>IELTS Recent Results:</b>\n"
        for m in ielts_mocks[:5]:
            date = m.completed_at.strftime('%d.%m') if m.completed_at else "—"
            text += f"  • Band <b>{m.score}</b>  ({date})\n"

    # ── CEFR trend ──────────────────────────────────────────
    cefr_hist = drf.get("cefr_history", [])
    if cefr_hist:
        text += "\n📊 <b>CEFR History:</b>\n"
        for h in cefr_hist[-8:]:
            bar = "█" * (int(h['score']) // 10)
            text += f"  {h['date']}  <b>{h['level']}</b>  {h['score']}/75  {bar}\n"
        scores = [h['score'] for h in cefr_hist]
        if len(scores) >= 2:
            change = scores[-1] - scores[0]
            emoji = "📈" if change > 0 else ("📉" if change < 0 else "➡️")
            text += f"  {emoji} Score change: <b>{'+' if change>0 else ''}{change}</b> pts\n"
    elif cefr_mocks:
        text += "\n📊 <b>CEFR Recent Results:</b>\n"
        for m in cefr_mocks[:5]:
            date = m.completed_at.strftime('%d.%m') if m.completed_at else "—"
            text += f"  • <b>{m.cefr_level}</b>  {int(m.score or 0)}/75  ({date})\n"

    # ── Weak areas ──────────────────────────────────────────
    weak = drf.get("weak_areas", [])
    if weak:
        text += "\n⚠️ <b>Areas to Improve:</b>\n"
        for w in weak[:4]:
            text += f"  • {w['skill']} — avg: <b>{w['avg']}</b>\n"

    # ── Practice plan ───────────────────────────────────────
    total = drf.get("total_mocks", user.total_mocks or 0)
    text += f"\n🎯 <b>Total mocks done:</b> {total}\n"

    if total == 0:
        text += "\n💡 <b>Recommendation:</b>\nStart with a CEFR mock to find your current level."
    elif total < 5:
        text += "\n💡 <b>Recommendation:</b>\nDo at least 2-3 mocks per week for best results."
    else:
        text += "\n💡 <b>Keep going!</b> Consistency is the key to improvement."

    await message.answer(text)

    # ── AI deep analysis ─────────────────────────────────────
    if drf and (drf.get("total_mocks", 0) > 0 or drf.get("total_ai_chats", 0) > 0):
        await message.answer("🤖 Generating AI analysis...")
        analysis = await analyze_statistics(drf)
        if analysis:
            await message.answer(
                "🤖 <b>AI Personal Analysis:</b>\n\n" + analysis +
                "\n\n📱 <b>Detailed charts:</b> Open Web App → My Progress"
            )


@dp.message_handler(commands=["leaderboard"])
@dp.message_handler(text="🏆 Reyting")
async def show_leaderboard(message: types.Message):
    await message.answer("⏳ Reyting yuklanmoqda...")

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📝 IELTS bo'yicha", callback_data="lb_sort:ielts_count"),
        types.InlineKeyboardButton("📊 CEFR bo'yicha", callback_data="lb_sort:cefr_count"),
        types.InlineKeyboardButton("💬 Chat bo'yicha", callback_data="lb_sort:chat_count"),
        types.InlineKeyboardButton("🎯 Amaliyot bo'yicha", callback_data="lb_sort:practice_count"),
    )
    leaders = await get_leaderboard(sort_by="ielts_count")
    text = _format_leaderboard(leaders, "ielts_count")
    await message.answer(text, reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data.startswith("lb_sort:"))
async def leaderboard_sort(call: types.CallbackQuery):
    sort_by = call.data.split(":")[1]
    leaders = await get_leaderboard(sort_by=sort_by)
    labels = {
        "ielts_count": "📝 IELTS",
        "cefr_count": "📊 CEFR",
        "chat_count": "💬 Chat",
        "practice_count": "🎯 Amaliyot",
    }
    text = _format_leaderboard(leaders, sort_by)
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📝 IELTS", callback_data="lb_sort:ielts_count"),
        types.InlineKeyboardButton("📊 CEFR", callback_data="lb_sort:cefr_count"),
        types.InlineKeyboardButton("💬 Chat", callback_data="lb_sort:chat_count"),
        types.InlineKeyboardButton("🎯 Amaliyot", callback_data="lb_sort:practice_count"),
    )
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


def _format_leaderboard(leaders: list, sort_by: str) -> str:
    labels = {
        "ielts_count": "IELTS mock",
        "cefr_count": "CEFR mock",
        "chat_count": "chat",
        "practice_count": "amaliyot",
    }
    label = labels.get(sort_by, sort_by)
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    text = f"🏆 <b>Global Reyting</b> ({label} bo'yicha)\n\n"
    if not leaders:
        text += "Hali reyting ma'lumotlari yo'q."
        return text

    for u in leaders:
        rank = u.get("rank", "—")
        medal = medals.get(rank, f"{rank}.")
        name = u.get("full_name", "User")
        username = u.get("username", "")
        premium = "💎" if u.get("is_premium") else ""
        count = u.get(sort_by, 0)
        name_display = f"@{username}" if username else name
        text += f"{medal} {name_display} {premium} — <b>{count}</b> ta\n"

    return text
