import json
import logging
import asyncio
from openai import AsyncOpenAI
from data.config import OPENAI_API_KEY

logger = logging.getLogger(__name__)
client = AsyncOpenAI(api_key=OPENAI_API_KEY, timeout=30.0, max_retries=2)


async def lookup_word_ai(word: str) -> dict:
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an English dictionary and vocabulary expert."},
                {"role": "user", "content": (
                    f'For the word "{word}", return JSON with keys: '
                    'word, level (A1/A2/B1/B2/C1/C2), definition (clear English), '
                    'translation_uz (Uzbek translation), examples (list of 5 academic sentences), '
                    'synonyms (list of 3-5 synonym words with brief meanings).'
                )}
            ],
            response_format={"type": "json_object"},
            max_tokens=700
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        logger.error(f"lookup_word_ai error: {e}")
        return None


async def evaluate_ielts(questions: list, transcripts: list) -> dict:
    lines = []
    for q, t in zip(questions, transcripts):
        lines.append(f"[Part {q.get('part', '?')}] Q: {q.get('question', '')}")
        lines.append(f"A: {t}")
        lines.append("")
    qa_text = "\n".join(lines)

    prompt = (
        "Evaluate this IELTS Speaking test:\n\n"
        + qa_text
        + "\n\nReturn JSON with: overall_band (float 1-9), "
        "sub_scores (fluency, lexical, grammar, pronunciation each as float), "
        "strengths (list of strings), improvements (list of strings), "
        "mistakes (list of {error, correction, explanation}), recommendations (list of strings), "
        "tense_errors (list of {tense, error, correction})."
    )

    try:
        resp = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a STRICT and honest IELTS Speaking examiner. "
                        "CRITICAL RULES:\n"
                        "1. If the candidate answers in Uzbek or mixes languages significantly, "
                        "add 'Off-language: candidate responded in Uzbek/non-English' to improvements "
                        "and reduce fluency by 1-2 bands.\n"
                        "2. If an answer is off-topic or doesn't address the question, "
                        "add 'Off-topic response for question X' to improvements.\n"
                        "3. Be BRUTALLY HONEST — do not inflate scores. "
                        "Band 9=native speaker, Band 7=only minor errors, Band 5=noticeable errors.\n"
                        "4. Short/incomplete answers must receive low fluency/coherence scores.\n"
                        "5. Evaluate strictly on 4 criteria: "
                        "Fluency & Coherence, Lexical Resource, Grammatical Range & Accuracy, Pronunciation. "
                        "Give bands 1.0-9.0 in 0.5 increments. Overall band = average of 4 criteria."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=1400
        )
        result = json.loads(resp.choices[0].message.content)
        raw_band = float(result.get("overall_band", 5.0))
        result["overall_band"] = min(9.0, round(raw_band + 0.5, 1))
        return result
    except Exception as e:
        logger.error(f"evaluate_ielts error: {e}")
        return {
            "overall_band": 5.0,
            "sub_scores": {},
            "strengths": [],
            "improvements": ["Server error occurred"],
            "mistakes": [],
            "recommendations": [],
            "tense_errors": []
        }


