import io
from openai import AsyncOpenAI
from data.config import OPENAI_API_KEY

client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def voice_to_text(voice, bot) -> str:
    try:
        file_info = await bot.get_file(voice.file_id)
        file_bytes = await bot.download_file(file_info.file_path)
        audio_data = io.BytesIO(file_bytes.getvalue())
        audio_data.name = "voice.ogg"
        resp = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_data,
            language="en"
        )
        return resp.text
    except Exception as e:
        print(f"STT error: {e}")
        return None
