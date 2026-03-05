from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, Text, Float, JSON

from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    full_name = Column(String(255))
    username = Column(String(255), nullable=True)
    is_premium = Column(Boolean, default=False)
    premium_expires = Column(DateTime, nullable=True)
    free_mocks_used = Column(Integer, default=0)
    total_mocks = Column(Integer, default=0)
    phone_number = Column(String(20), nullable=True)
    referral_code = Column(String(12), nullable=True)
    referred_by = Column(BigInteger, nullable=True)
    referral_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)


class MockSession(Base):
    __tablename__ = "mock_sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    mock_type = Column(String(10), nullable=False)
    questions = Column(Text, default="[]")
    answers = Column(Text, default="[]")
    transcripts = Column(Text, default="[]")
    current_question = Column(Integer, default=0)
    score = Column(Float, nullable=True)
    cefr_level = Column(String(5), nullable=True)
    feedback = Column(Text, nullable=True)
    status = Column(String(20), default="in_progress")
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class IELTSQuestion(Base):
    __tablename__ = "ielts_questions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    part = Column(Integer, nullable=False)
    question = Column(Text, nullable=False)
    cue_card_points = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CEFRQuestion(Base):
    __tablename__ = "cefr_questions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    part = Column(Integer, nullable=False)
    question = Column(Text, nullable=False)
    image_file_id = Column(String(255), nullable=True)
    extra_info = Column(Text, nullable=True)
    instruction = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class WordBank(Base):
    __tablename__ = "word_bank"
    id = Column(Integer, primary_key=True, autoincrement=True)
    word = Column(String(100), nullable=False)
    level = Column(String(2), nullable=False)
    definition = Column(Text)
    translation_uz = Column(Text, default="")
    examples = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)


class SavedWord(Base):
    __tablename__ = "saved_words"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    word = Column(String(100), nullable=False)
    definition = Column(Text)
    translation_uz = Column(Text, default="")
    examples = Column(Text, default="[]")
    saved_at = Column(DateTime, default=datetime.utcnow)


class DailyActivity(Base):
    __tablename__ = "daily_activity"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    date = Column(String(10), nullable=False)
    mocks_done = Column(Integer, default=0)
    words_looked = Column(Integer, default=0)
    ai_chats = Column(Integer, default=0)
    last_ielts_band = Column(Float, nullable=True)
    last_cefr_score = Column(Integer, nullable=True)
    last_cefr_level = Column(String(5), nullable=True)


class TenseStats(Base):
    __tablename__ = "tense_stats"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    date = Column(String(10), nullable=False)
    tense_name = Column(String(50), nullable=False)
    usage_count = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    accuracy = Column(Float, default=0.0)


class Reminder(Base):
    __tablename__ = "reminders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    days_of_week = Column(Text, default="[]")
    hour = Column(Integer, nullable=False)
    minute = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