async def evaluate_cefr(questions: list, transcripts: list) -> dict:
    lines = []
    for q, t in zip(questions, transcripts):
        lines.append(f"[Part {q.get('part', '?')}] Q: {q.get('question', '')}")
        lines.append(f"A: {t}")
        lines.append("")
    qa_text = "\n".join(lines)

    prompt = (
        "Evaluate this CEFR Speaking test:\n\n"
        + qa_text
        + "\n\nReturn JSON with: score (int 1-75), level (A1/A2/B1/B2/C1), "
        "feedback (object with: summary string, strengths list, improvements list, "
        "errors list of {error, correction, explanation}), "
        "tense_errors (list of {tense, error, correction})."
    )

    try:
        resp = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a STRICT and honest CEFR Speaking examiner. "
                        "CRITICAL RULES:\n"
                        "1. If the candidate answers in Uzbek or mixes languages, "
                        "add 'Off-language: used Uzbek instead of English' to improvements "
                        "and reduce score by 5-10 points.\n"
                        "2. If an answer is off-topic, add 'Off-topic response' to improvements.\n"
                        "3. Be BRUTALLY HONEST — do not inflate scores. "
                        "Score 70+ means near-native level. Most learners score 30-55.\n"
                        "4. Scoring: A1(1-14), A2(15-34), B1(35-50), B2(51-65), C1(66-75).\n"
                        "5. Evaluate strictly on: Range, Accuracy, Fluency, Interaction, Coherence."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=1200
        )
        result = json.loads(resp.choices[0].message.content)
        raw_score = int(result.get("score", 40))
        result["score"] = min(75, raw_score + 4)
        s = result["score"]
        if s <= 14:
            result["level"] = "A1"
        elif s <= 34:
            result["level"] = "A2"
        elif s <= 50:
            result["level"] = "B1"
        elif s <= 65:
            result["level"] = "B2"
        else:
            result["level"] = "C1"
        return result
    except Exception as e:
        logger.error(f"evaluate_cefr error: {e}")
        return {
            "score": 40,
            "level": "B1",
            "feedback": {
                "summary": "Error occurred during evaluation",
                "strengths": [],
                "improvements": [],
                "errors": []
            },
            "tense_errors": []
        }


async def text_to_speech(text: str, voice: str = "alloy") -> bytes:
    try:
        response = await client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
            response_format="opus"
        )
        return response.content
    except Exception as e:
        logger.error(f"text_to_speech error: {e}")
        return None


async def analyze_speaking_session(transcripts: list) -> str:
    """Suhbat tarixidan foydalanuvchi nutqini tahlil qilish (inglizcha)"""
    if not transcripts:
        return ""
    combined = "\n".join(f"- {t}" for t in transcripts)
    prompt = (
        "Analyze this English speaking session. The student said:\n\n"
        + combined
        + "\n\nProvide a concise analysis in English with 5-7 bullet points covering:\n"
        "• Grammar accuracy (tense usage, common mistakes)\n"
        "• Vocabulary range (variety, repetition)\n"
        "• Fluency (sentence structure, natural flow)\n"
        "• Top 2-3 specific mistakes with corrections\n"
        "• 2 actionable recommendations to improve\n"
        "Be honest but encouraging. Use bullet points (•). "
        "Do not include greetings or closing words."
    )
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert English speaking coach analyzing a student's speaking session."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=500
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"analyze_speaking_session error: {e}")
        return ""


async def chat_with_coach(history: list) -> str:
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=history,
            max_tokens=300
        )
        return resp.choices[0].message.content
    except Exception as e:
        logger.error(f"chat_with_coach error: {e}")
        return "Sorry, I had a technical issue. Please try again!"


async def discuss_word_with_coach(word: str, history: list) -> str:
    """So'z haqida AI bilan muhokama qilish"""
    system = (
        f"You are Alex, an English vocabulary coach. "
        f"The student wants to learn and practice the word '{word}'. "
        f"Help them understand its usage, nuances, collocations, and common mistakes. "
        f"Ask follow-up questions to make the student use the word actively. "
        f"Keep responses concise (2-4 sentences). "
        f"Gently correct any mistakes naturally."
    )
    full_history = [{"role": "system", "content": system}] + history
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=full_history,
            max_tokens=300
        )
        return resp.choices[0].message.content
    except Exception as e:
        logger.error(f"discuss_word_with_coach error: {e}")
        return "Sorry, I had a technical issue. Please try again!"


async def analyze_tenses(text: str) -> dict:
    """
    Foydalanuvchi matni bo'yicha zamonlar tahlili.
    Returns: {tense_name: {"usage": n, "correct": n}, ...}
    """
    if not text or len(text.split()) < 5:
        return {}
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a grammar analysis expert. "
                        "Analyze the given English text for tense usage. "
                        "Return JSON with keys for each tense found: "
                        "present_simple, past_simple, future_simple, present_perfect, "
                        "present_continuous, past_perfect, conditional. "
                        "For each tense provide: usage (how many times used), correct (how many times used correctly). "
                        "Only include tenses that actually appear in the text. "
                        "If no recognizable tenses, return empty JSON {}."
                    )
                },
                {"role": "user", "content": f"Analyze tenses in: {text}"}
            ],
            response_format={"type": "json_object"},
            max_tokens=250
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        logger.warning(f"analyze_tenses error: {e}")
        return {}


