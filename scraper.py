#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re
import asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta
from playwright.async_api import async_playwright

# ─── KANAL LİSTESİ ────────────────────────────────────────────────────────────
KANALLAR = [
    {"name": "usabc", "url": "https://tvnow247.top/watch/abc-usa/", "group": "US"},
    {"name": "uscbs", "url": "https://tvnow247.top/watch/cbs-usa/", "group": "US"},
    {"name": "usnbc", "url": "https://tvnow247.top/watch/nbc-usa/", "group": "US"},
    {"name": "usfox", "url": "https://tvnow247.top/watch/fox-usa/", "group": "US"},
    {"name": "usespn", "url": "https://tvnow247.top/watch/espn-usa/", "group": "US"},
    {"name": "usespn2", "url": "https://tvnow247.top/watch/espn-2/", "group": "US"},
    {"name": "ususa", "url": "https://tvnow247.top/watch/usa-network/", "group": "US"},
    {"name": "usnflnetwork", "url": "https://tvnow247.top/watch/nfl-network/", "group": "US"},
    {"name": "usnbatv", "url": "https://tvnow247.top/watch/nba-tv/", "group": "US"},
    {"name": "ukskysportsmainevent", "url": "https://tvnow247.top/watch/sky-sports-main-event/", "group": "UK"},
    {"name": "ukskysportspremierleague", "url": "https://tvnow247.top/watch/sky-sports-premier-league/", "group": "UK"},
    {"name": "ukskysportsf1", "url": "https://tvnow247.top/watch/sky-sports-f1/", "group": "UK"},
    {"name": "uktntsports1", "url": "https://tvnow247.top/watch/tnt-sports-1-uk/", "group": "UK"},
    {"name": "uktntsports2", "url": "https://tvnow247.top/watch/tnt-sports-2-uk/", "group": "UK"},
    {"name": "trbeinsports1", "url": "https://tvnow247.top/watch/bein-sports-1-turkey/", "group": "TR"},
]

# ─── AYARLAR ──────────────────────────────────────────────────────────────────
OUTPUT_DIR_NAME = "tvnow247"
DEBUG_FILE = "debug_failed.json"
MAX_CONCURRENT = 2          # Bot engeline takılmamak ve CPU'yu yormamak için 2 idealdir
PAGE_TIMEOUT = 25000        # Sayfa yükleme zaman aşımı (25 sn)
SCAN_WAIT = 10              # Yayın yakalama bekleme süresi (10 sn)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
}

# ──────────────────────────────────────────────────────────────────────────────

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def is_blacklisted(url: str) -> bool:
    bad_keywords = [
        "google", "analytics", "doubleclick", "adservice", "banner", 
        "popcash", "histats", "counter", "tracker", "adsterra"
    ]
    url_low = url.lower()
    return any(b in url_low for b in bad_keywords)


