import json
import uuid
import logging
from datetime import datetime, timedelta
from sqlalchemy import select, desc

from .database import async_session
from .models import User, MockSession, IELTSQuestion, CEFRQuestion, WordBank, SavedWord, DailyActivity, TenseStats, Reminder

logger = logging.getLogger(__name__)


async def get_or_create_user(telegram_id: int, full_name: str, username: str = None, ref_code: str = None) -> User:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            referral_code = str(uuid.uuid4())[:8].upper()
            user = User(telegram_id=telegram_id, full_name=full_name, username=username, referral_code=referral_code)
            if ref_code:
                ref_result = await session.execute(select(User).where(User.referral_code == ref_code))
                referrer = ref_result.scalar_one_or_none()
                if referrer and referrer.telegram_id != telegram_id:
                    user.referred_by = referrer.telegram_id
                    referrer.referral_count = (referrer.referral_count or 0) + 1
                    if referrer.referral_count % 2 == 0:
                        referrer.is_premium = True
                        referrer.premium_expires = datetime.utcnow() + timedelta(days=30)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        else:
            user.last_active = datetime.utcnow()
            user.full_name = full_name
            if username:
                user.username = username
            await session.commit()
        return user


async def save_phone_number(telegram_id: int, phone: str) -> bool:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            return False
        user.phone_number = phone
        await session.commit()
        return True


async def get_user(telegram_id: int) -> User:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()


async def get_all_users() -> list:
    async with async_session() as session:
        result = await session.execute(select(User))
        return result.scalars().all()


async def activate_premium(telegram_id: int, days: int = 30) -> bool:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            return False
        user.is_premium = True
        user.premium_expires = datetime.utcnow() + timedelta(days=days)
        await session.commit()
    # Also update Django DB (webapp sync)
    try:
        from services.drf_client import grant_user_premium
        await grant_user_premium(telegram_id, days)
    except Exception as e:
        logger.warning(f"[DRF premium sync] error: {e}")
    return True


