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


# ─── HIZ VE PERFORMANS AYARLARI ───────────────────────────────────────────────
API_URL = "https://api.cdnlivetv.is/api/v1/channels/?user=cdnlivetv&plan=free"
OUTPUT_FILE = "cdnlive.m3u"
DEBUG_FILE = "debug_failed.json"

TIMEOUT = 12000                 # Sayfa yükleme timeout (12s)
FIRST_WAIT = 2.0                # İlk yükleme bekleme süresi (sn)
RELOAD_WAIT = 4.0               # Yenileme sonrası bekleme süresi (sn)
MAX_RELOADS = 1                 # Bulunamazsa en fazla 1 kez yenile
MAX_CONCURRENT = 6              # Eşzamanlı sekme sayısı (Hızlı tarama için)
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

# Engellenecek gereksiz kaynak türleri (Hızlandırma için)
BLOCKED_RESOURCE_TYPES = {"image", "media", "font", "stylesheet"}

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


def get_channel_slug(player_url: str, code: str) -> str:
    """Kanalın sistemdeki benzersiz ID/Slug değerini çözer."""
    if code and len(code) > 1 and not code.isdigit():
        return code.lower().strip()
    
    if player_url:
        match = re.search(r'(?:id|ch|v|name)=([^&?#]+)', player_url, re.IGNORECASE)
        if match:
            return match.group(1).strip().lower()
        
        path = player_url.split('?')[0].split('#')[0]
        parts = [p for p in path.split('/') if p]
        if parts:
            last = parts[-1]
            if last and not last.endswith('.php') and not last.endswith('.html'):
                return last.lower().strip()
    return ""


def learn_stream_template(success_list: list) -> str:
    """
    Bulunan başarılı yayınlardan Token ve URL Şablonu üretir.
    Örnek çıktı: "https://sunucu.com/live/{id}.m3u8?token=12345"
    """
    for ch in success_list:
        stream_url = ch.get("stream_url", "")
        player_url = ch.get("player_url", "")
        code = ch.get("code", "")
        
        slug = get_channel_slug(player_url, code)
        if slug and slug in stream_url:
            # Kanal ID'sini şablon değişkeni {id} ile değiştiriyoruz
            template = stream_url.replace(slug, "{id}")
            if "{id}" in template:
                return template
    return ""


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
        "typeof jwplayer !== 'undefined' && jwplayer() ? jwplayer().getPlaylistItem()?.file : null",
        "typeof videojs !== 'undefined' ? videojs.getAllPlayers()[0]?.src() : null",
        "typeof Hls !== 'undefined' ? Hls?.url : null",
        "document.querySelector('video')?.src",
        "document.querySelector('video source')?.src",
    ]

    for expr in expressions:
        try:
            val = await page.evaluate(expr)
            if val and isinstance(val, str) and looks_like_stream(val):
                return val
        except Exception:
            pass

    return ""


