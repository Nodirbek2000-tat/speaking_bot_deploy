"""
bot/services/limits.py — YANGI FAYL
Bot handlerlarda limit tekshirish uchun markaziy servis.

Ishlatish:
    from services.limits import check_limit, LimitType

    allowed, used, total = await check_limit(telegram_id, LimitType.IELTS)
    if not allowed:
        await message.answer(f"Limit tugadi! {used}/{total}")
"""
import aiohttp
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class LimitType(str, Enum):
    SPEAKING = "speaking"       # Real partner call
    AI_CALL = "ai_call"        # AI call
    PRACTICE = "practice"      # Practice session
    IELTS = "ielts"            # IELTS Mock
    CEFR = "cefr"              # CEFR Mock


async def check_limit(telegram_id: int, limit_type: LimitType) -> tuple[bool, int, int]:
    """
    Foydalanuvchi limitini tekshirish.

    Returns:
        (allowed: bool, used: int, total: int)
        allowed=True  → davom etish mumkin
        allowed=False → limit tugagan
    """
    from data.config import DRF_URL, BOT_SECRET

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{DRF_URL}/webapp/bot-api/check-limit/",
                params={"telegram_id": telegram_id, "type": limit_type},
                headers={"X-Bot-Secret": BOT_SECRET},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return (
                        data.get("allowed", True),
                        data.get("used", 0),
                        data.get("total", 999),
                    )
    except Exception as e:
        logger.error(f"check_limit error: {e}")

    # Xato bo'lsa — ruxsat beramiz (fail open)
    return True, 0, 999


def limit_exceeded_text(limit_type: LimitType, used: int, total: int) -> str:
    """Limit tugaganda ko'rsatiladigan xabar"""
    names = {
        LimitType.SPEAKING: "Speaking qo'ng'iroqlar",
        LimitType.AI_CALL: "AI qo'ng'iroqlar",
        LimitType.PRACTICE: "Practice sessiyalar",
        LimitType.IELTS: "IELTS Mock testlar",
        LimitType.CEFR: "CEFR Mock testlar",
    }
    name = names.get(limit_type, "Bepul foydalanish")

    return (
        f"⚠️ <b>Bepul limit tugadi!</b>\n\n"
        f"📊 {name}: <b>{used}/{total}</b> ishlatildi\n\n"
        f"💎 Cheksiz foydalanish uchun <b>Premium</b> oling!\n"
        f"Premium bilan:\n"
        f"• ♾️ Cheksiz Speaking va AI qo'ng'iroqlar\n"
        f"• ♾️ Cheksiz Practice sessiyalar\n"
        f"• ♾️ Cheksiz IELTS va CEFR Mock testlar\n"
        f"• 📊 Batafsil tahlil va AI maslahatlar"
    )