async def generate_roadmap(
    ielts_band: float = None,
    cefr_score: int = None,
    cefr_level: str = None,
    total_mocks: int = 0,
    top_words: list = None,
    ielts_improvement: float = None,
    cefr_improvement: int = None,
    tense_stats: dict = None,
) -> str:
    level_parts = []
    if ielts_band:
        level_parts.append(f"IELTS Band: {ielts_band}")
    if cefr_level and cefr_score:
        level_parts.append(f"CEFR Level: {cefr_level} (Score: {cefr_score}/75)")
    if total_mocks:
        level_parts.append(f"Total mocks done: {total_mocks}")
    if ielts_improvement is not None:
        sign = "+" if ielts_improvement > 0 else ""
        level_parts.append(f"IELTS improvement: {sign}{ielts_improvement} bands")
    if cefr_improvement is not None:
        sign = "+" if cefr_improvement > 0 else ""
        level_parts.append(f"CEFR improvement: {sign}{cefr_improvement} points")
    if top_words:
        level_parts.append(f"Most used words: {', '.join(top_words)}")

    # Zaif zamonlar
    weak_tenses = []
    if tense_stats:
        for tense, v in tense_stats.items():
            if isinstance(v, dict) and v.get("accuracy", 100) < 60 and v.get("usage", 0) > 0:
                weak_tenses.append(f"{tense} ({v['accuracy']}% accuracy)")
        if weak_tenses:
            level_parts.append(f"Weak grammar tenses: {', '.join(weak_tenses)}")

    level_info = "\n".join(level_parts) if level_parts else "Beginner level (no tests taken yet)"

    prompt = (
        "Create a highly personalized English speaking improvement roadmap.\n\n"
        f"Student data:\n{level_info}\n\n"
        "Based on this data, provide:\n"
        "1. Identify weak areas from the data\n"
        "2. Create a 4-week roadmap with specific daily activities\n"
        "3. TODAY'S SCHEDULE: Recommend exactly how to spend study time today "
        "(e.g., '8:00 — 15 min vocabulary', '19:00 — 30 min IELTS Mock', '21:00 — 20 min AI Chat')\n"
        "4. If weak tenses found, include specific grammar exercises for those tenses\n"
        "5. Suggest vocabulary areas to improve\n"
        "6. Set realistic target scores for next 4 weeks\n"
        "Format with emojis. Week by week plan + Today's schedule section. "
        "Write in English but keep it easy to understand."
    )

    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert English learning coach creating personalized study roadmaps."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000
        )
        return resp.choices[0].message.content
    except Exception as e:
        logger.error(f"generate_roadmap error: {e}")
        return "Roadmap yaratishda xato yuz berdi. Keyinroq urinib ko'ring."


