# -*- coding: utf-8 -*-
"""
ساخت گزارش HTML صفحه‌ی «آموزش زبان انگلیسی» - خواهر کوچیک‌تر generate_report.py سایت خبری؛
عمدا همون سیستم طراحی (فونت/پالت رنگ/note-card/quiz) رو دوباره استفاده می‌کنه تا حس بصری
یکسانی داشته باشن، هرچند این دو پروژه کاملا جدا و مستقلن.
"""

import base64
import html as html_lib
import os
from datetime import datetime, timezone

import config
from jalali import format_dual_date

_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")
_FONT_WEIGHTS = [
    ("light", "300"),
    ("regular", "400"),
    ("semibold", "500 600"),
    ("bold", "700"),
    ("black", "800 900"),
]


def _embedded_font_face_css() -> str:
    """فونت Noto Sans Arabic به‌صورت base64 جاسازی می‌شه - عینا همون دلیل سایت خبری
    (این‌طوری صفحه مستقل از پوشه‌ی assets هم درست دیده می‌شه)."""
    blocks = []
    for name, weight in _FONT_WEIGHTS:
        path = os.path.join(_FONT_DIR, f"notosansarabic-{name}.woff")
        try:
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
        except OSError:
            continue
        blocks.append(f"""
  @font-face {{
    font-family: 'Noto Sans Arabic';
    font-style: normal;
    font-weight: {weight};
    font-display: swap;
    src: url('data:font/woff;base64,{b64}') format('woff');
  }}""")
    return "".join(blocks)


def _tip_card_html(section: str, tip: dict) -> str:
    style = config.SECTION_STYLE.get(section, {"icon": "📘", "color": "#333"})
    if not tip or not tip.get("title") or not tip.get("body_fa"):
        return ""
    title = html_lib.escape(tip["title"])
    body = html_lib.escape(tip["body_fa"])
    example_en = html_lib.escape(tip.get("example_en", ""))
    example_fa = html_lib.escape(tip.get("example_fa", ""))
    example_html = ""
    if example_en:
        example_html = f"""
        <div class="example-box">
          <div class="example-en" dir="ltr">{example_en}</div>
          {f'<div class="example-fa">{example_fa}</div>' if example_fa else ''}
        </div>
        """
    return f"""
    <div class="note-card lesson-tip">
      <div class="note-label">{style['icon']} <strong>نکته امروز: {title}</strong></div>
      <p>{body}</p>
      {example_html}
    </div>
    """


def _render_lesson_item(it: dict, accent_color: str, number: int) -> str:
    title_fa = it.get("title_fa", "").strip()
    explain_fa = it.get("explain_fa", "").strip()
    new_badge = '<span class="badge-new">جدید</span>' if it.get("is_new") else ""
    title_html = (
        f'<span class="title-fa">{html_lib.escape(title_fa)}</span>'
        f'<span class="title-orig" dir="ltr">{html_lib.escape(it["title"])}</span>'
        if title_fa else
        f'<span class="title-fa" dir="ltr">{html_lib.escape(it["title"])}</span>'
    )
    explain_html = f'<div class="lesson-explain">{html_lib.escape(explain_fa)}</div>' if explain_fa else ""
    return f"""
    <div class="news-item" style="border-right-color:{accent_color};">
      <div class="news-num" style="background:{accent_color};">{number}</div>
      <div class="news-body">
        <div class="news-source">{html_lib.escape(it['source'])}{new_badge}</div>
        <div class="news-title">{title_html}</div>
        {explain_html}
        <div class="news-actions">
          <a class="news-link" href="{it['link']}" target="_blank">مشاهده مطلب اصلی ←</a>
        </div>
      </div>
    </div>
    """


def _render_section(section: str, items: list, tip: dict) -> str:
    style = config.SECTION_STYLE.get(section, {"icon": "📘", "color": "#333"})
    icon, color = style["icon"], style["color"]
    tip_html = _tip_card_html(section, tip)
    items_html = "".join(_render_lesson_item(it, color, i + 1) for i, it in enumerate(items))
    return f"""
    <section class="card" style="border-top-color:{color};">
      <h2 style="color:{color};">{icon} {section} <span class="count-badge">{len(items)} مطلب</span></h2>
      {tip_html}
      <div class="items-list">
        {items_html if items_html else '<p class="empty">فعلا مطلب تازه‌ای از منابع پیدا نشد؛ نکته‌ی امروز بالا رو از دست نده.</p>'}
      </div>
    </section>
    """


