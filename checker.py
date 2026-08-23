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
from playwright.async_api import async_playwright, Error as PlaywrightError


# ─── AYARLAR ──────────────────────────────────────────────────────────────────
API_URL = "https://api.cdnlivetv.is/api/v1/channels/?user=cdnlivetv&plan=free"
OUTPUT_FILE = "cdnlive.m3u"
DEBUG_FILE = "debug_failed.json"

TIMEOUT = 15000                 # Sayfa yükleme zaman aşımı (15s)
FIRST_WAIT = 3.0                # İlk yüklemede akış bekleme süresi (sn)
RELOAD_WAIT = 4.5               # Yenileme sonrası bekleme süresi (sn)
MAX_CONCURRENT = 4              # Eşzamanlı sekme sayısı
ONLY_ONLINE = False             # Tüm kanalları tara

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
    "--mute-audio",
    "--ignore-certificate-errors",
    "--ignore-ssl-errors",
    "--disable-extensions",
    "--disable-background-networking",
    "--hide-scrollbars",
    "--autoplay-policy=no-user-gesture-required",
    "--disable-blink-features=AutomationControlled",
]

BLOCKED_RESOURCE_TYPES = {"image", "media", "font"}

# ──────────────────────────────────────────────────────────────────────────────


def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.3,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update(HEADERS)
    return s


def is_valid_stream_url(url: str) -> bool:
    """
    URL'nin gerçekten geçerli bir medya akış adresi (.m3u8 / .mpd) olup olmadığını
    kesin kurallarla doğrular. JS kodlarını ve çöp metinleri reddeder.
    """
    if not url or not isinstance(url, str):
        return False

    url = url.strip()

    # 1. Mutlaka http veya https ile başlamalı
    if not (url.startswith("http://") or url.startswith("https://")):
        return False

    # 2. İçinde JS kod parçacıkları, parantezler, HTML karakterleri olamaz
    invalid_chars = [
        " ", "{", "}", "<", ">", '"', "'", "`", ";", "(", ")",
        "\\", "\n", "\r", "\t", "&&", "||", "import", "function"
    ]
    if any(c in url for c in invalid_chars):
        return False

    # 3. Kütüphane / JS bundle / web worker adları olamaz
    junk_keywords = ["parser", "bundle", "webpack", "chunk", "worker", "player.min"]
    url_lower = url.lower()
    if any(k in url_lower for k in junk_keywords):
        return False

    # 4. Temiz path kısmında .m3u8 veya .mpd uzantısı bulunmalı
    base_path = url.split("?")[0].lower()
    if not (".m3u8" in base_path or ".mpd" in base_path):
        return False

    return True


def load_channels() -> list:
    print(f"🌐 API'den kanallar çekiliyor...")
    print(f"   {API_URL}\n")

    session = make_session()
    r = session.get(API_URL, timeout=20)
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
        print(f"📋 İşlenecek kanal  : {len(channels)} (Tümü)\n")

    return channels


def extract_from_html(html_text: str, base_url: str = "") -> str:
    """HTML veya metin içinden sadece geçerli HTTP URL'lerini ayıklar."""
    if not html_text:
        return ""

    html_text = html_text.replace("\\/", "/").replace("\\u0026", "&")

    # Yalnızca geçerli URL yapısını yakalayan sıkı Regex
    pattern = r'https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&*+,;=%]+\.(?:m3u8|mpd)(?:\?[a-zA-Z0-9\-._~:/?#\[\]@!$&*+,;=%]*)?'

    matches = re.findall(pattern, html_text, re.IGNORECASE)
    for m in matches:
        if is_valid_stream_url(m):
            return m

    return ""


