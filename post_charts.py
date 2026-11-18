
import os
import sys
import time
from datetime import datetime, time as clock_time
from zoneinfo import ZoneInfo

import requests

API_URL = "https://api.chart-img.com/v2/tradingview/advanced-chart"

CHARTS = {
    "saudi": [
        ("TASI", "TADAWUL:TASI"),
        ("Al Rajhi", "TADAWUL:1120"),
    ],
    "us": [
        ("S&P 500", "SP:SPX"),
        ("Nasdaq 100", "NASDAQ:NDX"),
    ],
}


def active_markets():
    now_sa = datetime.now(ZoneInfo("Asia/Riyadh"))
    now_us = datetime.now(ZoneInfo("America/New_York"))
    markets = []

    # Saudi: Sunday through Thursday, 10:00-15:00
    if (
        now_sa.weekday() in (6, 0, 1, 2, 3)
        and clock_time(10, 0) <= now_sa.time() < clock_time(15, 0)
    ):
        markets.append("saudi")

    # US: Monday through Friday, 09:30-16:00
    if (
        now_us.weekday() < 5
        and clock_time(9, 30) <= now_us.time() < clock_time(16, 0)
    ):
        markets.append("us")

    return markets


def generate_chart(symbol, api_key):
    response = requests.post(
        API_URL,
        headers={
            "x-api-key": api_key,
            "Content-Type": "application/json",
        },
        json={
            "symbol": symbol,
            "interval": "1h",
            "theme": "dark",
        },
        timeout=90,
    )
    response.raise_for_status()

    content_type = response.headers.get(
        "Content-Type", ""
    ).lower()

    if not content_type.startswith("image/"):
        raise ValueError(
            f"Expected image for {symbol}; got {content_type}"
        )

    return response.content



def send_chart(name, symbol, image, webhook_url):
    import json

    market = "🇸🇦 السوق السعودي" if symbol.startswith("TADAWUL:") else "🇺🇸 السوق الأمريكي"

    chart_names = {
        "TADAWUL:TASI": "مؤشر تاسي",
        "TADAWUL:1120": "مصرف الراجحي",
        "SP:SPX": "مؤشر S&P 500",
        "NASDAQ:NDX": "مؤشر Nasdaq 100",
    }

    chart_name = chart_names.get(symbol, name)

    message = (
    f"{market}\n"
    f"📈 **{chart_name}**\n"
    "⏱️ الإطار الزمني: ساعة واحدة (1H)\n\n"
    "💚 تابع حركة السوق عبر الشارت المرفق"
)

    filename = symbol.replace(":", "_") + ".png"

    response = requests.post(
        webhook_url,
        data={
            "payload_json": json.dumps(
                {
                    "content": message,
                    "allowed_mentions": {"parse": []},
                },
                ensure_ascii=False,
            )
        },
        files={
            "files[0]": (
                filename,
                image,
                "image/png",
            )
        },
        timeout=30,
    )

    response.raise_for_status()
    print(f"Posted chart: {name}")



def main():
    api_key = os.environ["CHART_IMG_API_KEY"]
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")

    # Must be explicitly enabled after
    # obtaining public redistribution permission.
    publish = os.getenv("ENABLE_PUBLIC_POSTING") == "true"

    markets = active_markets()

    if not markets:
        print("Markets closed; no charts requested.")
        return

    if publish and not webhook_url:
        raise RuntimeError("Missing Discord webhook URL")

    errors = []

    for market in markets:
        for name, symbol in CHARTS[market]:
            try:
                image = generate_chart(symbol, api_key)
                print(
                    f"Generated {name}: {len(image)} bytes"
                )

                if publish:
                    send_chart(
                        name, symbol, image, webhook_url
                    )
                else:
                    print(
                        f"Private test only: {name}. "
                        "Public posting disabled."
                    )

            except Exception as error:
                errors.append(f"{symbol}: {error}")
                print(f"ERROR {symbol}: {error}")

            # Stay below the free-tier 1 req/sec limit.
            time.sleep(2)

    if errors:
        raise RuntimeError("; ".join(errors))


if __name__ == "__main__":
    main()