def _quiz_html(quiz: dict = None) -> str:
    if not quiz or not quiz.get("question") or len(quiz.get("options") or []) != 4:
        return ""
    question = html_lib.escape(quiz["question"])
    options = [html_lib.escape(o) for o in quiz["options"]]
    explanation = html_lib.escape(quiz.get("explanation", ""))
    correct_index = quiz.get("correct_index", 0)
    section = quiz.get("section", "")
    options_html = "".join(
        f'<button type="button" class="quiz-option" data-index="{i}" onclick="checkDailyQuiz(this)">{opt}</button>'
        for i, opt in enumerate(options)
    )
    return f"""
    <div class="note-card blue quiz-box" id="daily-quiz" data-correct="{correct_index}">
      <div class="note-label">🧠 <strong>تست این دوره{f" - {html_lib.escape(section)}" if section else ""}</strong></div>
      <p class="quiz-question">{question}</p>
      <div class="quiz-options">{options_html}</div>
      <div class="quiz-result" id="quiz-result"></div>
      <div class="quiz-explanation" id="quiz-explanation">💡 {explanation}</div>
    </div>
    """


def build_report(section_data: dict, tips: dict, quiz: dict = None, output_dir: str = None) -> str:
    """
    section_data: {section_name: [items...]} از fetch_content.fetch_all + analyze.summarize_section
    tips: {section_key: {...}} از analyze.daily_language_tips
    quiz: خروجی analyze.daily_quiz یا None
    """
    output_dir = output_dir or config.OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    now_str = format_dual_date(datetime.now(timezone.utc))
    quiz_html = _quiz_html(quiz)

    sections_html = "".join(
        _render_section(section, section_data.get(section, []), tips.get(config.SECTION_KEYS[section], {}))
        for section in config.RSS_SOURCES.keys()
    )

    html = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>آموزش زبان انگلیسی - {now_str}</title>
