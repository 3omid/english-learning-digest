# -*- coding: utf-8 -*-
"""
ارسال درس‌های واکشی‌شده (fetch_content.py) به Gemini/Claude برای:
- ترجمه‌ی تیتر هر درس واقعی به فارسی + یک توضیح کوتاه فارسی از این‌که این درس دقیقا چه
  نکته‌ای از زبان انگلیسی رو یاد می‌ده (چرا برای زبان‌آموز فارسی‌زبان مفیده).
- تولید «نکته‌ی امروز» تازه برای هر ۴ بخش (گرامر/واژگان/رایتینگ/لیسنینگ‌واسپیکینگ) - با
  منطق عدم‌تکرار (recent-avoidance)، دقیقا هم‌خانواده‌ی مکانیزم tip/quiz/quote/poem سایت خبری.
- یک تست چهارگزینه‌ای زبان (رو یکی از ۴ بخش، چرخشی).
"""

import json
import logging
import re
import time

import requests

import config

log = logging.getLogger(__name__)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
GEMINI_URL_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"


def _call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 2000, retries: int = 2) -> str:
    """پل یکپارچه بین Gemini (پیش‌فرض) و Claude - عینا همون منطق analyze.py سایت خبری."""
    last_error = None
    for attempt in range(retries + 1):
        try:
            if config.MODEL_PROVIDER == "gemini":
                return _call_gemini(system_prompt, user_prompt, max_tokens)
            return _call_claude(system_prompt, user_prompt, max_tokens)
        except Exception as e:
            last_error = e
            if attempt < retries:
                wait = 2 * (attempt + 1)
                log.warning(f"تلاش {attempt + 1} ناموفق بود ({e}) - {wait} ثانیه صبر و تلاش دوباره...")
                time.sleep(wait)
    raise last_error


def _call_gemini(system_prompt: str, user_prompt: str, max_tokens: int = 2000) -> str:
    url = GEMINI_URL_TMPL.format(model=config.GEMINI_MODEL, key=config.GEMINI_API_KEY)
    body = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    try:
        resp = requests.post(url, json=body, timeout=90)
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError(f"پاسخ خالی از Gemini: {data}")
        parts = candidates[0].get("content", {}).get("parts", [])
        return "\n".join(p.get("text", "") for p in parts).strip()
    except requests.exceptions.HTTPError as e:
        detail = e.response.text if e.response is not None else str(e)
        log.error(f"خطای HTTP در فراخوانی Gemini (مدل: {config.GEMINI_MODEL}): {detail}")
        raise RuntimeError(f"Gemini API Error: {e}")


