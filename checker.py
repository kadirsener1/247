#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re
import asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from playwright.async_api import async_playwright


# ─── AYARLAR ──────────────────────────────────────────────────────────────────
API_URL = "https://api.cdnlivetv.is/api/v1/channels/?user=cdnlivetv&plan=free"
OUTPUT_FILE = "cdnlive.m3u"
DEBUG_FILE = "debug_failed.json"

TIMEOUT = 30000       # ms (Playwright için)
PAGE_WAIT = 10000     # ms - stream yüklenene kadar bekle
MAX_CONCURRENT = 3    # Aynı anda kaç sayfa açılsın
ONLY_ONLINE = True    # Sadece status=online olanları al

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8",
    "Referer": "https://cdnlivetv.tv/",
    "Origin": "https://cdnlivetv.tv",
}

BROWSER_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-gpu-sandbox",
    "--disable-software-rasterizer",
    "--disable-accelerated-2d-canvas",
    "--disable-accelerated-video-decode",
    "--disable-accelerated-video-encode",
    "--disable-webgl",
    "--disable-webgl2",
    "--disable-3d-apis",
    "--disable-extensions",
    "--no-zygote",
    "--single-process",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-background-networking",
    "--disable-default-apps",
    "--disable-sync",
    "--disable-translate",
    "--hide-scrollbars",
    "--metrics-recording-only",
    "--mute-audio",
    "--safebrowsing-disable-auto-update",
    "--ignore-certificate-errors",
    "--ignore-ssl-errors",
    "--ignore-certificate-errors-spki-list",
]

BROWSER_ENV = {
    "DISPLAY": "",
    "LIBGL_ALWAYS_SOFTWARE": "1",
    "GALLIUM_DRIVER": "softpipe",
}
# ──────────────────────────────────────────────────────────────────────────────


def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update(HEADERS)
    return s


def looks_like_stream(url: str) -> bool:
    if not url:
        return False
    u = url.lower()
    return any(x in u for x in [
        ".m3u8",
        ".mpd",
        "/manifest",
        "mpegurl",
        "application/dash",
        "master.m3u8",
        "index.m3u8",
        "/hls/",
        "/dash/",
        "/live/stream",
    ])


def load_channels() -> list:
    print(f"🌐 API'den kanallar çekiliyor...")
    print(f"   {API_URL}\n")

    session = make_session()
    r = session.get(API_URL, timeout=30)
    r.raise_for_status()
    data = r.json()

    channels = data.get("channels", [])
    print(f"📡 API toplam kanal  : {data.get('total_channels', len(channels))}")

    if ONLY_ONLINE:
        channels = [
            c for c in channels
            if str(c.get("status", "")).lower() == "online"
        ]
        print(f"🟢 Online kanal     : {len(channels)}\n")
    else:
        print(f"📋 İşlenecek kanal  : {len(channels)}\n")

    return channels


def extract_from_html(html_text: str, base_url: str = "") -> str:
    """HTML / JS içinden stream URL çıkarır."""
    if not html_text:
        return ""

    html_text = html_text.replace("\\/", "/").replace("\\u0026", "&")

    patterns = [
        r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*',
        r'https?://[^\s"\'<>]+\.mpd[^\s"\'<>]*',
        r'(?:file|src|source|hls|stream|manifest|url)\s*[=:]\s*["\']([^"\']+)["\']',
        r'["\']([^"\']*(?:\.m3u8|\.mpd)[^"\']*)["\']',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html_text, re.IGNORECASE)
        for m in matches:
            m = m.strip().replace("\\/", "/")
            if looks_like_stream(m):
                if m.startswith("//"):
                    m = "https:" + m
                return m

    return ""


async def extract_from_js(page) -> str:
    """Sayfanın JS scope'undaki değişkenleri kontrol eder."""
    expressions = [
        "window.stream_url",
        "window.hls_url",
        "window.streamUrl",
        "window.hlsUrl",
        "window.playerSrc",
        "window.videoSrc",
        "window.source",
        "window.manifestUrl",
        "window.file",
        "window.streamFile",
        (
            "typeof jwplayer !== 'undefined' && jwplayer() ? "
            "jwplayer().getPlaylistItem()?.file : null"
        ),
        (
            "typeof videojs !== 'undefined' ? "
            "videojs.getAllPlayers()[0]?.src() : null"
        ),
        "typeof Hls !== 'undefined' ? Hls?.url : null",
        "document.querySelector('video')?.src",
        "document.querySelector('video source')?.src",
        (
            "Array.from(document.querySelectorAll('source'))"
            ".map(s => s.src).find(s => s.includes('.m3u8'))"
        ),
    ]

    for expr in expressions:
        try:
            val = await page.evaluate(expr)
            if val and isinstance(val, str) and looks_like_stream(val):
                return val
        except Exception:
            pass

    return ""


