from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

from data.config import WEBAPP_URL


def main_menu(is_premium: bool = False, webapp_url: str = None):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    # Web App button — faqat HTTPS URL larda ishlaydi (Telegram talabi)
    url = webapp_url or WEBAPP_URL
    if url and url.startswith("https://"):
        kb.add(KeyboardButton("🌐 Web App", web_app=WebAppInfo(url=url)))

    kb.row(KeyboardButton("🤖 AI Chat"), KeyboardButton("📝 IELTS Mock"))
    kb.row(KeyboardButton("📊 CEFR Mock"), KeyboardButton("📚 Lug'at"))
    kb.row(KeyboardButton("🗺 Roadmap"), KeyboardButton("📊 My Progress"))
    kb.row(KeyboardButton("⚙️ Sozlamalar"))
    if not is_premium:
        kb.add(KeyboardButton("💎 Premium"))
    return kb


def back_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("🔙 Orqaga"))
    return kb
