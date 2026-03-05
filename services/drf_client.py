import logging
import time
import aiohttp
from data.config import DRF_URL, DRF_FALLBACK_URL, BOT_SECRET, WEBAPP_URL, WEBAPP_FALLBACK_URL

logger = logging.getLogger(__name__)
HEADERS = {"X-Bot-Secret": BOT_SECRET}

# Primary → ittatuz.uz, Fallback → 127.0.0.1:8000
BASE_URLS = [DRF_URL, DRF_FALLBACK_URL]

# Web App URL cache (5 daqiqa)
_webapp_url_cache: str | None = None
_webapp_url_checked_at: float = 0
_WEBAPP_URL_TTL = 300  # 5 daqiqa

# Singleton ClientSession — yangi connection har safar ochilmaydi
_session: aiohttp.ClientSession = None


def get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=30, ttl_dns_cache=300)
        timeout = aiohttp.ClientTimeout(total=15, connect=5)
        _session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=HEADERS
        )
    return _session


async def get_webapp_url() -> str:
    """
    Web App URL ni qaytaradi.
    Avval ittatuz.uz ni tekshiradi, ishlamasa localhost ga fallback.
    Natija 5 daqiqa cache qilinadi.
    """
    global _webapp_url_cache, _webapp_url_checked_at

    now = time.monotonic()
    if _webapp_url_cache and (now - _webapp_url_checked_at) < _WEBAPP_URL_TTL:
        return _webapp_url_cache

    primary = WEBAPP_URL.rstrip('/')
    fallback = WEBAPP_FALLBACK_URL.rstrip('/')

    for url in [primary, fallback]:
        try:
            session = get_session()
            check_timeout = aiohttp.ClientTimeout(total=4, connect=3)
            async with session.get(url + '/', timeout=check_timeout, allow_redirects=True) as resp:
                if resp.status < 500:
                    _webapp_url_cache = url + '/'
                    _webapp_url_checked_at = now
                    if url == fallback and primary != fallback:
                        logger.info(f"[webapp_url] primary ishlamadi, fallback: {fallback}/")
                    return _webapp_url_cache
        except Exception:
            continue

    # Ikkalasi ham ishlamasa fallback qaytaradi
    _webapp_url_cache = fallback + '/'
    _webapp_url_checked_at = now
    return _webapp_url_cache


async def close_session():
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None


async def _get(path: str, params: dict = None) -> dict:
    """Avval primary URL ga, ishlamasa fallback URL ga so'rov yuboradi."""
    for base in BASE_URLS:
        url = f"{base}{path}"
        try:
            session = get_session()
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.warning(f"[DRF GET] {url} → HTTP {resp.status}")
        except Exception as e:
            logger.warning(f"[DRF GET] {url} → {e}")
    return {}


async def _post(path: str, data: dict) -> dict:
    """Avval primary URL ga, ishlamasa fallback URL ga so'rov yuboradi."""
    for base in BASE_URLS:
        url = f"{base}{path}"
        try:
            session = get_session()
            async with session.post(url, json=data) as resp:
                return await resp.json()
        except Exception as e:
            logger.warning(f"[DRF POST] {url} → {e}")
    return {}


# ─── IELTS / CEFR Savollar ───────────────────────────────────────────────────

async def fetch_ielts_questions() -> list:
    data = await _get("/api/ielts/bot/questions/")
    return data.get("questions", [])


async def fetch_cefr_questions() -> list:
    data = await _get("/api/cefr/bot/questions/")
    return data.get("questions", [])


# ─── Faoliyat loglash ─────────────────────────────────────────────────────────

async def log_bot_activity(telegram_id: int, full_name: str, username: str,
                            activity_type: str, data: dict):
    await _post("/api/auth/bot/activity/", {
        "telegram_id": telegram_id,
        "full_name": full_name,
        "username": username or "",
        "activity_type": activity_type,
        "data": data,
    })


# ─── Statistika ───────────────────────────────────────────────────────────────

async def get_bot_statistics(telegram_id: int) -> dict:
    return await _get(
        "/api/auth/bot/statistics/",
        params={"telegram_id": telegram_id}
    )


# ─── Lug'at ──────────────────────────────────────────────────────────────────

async def fetch_vocab_words(level: str = "B1", telegram_id: int = None) -> list:
    params = {"level": level}
    if telegram_id:
        params["telegram_id"] = telegram_id
    data = await _get("/api/vocabulary/bot/words/", params=params)
    return data.get("words", [])


async def get_scheduled_vocab_word() -> dict:
    """Har 4 soatda yuboriladigan so'zni olish"""
    return await _get("/webapp/bot-api/scheduled-word/")


# ─── Free Limits ──────────────────────────────────────────────────────────────

async def get_free_limits() -> dict:
    """DRF AppSettings dan bepul limitlarni olish"""
    settings = await get_app_settings()
    return {
        "free_mocks_limit": settings.get("free_calls_limit", 2),
        "free_messages_limit": settings.get("free_messages_limit", 10),
    }


# ─── Bot Admin API ───────────────────────────────────────────────────────────

async def get_global_stats() -> dict:
    return await _get("/webapp/bot-api/stats/")


async def get_required_channels() -> list:
    data = await _get("/webapp/bot-api/channels/")
    return data.get("channels", [])


