# -*- coding: utf-8 -*-
"""
صدای انگلیسی طبیعی (آمریکایی) برای متن‌های انگلیسی صفحه.

generate_report هر متن انگلیسی رو با audio_button(text) ثبت می‌کنه و یک دکمه‌ی 🔊 کنارش می‌ذاره.
بعد از ساخت HTML، render(output_dir) همه‌ی این متن‌ها رو با مدل Kokoro-82M (صدای af_heart، لهجه‌ی
آمریکایی) به فایل MP3 در output/audio/ تبدیل می‌کنه. اگه Kokoro نصب نبود یا خطا داد، هیچ اشکالی پیش
نمیاد: دکمه‌ها خودشون با صدای مرورگر (en-US) می‌خونن، پس صفحه همیشه منتشر می‌شه.
"""

import hashlib
import html as html_lib
import logging
import os
import re
import subprocess

log = logging.getLogger(__name__)

_TEXTS = {}  # key -> text
SR = 24000


def _key(text: str) -> str:
    return hashlib.sha1(re.sub(r"\s+", " ", text).strip().lower().encode("utf-8")).hexdigest()[:16]


def speakable(text: str) -> str:
    """متنی که دکمه باید بخونه: خودِ متن اگه کاملا انگلیسیه، وگرنه فقط تکه‌ی انگلیسیِ داخلش (یا هیچ)."""
    if not re.search(r"[\u0600-\u06FF]", text or ""):
        return text if len(re.findall(r"[A-Za-z]", text or "")) >= 3 else ""
    return english_part(text)


def ltr_attr(text: str) -> str:
    """خطی که هیچ حرف فارسی نداره چپ‌چین نشون داده بشه (تا نقطه‌ی آخر جمله جابه‌جا نشه)."""
    return ' dir="ltr"' if re.search(r"[A-Za-z]", text or "") and not re.search(r"[\u0600-\u06FF]", text or "") else ""


def is_english(text: str) -> bool:
    """متنی که بیشترش حروف انگلیسیه (مثلا جمله‌ی نمونه)، نه فارسی با یکی دو کلمه‌ی انگلیسی."""
    latin = len(re.findall(r"[A-Za-z]", text or ""))
    persian = len(re.findall(r"[؀-ۿ]", text or ""))
    return latin >= 8 and latin > 2 * persian


def english_part(text: str) -> str:
    """از یک خط مخلوط، تکه‌ی انگلیسیِ اصلی رو برمی‌گردونه (مثلا جمله‌ی مثال داخل یک خط فارسی)."""
    parts = re.findall(r"[A-Za-z][A-Za-z0-9 ,.'’!?;:\-\"()]{12,}", text or "")
    parts = [p.strip(" ,;:-\"()") for p in parts]
    parts = [p for p in parts if len(re.findall(r"[A-Za-z]", p)) >= 10 and " " in p]
    return max(parts, key=len) if parts else ""


def audio_button(text: str, label: str = "🔊") -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text or not re.search(r"[A-Za-z]", text):
        return ""
    k = _key(text)
    _TEXTS[k] = text
    return (f'<button type="button" class="say-btn" data-src="audio/{k}.mp3" '
            f'data-text="{html_lib.escape(text)}" onclick="sayIt(this)" aria-label="Listen">{label}</button>')


# پخش: اول فایل ضبط‌شده، اگه نبود صدای خودِ مرورگر
PLAYER_JS = """
let _sayA=null;
function sayIt(b){
  try{if(_sayA){_sayA.pause();_sayA=null}speechSynthesis.cancel()}catch(e){}
  const t=b.dataset.text;
  const fallback=()=>{try{const u=new SpeechSynthesisUtterance(t);u.lang='en-US';u.rate=.9;
    const v=speechSynthesis.getVoices().filter(x=>/en[-_]US/i.test(x.lang));const best=v.find(x=>/natural|neural|premium|enhanced|samantha|aria|jenny/i.test(x.name))||v[0];if(best)u.voice=best;
    speechSynthesis.speak(u)}catch(e){}};
  const a=new Audio(b.dataset.src);_sayA=a;b.classList.add('playing');
  a.onended=a.onerror=()=>b.classList.remove('playing');
  a.play().catch(()=>{b.classList.remove('playing');fallback()});
}
"""

PLAYER_CSS = """
.say-btn{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;margin:0 6px;
  border-radius:50%;border:1.5px solid #c9b88a;background:#fffaf0;cursor:pointer;font-size:16px;vertical-align:middle;flex:none}
.say-btn:hover{background:#f3e7c8}.say-btn.playing{background:#ffe08a;animation:sayp 1s infinite}
@keyframes sayp{50%{transform:scale(1.1)}}
"""


def render(output_dir: str) -> int:
    """متن‌های ثبت‌شده رو به MP3 تبدیل می‌کنه. تعداد فایل‌های ساخته‌شده رو برمی‌گردونه (۰ اگه Kokoro نبود)."""
    if not _TEXTS:
        return 0
    try:
        import numpy as np
        from kokoro import KPipeline
    except Exception as e:  # noqa: BLE001
        log.warning(f"Kokoro نصب نیست ({e})؛ دکمه‌های صدا با صدای مرورگر کار می‌کنن.")
        return 0
    audio_dir = os.path.join(output_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    try:
        pipe = KPipeline(lang_code="a")  # American English
    except Exception as e:  # noqa: BLE001
        log.warning(f"مدل Kokoro بارگذاری نشد ({e})؛ صدای مرورگر استفاده می‌شه.")
        return 0
    made = 0
    for k, text in _TEXTS.items():
        path = os.path.join(audio_dir, f"{k}.mp3")
        if os.path.exists(path):
            made += 1
            continue
        try:
            parts = [r.audio.numpy() for r in pipe(text, voice="af_heart", speed=1.0) if r.audio is not None]
            if not parts:
                continue
            audio = np.concatenate(parts)
            peak = float(np.max(np.abs(audio))) or 1.0
            pcm = (np.clip(audio * (0.89 / peak), -1, 1) * 32767).astype("<i2").tobytes()
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "s16le", "-ar", str(SR), "-ac", "1",
                            "-i", "pipe:0", "-codec:a", "libmp3lame", "-b:a", "96k", path],
                           input=pcm, check=True)
            made += 1
        except Exception as e:  # noqa: BLE001 - یک متن خراب نباید بقیه رو متوقف کنه
            log.warning(f"صدا برای «{text[:50]}» ساخته نشد: {e}")
    log.info(f"{made} فایل صوتی از {len(_TEXTS)} متن انگلیسی ساخته شد.")
    return made