async def extract_from_js(page) -> str:
    """Sadece doğrudan video oynatıcı nesnelerinin src değerlerini kontrol eder."""
    try:
        val = await page.evaluate("""
            () => {
                // 1. JWPlayer kontrolü
                try {
                    if (typeof jwplayer !== 'undefined' && jwplayer().getPlaylistItem) {
                        const f = jwplayer().getPlaylistItem()?.file;
                        if (f && typeof f === 'string' && f.startsWith('http')) return f;
                    }
                } catch(e){}

                // 2. VideoJS kontrolü
                try {
                    if (typeof videojs !== 'undefined') {
                        const players = videojs.getAllPlayers();
                        for (let p of players) {
                            const src = p.currentSrc ? p.currentSrc() : (p.src ? p.src() : null);
                            if (src && typeof src === 'string' && src.startsWith('http')) return src;
                        }
                    }
                } catch(e){}

                // 3. Hls.js kontrolü
                try {
                    if (typeof Hls !== 'undefined' && Hls.url && Hls.url.startsWith('http')) return Hls.url;
                } catch(e){}

                // 4. Standart HTML5 Video Elementi
                const v = document.querySelector('video');
                if (v && v.src && v.src.startsWith('http')) return v.src;

                // 5. Source Elementi
                const s = document.querySelector('video source');
                if (s && s.src && s.src.startsWith('http')) return s.src;

                return null;
            }
        """)
        if val and is_valid_stream_url(val):
            return val
    except Exception:
        pass

    return ""


async def try_trigger_play(page):
    """Oynatıcıyı ve token oluşturmayı tetiklemek için sayfaya tıklar."""
    try:
        await page.mouse.click(200, 200)
    except Exception:
        pass

    try:
        await page.evaluate("""
            () => {
                document.querySelectorAll('video').forEach(v => {
                    try { v.muted = true; v.play(); } catch(e) {}
                });
                const btns = document.querySelectorAll(
                    '.jw-icon-display, .vjs-big-play-button, button[aria-label*="play" i], .play-button, #play'
                );
                btns.forEach(b => { try { b.click(); } catch(e) {} });
            }
        """)
    except Exception:
        pass


async def get_stream_url(browser, player_url: str, channel_name: str) -> str:
    stream_url = ""
    found_event = asyncio.Event()

    if not browser.is_connected():
        return ""

    context = None
    page = None

    try:
        context = await browser.new_context(
            user_agent=HEADERS["User-Agent"],
            extra_http_headers={
                "Accept-Language": HEADERS["Accept-Language"],
                "Referer": HEADERS["Referer"],
            },
            bypass_csp=True,
            ignore_https_errors=True,
            viewport={"width": 1280, "height": 720},
        )

        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

        page = await context.new_page()

        # Kaynak filtreleme (Görsel ve gereksiz medya isteklerini kes)
        async def route_filter(route):
            req = route.request
            if is_valid_stream_url(req.url):
                await route.continue_()
            elif req.resource_type in BLOCKED_RESOURCE_TYPES:
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", route_filter)

        # ── Ağ İstek Dinleyicileri ──
        async def on_request(request):
            nonlocal stream_url
            url = request.url
            if not stream_url and is_valid_stream_url(url):
                stream_url = url
                found_event.set()

        async def on_response(response):
            nonlocal stream_url
            if stream_url:
                return

            url = response.url
            if is_valid_stream_url(url):
                stream_url = url
                found_event.set()
                return

            # SADECE gerçek JSON API yanıtlarını tara (JS kodlarını ASLA metin olarak tarama!)
            ct = response.headers.get("content-type", "").lower()
            if "application/json" in ct:
                try:
                    text = await response.text()
                    if ".m3u8" in text or ".mpd" in text:
                        found = extract_from_html(text, url)
                        if found and is_valid_stream_url(found):
                            stream_url = found
                            found_event.set()
                except Exception:
                    pass

        page.on("request", on_request)
        page.on("response", on_response)

        # ── 1. İlk Yükleme ──
        try:
            await page.goto(player_url, timeout=TIMEOUT, wait_until="domcontentloaded")
        except Exception:
            pass

        try:
            await asyncio.wait_for(found_event.wait(), timeout=FIRST_WAIT)
        except asyncio.TimeoutError:
            pass

        # ── 2. Bulunamadıysa Sayfa Yenileme (Refresh & Token Alma) ──
        if not stream_url:
            await try_trigger_play(page)
            try:
                await page.reload(timeout=TIMEOUT, wait_until="domcontentloaded")
                await try_trigger_play(page)
                await asyncio.wait_for(found_event.wait(), timeout=RELOAD_WAIT)
            except Exception:
                pass

        # ── 3. DOM & JS Oynatıcı Nesnelerinden Ara ──
        if not stream_url:
            stream_url = await extract_from_js(page)

        # ── 4. HTML Kaynağından Ara ──
        if not stream_url:
            try:
                content = await page.content()
                found = extract_from_html(content, player_url)
                if is_valid_stream_url(found):
                    stream_url = found
            except Exception:
                pass

        # ── 5. Iframe'leri Tara ──
        if not stream_url:
            try:
                for frame in page.frames:
                    if frame.url and frame.url != player_url:
                        try:
                            fc = await frame.content()
                            found = extract_from_html(fc, frame.url)
                            if is_valid_stream_url(found):
                                stream_url = found
                                break
                        except Exception:
                            pass
            except Exception:
                pass

    except Exception:
        pass
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass
        if context:
            try:
                await context.close()
            except Exception:
                pass

    return stream_url if is_valid_stream_url(stream_url) else ""


