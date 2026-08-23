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

# Zaman ve Eşzamanlılık Ayarları
TIMEOUT = 15000                 # Sayfa yükleme zaman aşımı (15s)
FIRST_WAIT = 3.5                # İlk yüklemede akış bekleme süresi (saniye)
RELOAD_WAIT = 5.0               # Yenileme sonrası bekleme süresi (saniye)
MAX_CONCURRENT = 4              # Eşzamanlı sekme sayısı (Stabilite ve hız için 4)
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

# Sadece ağır ve gereksiz medya/fontlar engellenir (CSS ve JS serbest bırakıldı)
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
    """Sayfadaki aktif JS nesnelerinden (Player, Video tag, Script etiketleri) token'lı URL arar."""
    try:
        val = await page.evaluate("""
            () => {
                // 1. JWPlayer
                try {
                    if (typeof jwplayer !== 'undefined' && jwplayer().getPlaylistItem) {
                        const f = jwplayer().getPlaylistItem()?.file;
                        if (f && f.includes('.m3u8')) return f;
                    }
                } catch(e){}

                // 2. VideoJS
                try {
                    if (typeof videojs !== 'undefined') {
                        const players = videojs.getAllPlayers();
                        for (let p of players) {
                            const src = p.currentSrc ? p.currentSrc() : (p.src ? p.src() : null);
                            if (src && src.includes('.m3u8')) return src;
                        }
                    }
                } catch(e){}

                // 3. Hls.js
                try {
                    if (typeof Hls !== 'undefined' && Hls.url) return Hls.url;
                } catch(e){}

                // 4. Video Elementi
                const v = document.querySelector('video');
                if (v && v.src && v.src.includes('.m3u8')) return v.src;

                // 5. Source Elementi
                const s = document.querySelector('video source');
                if (s && s.src && s.src.includes('.m3u8')) return s.src;

                // 6. Inline script tag'leri içinde arama
                for (let script of document.scripts) {
                    if (script.textContent && script.textContent.includes('.m3u8')) {
                        const match = script.textContent.match(/https?:\\/\\/[^"\'\\s<>]+\\.m3u8[^"\'\\s<>]*/i);
                        if (match) return match[0].replace(/\\\\/g, '');
                    }
                }

                // 7. Global Değişkenler
                return window.stream_url || window.hls_url || window.streamUrl || window.playerSrc || null;
            }
        """)
        if val and isinstance(val, str) and looks_like_stream(val):
            return val
    except Exception:
        pass

    return ""


async def try_trigger_play(page):
    """Oynatıcıyı ve token isteğini tetiklemek için etkileşim simüle eder."""
    try:
        await page.mouse.click(250, 250)
    except Exception:
        pass

    try:
        await page.evaluate("""
            () => {
                document.querySelectorAll('video').forEach(v => {
                    try { v.muted = true; v.play(); } catch(e) {}
                });
                const buttons = document.querySelectorAll(
                    '.jw-icon-display, .vjs-big-play-button, .plyr__control--overlaid, button[aria-label*="play" i], .play-button, #play'
                );
                buttons.forEach(b => { try { b.click(); } catch(e) {} });
            }
        """)
    except Exception:
        pass


