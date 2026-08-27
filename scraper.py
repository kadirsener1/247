#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re
import asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta
from playwright.async_api import async_playwright

# ─── KANAL LİSTESİ (tvnow247.top) ─────────────────────────────────────────────
KANALLAR = [
    {
        "name": "usabc",
        "url": "https://tvnow247.top/watch/abc-usa/",
        "group": "US"
    },
    {
        "name": "uscbs",
        "url": "https://tvnow247.top/watch/cbs-usa/",
        "group": "US"
    },
    {
        "name": "usnbc",
        "url": "https://tvnow247.top/watch/nbc-usa/",
        "group": "US"
    },
    {
        "name": "usfox",
        "url": "https://tvnow247.top/watch/fox-usa/",
        "group": "US"
    },
    {
        "name": "usespn",
        "url": "https://tvnow247.top/watch/espn-usa/",
        "group": "US"
    },
    {
        "name": "usespn2",
        "url": "https://tvnow247.top/watch/espn-2/",
        "group": "US"
    },
    {
        "name": "ususa",
        "url": "https://tvnow247.top/watch/usa-network/",
        "group": "US"
    },
    {
        "name": "usnflnetwork",
        "url": "https://tvnow247.top/watch/nfl-network/",
        "group": "US"
    },
    {
        "name": "usnbatv",
        "url": "https://tvnow247.top/watch/nba-tv/",
        "group": "US"
    },
    {
        "name": "ukskysportsmainevent",
        "url": "https://tvnow247.top/watch/sky-sports-main-event/",
        "group": "UK"
    },
    {
        "name": "ukskysportspremierleague",
        "url": "https://tvnow247.top/watch/sky-sports-premier-league/",
        "group": "UK"
    },
    {
        "name": "ukskysportsf1",
        "url": "https://tvnow247.top/watch/sky-sports-f1/",
        "group": "UK"
    },
    {
        "name": "uktntsports1",
        "url": "https://tvnow247.top/watch/tnt-sports-1-uk/",
        "group": "UK"
    },
    {
        "name": "uktntsports2",
        "url": "https://tvnow247.top/watch/tnt-sports-2-uk/",
        "group": "UK"
    },
    {
        "name": "trbeinsports1",
        "url": "https://tvnow247.top/watch/bein-sports-1-turkey/",
        "group": "TR"
    }
    # Yeni kanalları buraya ekleyebilirsiniz.
]

# ─── AYARLAR ──────────────────────────────────────────────────────────────────
OUTPUT_DIR_NAME = "tvnow247"    # Dosyaların kaydedileceği klasör
DEBUG_FILE = "debug_failed.json"
MAX_CONCURRENT = 3              # Aynı anda taranacak sayfa sayısı
WAIT_TIMEOUT = 12               # Bir kanal için maksimum bekleme süresi (saniye)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8",
    "Referer": "https://tvnow247.top/",
}

# ──────────────────────────────────────────────────────────────────────────────

def is_valid_m3u8(url: str) -> bool:
    """Ağ trafiğinden yakalanan linkin geçerli bir m3u8 yayın linki olup olmadığını denetler."""
    if not url or not isinstance(url, str):
        return False
    
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return False
        
    base_path = url.split("?")[0].lower()
    
    # Reklam ve analiz isteklerini ele
    bad_words = ["ads", "doubleclick", "telemetry", "analytics", "banner"]
    if any(b in url.lower() for b in bad_words):
        return False

    # Linkin m3u8 veya mpd dosyası olduğunu doğrula
    if ".m3u8" in base_path or ".mpd" in base_path:
        return True
        
    return False


