from aiogram.dispatcher.filters.state import State, StatesGroup

class IELTSMock(StatesGroup):
    part1 = State()
    part2 = State()
    part3 = State()

class CEFRMock(StatesGroup):
    answering = State()

class SpeakingChat(StatesGroup):
    selecting_gender = State()
    chatting = State()

class WordDiscuss(StatesGroup):
    discussing = State()

class VocabSearch(StatesGroup):
    waiting_word = State()
    viewing_word = State()

class PremiumPurchase(StatesGroup):
    waiting_plan = State()
    waiting_receipt = State()

class AdminStates(StatesGroup):
    waiting_user_id = State()
    confirming_premium = State()
    adding_ielts_question = State()
    adding_cefr_question = State()
    adding_cefr_image = State()
    adding_words_json = State()
    broadcast_message = State()

class SettingsStates(StatesGroup):
    main = State()
    reminder_days = State()
    reminder_hour = State()
    reminder_minute = State()

class VocabPractice(StatesGroup):
    quizzing = State()

class PhoneRequest(StatesGroup):
    waiting_phone = State()