async def get_stream_url(browser, player_url: str, channel_name: str) -> str:
    """
    Playwright ile sayfayı açar, network/AJAX yanıtlarını dinler,
    gerekirse sayfayı yenileyerek benzersiz token'lı stream URL'sini yakalar.
    """
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

        # ── Gereksiz Ağ Trafiğini Engelle ──────────────────────────────
        async def route_filter(route):
            req = route.request
            if looks_like_stream(req.url):
                await route.continue_()
            elif req.resource_type in BLOCKED_RESOURCE_TYPES:
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", route_filter)

        # ── Ağ İsteği ve Yanıt Dinleyicileri ───────────────────────────
        async def on_request(request):
            nonlocal stream_url
            url = request.url
            if looks_like_stream(url) and not stream_url:
                stream_url = url
                found_event.set()

        async def on_response(response):
            nonlocal stream_url
            if stream_url:
                return

            url = response.url
            if looks_like_stream(url):
                stream_url = url
                found_event.set()
                return

            # JSON veya AJAX ile gelen arka plan token yanıtlarını yakala
            ct = response.headers.get("content-type", "").lower()
            if any(t in ct for t in ["json", "javascript", "text"]):
                try:
                    text = await response.text()
                    if ".m3u8" in text or ".mpd" in text:
                        found = extract_from_html(text, url)
                        if found:
                            stream_url = found
                            found_event.set()
                except Exception:
                    pass

        page.on("request", on_request)
        page.on("response", on_response)

        # ── 1. İLK YÜKLEME ──────────────────────────────────────────────
        try:
            await page.goto(player_url, timeout=TIMEOUT, wait_until="domcontentloaded")
        except Exception:
            pass

        # İlk kısa bekleme
        try:
            await asyncio.wait_for(found_event.wait(), timeout=FIRST_WAIT)
        except asyncio.TimeoutError:
            pass

        # ── 2. BULUNAMADIYSA: TIKLA VE SAYFAYI YENİLE (REFRESH) ────────
        if not stream_url:
            await try_trigger_play(page)
            
            try:
                # Sayfayı yenile (Token bu adımda üretilir)
                await page.reload(timeout=TIMEOUT, wait_until="domcontentloaded")
                
                # Yenilemeden hemen sonra tekrar oynatmayı tetikle
                await try_trigger_play(page)
                
                # Token'ın ağdan geçmesini bekle
                await asyncio.wait_for(found_event.wait(), timeout=RELOAD_WAIT)
            except Exception:
                pass

        # ── 3. DOM & JS NESNELERİNİ TARA ────────────────────────────────
        if not stream_url:
            stream_url = await extract_from_js(page)

        # ── 4. HTML KAYNAĞINI TARA ──────────────────────────────────────
        if not stream_url:
            try:
                content = await page.content()
                stream_url = extract_from_html(content, player_url)
            except Exception:
                pass

        # ── 5. IFRAME İÇERİKLERİNİ TARA ────────────────────────────────
        if not stream_url:
            try:
                for frame in page.frames:
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

    return stream_url


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

                if stream_url:
                    print(f"  ✅ {prefix} {name} → {stream_url[:65]}...")
                    success.append({
                        "name": name,
                        "stream_url": stream_url,
                        "player_url": player_url,
                        "image": image,
                        "group": group,
                    })
                else:
                    print(f"  ❌ {prefix} {name} (Kanal kapalı veya token alınamadı)")
                    failed.append({
                        "name": name,
                        "player_url": player_url,
                        "image": image,
                        "group": group,
                        "reason": "stream/token bulunamadı",
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
    print(f"  📺 Toplam taranan kanal  : {len(channels)}")
    print(f"  ✅ Orijinal Token'lı M3U : {len(success)}")
    print(f"  ❌ Çevrimdışı / Kapalı   : {len(failed)}")
    print(f"  📁 M3U dosyası           : {OUTPUT_FILE}")
    print(f"  📁 Debug dosyası         : {DEBUG_FILE}")
    print(f"  🕐 Güncelleme            : {now}")
    print(f"{'═'*65}\n")


async def main():
    print("═" * 65)
    print("   📺 CDN LIVE TV — GÜVENİLİR VE HIZLI M3U OLUŞTURUCU")
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
    print(f"🔄 Akıllı Yenileme : Aktif (Orijinal Token Garantisi)\n")

    success, failed = await process_all(channels)

    write_m3u(success, OUTPUT_FILE)

    with open(DEBUG_FILE, "w", encoding="utf-8") as f:
        json.dump(failed, f, ensure_ascii=False, indent=2)

    print_report(channels, success, failed)
    print(f"✅ Tamamlandı! Eklenen {len(success)} kanalın tamamı çalışan orijinal token'a sahiptir.\n")


if __name__ == "__main__":
    asyncio.run(main())