async def add_required_channel(username: str, title: str, link: str) -> dict:
    return await _post("/webapp/bot-api/channels/", {
        "action": "add",
        "channel_username": username.lstrip("@"),
        "channel_title": title,
        "channel_link": link,
    })


async def remove_required_channel(username: str) -> dict:
    return await _post("/webapp/bot-api/channels/", {
        "action": "remove",
        "channel_username": username.lstrip("@"),
    })


async def set_channel_bot_admin(username: str, is_admin: bool) -> dict:
    return await _post("/webapp/bot-api/channels/", {
        "action": "set_bot_admin",
        "channel_username": username.lstrip("@"),
        "is_bot_admin": is_admin,
    })


async def cancel_user_premium(telegram_id: int) -> dict:
    return await _post("/webapp/bot-api/cancel-premium/", {
        "telegram_id": telegram_id,
    })


async def grant_user_premium(telegram_id: int, days: int = 30) -> dict:
    return await _post("/webapp/bot-api/grant-premium/", {
        "telegram_id": telegram_id,
        "days": days,
    })


async def get_app_settings() -> dict:
    return await _get("/webapp/bot-api/settings/")


async def update_app_settings(**kwargs) -> dict:
    return await _post("/webapp/bot-api/settings/", kwargs)


async def get_payment_card_info() -> dict:
    """DRF dan aktiv to'lov kartasi va 1 oylik reja narxini olish"""
    return await _get("/webapp/bot-api/payment-card/")


async def create_premium_request_drf(
    telegram_id: int, full_name: str, username: str,
    receipt_file_id: str, plan_id: int = None
) -> dict:
    """Bot chek yuborilganda DRF da PremiumPurchase yaratish"""
    data = {
        "telegram_id": telegram_id,
        "full_name": full_name,
        "username": username or "",
        "receipt_file_id": receipt_file_id,
    }
    if plan_id:
        data["plan_id"] = plan_id
    return await _post("/webapp/bot-api/premium-request/", data)


async def sync_tense_stats(telegram_id: int, tense_data: dict) -> dict:
    """Bot tense statistikasini DRF ga yuborish"""
    if not tense_data:
        return {}
    return await _post("/api/auth/bot/tense-stats/", {
        "telegram_id": telegram_id,
        "tense_data": tense_data,
    })


# ─── Leaderboard ──────────────────────────────────────────────────────────────

async def get_leaderboard(sort_by: str = "ielts_count") -> list:
    """Global reyting ro'yxatini olish"""
    data = await _get("/webapp/bot-api/leaderboard/", params={"sort": sort_by})
    return data.get("leaderboard", [])


# ─── IELTS / CEFR natijalarni DRF ga saqlash ─────────────────────────────────

async def save_ielts_result(telegram_id: int, band: float, sub_scores: dict, feedback: dict) -> dict:
    """IELTS mock natijasini DRF IELTSSession ga saqlash"""
    return await _post("/webapp/bot-api/save-ielts/", {
        "telegram_id": telegram_id,
        "band": band,
        "sub_scores": sub_scores,
        "feedback": feedback,
    })


async def sync_phone_number(telegram_id: int, phone: str) -> dict:
    """Bot dan olingan telefon raqamini DRF ga saqlash"""
    return await _post("/webapp/bot-api/save-phone/", {
        "telegram_id": telegram_id,
        "phone": phone,
    })


async def save_cefr_result(telegram_id: int, score: int, level: str, feedback: dict) -> dict:
    """CEFR mock natijasini DRF CEFRSession ga saqlash"""
    return await _post("/webapp/bot-api/save-cefr/", {
        "telegram_id": telegram_id,
        "score": score,
        "level": level,
        "feedback": feedback,
    })

# ─── mock_ielts.py uchun funksiyalar ─────────────────────────────────────────

async def get_ielts_questions() -> list:
    """IELTS savollarini backenddan olish (mock_ielts.py uchun)"""
    return await fetch_ielts_questions()


async def save_ielts_session(
    telegram_id: int,
    band: float,
    sub_scores: dict,
    feedback: dict,
    answers: list = None,
) -> dict | None:
    """IELTS natijasini backendga saqlash (answers bilan)"""
    return await _post("/webapp/bot-api/save-ielts/", {
        "telegram_id": telegram_id,
        "band": band,
        "sub_scores": sub_scores,
        "feedback": feedback,
        "answers": answers or [],
    })


async def get_user_profile(telegram_id: int) -> dict:
    """Foydalanuvchi profilini (premium, limit) DRF dan olish"""
    data = await _get("/api/auth/bot/statistics/", params={"telegram_id": telegram_id})
    if data:
        return data
    return {
        "id": telegram_id,
        "ielts_count": 0,
        "free_ielts_limit": 2,
        "has_premium": False,
    }


async def sync_user_phone(
    telegram_id: int,
    phone: str,
    username: str = '',
    full_name: str = '',
    first_name: str = '',
    last_name: str = '',
) -> dict:
    """Bot dan olingan telefon + user ma'lumotlarini DRF ga yuborish"""
    return await _post("/webapp/bot-api/save-phone/", {
        "telegram_id": telegram_id,
        "phone": phone,
        "username": username or '',
        "full_name": full_name or '',
        "first_name": first_name or '',
        "last_name": last_name or '',
    })