async def deactivate_premium(telegram_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            return False
        user.is_premium = False
        user.premium_expires = None
        await session.commit()
        return True


async def check_premium(telegram_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            return False
        if user.is_premium:
            if user.premium_expires and user.premium_expires < datetime.utcnow():
                user.is_premium = False
                await session.commit()
                return False
            return True
        return False


async def can_do_mock(telegram_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            return False
        if user.is_premium:
            if user.premium_expires and user.premium_expires < datetime.utcnow():
                user.is_premium = False
                await session.commit()
            else:
                return True
        # DRF dan limit olish (fallback: config)
        try:
            from services.drf_client import get_free_limits
            limits = await get_free_limits()
            limit = limits.get("free_mocks_limit", 2)
        except Exception:
            from data.config import FREE_MOCK_LIMIT
            limit = FREE_MOCK_LIMIT
        return user.free_mocks_used < limit


async def increment_mock_count(telegram_id: int):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user:
            user.free_mocks_used += 1
            user.total_mocks += 1
            await session.commit()


async def create_mock_session(user_id: int, mock_type: str, questions: list) -> MockSession:
    async with async_session() as session:
        ms = MockSession(user_id=user_id, mock_type=mock_type, questions=json.dumps(questions, ensure_ascii=False))
        session.add(ms)
        await session.commit()
        await session.refresh(ms)
        return ms


async def get_active_mock(user_id: int) -> MockSession:
    async with async_session() as session:
        result = await session.execute(
            select(MockSession).where(MockSession.user_id == user_id, MockSession.status == "in_progress").order_by(desc(MockSession.id))
        )
        return result.scalars().first()


async def update_mock_answer(session_id: int, transcript: str, answer_text: str):
    async with async_session() as session:
        result = await session.execute(select(MockSession).where(MockSession.id == session_id))
        ms = result.scalar_one_or_none()
        if ms:
            transcripts = json.loads(ms.transcripts or "[]")
            transcripts.append(transcript)
            ms.transcripts = json.dumps(transcripts, ensure_ascii=False)
            answers = json.loads(ms.answers or "[]")
            answers.append(answer_text)
            ms.answers = json.dumps(answers, ensure_ascii=False)
            ms.current_question += 1
            await session.commit()
        return ms


async def complete_mock(session_id: int, score, cefr_level: str, feedback: str):
    async with async_session() as session:
        result = await session.execute(select(MockSession).where(MockSession.id == session_id))
        ms = result.scalar_one_or_none()
        if ms:
            ms.score = score
            ms.cefr_level = cefr_level
            ms.status = "completed"
            ms.feedback = feedback
            ms.completed_at = datetime.utcnow()
            await session.commit()
        return ms


async def get_user_mocks(user_id: int, mock_type: str = None, limit: int = 5) -> list:
    async with async_session() as session:
        q = select(MockSession).where(MockSession.user_id == user_id, MockSession.status == "completed")
        if mock_type:
            q = q.where(MockSession.mock_type == mock_type)
        q = q.order_by(desc(MockSession.completed_at)).limit(limit)
        result = await session.execute(q)
        return result.scalars().all()


async def add_ielts_question(part: int, question: str, cue_card_points: list = None) -> IELTSQuestion:
    async with async_session() as session:
        q = IELTSQuestion(part=part, question=question, cue_card_points=json.dumps(cue_card_points) if cue_card_points else None)
        session.add(q)
        await session.commit()
        await session.refresh(q)
        return q


async def get_ielts_questions(part: int = None) -> list:
    async with async_session() as session:
        query = select(IELTSQuestion).where(IELTSQuestion.is_active == True)
        if part:
            query = query.where(IELTSQuestion.part == part)
        result = await session.execute(query)
        return result.scalars().all()


async def get_random_ielts_set() -> list:
    import random
    p1 = await get_ielts_questions(1)
    p2 = await get_ielts_questions(2)
    p3 = await get_ielts_questions(3)
    result = []
    if p1: result += random.sample(p1, min(3, len(p1)))
    if p2: result += random.sample(p2, min(1, len(p2)))
    if p3: result += random.sample(p3, min(3, len(p3)))
    return result


async def delete_ielts_question(qid: int) -> bool:
    async with async_session() as session:
        result = await session.execute(select(IELTSQuestion).where(IELTSQuestion.id == qid))
        q = result.scalar_one_or_none()
        if q:
            await session.delete(q)
            await session.commit()
            return True
        return False


async def add_cefr_question(part: int, question: str, image_file_id: str = None, instruction: str = None, extra_info: str = None) -> CEFRQuestion:
    async with async_session() as session:
        q = CEFRQuestion(part=part, question=question, image_file_id=image_file_id, instruction=instruction, extra_info=extra_info)
        session.add(q)
        await session.commit()
        await session.refresh(q)
        return q


async def get_cefr_questions(part: int = None) -> list:
    async with async_session() as session:
        query = select(CEFRQuestion).where(CEFRQuestion.is_active == True)
        if part:
            query = query.where(CEFRQuestion.part == part)
        result = await session.execute(query)
        return result.scalars().all()


async def get_random_cefr_set() -> list:
    import random
    p1 = await get_cefr_questions(1)
    p2 = await get_cefr_questions(2)
    p3 = await get_cefr_questions(3)
    p4 = await get_cefr_questions(4)
    result = []
    if p1: result += random.sample(p1, min(3, len(p1)))
    if p2: result += random.sample(p2, min(1, len(p2)))
    if p3: result += random.sample(p3, min(1, len(p3)))
    if p4: result += random.sample(p4, min(2, len(p4)))
    return result


async def delete_cefr_question(qid: int) -> bool:
    async with async_session() as session:
        result = await session.execute(select(CEFRQuestion).where(CEFRQuestion.id == qid))
        q = result.scalar_one_or_none()
        if q:
            await session.delete(q)
            await session.commit()
            return True
        return False


async def add_word_to_bank(word: str, level: str, definition: str, translation_uz: str = "", examples: list = None) -> WordBank:
    async with async_session() as session:
        wb = WordBank(word=word, level=level, definition=definition, translation_uz=translation_uz, examples=json.dumps(examples or [], ensure_ascii=False))
        session.add(wb)
        await session.commit()
        await session.refresh(wb)
        return wb


async def get_random_words(level: str = None, count: int = 5) -> list:
    import random
    async with async_session() as session:
        query = select(WordBank)
        if level:
            query = query.where(WordBank.level == level)
        result = await session.execute(query)
        words = result.scalars().all()
        return random.sample(words, min(count, len(words))) if words else []


async def get_all_bank_words() -> list:
    async with async_session() as session:
        result = await session.execute(select(WordBank))
        return result.scalars().all()


async def save_word(user_id: int, word: str, definition: str, translation_uz: str, examples: list):
    async with async_session() as session:
        existing = await session.execute(select(SavedWord).where(SavedWord.user_id == user_id, SavedWord.word == word))
        if existing.scalar_one_or_none():
            return False
        sw = SavedWord(user_id=user_id, word=word, definition=definition, translation_uz=translation_uz, examples=json.dumps(examples, ensure_ascii=False))
        session.add(sw)
        await session.commit()
        return True


async def get_saved_words(user_id: int) -> list:
    async with async_session() as session:
        result = await session.execute(select(SavedWord).where(SavedWord.user_id == user_id).order_by(desc(SavedWord.saved_at)))
        return result.scalars().all()


async def log_activity(user_id: int, mock_done: bool = False, word_looked: bool = False, ai_chat: bool = False,
                       ielts_band: float = None, cefr_score: int = None, cefr_level: str = None):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    async with async_session() as session:
        result = await session.execute(select(DailyActivity).where(DailyActivity.user_id == user_id, DailyActivity.date == today))
        da = result.scalar_one_or_none()
        if not da:
            da = DailyActivity(user_id=user_id, date=today)
            session.add(da)
        if mock_done: da.mocks_done = (da.mocks_done or 0) + 1
        if word_looked: da.words_looked = (da.words_looked or 0) + 1
        if ai_chat: da.ai_chats = (da.ai_chats or 0) + 1
        if ielts_band: da.last_ielts_band = ielts_band
        if cefr_score: da.last_cefr_score = cefr_score
        if cefr_level: da.last_cefr_level = cefr_level
        await session.commit()


async def get_today_activity(user_id: int) -> DailyActivity:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    async with async_session() as session:
        result = await session.execute(select(DailyActivity).where(DailyActivity.user_id == user_id, DailyActivity.date == today))
        return result.scalar_one_or_none()


async def get_all_activity_today() -> list:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    async with async_session() as session:
        result = await session.execute(select(DailyActivity).where(DailyActivity.date == today))
        return result.scalars().all()


# ─── TenseStats CRUD ──────────────────────────────────────────────────────────

async def update_tense_stats(user_id: int, tense_data: dict):
    """tense_data: {tense_name: {"usage": n, "correct": n}, ...}"""
    if not tense_data:
        return
    today = datetime.utcnow().strftime("%Y-%m-%d")
    async with async_session() as session:
        for tense_name, counts in tense_data.items():
            result = await session.execute(
                select(TenseStats).where(
                    TenseStats.user_id == user_id,
                    TenseStats.date == today,
                    TenseStats.tense_name == tense_name
                )
            )
            ts = result.scalar_one_or_none()
            if not ts:
                ts = TenseStats(user_id=user_id, date=today, tense_name=tense_name)
                session.add(ts)
            ts.usage_count = (ts.usage_count or 0) + counts.get("usage", 0)
            ts.correct_count = (ts.correct_count or 0) + counts.get("correct", 0)
            if ts.usage_count > 0:
                ts.accuracy = round(ts.correct_count / ts.usage_count * 100, 1)
        await session.commit()


async def get_tense_stats_summary(user_id: int, days: int = 30) -> dict:
    """Aggregated tense stats for last N days"""
    start_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    async with async_session() as session:
        result = await session.execute(
            select(TenseStats).where(
                TenseStats.user_id == user_id,
                TenseStats.date >= start_date
            )
        )
        stats = result.scalars().all()

    summary = {}
    for s in stats:
        if s.tense_name not in summary:
            summary[s.tense_name] = {"usage": 0, "correct": 0}
        summary[s.tense_name]["usage"] += s.usage_count
        summary[s.tense_name]["correct"] += s.correct_count

    for tense in summary:
        usage = summary[tense]["usage"]
        if usage > 0:
            summary[tense]["accuracy"] = round(summary[tense]["correct"] / usage * 100)
        else:
            summary[tense]["accuracy"] = 0
    return summary


# ─── Reminder CRUD ────────────────────────────────────────────────────────────

async def save_reminder(user_id: int, days_of_week: list, hour: int, minute: int) -> Reminder:
    async with async_session() as session:
        r = Reminder(
            user_id=user_id,
            days_of_week=json.dumps(days_of_week),
            hour=hour,
            minute=minute,
            is_active=True
        )
        session.add(r)
        await session.commit()
        await session.refresh(r)
        return r


async def get_user_reminders(user_id: int) -> list:
    async with async_session() as session:
        result = await session.execute(
            select(Reminder).where(Reminder.user_id == user_id, Reminder.is_active == True)
        )
        return result.scalars().all()


async def get_all_active_reminders() -> list:
    async with async_session() as session:
        result = await session.execute(
            select(Reminder).where(Reminder.is_active == True)
        )
        return result.scalars().all()


async def delete_reminder(reminder_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(select(Reminder).where(Reminder.id == reminder_id))
        r = result.scalar_one_or_none()
        if r:
            r.is_active = False
            await session.commit()
            return True
        return False
