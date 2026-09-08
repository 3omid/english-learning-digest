# -*- coding: utf-8 -*-
"""تبدیل تاریخ میلادی به شمسی - بدون نیاز به کتابخونه خارجی (خودکفا)."""

from zoneinfo import ZoneInfo

TEHRAN_TZ = ZoneInfo("Asia/Tehran")
TORONTO_TZ = ZoneInfo("America/Toronto")

PERSIAN_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def to_persian_digits(s) -> str:
    return str(s).translate(PERSIAN_DIGITS)


def _div(a, b):
    return a // b if a >= 0 else -((-a) // b)


def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    gy2 = gy + 1 if gm > 2 else gy
    days = (365 * gy) + _div(gy2 + 3, 4) - _div(gy2 + 99, 100) + _div(gy2 + 399, 400) - 80 + gd + g_d_m[gm - 1]
    jy += 33 * _div(days, 12053)
    days %= 12053
    jy += 4 * _div(days, 1461)
    days %= 1461
    if days > 365:
        jy += _div(days - 1, 365)
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + _div(days, 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + _div(days - 186, 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


def format_dual_date(dt) -> str:
    """
    ورودی: datetime.datetime (ترجیحا timezone-aware - اگه naive باشه فقط تاریخ برمی‌گرده،
    بدون ساعت، چون نمی‌شه مطمئن بود این زمان مال کدوم منطقه زمانیه).
    خروجی: تاریخ شمسی + میلادی + ساعت محلی تهران و تورنتو، مثل:
    «۱۳ شهریور ۱۴۰۵ | 2026-09-04 · تهران ۱۴:۳۰ · تورنتو ۰۷:۰۰»
    قبلا فقط تاریخ (بدون ساعت) نشون داده می‌شد و هیچ ساعتی برای کانادا نبود -
    این تابع الان همون‌جوری که بخش آب‌وهوا هر دو شهر رو نشون می‌ده، این‌جا هم نشون می‌ده.
    """
    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    jd_str = f"{jd} {PERSIAN_MONTHS[jm - 1]} {jy}".translate(PERSIAN_DIGITS)
    g_str = dt.strftime("%Y-%m-%d")
    time_str = ""
    if dt.tzinfo is not None:
        tehran_time = to_persian_digits(dt.astimezone(TEHRAN_TZ).strftime("%H:%M"))
        toronto_time = to_persian_digits(dt.astimezone(TORONTO_TZ).strftime("%H:%M"))
        time_str = f" · تهران {tehran_time} · تورنتو {toronto_time}"
    return f"{jd_str} | {g_str}{time_str}"


if __name__ == "__main__":
    import datetime
    print(format_dual_date(datetime.datetime(2026, 9, 4)))
