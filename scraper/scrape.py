# -*- coding: utf-8 -*-
"""Собирает объявления с Krisha.kz по запросам из searches.json.

Результат: data/listings.json — все объявления с отметкой first_seen,
чтобы приложение могло показать, какие появились недавно.
Запускается GitHub Actions по расписанию.
"""
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
}


def fetch(url: str) -> str:
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


CARD_RE = re.compile(r'<div[^>]+class="[^"]*a-card[^"]*"[^>]+data-id="(\d+)"(.*?)(?=<div[^>]+class="[^"]*a-card[^"]*"[^>]+data-id="|\Z)', re.S)
TITLE_RE = re.compile(r'a-card__title[^>]*>(.*?)</a>', re.S)
HREF_RE = re.compile(r'<a[^>]+class="[^"]*a-card__title[^"]*"[^>]+href="([^"]+)"')
PRICE_RE = re.compile(r'a-card__price[^>]*>(.*?)</div>', re.S)
ADDR_RE = re.compile(r'a-card__subtitle[^>]*>(.*?)</div>', re.S)


def clean(html_fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html_fragment)
    text = re.sub(r"&nbsp;?", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_listings(html: str):
    items = []
    for m in CARD_RE.finditer(html):
        ad_id, body = m.group(1), m.group(2)
        href = HREF_RE.search(body)
        title = TITLE_RE.search(body)
        price = PRICE_RE.search(body)
        addr = ADDR_RE.search(body)
        items.append({
            "id": ad_id,
            "url": "https://krisha.kz" + href.group(1) if href else f"https://krisha.kz/a/show/{ad_id}",
            "title": clean(title.group(1)) if title else "Объявление " + ad_id,
            "price": clean(price.group(1)) if price else "",
            "address": clean(addr.group(1)) if addr else "",
        })
    return items


def main():
    searches = json.loads((ROOT / "searches.json").read_text(encoding="utf-8"))["searches"]

    listings_path = DATA / "listings.json"
    old = {}
    if listings_path.exists():
        try:
            for s in json.loads(listings_path.read_text(encoding="utf-8"))["searches"]:
                for it in s["items"]:
                    old[(s["id"], it["id"])] = it.get("first_seen")
        except Exception:
            pass

    now = datetime.now(timezone.utc).isoformat()
    out = {"updated": now, "searches": []}
    errors = []

    for s in searches:
        items = []
        try:
            html = fetch(s["url"])
            items = parse_listings(html)
        except Exception as e:
            errors.append(f"{s['id']}: {e}")
        for it in items:
            it["first_seen"] = old.get((s["id"], it["id"])) or now
        out["searches"].append({
            "id": s["id"], "title": s["title"], "type": s.get("type", "flat"),
            "url": s["url"], "items": items,
        })
        time.sleep(2)  # вежливая пауза между запросами

    if errors:
        print("Ошибки:", *errors, sep="\n", file=sys.stderr)

    listings_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(len(s["items"]) for s in out["searches"])
    print(f"Готово: {total} объявлений по {len(out['searches'])} запросам")


if __name__ == "__main__":
    main()