<style>
  {_embedded_font_face_css()}
  :root {{
    --bg: #eef1f5;
    --card: #ffffff;
    --navy: #1f3864;
    --navy-dark: #142544;
    --text: #202531;
    --muted: #757c8a;
    --up: #1e8449;
    --down: #c0392b;
    --border: #e3e7ee;
  }}
  * {{ box-sizing: border-box; }}
  html {{ -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }}
  html, body, div, span, h1, h2, h3, p, a, label, summary, input, button {{
    font-family: 'Noto Sans Arabic', Tahoma, Arial, sans-serif !important;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    text-rendering: optimizeLegibility;
    -webkit-text-stroke: 0;
  }}
  body {{ background: var(--bg); color: var(--text); margin: 0; padding: 0; font-size: 15px; line-height: 1.65; }}
  header {{
    background: linear-gradient(135deg, var(--navy), var(--navy-dark));
    color: #fff; padding: 22px 18px; border-radius: 0 0 20px 20px;
  }}
  .header-top {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 10px; }}
  .header-name {{ font-weight: 700; font-size: 13px; }}
  header h1 {{ margin: 0; font-size: 21px; font-weight: 800; }}
  header p {{ margin: 6px 0 0; opacity: .85; font-size: 12.5px; }}

  .container {{ max-width: 760px; margin: 0 auto; padding: 14px; }}
  .sections-grid {{ display: block; }}
  @media (min-width: 860px) {{
    .container {{ max-width: 1400px; padding: 18px; }}
    .sections-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; align-items: start; }}
  }}

  .note-card {{ border-radius: 12px; padding: 12px 14px; margin-bottom: 12px; font-size: 13.5px; border-right: 4px solid; }}
  .note-card.lesson-tip {{ background: #eaf1f8; border-color: var(--navy); }}
  .note-card.blue {{ background: #eaf1f8; border-color: var(--navy); }}
  .note-card p {{ margin: 0 0 8px; text-align: justify; text-align-last: right; }}
  .note-card p:last-child {{ margin-bottom: 0; }}
  .note-label {{ font-size: 13.5px; margin-bottom: 6px; }}

  .example-box {{ background: #fff; border: 1px dashed var(--border); border-radius: 8px; padding: 8px 10px; margin-top: 6px; }}
  .example-en {{ font-size: 13px; font-weight: 600; text-align: left; }}
  .example-fa {{ font-size: 12.5px; color: var(--muted); margin-top: 3px; text-align: right; }}

  .quiz-question {{ font-weight: 700; margin: 0 0 10px; }}
  .quiz-options {{ display: flex; flex-direction: column; gap: 7px; margin-bottom: 4px; }}
  .quiz-option {{
    display: block; width: 100%; text-align: right; background: #fff; border: 1.5px solid var(--border);
    border-radius: 10px; padding: 9px 12px; font-size: 13.5px; cursor: pointer; color: var(--text);
  }}
  .quiz-option:hover:not(:disabled) {{ border-color: var(--navy); }}
  .quiz-option:disabled {{ cursor: default; opacity: .75; }}
  .quiz-option.quiz-correct {{ background: #e5f6ec; border-color: var(--up); color: #14532d; font-weight: 700; }}
  .quiz-option.quiz-wrong {{ background: #fbeaea; border-color: var(--down); color: #7f1d1d; }}
  .quiz-result {{ font-weight: 700; font-size: 13.5px; margin-top: 8px; }}
  .quiz-result.quiz-result-correct {{ color: var(--up); }}
  .quiz-result.quiz-result-wrong {{ color: var(--down); }}
  .quiz-explanation {{ display: none; font-size: 12.5px; color: var(--muted); margin-top: 6px; text-align: justify; text-align-last: right; }}

  .card {{
    background: var(--card); border-radius: 16px; padding: 16px; margin-bottom: 14px;
    border-top: 4px solid; box-shadow: 0 1px 4px rgba(20,30,50,.06);
  }}
  .card h2 {{ margin: 0 0 10px; font-size: 17px; display: flex; align-items: center; gap: 6px; }}
  .count-badge {{ margin-right: auto; font-size: 10.5px; font-weight: 600; color: var(--muted); background: #f1f3f7; border-radius: 20px; padding: 2px 9px; }}

  .news-item {{ display: flex; gap: 10px; padding: 10px 10px 10px 0; border-bottom: 1px solid var(--border); border-right: 3px solid; margin-bottom: 2px; }}
  .news-item:last-child {{ border-bottom: none; }}
  .news-num {{
    flex-shrink: 0; width: 22px; height: 22px; border-radius: 50%; color: #fff;
    font-size: 11.5px; font-weight: 700; display: flex; align-items: center; justify-content: center; margin-top: 1px;
  }}
  .news-body {{ flex: 1; min-width: 0; }}
  .news-source {{ font-size: 10.5px; font-weight: 700; color: #b91c1c; margin-bottom: 3px; }}
  .badge-new {{ display: inline-block; background: var(--up); color: #fff; font-size: 9.5px; padding: 1px 7px; border-radius: 20px; margin-right: 6px; font-weight: 600; }}
  .news-title {{ font-weight: 700; font-size: 14.5px; line-height: 1.6; }}
  .title-orig {{ display: block; font-size: 12px; font-weight: 500; color: var(--muted); margin-top: 2px; }}
  .lesson-explain {{ font-size: 12.5px; color: var(--text); margin-top: 5px; background: #f7f8fa; border-radius: 8px; padding: 7px 9px; text-align: justify; text-align-last: right; }}
  .news-actions {{ margin-top: 6px; }}
  .news-link {{ font-size: 12px; color: var(--navy); text-decoration: none; font-weight: 600; }}
  .empty {{ color: var(--muted); font-size: 13px; }}

  footer {{ text-align: center; padding: 22px; font-size: 11px; color: var(--muted); }}

  @media (max-width: 480px) {{
    body {{ font-size: 16px; }}
    header p {{ font-size: 13.5px; }}
    .note-card, .note-label {{ font-size: 15px; }}
    .news-link {{ font-size: 13.5px; }}
    .count-badge {{ font-size: 12px; }}
  }}
</style>
</head>
<body>
<header>
  <div class="header-top">
    <div class="header-name">👋 {config.USER_NAME}</div>
  </div>
  <h1>📚 خلاصه‌ی آموزش زبان انگلیسی</h1>
  <p>{now_str}</p>
</header>
<div class="container">
  <div class="sections-grid">
    {sections_html}
  </div>
  {quiz_html}
</div>
<footer>
  این صفحه به‌صورت خودکار (۲ بار در روز) از منابع واقعی آموزش زبان (VOA Learning English،
  Merriam-Webster) به‌علاوه‌ی نکته‌های تولیدشده توسط هوش مصنوعی ساخته می‌شه. برای متن کامل
  هر درس روی «مشاهده مطلب اصلی» بزن.
</footer>
<script>
function checkDailyQuiz(btn) {{
  var box = document.getElementById('daily-quiz');
  var correct = parseInt(box.getAttribute('data-correct'), 10);
  var clicked = parseInt(btn.getAttribute('data-index'), 10);
  var buttons = box.querySelectorAll('.quiz-option');
  buttons.forEach(function(b) {{ b.disabled = true; }});
  var resultEl = document.getElementById('quiz-result');
  var explEl = document.getElementById('quiz-explanation');
  if (clicked === correct) {{
    btn.classList.add('quiz-correct');
    resultEl.textContent = '✅ آفرین، درست بود!';
    resultEl.className = 'quiz-result quiz-result-correct';
  }} else {{
    btn.classList.add('quiz-wrong');
    buttons[correct].classList.add('quiz-correct');
    resultEl.textContent = '❌ جواب درست گزینه‌ی دیگه‌ای بود.';
    resultEl.className = 'quiz-result quiz-result-wrong';
  }}
  explEl.style.display = 'block';
}}
</script>
</body>
</html>
"""

    out_path = os.path.join(output_dir, "latest.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return html
