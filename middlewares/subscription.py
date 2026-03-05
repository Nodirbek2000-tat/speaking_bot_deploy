from aiogram import types
from aiogram.dispatcher.middlewares import BaseMiddleware
from loader import bot
from data.config import CHANNEL_ID

EXEMPT_COMMANDS = ["/start", "/admin"]


class SubscriptionMiddleware(BaseMiddleware):
    async def on_pre_process_message(self, message: types.Message, data: dict):
        if message.text and any(message.text.startswith(cmd) for cmd in EXEMPT_COMMANDS):
            return
        if not CHANNEL_ID or CHANNEL_ID == "@speaking_bot_channel":
            return
        try:
            member = await bot.get_chat_member(CHANNEL_ID, message.from_user.id)
            if member.status in ["left", "kicked", "banned"]:
                from keyboards.inline.subscription import subscribe_kb
                await message.answer(
                    "⚠️ Botdan foydalanish uchun kanalimizga obuna bo'lishingiz shart!",
                    reply_markup=subscribe_kb()
                )
                raise Exception("Not subscribed")
        except Exception as e:
            if "Not subscribed" in str(e):
                raise
            pass