def sanitize_filename(name: str) -> str:
    """Dosya adlarındaki geçersiz karakterleri temizler."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


async def get_channel_stream(browser, page_url: str) -> str:
    """Sayfayı açar ve arka planda oynatılan m3u8 linkini yakalar."""
    stream_url = ""
    found_event = asyncio.Event()

    context = await browser.new_context(
        user_agent=HEADERS["User-Agent"],
        extra_http_headers={"Referer": HEADERS["Referer"]},
        bypass_csp=True,
        ignore_https_errors=True,
        viewport={"width": 1280, "height": 720}
    )

    page = await context.new_page()

    # Sayfadaki reklam açılır pencerelerini (Pop-up) otomatik kapat
    page.on("popup", lambda p: asyncio.create_task(p.close()))

    # Ağ trafiğini (Network) dinle ve m3u8 isteğini yakala
    async def handle_request(request):
        nonlocal stream_url
        if not stream_url and is_valid_m3u8(request.url):
            stream_url = request.url
            found_event.set()

    page.on("request", handle_request)

    try:
        # Sayfaya git
        await page.goto(page_url, timeout=20000, wait_until="domcontentloaded")

        # Oynatıcıyı tetiklemek için ekrana tıkla
        try:
            await page.mouse.click(350, 250)
            await page.evaluate("""() => {
                const v = document.querySelector('video');
                if (v) { v.muted = true; v.play().catch(()=>{}); }
            }""")
        except Exception:
            pass

        # Yayın linki yakalanana kadar bekle
        try:
            await asyncio.wait_for(found_event.wait(), timeout=WAIT_TIMEOUT)
        except asyncio.TimeoutError:
            pass

        # Eğer istekten gelmediyse HTML içinden regex ile tara
        if not stream_url:
            html = await page.content()
            matches = re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', html)
            for m in matches:
                if is_valid_m3u8(m):
                    stream_url = m
                    break

    except Exception:
        pass
    finally:
        await page.close()
        await context.close()

    return stream_url


async def process_all(channels: list):
    success = []
    failed = []
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    total = len(channels)
    done_count = 0
    lock = asyncio.Lock()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--mute-audio"]
        )

        async def handle(ch):
            nonlocal done_count
            name = ch.get("name", "isimsiz")
            url = ch.get("url", "")

            async with semaphore:
                stream_url = await get_channel_stream(browser, url)

            async with lock:
                done_count += 1
                prefix = f"[{done_count:02d}/{total}]"

                if stream_url:
                    print(f"  ✅ {prefix} {name} → {stream_url[:70]}...")
                    success.append({"name": name, "stream_url": stream_url, "group": ch.get("group", "")})
                else:
                    print(f"  ❌ {prefix} {name} → Yayın linki bulunamadı!")
                    failed.append({"name": name, "page_url": url})

        await asyncio.gather(*[handle(ch) for ch in channels], return_exceptions=True)
        await browser.close()

    return success, failed


def write_to_m3u8_files(items: list, output_dir: str):
    """Bulunan yayın linklerini tvnow247/kanal_adi.m3u8 formatında kaydeder."""
    base_path = Path(__file__).parent.resolve()
    target_dir = base_path / output_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📂 Dosyalar Yazılıyor: {target_dir}")

    for ch in items:
        safe_name = sanitize_filename(ch["name"])
        file_path = target_dir / f"{safe_name}.m3u8"
        stream_link = ch["stream_url"]

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                f.write("#EXT-X-VERSION:3\n")
                f.write("#EXT-X-STREAM-INF:BANDWIDTH=8000000\n")
                f.write(f"{stream_link}\n")
            print(f"   💾 Kaydedildi: {file_path.name}")
        except Exception as e:
            print(f"   ❌ Hata ({safe_name}): {e}")


async def main():
    print("=" * 60)
    print("   📺 TVNOW247 - CANLI YAYIN LİNKİ ÇEKİCİ")
    print("=" * 60 + "\n")

    success, failed = await process_all(KANALLAR)

    # Dosyaları ayrı .m3u8 olarak kaydet
    write_to_m3u8_files(success, OUTPUT_DIR_NAME)

    # Başarısızları logla
    with open(DEBUG_FILE, "w", encoding="utf-8") as f:
        json.dump(failed, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"📊 ÖZET:")
    print(f"  Toplam Kanal : {len(KANALLAR)}")
    print(f"  Başarılı     : {len(success)}")
    print(f"  Başarısız    : {len(failed)}")
    print(f"  Klasör       : ./{OUTPUT_DIR_NAME}/")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
