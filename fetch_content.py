# -*- coding: utf-8 -*-
"""
گرفتن درس/مطلب واقعی از منابع RSS آموزش زبان (BBC/VOA Learning English،
Merriam-Webster). دقیقا همون منطق دولایه‌ی fetch_news.py سایت خبری:
1) «نمایش»: هر بخش تا HEADLINES_PER_SECTION آیتم مهم رو نشون می‌ده (حتی قبلا دیده‌شده)
   تا خالی به‌نظر نرسه.
2) «تازگی»: یک فلگ is_new (برچسب «جدید») برای آیتم‌هایی که اخیرا (طی NOTIFY_LOOKBACK_HOURS)
   اولین‌بار دیده شدن.
همون seen_content.db هم برای دیتابیس عدم‌تکرار «نکته‌های تولیدی هوش مصنوعی» (نکته
گرامر/واژه روز/نکته نگارش/نکته تلفظ) استفاده می‌شه - تابع‌های get_recent_extras/save_extra.
"""

import sqlite3
import hashlib
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import feedparser

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def _init_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seen_content (
            id TEXT PRIMARY KEY,
            title TEXT,
            source TEXT,
            section TEXT,
            first_seen_at TEXT
        )
    """)
    conn.commit()
    return conn


def _content_id(link: str, title: str) -> str:
    return hashlib.sha256((link or title).encode("utf-8")).hexdigest()


def _get_or_mark_first_seen(conn, cid, title, source, section):
    cur = conn.execute("SELECT first_seen_at FROM seen_content WHERE id = ?", (cid,))
    row = cur.fetchone()
    if row:
        return row[0]
    now_iso = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO seen_content (id, title, source, section, first_seen_at) VALUES (?, ?, ?, ?, ?)",
        (cid, title, source, section, now_iso),
    )
    conn.commit()
    return now_iso


def _parse_entry_time(entry):
    for key in ("published_parsed", "updated_parsed"):
        val = getattr(entry, key, None)
        if val:
            return datetime(*val[:6], tzinfo=timezone.utc)
    return None


def fetch_all(db_path: str = None):
    """
    خروجی: dict {section: [ {title, link, summary, source, published, is_new} ]}
    هر بخش حداکثر HEADLINES_PER_SECTION آیتم داره (جدیدترین‌ها، چرخشی بین منبع‌های اون بخش).
    """
    db_path = db_path or config.DB_PATH
    conn = _init_db(db_path)
    display_cutoff = datetime.now(timezone.utc) - timedelta(hours=config.DISPLAY_LOOKBACK_HOURS)
    notify_cutoff = datetime.now(timezone.utc) - timedelta(hours=config.NOTIFY_LOOKBACK_HOURS)

    results = {sec: [] for sec in config.RSS_SOURCES}
    assigned_ids = set()

    for section, sources in config.RSS_SOURCES.items():
        section_items = []
        for src in sources:
            try:
                feed = feedparser.parse(src["url"])
                if feed.bozo and not feed.entries:
                    log.warning(f"منبع جواب نداد یا خراب است: {src['name']} ({src['url']})")
                    continue

                for entry in feed.entries[: config.MAX_ITEMS_PER_SOURCE]:
                    title = getattr(entry, "title", "").strip()
                    link = getattr(entry, "link", "").strip()
                    summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
                    if not title:
                        continue

                    pub_time = _parse_entry_time(entry)
                    if pub_time and pub_time < display_cutoff:
                        continue

                    cid = _content_id(link, title)
                    if cid in assigned_ids:
                        continue
                    assigned_ids.add(cid)

                    first_seen_str = _get_or_mark_first_seen(conn, cid, title, src["name"], section)
                    first_seen_dt = datetime.fromisoformat(first_seen_str)
                    is_new = first_seen_dt >= notify_cutoff

                    section_items.append({
                        "title": title,
                        "link": link,
                        "summary": summary,
                        "source": src["name"],
                        "tag": src.get("tag", ""),
                        "published": pub_time.isoformat() if pub_time else first_seen_str,
                        "published_dt": pub_time or first_seen_dt,
                        "is_new": is_new,
                    })

            except Exception as e:
                log.error(f"خطا در دریافت {src['name']}: {e}")

        # چرخشی بین منبع‌های یک بخش، مثل fetch_news.py، تا یک منبع پرکار همه‌ی جا رو نگیره.
        section_items.sort(key=lambda x: x["published_dt"], reverse=True)
        by_source = defaultdict(list)
        for it in section_items:
            by_source[it["source"]].append(it)
        sources_ordered = sorted(by_source.keys(), key=lambda s: by_source[s][0]["published_dt"], reverse=True) if by_source else []

        top_items = []
        idx = 0
        remaining = len(section_items)
        while len(top_items) < config.HEADLINES_PER_SECTION and remaining > 0 and sources_ordered:
            source = sources_ordered[idx % len(sources_ordered)]
            if by_source[source]:
                top_items.append(by_source[source].pop(0))
                remaining -= 1
            idx += 1

        top_items.sort(key=lambda x: x["published_dt"], reverse=True)
        for it in top_items:
            it.pop("published_dt", None)
        results[section] = top_items

        new_count = sum(1 for it in top_items if it["is_new"])
        log.info(f"[{section}] {len(top_items)} آیتم نمایش داده می‌شه، {new_count} تاش واقعا جدیده")

    conn.close()
    return results


def _init_extras_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sent_extras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            key_text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()


def get_recent_extras(kind: str, limit: int = 40, db_path: str = None):
    """
    عنوان/متن کوتاه آخرین نکته‌های تولیدشده توسط هوش مصنوعی از یک نوع مشخص (kind:
    grammar_tip / vocab_word / writing_tip / speaking_tip / quiz) - برای اینکه مدل
    هر بار موضوع تازه انتخاب کنه و تکراری نشه (دقیقا مثل مکانیزم tip/quiz/quote/poem
    سایت خبری).
    """
    db_path = db_path or config.DB_PATH
    conn = sqlite3.connect(db_path)
    _init_extras_table(conn)
    cur = conn.execute(
        "SELECT key_text FROM sent_extras WHERE kind = ? ORDER BY id DESC LIMIT ?", (kind, limit)
    )
    items = [r[0] for r in cur.fetchall() if r[0]]
    conn.close()
    return items


def save_extra(kind: str, key_text: str, db_path: str = None):
    if not kind or not key_text:
        return
    db_path = db_path or config.DB_PATH
    conn = sqlite3.connect(db_path)
    _init_extras_table(conn)
    conn.execute(
        "INSERT INTO sent_extras (kind, key_text, created_at) VALUES (?, ?, ?)",
        (kind, key_text, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    data = fetch_all()
    for sec, items in data.items():
        print(f"\n=== {sec} ({len(items)} آیتم) ===")
        for it in items:
            print(" -", it["title"], "|", it["source"], "| جدید:", it["is_new"])