async def get_channel_stream(browser, page_url: str) -> str:
    stream_url = ""
    found_event = asyncio.Event()

    context = await browser.new_context(
        user_agent=HEADERS["User-Agent"],
        viewport={"width": 1366, "height": 768},
        ignore_https_errors=True,
        has_touch=True,
    )

    # 1. BOT KORUMASINI GİZLE (Stealth Evasion)
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        window.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en', 'tr'] });
    """)

    page = await context.new_page()

    # Reklam sekmelerini açıldığı anda imha et
    page.on("popup", lambda p: asyncio.create_task(p.close()))

    # 2. AĞ TRAFİĞİNİ DERİNLEMESİNE DİNLE (URL + Response Body Denetimi)
    async def handle_response(response):
        nonlocal stream_url
        if stream_url:
            return

        url = response.url
        if is_blacklisted(url):
            return

        # A) Doğrudan URL uzantısı kontrolü (.m3u8 veya .mpd)
        clean_url = url.split("?")[0].lower()
        if clean_url.endswith(".m3u8") or ".m3u8" in clean_url or clean_url.endswith(".mpd"):
            stream_url = url
            found_event.set()
            return

        # B) Content-Type header kontrolü (HLS akışları)
        content_type = response.headers.get("content-type", "").lower()
        if "mpegurl" in content_type or "application/x-mpegurl" in content_type:
            stream_url = url
            found_event.set()
            return

        # C) Paket içeriğinde #EXTM3U kontrolü (Gizlenmiş Tokenli Yayınlar)
        if response.status == 200 and ("text" in content_type or "octet-stream" in content_type or not content_type):
            try:
                body = await response.text()
                if body.startswith("#EXTM3U") or "#EXT-X-STREAM-INF" in body:
                    stream_url = url
                    found_event.set()
            except Exception:
                pass

    page.on("response", handle_response)

    try:
        # Sayfaya git
        await page.goto(page_url, timeout=PAGE_TIMEOUT, wait_until="domcontentloaded")
        await asyncio.sleep(2)

        # 3. TÜM IFRAME'LERİ TARA VE SAHTE REKLAM KATMANLARINA TIKLA
        for _ in range(3):  # Reklamları geçmek için 3 defa tıklama simülasyonu
            if stream_url:
                break

            # Ana sayfaya tıkla
            try:
                await page.mouse.click(640, 360)
            except Exception:
                pass

            # Bütün iframe'lerin içine girip oynatıcı butonlarına ve video etiketlerine tıkla
            for frame in page.frames:
                try:
                    await frame.evaluate("""() => {
                        // Video elementlerini zorla oynat
                        document.querySelectorAll('video').forEach(v => {
                            v.muted = true;
                            v.play().catch(()=>{});
                        });
                        // Olası butonlara tıkla
                        const playBtns = document.querySelectorAll(
                            '.play-wrapper, .vjs-big-play-button, .jw-display-icon-container, #player, .player-poster, button'
                        );
                        playBtns.forEach(btn => btn.click());
                    }""")
                except Exception:
                    pass

            await asyncio.sleep(1.5)

        # Yayın gelene kadar bekle
        try:
            await asyncio.wait_for(found_event.wait(), timeout=SCAN_WAIT)
        except asyncio.TimeoutError:
            pass

        # 4. YEDEK PLAN: JavaScript Global Değişkenlerinden Ara
        if not stream_url:
            for frame in page.frames:
                try:
                    val = await frame.evaluate("""() => {
                        try { if (typeof jwplayer !== 'undefined') return jwplayer().getPlaylist()[0].file; } catch(e){}
                        try { if (typeof player !== 'undefined' && player.src) return player.src(); } catch(e){}
                        try { if (typeof Hls !== 'undefined' && Hls.url) return Hls.url; } catch(e){}
                        const v = document.querySelector('video');
                        if (v && v.src && v.src.startsWith('http')) return v.src;
                        return null;
                    }""")
                    if val and (".m3u8" in val or ".mpd" in val):
                        stream_url = val
                        break
                except Exception:
                    pass

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
        # İnsan benzeri Chrome argümanları ile başlat
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--mute-audio",
                "--disable-web-security"
            ]
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
                    print(f"  ✅ {prefix} {name} → {stream_url[:65]}...")
                    success.append({"name": name, "stream_url": stream_url, "group": ch.get("group", "")})
                else:
                    print(f"  ❌ {prefix} {name} → Yayın linki bulunamadı!")
                    failed.append({"name": name, "page_url": url})

        await asyncio.gather(*[handle(ch) for ch in channels], return_exceptions=True)
        await browser.close()

    return success, failed


def write_to_m3u8_files(items: list, output_dir: str):
    base_path = Path(__file__).parent.resolve()
    target_dir = base_path / output_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📂 Dosyalar Oluşturuluyor: {target_dir}")

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
    print("   📺 TVNOW247 - GELİŞMİŞ IFRAME / M3U8 YAKALAYICI")
    print("=" * 60 + "\n")

    success, failed = await process_all(KANALLAR)

    write_to_m3u8_files(success, OUTPUT_DIR_NAME)

    with open(DEBUG_FILE, "w", encoding="utf-8") as f:
        json.dump(failed, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"📊 SONUÇ:")
    print(f"  Toplam Kanal : {len(KANALLAR)}")
    print(f"  Başarılı     : {len(success)}")
    print(f"  Başarısız    : {len(failed)}")
    print(f"  Klasör       : ./{OUTPUT_DIR_NAME}/")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
