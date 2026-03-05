import asyncio
import json
import logging
from datetime import datetime, timezone as dt_timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    return _scheduler


def setup_scheduler():
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    _scheduler.add_job(send_daily_reports, CronTrigger(hour=22, minute=0), id="daily_reports")
    _scheduler.add_job(send_premium_expiry_warnings, CronTrigger(hour=10, minute=0), id="premium_warnings")
    _scheduler.add_job(send_scheduled_vocab_word, CronTrigger(hour="*/4", minute=0), id="vocab_word")
    _scheduler.add_job(check_and_send_reminders, CronTrigger(minute="*"), id="reminders")
    _scheduler.start()
    logger.info("Scheduler started: daily_reports 22:00, premium_warnings 10:00, vocab */4h, reminders */1min")


async def load_user_reminders():
    """Startup da barcha active reminderlarni schedule qilish"""
    try:
        from utils.db_api.crud import get_all_active_reminders
        reminders = await get_all_active_reminders()
        for r in reminders:
            schedule_one_reminder(r)
        logger.info(f"Loaded {len(reminders)} reminders from DB")
    except Exception as e:
        logger.warning(f"load_user_reminders error: {e}")


def schedule_one_reminder(reminder):
    """Bitta eslatmani APScheduler ga qo'shish"""
    if _scheduler is None:
        return
    job_id = f"reminder_{reminder.id}"
    try:
        days = json.loads(reminder.days_of_week or "[]")
        if not days:
            return
        # APScheduler cron day_of_week: 0=Mon ... 6=Sun
        dow_str = ",".join(str(d) for d in days)
        _scheduler.add_job(
            _send_reminder,
            CronTrigger(day_of_week=dow_str, hour=reminder.hour, minute=reminder.minute),
            id=job_id,
            args=[reminder.user_id, reminder.id],
            replace_existing=True
        )
    except Exception as e:
        logger.warning(f"schedule_one_reminder {reminder.id} error: {e}")


def remove_reminder_job(reminder_id: int):
    """Eslatmani schedulerdan o'chirish"""
    if _scheduler is None:
        return
    job_id = f"reminder_{reminder_id}"
    try:
        job = _scheduler.get_job(job_id)
        if job:
            job.remove()
    except Exception as e:
        logger.warning(f"remove_reminder_job {reminder_id} error: {e}")


async def _send_reminder(user_id: int, reminder_id: int):
    """Eslatma xabarini yuborish"""
    from loader import bot
    try:
        await bot.send_message(
            user_id,
            "🔔 <b>O'qish vaqti!</b>\n\n"
            "📚 Ingliz tilini mashq qilish vaqti keldi.\n"
            "Bugun kamida 20 daqiqa ajrating:\n"
            "  • 🎙 AI Chat bilan gaplashing\n"
            "  • 📝 Mock test topshiring\n"
            "  • 📖 Yangi so'z o'rganing\n\n"
            "💪 Har kun oz-ozdan — katta natija!"
        )
    except Exception as e:
        logger.warning(f"Send reminder {reminder_id} to {user_id} error: {e}")


async def check_and_send_reminders():
    """Har daqiqada reminder tekshirish (APScheduler fallback)"""
    # schedule_one_reminder orqali individual cron ishlatilmoqda
    # Bu funksiya faqat log uchun
    pass


