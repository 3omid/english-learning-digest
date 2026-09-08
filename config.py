# -*- coding: utf-8 -*-
"""
تنظیمات صفحه‌ی «آموزش زبان انگلیسی» - خواهر کوچیک‌تر پروژه‌ی persian-news-digest.

ایده: یه صفحه‌ی حالت روزنامه‌وار (دقیقا شبیه سایت اخبار) ولی برای یادگیری زبان، با
۴ بخش ثابت: گرامر، واژگان، رایتینگ/نگارش، لیسنینگ‌واسپیکینگ. محتوای هر بخش ترکیبی
از دو منبع مستقله:
1) خبر/درس واقعی از RSS منابع شناخته‌شده‌ی آموزش زبان (BBC/VOA Learning English،
   Merriam-Webster Word of the Day) - با لینک مستقیم به صفحه‌ی اصلی مطلب.
2) یک نکته‌ی تازه‌ی تولیدشده توسط هوش مصنوعی (نکته گرامری/واژه امروز/نکته نگارش/
   نکته تلفظ) - دقیقا مثل مکانیزم «نکته آموزشی/تست هوش/سخن بزرگان/شعر» تو سایت خبری،
   با منطق «عدم تکرار» (recent-avoidance) که در fetch_content.py پیاده شده.
"""

import os

USER_NAME = "امید"

# ---------------------------------------------------------------------------
# ۱) منابع RSS واقعی - دسته‌بندی‌شده در ۴ بخش ثابت درخواستی کاربر.
# نکته: بعضی این فیدها (مخصوصا Everyday Grammar خودِ VOA) خیلی پرکار نیستن؛ به همین
# خاطر DISPLAY_LOOKBACK_HOURS پایین‌تر نسبتا بزرگ (۹۶ ساعت) گذاشته شده تا هر بخش
# همیشه چندتا آیتم برای نمایش داشته باشه، نه خالی بمونه.
# ---------------------------------------------------------------------------
RSS_SOURCES = {
    "گرامر": [
        {
            "name": "VOA Learning English - Everyday Grammar",
            "url": "https://learningenglish.voanews.com/api/zoroqql-vomx-tpeptpqq",
            "tag": "آموزش گرامر با مثال‌های واقعی از زبان محاوره و نوشتار آمریکایی",
        },
        {
            "name": "VOA Learning English - Ask a Teacher",
            "url": "https://learningenglish.voanews.com/api/zti_qvl-vomx-tpekgvqr",
            "tag": "پاسخ معلم‌های VOA به سوالات رایج گرامری زبان‌آموزان",
        },
    ],
    "واژگان": [
        {
            "name": "Merriam-Webster - Word of the Day",
            "url": "https://www.merriam-webster.com/wotd/feed/rss2",
            "tag": "واژه روز با تعریف، تلفظ و مثال از معتبرترین فرهنگ لغت آمریکایی",
        },
        {
            "name": "VOA Learning English - Words and Their Stories",
            "url": "https://learningenglish.voanews.com/api/zmypyl-vomx-tpeyry_",
            "tag": "ریشه و داستان اصطلاحات و ضرب‌المثل‌های رایج انگلیسی آمریکایی",
        },
    ],
    "رایتینگ و نگارش": [
        {
            "name": "VOA Learning English - Education Tips",
            "url": "https://learningenglish.voanews.com/api/z_gjqyl-vomx-tpevmrov",
            "tag": "راهکارهای عملی نوشتن و مطالعه برای زبان‌آموزان",
        },
    ],
    "لیسنینگ و اسپیکینگ": [
        {
            "name": "VOA Learning English - How to Pronounce",
            "url": "https://learningenglish.voanews.com/api/zpivqol-vomx-tpe_guqi",
            "tag": "آموزش تلفظ صحیح کلمات پرکاربرد انگلیسی آمریکایی",
        },
        {
            "name": "VOA Learning English - English in a Minute",
            "url": "https://learningenglish.voanews.com/api/zjk-rl-vomx-tpebpqqo",
            "tag": "کلیپ‌های صوتی/تصویری کوتاه یک‌دقیقه‌ای برای تمرین شنیداری",
        },
    ],
}

# استایل هر بخش تو گزارش (آیکون + رنگ) - دقیقا هم‌خانواده‌ی CATEGORY_STYLE تو
# generate_report.py سایت خبری، برای حس بصری یکسان.
SECTION_STYLE = {
    "گرامر": {"icon": "📐", "color": "#1f3864"},
    "واژگان": {"icon": "🔤", "color": "#6c4f8c"},
    "رایتینگ و نگارش": {"icon": "✍️", "color": "#2e7d5b"},
    "لیسنینگ و اسپیکینگ": {"icon": "🎧", "color": "#b5651d"},
}

# کلید داخلی هر بخش برای استفاده در دیتابیس/prompt (بدون فاصله/کاراکتر خاص)
SECTION_KEYS = {
    "گرامر": "grammar",
    "واژگان": "vocabulary",
    "رایتینگ و نگارش": "writing",
    "لیسنینگ و اسپیکینگ": "listening_speaking",
}
SECTION_KEYS_REVERSE = {v: k for k, v in SECTION_KEYS.items()}

# ---------------------------------------------------------------------------
# ۲) تنظیمات واکشی خبر/درس
# ---------------------------------------------------------------------------
DISPLAY_LOOKBACK_HOURS = 24 * 21   # تا ۳ هفته‌ی اخیر رو نشون بده - این فیدها هرروز پست جدید ندارن
NOTIFY_LOOKBACK_HOURS = 14         # با توجه به آپدیت ۲ بار در روز (~۹ ساعت فاصله)، آیتمی که تو ۱۴ ساعت اخیر اولین‌بار دیده شده «جدید»‌ه
HEADLINES_PER_SECTION = 4          # حداکثر تعداد آیتم واقعی نمایش داده‌شده در هر بخش
MAX_ITEMS_PER_SOURCE = 8
DB_PATH = "seen_content.db"
OUTPUT_DIR = "output"

# ---------------------------------------------------------------------------
# ۳) تنظیمات مدل هوش مصنوعی - دقیقا همون پل Gemini/Claude پروژه‌ی خبری
# (تصمیم کاربر: Gemini، هم‌خانواده‌ی سایت اخبار - کلید API باید جدا برای این
# ریپازیتوری به‌عنوان GitHub Secret اضافه بشه، چون گیت‌هاب اجازه‌ی کپی مقدار
# secret بین دو ریپازیتوری رو نمی‌ده.)
# ---------------------------------------------------------------------------
MODEL_PROVIDER = os.environ.get("MODEL_PROVIDER", "gemini")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-3.5-flash-lite"

CLAUDE_MODEL = "claude-sonnet-5"
CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
