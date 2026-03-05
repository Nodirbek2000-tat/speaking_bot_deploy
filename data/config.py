from environs import Env

env = Env()
env.read_env()

BOT_TOKEN = env.str("BOT_TOKEN")
ADMINS = env.list("ADMINS")
IP = env.str("ip", "localhost")
OPENAI_API_KEY = env.str("OPENAI_API_KEY")
FREE_MOCK_LIMIT = env.int("FREE_MOCK_LIMIT", 2)
CHANNEL_ID = env.str("CHANNEL_ID", "@speaking_bot_channel")
CHANNEL_LINK = env.str("CHANNEL_LINK", "https://t.me/speaking_bot_channel")
OWNER_USERNAME = env.str("OWNER_USERNAME", "@nodirbek_shukurov1")

# DRF backend — primary ittatuz.uz, fallback localhost
DRF_URL = env.str("DRF_URL", "http://ittatuz.uz")
DRF_FALLBACK_URL = env.str("DRF_FALLBACK_URL", "http://127.0.0.1:8000")

# Web App URL — primary ittatuz.uz, fallback localhost
WEBAPP_URL = env.str("WEBAPP_URL", "https://ittatuz.uz/webapp/another/")
WEBAPP_FALLBACK_URL = env.str("WEBAPP_FALLBACK_URL", "http://127.0.0.1:8000/webapp/")

BOT_SECRET = env.str("BOT_SECRET", "speaking-bot-secret-key-2024")
BOT_USERNAME = env.str("BOT_USERNAME", "speaking_engbot")
PAYMENT_CHANNEL = env.str("PAYMENT_CHANNEL", "")