async def try_trigger_play(page):
    try:
        await page.evaluate("""
            () => {
                document.querySelectorAll('video').forEach(v => {
                    try { v.muted = true; v.play(); } catch(e) {}
                });
                const btns = document.querySelectorAll('.jw-icon-display, .vjs-big-play-button, button[aria-label*="play" i], .play-button');
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
            viewport={"width": 800, "height": 600},
        )

        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

        page = await context.new_page()

        async def route_filter(route):
            req = route.request
            if looks_like_stream(req.url):
                await route.continue_()
            elif req.resource_type in BLOCKED_RESOURCE_TYPES:
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", route_filter)

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
            await page.goto(player_url, timeout=TIMEOUT, wait_until="domcontentloaded")
        except Exception:
            pass

        try:
            await asyncio.wait_for(found_event.wait(), timeout=FIRST_WAIT)
        except asyncio.TimeoutError:
            pass

        if not stream_url and MAX_RELOADS > 0:
            await try_trigger_play(page)
            try:
                await page.reload(timeout=TIMEOUT, wait_until="domcontentloaded")
                await asyncio.wait_for(found_event.wait(), timeout=RELOAD_WAIT)
            except Exception:
                pass

        if not stream_url:
            stream_url = await extract_from_js(page)

        if not stream_url:
            try:
                content = await page.content()
                stream_url = extract_from_html(content, player_url)
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
            code = str(ch.get("code", "")).strip()
            group = str(ch.get("group", "GENEL")).strip().upper()

            if not player_url:
                async with lock:
                    done_count += 1
                    failed.append({
                        "name": name, "player_url": "", "image": image,
                        "group": group, "code": code, "reason": "URL yok"
                    })
                return

            async with semaphore:
                stream_url = await get_stream_url(browser, player_url, name)

            async with lock:
                done_count += 1
                prefix = f"[{done_count:03d}/{total}]"

                if stream_url:
                    print(f"  ✅ {prefix} {name} → {stream_url[:60]}...")
                    success.append({
                        "name": name,
                        "stream_url": stream_url,
                        "player_url": player_url,
                        "image": image,
                        "group": group,
                        "code": code,
                    })
                else:
                    print(f"  ❌ {prefix} {name} (Playwright ile bulunamadı, beklemeye alındı)")
                    failed.append({
                        "name": name,
                        "player_url": player_url,
                        "image": image,
                        "group": group,
                        "code": code,
                        "reason": "stream bulunamadı",
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

            # Klonlanan kanalları ayırt etmek isterseniz isminin yanına küçük bir işaret koyabilirsiniz.
            # Örneğin: if ch.get("cloned"): name += " 🔄"

            extinf = f'#EXTINF:-1 tvg-name="{name}"'
            if logo:
                extinf += f' tvg-logo="{logo}"'
            if group:
                extinf += f' group-title="{group}"'
            extinf += f',{name}'

            f.write(extinf + "\n")
            f.write(stream + "\n\n")


def print_report(channels: list, success: list, failed: list, cloned_count: int):
    turkey_tz = timezone(timedelta(hours=3))
    now = datetime.now(turkey_tz).strftime("%d.%m.%Y %H:%M:%S")

    print(f"\n{'═'*65}")
    print(f"📊 SONUÇ RAPORU")
    print(f"{'═'*65}")
    print(f"  📺 Toplam kanal           : {len(channels)}")
    print(f"  ✅ Direkt bulunan (Web)   : {len(success) - cloned_count}")
    print(f"  🔄 Token ile klonlanan    : {cloned_count}")
    print(f"  🎉 Toplam eklenen (M3U)   : {len(success)}")
    print(f"  ❌ Gerçekten bulunamayan  : {len(failed)}")
    print(f"  📁 M3U dosyası            : {OUTPUT_FILE}")
    print(f"  🕐 Güncelleme             : {now}")
    print(f"{'═'*65}\n")


async def main():
    print("═" * 65)
    print("   📺 CDN LIVE TV — AKILLI VE HIZLI PLAYLIST OLUŞTURUCU")
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

    print(f"⚡ Eşzamanlı Sekme  : {MAX_CONCURRENT}")
    print(f"⚡ Performans Modu  : Aktif (Görseller ve CSS yüklenmiyor)")
    print(f"🔑 Akıllı Kurtarma  : Aktif (Token klonlama devrede)\n")

    success, failed = await process_all(channels)

    # ── KEY DETECT & FALLBACK RECONSTRUCTION (TOKEN KLONLAMA) ────────────────
    cloned_count = 0
    template = learn_stream_template(success)

    if template and failed:
        print(f"\n🔑 Token ve Şablon Çözüldü: {template[:90]}...")
        print(f"🔄 Bulunamayan {len(failed)} kanal şablon kullanılarak kurtarılıyor...")
        
        still_failed = []
        for ch in failed:
            slug = get_channel_slug(ch.get("player_url", ""), ch.get("code", ""))
            if slug:
                fallback_stream = template.replace("{id}", slug)
                ch["stream_url"] = fallback_stream
                ch["cloned"] = True
                success.append(ch)
                cloned_count += 1
            else:
                still_failed.append(ch)
        failed = still_failed

    # ──────────────────────────────────────────────────────────────────────────

    write_m3u(success, OUTPUT_FILE)

    with open(DEBUG_FILE, "w", encoding="utf-8") as f:
        json.dump(failed, f, ensure_ascii=False, indent=2)

    print_report(channels, success, failed, cloned_count)
    print(f"✅ Başarıyla tamamlandı! ({len(success)} kanal M3U listesine eklendi.)\n")


if __name__ == "__main__":
    asyncio.run(main())