async def get_stream_url(browser, player_url: str, channel_name: str) -> str:
    """
    Playwright ile player sayfasını açar,
    ağ isteklerini dinleyerek .m3u8 / .mpd URL'sini yakalar.
    """
    stream_url = ""
    found_event = asyncio.Event()

    context = await browser.new_context(
        user_agent=HEADERS["User-Agent"],
        extra_http_headers={
            "Accept-Language": HEADERS["Accept-Language"],
            "Referer": HEADERS["Referer"],
        },
        bypass_csp=True,
        ignore_https_errors=True,
    )

    page = await context.new_page()

    # ── Ağ isteği dinleyicisi ──────────────────────────────────────────────────
    async def on_request(request):
        nonlocal stream_url
        url = request.url
        if looks_like_stream(url) and not stream_url:
            stream_url = url
            found_event.set()

    async def on_response(response):
        nonlocal stream_url
        url = response.url
        if looks_like_stream(url) and not stream_url:
            stream_url = url
            found_event.set()

    page.on("request", on_request)
    page.on("response", on_response)

    try:
        await page.goto(
            player_url,
            timeout=TIMEOUT,
            wait_until="domcontentloaded",
        )

        # Stream yakalanana kadar bekle
        try:
            await asyncio.wait_for(
                found_event.wait(),
                timeout=PAGE_WAIT / 1000
            )
        except asyncio.TimeoutError:
            pass

        # Hala bulunamadıysa HTML'den dene
        if not stream_url:
            content = await page.content()
            stream_url = extract_from_html(content, player_url)

        # Hala bulunamadıysa JS değişkenlerinden dene
        if not stream_url:
            stream_url = await extract_from_js(page)

        # Hala bulunamadıysa iframe'lere gir
        if not stream_url:
            try:
                frames = page.frames
                for frame in frames:
                    if frame.url and frame.url != player_url:
                        try:
                            fc = await frame.content()
                            found = extract_from_html(fc, frame.url)
                            if found:
                                stream_url = found
                                break
                        except Exception:
                            pass
            except Exception:
                pass

    except Exception as e:
        print(f"      ⚠️  [{channel_name}] Hata: {type(e).__name__}: {e}")
    finally:
        try:
            await page.close()
        except Exception:
            pass
        try:
            await context.close()
        except Exception:
            pass

    return stream_url


async def process_all(channels: list) -> tuple:
    """Tüm kanalları paralel olarak işler."""
    success = []
    failed = []
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    total = len(channels)
    done_count = 0
    lock = asyncio.Lock()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=BROWSER_ARGS,
            env=BROWSER_ENV,
        )

        print(f"✅ Tarayıcı başlatıldı.\n")

        async def handle(ch):
            nonlocal done_count

            name = str(ch.get("name", "?")).strip()
            player_url = str(ch.get("url", "")).strip()
            image = str(ch.get("image", "")).strip()
            group = str(ch.get("code", "GENEL")).strip().upper()

            if not player_url:
                async with lock:
                    done_count += 1
                    print(f"  ⏭️  [{done_count:03d}/{total}] {name} — URL yok")
                    failed.append({
                        "name": name,
                        "player_url": "",
                        "image": image,
                        "group": group,
                        "reason": "URL yok",
                    })
                return

            async with semaphore:
                stream_url = await get_stream_url(browser, player_url, name)

            async with lock:
                done_count += 1
                prefix = f"[{done_count:03d}/{total}]"

                if stream_url:
                    print(f"  ✅ {prefix} {name}")
                    print(f"      → {stream_url[:80]}...")
                    success.append({
                        "name": name,
                        "stream_url": stream_url,
                        "player_url": player_url,
                        "image": image,
                        "group": group,
                    })
                else:
                    print(f"  ❌ {prefix} {name} — stream bulunamadı")
                    failed.append({
                        "name": name,
                        "player_url": player_url,
                        "image": image,
                        "group": group,
                        "reason": "stream bulunamadı",
                    })

        await asyncio.gather(*[handle(ch) for ch in channels])

        try:
            await browser.close()
        except Exception:
            pass

    return success, failed


