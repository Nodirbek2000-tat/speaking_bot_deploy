"""
services/openai_service.py
mock_ielts.py va mock_cefr.py uchun ikkita asosiy funksiya:
  - transcribe_audio(file_url)      — Whisper STT
  - analyze_ielts_speaking(text)    — GPT-4o IELTS baholash
"""
import io
import json
import logging

import aiohttp
from openai import AsyncOpenAI

from data.config import OPENAI_API_KEY

logger = logging.getLogger(__name__)
_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def transcribe_audio(file_url: str) -> str:
    """Telegram file URL dan audio yuklab Whisper orqali matnga o'girish."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as resp:
                if resp.status != 200:
                    logger.error(f"Audio download failed: HTTP {resp.status}")
                    return ""
                audio_bytes = await resp.read()

        audio_data = io.BytesIO(audio_bytes)
        audio_data.name = "voice.ogg"
        result = await _client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_data,
            language="en",
        )
        return result.text or ""
    except Exception as e:
        logger.error(f"transcribe_audio error: {e}")
        return ""


async def analyze_ielts_speaking(full_transcript: str) -> dict | None:
    """
    IELTS speaking transcriptini GPT-4o orqali baholash.
    full_transcript — "Q1: ... Q2: ..." formatidagi birlashtirilgan matn.
    """
    if not full_transcript:
        return None

    prompt = (
        "Evaluate this IELTS Speaking test transcript:\n\n"
        + full_transcript
        + "\n\nReturn JSON with keys: "
        "overall_band (float 1.0-9.0), "
        "sub_scores (object: fluency, lexical, grammar, pronunciation — each float), "
        "strengths (list of strings), "
        "improvements (list of strings), "
        "mistakes (list of {error, correction, explanation}), "
        "recommendations (list of strings)."
    )

    try:
        resp = await _client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a STRICT IELTS Speaking examiner. "
                        "Give overall_band and sub_scores in 0.5 increments (1.0–9.0). "
                        "Be brutally honest — do NOT inflate scores. "
                        "Band 9 = native speaker. Band 7 = only minor errors. Band 5 = noticeable errors. "
                        "If the candidate uses Uzbek or mixes languages, reduce fluency by 1–2 bands. "
                        "Short or off-topic answers must receive low scores."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=1200,
        )
        result = json.loads(resp.choices[0].message.content)
        # Band ni tekshirish
        raw_band = float(result.get("overall_band", 5.0))
        result["overall_band"] = round(min(9.0, max(1.0, raw_band)), 1)
        return result
    except Exception as e:
        logger.error(f"analyze_ielts_speaking error: {e}")
        return {
            "overall_band": 5.0,
            "sub_scores": {"fluency": 5.0, "lexical": 5.0, "grammar": 5.0, "pronunciation": 5.0},
            "strengths": [],
            "improvements": ["Analysis error — please try again"],
            "mistakes": [],
            "recommendations": [],
        }