async def analyze_statistics(stats: dict) -> str:
    ielts_hist = stats.get("ielts_history", [])
    cefr_hist = stats.get("cefr_history", [])
    ielts_imp = stats.get("ielts_improvement")
    cefr_imp = stats.get("cefr_improvement")
    weak = stats.get("weak_areas", [])
    top_words = stats.get("top_words", [])
    total_mocks = stats.get("total_mocks", 0)
    total_ai = stats.get("total_ai_chats", 0)
    last_band = stats.get("last_ielts_band")
    last_cefr = stats.get("last_cefr_score")
    last_level = stats.get("last_cefr_level")

    data_lines = [f"Jami mock testlar: {total_mocks}", f"AI suhbatlar: {total_ai}"]
    if ielts_hist:
        bands = [str(h['band']) for h in ielts_hist[-5:]]
        data_lines.append(f"IELTS tarixi (so'nggi 5): {', '.join(bands)}")
    if last_band:
        data_lines.append(f"So'nggi IELTS band: {last_band}")
    if ielts_imp is not None:
        sign = "+" if ielts_imp > 0 else ""
        data_lines.append(f"IELTS o'zgarish: {sign}{ielts_imp} band")
    if cefr_hist:
        scores = [str(h['score']) for h in cefr_hist[-5:]]
        data_lines.append(f"CEFR tarixi (so'nggi 5): {', '.join(scores)}")
    if last_cefr and last_level:
        data_lines.append(f"So'nggi CEFR: {last_cefr}/75 ({last_level})")
    if cefr_imp is not None:
        sign = "+" if cefr_imp > 0 else ""
        data_lines.append(f"CEFR o'zgarish: {sign}{cefr_imp} ball")
    if weak:
        w_str = ", ".join(f"{w['skill']} ({w['avg']})" for w in weak)
        data_lines.append(f"Zaif qismlar: {w_str}")
    if top_words:
        words_str = ", ".join(w['word'] for w in top_words[:6])
        data_lines.append(f"Ko'p ishlatiladigan so'zlar: {words_str}")

    prompt = (
        "O'zbek tilida ingliz tili bo'yicha shaxsiy statistika tahlili yoz.\n\n"
        "Talaba ma'lumotlari:\n"
        + "\n".join(data_lines)
        + "\n\nQuyidagilarni yoz (4-6 gap, qisqa va aniq):\n"
        "1. Umumiy progress qanday (o'sdi/tushdi/bir xil) — raqam bilan\n"
        "2. Eng zaif 1-2 qism qaysi va nima uchun\n"
        "3. Ertaga yoki bu hafta nima qilish kerak (1-2 aniq tavsiya)\n"
        "4. Rag'batlantiruvchi so'z bilan tugat\n"
        "Emoji ishlatma. Faqat o'zbek tilida."
    )
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Siz ingliz tili treneriсiz. O'zbek tilida aniq va qisqa yozing."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=400
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"analyze_statistics error: {e}")
        return ""


async def generate_daily_report(activity_data: dict, drf_stats: dict = None) -> str:
    mocks = activity_data.get('mocks_done', 0)
    words = activity_data.get('words_looked', 0)
    chats = activity_data.get('ai_chats', 0)
    band = activity_data.get('last_ielts_band')
    cefr_level = activity_data.get('last_cefr_level')
    cefr_score = activity_data.get('last_cefr_score')

    today_lines = [
        f"Bugun topshirilgan mocklar: {mocks}",
        f"Ko'rilgan so'zlar: {words}",
        f"AI suhbatlar: {chats}",
    ]
    if band:
        today_lines.append(f"Bugungi IELTS natija: Band {band}")
    if cefr_score and cefr_level:
        today_lines.append(f"Bugungi CEFR natija: {cefr_score}/75 ({cefr_level})")

    context_lines = []
    if drf_stats:
        imp_i = drf_stats.get("ielts_improvement")
        imp_c = drf_stats.get("cefr_improvement")
        weak = drf_stats.get("weak_areas", [])
        total = drf_stats.get("total_mocks", 0)
        if total:
            context_lines.append(f"Jami mock testlar: {total}")
        if imp_i is not None:
            context_lines.append(f"IELTS umumiy o'zgarish: {'+' if imp_i > 0 else ''}{imp_i} band")
        if imp_c is not None:
            context_lines.append(f"CEFR umumiy o'zgarish: {'+' if imp_c > 0 else ''}{imp_c} ball")
        if weak:
            context_lines.append(f"Zaif qismlar: {', '.join(w['skill'] for w in weak)}")

    prompt = (
        "O'zbek tilida BUGUNGI faoliyat hisobotini yoz (3-4 gap).\n\n"
        "Bugun qilinganlar:\n"
        + "\n".join(today_lines)
        + (("\n\nUmumiy kontekst:\n" + "\n".join(context_lines)) if context_lines else "")
        + "\n\nYoz: 1) Bugun nima qildim (qisqa), "
        "2) Eng yaxshi narsa nima edi, "
        "3) Ertaga nima qilish kerak (1 aniq tavsiya). "
        "Rag'batlantiruvchi ohangda. Emoji ishlatma."
    )
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Siz ingliz tili treneriсiz. O'zbek tilida yozing."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=350
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return "Bugun ham yaxshi ish qildingiz! Ertaga ham davom eting."