async def send_scheduled_vocab_word():
    """Har 4 soatda barcha foydalanuvchilarga so'z yuborish"""
    from loader import bot
    from utils.db_api.crud import get_all_users
    from services.drf_client import get_scheduled_vocab_word

    # DRF dan so'z olish
    word_data = await get_scheduled_vocab_word()
    if not word_data or not word_data.get("word"):
        logger.info("No scheduled vocab word available")
        return

    word = word_data.get("word", "")
    translation = word_data.get("translation", "")
    definition = word_data.get("definition", "")
    example = word_data.get("example", "")
    level = word_data.get("level", "")

    text = (
        f"📚 <b>Kunlik So'z</b>\n\n"
        f"<b>{word}</b>  <code>[{level}]</code>\n\n"
        f"📝 <i>{definition}</i>\n"
        f"🇺🇿 {translation}\n\n"
    )
    if example:
        text += f"✍️ <i>{example}</i>\n\n"
    text += "📖 /vocabulary — so'z qidirish va saqlash"

    users = await get_all_users()
    tg_users = [u for u in users if u.telegram_id]

    BATCH = 50

    async def send_one(user):
        try:
            await bot.send_message(user.telegram_id, text)
            return True
        except Exception:
            return False

    sent = 0
    for i in range(0, len(tg_users), BATCH):
        batch = tg_users[i:i + BATCH]
        results = await asyncio.gather(*[send_one(u) for u in batch])
        sent += sum(results)
        await asyncio.sleep(0.5)

    logger.info(f"Vocab word '{word}' sent to {sent}/{len(tg_users)} users")


async def send_premium_expiry_warnings():
    from loader import bot
    from utils.db_api.crud import get_all_users

    users = await get_all_users()
    now = datetime.now(dt_timezone.utc)

    BATCH = 50

    async def check_and_warn(user):
        if not user.is_premium or not user.premium_expires:
            return
        try:
            expires = user.premium_expires
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=dt_timezone.utc)
            days_left = (expires - now).days

            if days_left in (1, 2, 3):
                exp_str = expires.strftime('%d.%m.%Y')
                await bot.send_message(
                    user.telegram_id,
                    f"⚠️ <b>Premium muddati tugayapti!</b>\n\n"
                    f"💎 Premiumingiz <b>{days_left} kun</b> ichida tugaydi.\n"
                    f"📅 Tugash sanasi: <b>{exp_str}</b>\n\n"
                    f"Davom ettirish uchun /premium buyrug'ini yuboring."
                )
        except Exception as e:
            logger.warning(f"Premium expiry warning error for {user.telegram_id}: {e}")

    for i in range(0, len(users), BATCH):
        batch = users[i:i + BATCH]
        await asyncio.gather(*[check_and_warn(u) for u in batch])
        await asyncio.sleep(0.2)


TENSE_DISPLAY_REPORT = {
    "present_simple": "Pres.Simple",
    "present_continuous": "Pres.Cont.",
    "past_simple": "Past Simple",
    "past_perfect": "Past Perf.",
    "future_simple": "Future",
    "present_perfect": "Pres.Perf.",
    "conditional": "Conditional",
}