def _call_claude(system_prompt: str, user_prompt: str, max_tokens: int = 2000) -> str:
    headers = {
        "x-api-key": config.CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": config.CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    resp = requests.post(ANTHROPIC_URL, headers=headers, json=body, timeout=90)
    resp.raise_for_status()
    data = resp.json()
    parts = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
    return "\n".join(parts).strip()


def _parse_json_block(raw: str):
    raw_clean = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw_clean)
    except (json.JSONDecodeError, ValueError):
        pass
    match = re.search(r"[\{\[].*[\}\]]", raw_clean, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError("پاسخ مدل هیچ بلوک JSON قابل‌شناسایی‌ای نداشت.")


def _format_items_for_prompt(items):
    lines = []
    for i, it in enumerate(items, 1):
        tag = it.get("tag", "")
        source_label = f"{it['source']} - {tag}" if tag else it["source"]
        summary = re.sub(r"<[^>]+>", " ", it.get("summary", "") or "")  # حذف تگ‌های HTML خام RSS
        summary = re.sub(r"\s+", " ", summary).strip()[:900]
        lines.append(f"{i}. [{source_label}] {it['title']}\n   خلاصه انگلیسی: {summary}\n   لینک: {it['link']}")
    return "\n\n".join(lines)


def summarize_section(section: str, items: list) -> list:
    """
    خروجی: همون items ورودی، به‌علاوه‌ی دو کلید تازه روی هرکدوم:
    - title_fa: ترجمه فارسی تیتر
    - lesson_fa: خودِ درس، کامل و مستقل، به فارسی (نه فقط یک اشاره‌ی کوتاه که «این مطلب
      درباره‌ی چیه» - بلکه طوری نوشته می‌شه که کاربر بدون کلیک روی لینک منبع، همون‌جا
      واقعا نکته‌ی زبانی رو یاد بگیره).
    اگه items خالی باشه یا فراخوانی مدل شکست بخوره، items بدون این دو کلید برگردونده می‌شه
    (generate_report.py باید graceful این حالت رو هندل کنه - عنوان انگلیسی خام نشون بده).
    """
    if not items:
        return items

    system_prompt = (
        "تو معلم زبان انگلیسی هستی که برای فارسی‌زبان‌هایی که دارن انگلیسی یاد می‌گیرن محتوای "
        "قابل‌فهم و مستقل می‌سازی. کاربر این صفحه معمولا روی لینک منبع کلیک نمی‌کنه - پس خودِ "
        "متنی که تو می‌نویسی باید کل درس رو کامل منتقل کنه، نه فقط یک اشاره‌ی کوتاه به این‌که "
        "«این مطلب درباره‌ی چیه». برای هر مطلب داده‌شده (که از یک منبع واقعی آموزش زبان مثل "
        "VOA Learning English یا Merriam-Webster گرفته شده و یک خلاصه‌ی انگلیسیِ منبع همراهش "
        "اومده) دو کار می‌کنی:\n"
        "۱) عنوان رو به فارسیِ روان (نه ترجمه لغت‌به‌لغت خشک) برگردون - طوری که یک زبان‌آموز "
        "فارسی‌زبان فورا بفهمه این مطلب درباره چیه.\n"
        "۲) خودِ درس رو به فارسیِ روان و کامل بنویس (lesson_fa)، حدودا ۴ تا ۸ جمله (نه یک خط "
        "و نه یک مقاله‌ی بلند). این باید شامل نکته‌ی زبانی/گرامری/واژگانی واقعی باشه، نه فقط "
        "توضیح این‌که «این مطلب مفیده». مشخصا:\n"
        "   - اگه گرامریه: خودِ قاعده رو با کلمات ساده توضیح بده و حتما ۲ تا ۳ جمله‌ی نمونه‌ی "
        "انگلیسی (با ترجمه‌ی فارسیِ جلوشون) بیار که قاعده رو نشون بدن.\n"
        "   - اگه واژه/اصطلاحه: معنی دقیق فارسی، تلفظ تقریبی (با حروف فارسی)، و ۱ تا ۲ جمله‌ی "
        "نمونه‌ی انگلیسی با ترجمه بیار.\n"
        "   - اگه نکته‌ی نگارش/رایتینگه: خودِ ترفند یا اشتباه رایج رو با یک نمونه‌ی غلط و یک "
        "نمونه‌ی درست (هر دو انگلیسی، با ترجمه) نشون بده.\n"
        "   - اگه نکته‌ی تلفظ/مکالمه‌ست: خودِ نکته‌ی تلفظی یا عبارت محاوره‌ای رو با تلفظ تقریبی "
        "و یک جمله‌ی نمونه‌ی کاربردی (با ترجمه) بیار.\n"
        "   از روی خلاصه‌ی انگلیسیِ منبع شروع کن، ولی لازم نیست بهش محدود بمونی - از دانش خودت "
        "هم برای کامل و درست نوشتن درس استفاده کن. اگه لازم شد بین توضیح اصلی و مثال‌ها خط "
        "جدید (\\n) بذار تا خواندنش راحت‌تر باشه.\n\n"
        "خروجی رو دقیقا به فرمت JSON زیر بده، بدون هیچ متن اضافه قبل یا بعدش:\n"
        '{"items": [{"title_fa": "...", "lesson_fa": "..."}, ...]}\n'
        "طول آرایه items باید دقیقا برابر تعداد مطلب‌های داده‌شده باشه و به همون ترتیب."
    )
    user_prompt = f"بخش: {section}\n\nمطلب‌ها (به ترتیب شماره):\n\n{_format_items_for_prompt(items)}"

    try:
        raw = _call_llm(system_prompt, user_prompt, max_tokens=4000)
        parsed = _parse_json_block(raw)
        results = parsed.get("items", [])
        while len(results) < len(items):
            results.append({})
        for it, r in zip(items, results):
            title_fa = (r or {}).get("title_fa", "").strip()
            lesson_fa = (r or {}).get("lesson_fa", "").strip()
            if title_fa:
                it["title_fa"] = title_fa
            if lesson_fa:
                it["lesson_fa"] = lesson_fa
    except Exception as e:
        log.error(f"خطا در ترجمه/تحلیل بخش {section}: {e}")

    return items


SECTION_LABELS_FOR_PROMPT = {
    "گرامر": "یک نکته‌ی گرامری (grammar) - یک قاعده یا ساختار گرامری پرکاربرد، با ۲-۳ جمله‌ی مثال انگلیسی و ترجمه فارسی‌شون",
    "واژگان": "یک واژه یا اصطلاح انگلیسی پرکاربرد (vocabulary) - با معنی فارسی، تلفظ تقریبی، و ۲ جمله‌ی مثال انگلیسی با ترجمه",
    "رایتینگ و نگارش": "یک نکته‌ی نگارش/رایتینگ (writing) - یک اشتباه رایج یا ترفند برای بهتر نوشتن به انگلیسی، با نمونه‌ی غلط و درست",
    "لیسنینگ و اسپیکینگ": "یک نکته‌ی تلفظ/مکالمه (speaking) - یک نکته‌ی تلفظ یا یک عبارت محاوره‌ای پرکاربرد برای صحبت‌کردن روان‌تر، با مثال",
}


def daily_language_tips(recent: dict = None) -> dict:
    """
    برای هر ۴ بخش، یک «نکته‌ی امروز» تازه تولید می‌کنه (دقیقا هم‌خانواده‌ی مکانیزم
    daily_extras سایت خبری). recent: دیکشنری {section_key: [متن‌های قبلی]} از
    fetch_content.get_recent_extras، برای جلوگیری از تکرار.
    خروجی: {section_key: {"title": "...", "body_fa": "...", "example_en": "...", "example_fa": "..."}}
    """
    recent = recent or {}
    keys = list(config.SECTION_KEYS.values())

    def _fmt(key):
        items = recent.get(key) or []
        return f"موارد قبلی بخش {key}:\n" + ("، ".join(items) if items else "(قبلا موردی ثبت نشده)")

    schema_parts = ", ".join(
        f'"{key}": {{"title": "عنوان کوتاه ۲-۵ کلمه‌ای فارسی", "body_fa": "توضیح ۲-۴ جمله‌ای فارسی", '
        f'"example_en": "یک یا دو جمله‌ی نمونه انگلیسی", "example_fa": "ترجمه فارسی همون جمله"}}'
        for key in keys
    )
    system_prompt = (
        "تو معلم زبان انگلیسی هستی و داری محتوای آموزشی روزانه برای یک صفحه‌ی وب فارسی‌زبان "
        "می‌سازی. باید دقیقا ۴ نکته‌ی زیر رو تولید کنی، هرکدوم برای یک بخش متفاوت:\n"
        + "\n".join(f"- {config.SECTION_KEYS_REVERSE[k]} ({k}): {SECTION_LABELS_FOR_PROMPT[config.SECTION_KEYS_REVERSE[k]]}" for k in keys)
        + "\n\nخروجی رو دقیقا و فقط به این فرمت JSON بده، بدون هیچ متن اضافه:\n"
        f'{{{schema_parts}}}\n\n'
        "قوانین: لحن ساده، صمیمی و مفید برای زبان‌آموز فارسی‌زبان سطح متوسط. هرکدوم باید کاملا "
        "متفاوت از موارد قبلی (که در پیام کاربر لیست شدن) باشه - نه فقط بازنویسی همون."
    )
    user_prompt = "\n\n".join(_fmt(key) for key in keys)

    empty = {key: {} for key in keys}
    try:
        raw = _call_llm(system_prompt, user_prompt, max_tokens=1600)
        parsed = _parse_json_block(raw)
    except Exception as e:
        log.error(f"خطا در تولید نکته‌های روزانه آموزش زبان: {e}")
        parsed = {}

    result = dict(empty)
    for key in keys:
        item = parsed.get(key) or {}
        title = (item.get("title") or "").strip()
        body_fa = (item.get("body_fa") or "").strip()
        example_en = (item.get("example_en") or "").strip()
        example_fa = (item.get("example_fa") or "").strip()
        if title and body_fa:
            result[key] = {
                "title": title, "body_fa": body_fa,
                "example_en": example_en, "example_fa": example_fa,
            }
    return result


def daily_quiz(section: str, recent: list = None) -> dict:
    """
    یک تست چهارگزینه‌ای زبان روی بخش مشخص‌شده (چرخشی بین ۴ بخش - main.py تصمیم می‌گیره
    کدوم بخش). خروجی دقیقا هم‌فرمت quiz سایت خبری، تا از همون _quiz_html/CSS/JS استفاده بشه.
    """
    recent = recent or []
    system_prompt = (
        "تو معلم زبان انگلیسی هستی. یک سوال تستی چهارگزینه‌ای برای زبان‌آموز فارسی‌زبان سطح "
        f"متوسط بساز، دقیقا درباره‌ی موضوع «{section}». سوال باید واقعا دانش زبانی رو بسنجه "
        "(نه دانش عمومی). فقط و فقط یک JSON خالص برگردون:\n"
        '{"question": "متن سوال (می‌تونه شامل جمله‌ی انگلیسی ناقص یا اشتباه باشه)", '
        '"options": ["گزینه ۱", "گزینه ۲", "گزینه ۳", "گزینه ۴"], "correct_index": 0, '
        '"explanation": "یک یا دو جمله فارسی که توضیح بده چرا این گزینه درسته"}\n'
        "دقیقا ۴ گزینه‌ی متفاوت و قابل‌قبول بساز؛ correct_index عددی بین ۰ تا ۳.\n"
        "این سوال نباید با سوال‌های قبلی زیر یکسان یا خیلی شبیه باشه: "
        + ("، ".join(recent) if recent else "(قبلا سوالی ثبت نشده)")
    )
    try:
        raw = _call_llm(system_prompt, "یک سوال تازه بساز.", max_tokens=600)
        parsed = _parse_json_block(raw)
        question = (parsed.get("question") or "").strip()
        options = parsed.get("options") or []
        correct_index = parsed.get("correct_index")
        explanation = (parsed.get("explanation") or "").strip()
        if (question and isinstance(options, list) and len(options) == 4
                and all(isinstance(o, str) and o.strip() for o in options)
                and isinstance(correct_index, int) and 0 <= correct_index <= 3 and explanation):
            return {
                "question": question, "options": [o.strip() for o in options],
                "correct_index": correct_index, "explanation": explanation, "section": section,
            }
    except Exception as e:
        log.error(f"خطا در تولید تست زبان ({section}): {e}")
    return {}