async def process_all(channels: list) -> tuple:
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
        )

        async def handle(ch):
            nonlocal done_count

            name = str(ch.get("name", "?")).strip()
            player_url = str(ch.get("url", "")).strip()
            image = str(ch.get("image", "")).strip()
            group = str(ch.get("code", "GENEL")).strip().upper()

            if not player_url:
                async with lock:
                    done_count += 1
                    failed.append({
                        "name": name, "player_url": "", "image": image,
                        "group": group, "reason": "URL yok"
                    })
                return

            async with semaphore:
                stream_url = await get_stream_url(browser, player_url, name)

            async with lock:
                done_count += 1
                prefix = f"[{done_count:03d}/{total}]"

                if stream_url and is_valid_stream_url(stream_url):
                    print(f"  ✅ {prefix} {name} → {stream_url[:65]}...")
                    success.append({
                        "name": name,
                        "stream_url": stream_url,
                        "player_url": player_url,
                        "image": image,
                        "group": group,
                    })
                else:
                    print(f"  ❌ {prefix} {name} (Kanal kapalı / Token alınamadı)")
                    failed.append({
                        "name": name,
                        "player_url": player_url,
                        "image": image,
                        "group": group,
                        "reason": "Geçerli stream URL bulunamadı",
                    })

        await asyncio.gather(*[handle(ch) for ch in channels], return_exceptions=True)

        try:
            await browser.close()
        except Exception:
            pass

    return success, failed


def write_m3u(items: list, output_path: str):
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
    print(f"  📺 Taranan kanal sayısı  : {len(channels)}")
    print(f"  ✅ Geçerli akış (M3U)    : {len(success)}")
    print(f"  ❌ Başarısız / Kapalı    : {len(failed)}")
    print(f"  📁 M3U dosyası           : {OUTPUT_FILE}")
    print(f"  🕐 Güncelleme            : {now}")
    print(f"{'═'*65}\n")


async def main():
    print("═" * 65)
    print("   📺 CDN LIVE TV — TEMİZ VE GÜVENİLİR M3U OLUŞTURUCU")
    print("═" * 65 + "\n")

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

    print(f"⚡ Eşzamanlı Sekme : {MAX_CONCURRENT}")
    print(f"🛡️  URL Doğrulayıcı : Aktif (Sadece gerçek .m3u8/.mpd linkleri alınır)\n")

    success, failed = await process_all(channels)

    write_m3u(success, OUTPUT_FILE)

    with open(DEBUG_FILE, "w", encoding="utf-8") as f:
        json.dump(failed, f, ensure_ascii=False, indent=2)

    print_report(channels, success, failed)
    print(f"✅ İşlem tamamlandı! Toplam {len(success)} geçerli kanal eklendi.\n")


if __name__ == "__main__":
    asyncio.run(main())