async def send_daily_reports():
    from loader import bot
    from utils.db_api.crud import get_all_users, get_today_activity, get_tense_stats_summary
    from services.ai_service import generate_daily_report
    from services.drf_client import get_bot_statistics

    users = await get_all_users()
    active_users = []

    for user in users:
        activity = await get_today_activity(user.telegram_id)
        if not activity:
            continue
        if activity.mocks_done == 0 and activity.words_looked == 0 and activity.ai_chats == 0:
            continue
        active_users.append((user, activity))

    BATCH = 20

    async def send_report(user, activity):
        try:
            activity_data = {
                "mocks_done": activity.mocks_done,
                "words_looked": activity.words_looked,
                "ai_chats": activity.ai_chats,
                "last_ielts_band": activity.last_ielts_band,
                "last_cefr_score": activity.last_cefr_score,
                "last_cefr_level": activity.last_cefr_level,
            }
            drf_stats, today_tense = await asyncio.gather(
                get_bot_statistics(user.telegram_id),
                get_tense_stats_summary(user.telegram_id, days=1),
            )
            report = await generate_daily_report(activity_data, drf_stats=drf_stats)

            # ─── Asosiy ma'lumotlar ───────────────────────────
            details = ""
            if activity.last_ielts_band:
                details += f"\n📝 Bugungi IELTS: <b>Band {activity.last_ielts_band}</b>"
                # Sub-scores (DRF dan)
                if drf_stats:
                    ielts_hist = drf_stats.get("ielts_history", [])
                    if ielts_hist:
                        last_sub = ielts_hist[-1].get("sub_scores", {})
                        if last_sub:
                            sub_parts = []
                            lbl = {"fluency": "Flu", "lexical": "Lex", "grammar": "Gram", "pronunciation": "Pron"}
                            for k, l in lbl.items():
                                v = last_sub.get(k)
                                if v:
                                    sub_parts.append(f"{l}:{v}")
                            if sub_parts:
                                details += f" <i>({' | '.join(sub_parts)})</i>"
            if activity.last_cefr_score:
                lvl = activity.last_cefr_level or ""
                details += f"\n📊 Bugungi CEFR: <b>{int(activity.last_cefr_score)}/75</b> ({lvl})"

            # ─── Faoliyat qisqacha ───────────────────────────
            activity_line = ""
            parts = []
            if activity.mocks_done:
                parts.append(f"📝 {activity.mocks_done} ta mock")
            if activity.words_looked:
                parts.append(f"📚 {activity.words_looked} ta so'z")
            if activity.ai_chats:
                parts.append(f"🤖 {activity.ai_chats} ta AI suhbat")
            if parts:
                activity_line = "\n🎯 Bugun: " + " | ".join(parts)

            # ─── Tense statistikasi ──────────────────────────
            tense_block = ""
            if today_tense:
                tense_block = "\n\n📊 <b>Bugungi grammatika:</b>\n"
                shown = 0
                for tense_key, label in TENSE_DISPLAY_REPORT.items():
                    if tense_key in today_tense:
                        v = today_tense[tense_key]
                        acc = v.get("accuracy", 0)
                        usage = v.get("usage", 0)
                        filled = round(acc / 10)
                        bar = "█" * filled + "░" * (10 - filled)
                        tense_block += f"  <code>{bar}</code> {label}: <b>{acc}%</b> ({usage}x)\n"
                        shown += 1
                if shown == 0:
                    tense_block = ""
            else:
                tense_block = "\n\n📊 <i>Bugun AI chat qilinmadi — grammatika hisoblanmadi</i>"

            # ─── Vocab o'sish ────────────────────────────────
            vocab_note = ""
            if activity.words_looked == 0:
                vocab_note = "\n📚 <i>Bugun yangi so'z o'rganilmadi — ertaga sinab ko'ring!</i>"

            text = (
                "📊 <b>Kunlik Hisobot</b>"
                + details
                + activity_line
                + tense_block
                + vocab_note
                + "\n\n"
                + report
            )
            await bot.send_message(user.telegram_id, text)
        except Exception as e:
            logger.warning(f"Daily report error for {user.telegram_id}: {e}")

    for i in range(0, len(active_users), BATCH):
        batch = active_users[i:i + BATCH]
        await asyncio.gather(*[send_report(u, a) for u, a in batch])
        await asyncio.sleep(0.5)

    # Faol bo'lmagan userlarga eslatma (mock yoki chat qilmagan)
    inactive_users = [u for u in users if u not in [uu for uu, _ in active_users]]
    INACTIVE_BATCH = 50

    async def send_inactive_reminder(user):
        try:
            await bot.send_message(
                user.telegram_id,
                "👋 <b>Bugun hali mashq qilmadingiz!</b>\n\n"
                "📝 Mock test topshiring yoki\n"
                "🤖 AI Chat bilan gaplashing.\n\n"
                "Har kunlik mashq — tez o'sishning kaliti! 💪"
            )
        except Exception:
            pass

    for i in range(0, len(inactive_users), INACTIVE_BATCH):
        batch = inactive_users[i:i + INACTIVE_BATCH]
        await asyncio.gather(*[send_inactive_reminder(u) for u in batch])
        await asyncio.sleep(0.3)

    logger.info(f"Daily reports sent to {len(active_users)} active users, {len(inactive_users)} reminders sent")