def write_m3u(items: list, output_path: str):
    """M3U dosyasını yazar."""
    turkey_tz = timezone(timedelta(hours=3))
    now = datetime.now(turkey_tz).strftime("%d.%m.%Y %H:%M:%S")

    items = sorted(items, key=lambda x: x["name"].lower())

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f"# Son guncelleme : {now} (TR)\n")
        f.write(f"# Kanal sayisi   : {len(items)}\n")
        f.write(f"# Kaynak         : cdnlivetv.is\n\n")

        for ch in items:
            name = ch["name"]
            logo = ch.get("image", "")
            group = ch.get("group", "GENEL")
            stream = ch["stream_url"]

            extinf = f'#EXTINF:-1 tvg-name="{name}"'
            if logo:
                extinf += f' tvg-logo="{logo}"'
            if group:
                extinf += f' group-title="{group}"'
            extinf += f',{name}'

            f.write(extinf + "\n")
            f.write(stream + "\n\n")


def print_report(channels: list, success: list, failed: list):
    turkey_tz = timezone(timedelta(hours=3))
    now = datetime.now(turkey_tz).strftime("%d.%m.%Y %H:%M:%S")

    print(f"\n{'═'*65}")
    print(f"📊 SONUÇ RAPORU")
    print(f"{'═'*65}")
    print(f"  📺 İşlenen kanal    : {len(channels)}")
    print(f"  ✅ M3U'ya eklenen   : {len(success)}")
    print(f"  ❌ Bulunamayan      : {len(failed)}")
    print(f"  📁 M3U dosyası      : {OUTPUT_FILE}")
    print(f"  📁 Debug dosyası    : {DEBUG_FILE}")
    print(f"  🕐 Güncelleme       : {now}")
    print(f"{'═'*65}\n")

    # Grup istatistiği
    if success:
        groups: dict = {}
        for ch in success:
            g = ch.get("group", "GENEL")
            groups[g] = groups.get(g, 0) + 1

        print("📂 Ülke / Kategori bazında:")
        for g, count in sorted(groups.items(), key=lambda x: -x[1]):
            bar = "█" * min(count, 30)
            print(f"   {g:<20}: {count:>4} kanal  {bar}")
        print()


async def main():
    print("═" * 65)
    print("   📺 CDN LIVE TV — M3U PLAYLIST OLUŞTURUCU (Playwright)")
    print("═" * 65 + "\n")

    # Kanalları yükle
    try:
        channels = load_channels()
    except Exception as e:
        print(f"❌ API okunamadı: {e}")
        Path(OUTPUT_FILE).write_text("#EXTM3U\n", encoding="utf-8")
        return

    if not channels:
        print("⚠️  İşlenecek kanal bulunamadı.")
        Path(OUTPUT_FILE).write_text("#EXTM3U\n", encoding="utf-8")
        return

    print(f"{'═'*65}")
    print(f"🎭 Playwright Chromium başlatılıyor...")
    print(f"⚡ Eşzamanlı sayfa  : {MAX_CONCURRENT}")
    print(f"⏱️  Sayfa bekleme   : {PAGE_WAIT / 1000}s")
    print(f"⏱️  Timeout         : {TIMEOUT / 1000}s")
    print(f"{'═'*65}\n")

    # Tüm kanalları işle
    success, failed = await process_all(channels)

    # M3U yaz
    write_m3u(success, OUTPUT_FILE)

    # Debug dosyası yaz
    with open(DEBUG_FILE, "w", encoding="utf-8") as f:
        json.dump(failed, f, ensure_ascii=False, indent=2)

    # Rapor
    print_report(channels, success, failed)

    if len(success) == 0:
        print("⚠️  Hiç stream URL çıkarılamadı!")
        print(f"💡 {DEBUG_FILE} dosyasına bakın.\n")
    else:
        print(f"✅ {OUTPUT_FILE} başarıyla oluşturuldu! ({len(success)} kanal)\n")


if __name__ == "__main__":
    asyncio.run(main())
