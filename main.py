# -*- coding: utf-8 -*-
"""
اجرای اصلی صفحه‌ی «آموزش زبان انگلیسی». دقیقا مثل main.py سایت خبری، ولی ساده‌تر (بدون
تلگرام/ارز/طلا/کریپتو): واکشی محتوای واقعی، ترجمه/تحلیل با LLM، تولید نکته‌های روزانه و
یک تست، ساخت HTML.
"""

import argparse
import logging
from datetime import datetime, timezone

import config
import fetch_content
import analyze
import generate_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="حتی بدون مطلب تازه هم گزارش بساز")
    args = parser.parse_args()

    log.info("در حال واکشی مطالب از منابع RSS آموزش زبان...")
    section_data = fetch_content.fetch_all()

    total_items = sum(len(v) for v in section_data.values())
    total_new = sum(1 for items in section_data.values() for it in items if it.get("is_new"))
    log.info(f"مجموعا {total_items} مطلب ({total_new} تازه) در {len(section_data)} بخش واکشی شد.")

    if total_items == 0 and total_new == 0 and not args.force:
        log.info("هیچ مطلبی (نه تازه نه قدیمی) پیدا نشد و --force هم ست نشده؛ گزارشی ساخته نمی‌شه.")
        return

    log.info("در حال ترجمه/تحلیل هر بخش با هوش مصنوعی...")
    for section, items in section_data.items():
        section_data[section] = analyze.summarize_section(section, items)

    log.info("در حال تولید نکته‌های روزانه‌ی هر بخش...")
    recent_tips = {
        key: fetch_content.get_recent_extras(f"tip_{key}", limit=20)
        for key in config.SECTION_KEYS.values()
    }
    tips = analyze.daily_language_tips(recent_tips)
    for key, tip in tips.items():
        if tip and tip.get("title"):
            fetch_content.save_extra(f"tip_{key}", f"{tip['title']}: {tip.get('body_fa', '')[:120]}")

    # تست این دوره - چرخشی بین ۴ بخش بر اساس تعداد اجراهای قبلی (نه صرفا روز، چون این
    # صفحه روزی ۲ بار آپدیت می‌شه و می‌خوایم هر دو اجرای یک روز هم اگه ممکنه بخش متفاوتی
    # رو تست بزنن، نه دقیقا یکی).
    quiz_history = fetch_content.get_recent_extras("quiz_section_order", limit=1)
    section_names = list(config.RSS_SOURCES.keys())
    if quiz_history:
        try:
            last_idx = section_names.index(quiz_history[0])
        except ValueError:
            last_idx = -1
    else:
        last_idx = -1
    next_section = section_names[(last_idx + 1) % len(section_names)]
    recent_quiz_questions = fetch_content.get_recent_extras(f"quiz_{config.SECTION_KEYS[next_section]}", limit=15)

    log.info(f"در حال تولید تست این دوره برای بخش «{next_section}»...")
    quiz = analyze.daily_quiz(next_section, recent_quiz_questions)
    if quiz and quiz.get("question"):
        fetch_content.save_extra(f"quiz_{config.SECTION_KEYS[next_section]}", quiz["question"])
        fetch_content.save_extra("quiz_section_order", next_section)

    log.info("در حال ساخت گزارش HTML...")
    generate_report.build_report(section_data, tips, quiz)
    log.info("گزارش با موفقیت در output/latest.html ساخته شد.")


if __name__ == "__main__":
    main()
