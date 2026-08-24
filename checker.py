#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re
import asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests
from playwright.async_api import async_playwright, Error as PlaywrightError


# ─── KULLANICI KANAL LİSTESİ ──────────────────────────────────────────────────
KANALLAR = [
    {
        "name": "BeinSports1",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20SPORTS%201&code=tr&user=cdnlivetv&plan=free",
        "image": "https://img-s-msn-com.akamaized.net/tenant/amp/entityid/AA1pt7gT.img",
        "group": "Turkey"
    },
    {
        "name": "BeinSports2",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20SPORTS%202&code=tr&user=cdnlivetv&plan=free",
        "image": "",
        "group": "Turkey"
    },
    {
        "name": "BeinSports3",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20SPORTS%203&code=tr&user=cdnlivetv&plan=free",
        "image": "",
        "group": "Turkey"
    },
    {
        "name": "BeinSports4",
        "url": "https://cdnlivetv.tv/api/v1/channels/player/?name=beIN%20SPORTS%204&code=tr&user=cdnlivetv&plan=free",
        "image": "",
        "group": "Turkey"
    }
    # Yeni kanalları yukarıdaki şablona göre buraya ekleyebilirsiniz.
]

# ─── SİSTEM AYARLARI ──────────────────────────────────────────────────────────
OUTPUT_DIR_NAME = "cdnlive"     # Klasör adı
DEBUG_FILE = "debug_failed.json"

TIMEOUT = 15000                 # Sayfa yükleme zaman aşımı (15s)
FIRST_WAIT = 3.0                # İlk yüklemede akış bekleme süresi (sn)
RELOAD_WAIT = 4.5               # Yenileme sonrası bekleme süresi (sn)
MAX_CONCURRENT = 4              # Eşzamanlı sekme sayısı

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


def is_valid_stream_url(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False

    url = url.strip()

    if not (url.startswith("http://") or url.startswith("https://")):
        return False

    invalid_chars = [
        " ", "{", "}", "<", ">", '"', "'", "`", ";", "(", ")",
        "\\", "\n", "\r", "\t", "&&", "||", "import", "function"
    ]
    if any(c in url for c in invalid_chars):
        return False

    junk_keywords = ["parser", "bundle", "webpack", "chunk", "worker", "player.min"]
    url_lower = url.lower()
    if any(k in url_lower for k in junk_keywords):
        return False

    base_path = url.split("?")[0].lower()
    if not (".m3u8" in base_path or ".mpd" in base_path):
        return False

    return True


def sanitize_filename(name: str) -> str:
    """Dosya adlarında hata yaratabilecek geçersiz karakterleri temizler."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


def extract_from_html(html_text: str, base_url: str = "") -> str:
    if not html_text:
        return ""

    html_text = html_text.replace("\\/", "/").replace("\\u0026", "&")

    pattern = r'https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&*+,;=%]+\.(?:m3u8|mpd)(?:\?[a-zA-Z0-9\-._~:/?#\[\]@!$&*+,;=%]*)?'

    matches = re.findall(pattern, html_text, re.IGNORECASE)
    for m in matches:
        if is_valid_stream_url(m):
            return m

    return ""


async def extract_from_js(page) -> str:
    try:
        val = await page.evaluate("""
            () => {
                try {
                    if (typeof jwplayer !== 'undefined' && jwplayer().getPlaylistItem) {
                        const f = jwplayer().getPlaylistItem()?.file;
                        if (f && typeof f === 'string' && f.startsWith('http')) return f;
                    }
                } catch(e){}

                try {
                    if (typeof videojs !== 'undefined') {
                        const players = videojs.getAllPlayers();
                        for (let p of players) {
                            const src = p.currentSrc ? p.currentSrc() : (p.src ? p.src() : null);
                            if (src && typeof src === 'string' && src.startsWith('http')) return src;
                        }
                    }
                } catch(e){}

                try {
                    if (typeof Hls !== 'undefined' && Hls.url && Hls.url.startsWith('http')) return Hls.url;
                } catch(e){}

                const v = document.querySelector('video');
                if (v && v.src && v.src.startsWith('http')) return v.src;

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

        async def route_filter(route):
            req = route.request
            if is_valid_stream_url(req.url):
                await route.continue_()
            elif req.resource_type in BLOCKED_RESOURCE_TYPES:
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", route_filter)

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

        try:
            await page.goto(player_url, timeout=TIMEOUT, wait_until="domcontentloaded")
        except Exception:
            pass

        try:
            await asyncio.wait_for(found_event.wait(), timeout=FIRST_WAIT)
        except asyncio.TimeoutError:
            pass

        if not stream_url:
            await try_trigger_play(page)
            try:
                await page.reload(timeout=TIMEOUT, wait_until="domcontentloaded")
                await try_trigger_play(page)
                await asyncio.wait_for(found_event.wait(), timeout=RELOAD_WAIT)
            except Exception:
                pass

        if not stream_url:
            stream_url = await extract_from_js(page)

        if not stream_url:
            try:
                content = await page.content()
                found = extract_from_html(content, player_url)
                if is_valid_stream_url(found):
                    stream_url = found
            except Exception:
                pass

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
            group = str(ch.get("group", "GENEL")).strip().upper()

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
                    print(f"  ❌ {prefix} {name} (Başarısız / Token Alınamadı)")
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


def write_individual_m3u8(items: list, output_dir_name: str):
    """Bulunan her kanal için cdnlive klasörü altında ayrı bir .m3u8 dosyası oluşturur."""
    # Projenin çalıştığı ana dizini baz alarak mutlak (absolute) yol oluşturuyoruz.
    base_path = Path(__file__).parent.resolve()
    target_dir = base_path / output_dir_name
    
    # Klasörü kesin olarak oluştur
    target_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📂 Yazma İşlemi Başlatıldı (Klasör: {target_dir})")

    if not items:
        print("   ⚠️ Yazılacak başarılı kanal bulunamadı.")
        return

    for ch in items:
        name = ch["name"]
        stream = ch["stream_url"]
        logo = ch.get("image", "")
        group = ch.get("group", "GENEL")

        # Güvenli dosya adı
        safe_name = sanitize_filename(name)
        file_path = target_dir / f"{safe_name}.m3u8"

        # M3U8 içeriğini oluşturup dosyaya kaydet
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                extinf = f'#EXTINF:-1 tvg-name="{name}"'
                if logo:
                    extinf += f' tvg-logo="{logo}"'
                if group:
                    extinf += f' group-title="{group}"'
                extinf += f',{name}\n'
                
                f.write(extinf)
                f.write(stream + "\n")
            print(f"   💾 Yazıldı: {file_path.name}")
        except Exception as e:
            print(f"   ❌ Dosya yazma hatası ({name}): {e}")


def print_report(channels: list, success: list, failed: list):
    turkey_tz = timezone(timedelta(hours=3))
    now = datetime.now(turkey_tz).strftime("%d.%m.%Y %H:%M:%S")

    print(f"\n{'═'*65}")
    print(f"📊 SONUÇ RAPORU")
    print(f"{'═'*65}")
    print(f"  📺 Girilen kanal sayısı  : {len(channels)}")
    print(f"  ✅ Başarıyla çözülen     : {len(success)}")
    print(f"  ❌ Başarısız olan        : {len(failed)}")
    print(f"  📁 Çıktı Klasör Yolu     : ./{OUTPUT_DIR_NAME}/")
    print(f"  🕐 Güncelleme zamanı     : {now}")
    print(f"{'═'*65}\n")


async def main():
    print("═" * 65)
    print("   📺 ÖZEL LİSTE — ÇOKLU KANAL AYRI DOSYA KAYDEDİCİ")
    print("═" * 65 + "\n")

    if not KANALLAR:
        print("⚠️  Lütfen 'KANALLAR' listesine en az bir kanal ekleyin.")
        return

    print(f"📋 İşlenecek kanal sayısı: {len(KANALLAR)}")
    print(f"⚡ Eşzamanlı Sekme       : {MAX_CONCURRENT}")
    print(f"📁 Klasör Hedefi         : ./{OUTPUT_DIR_NAME}/\n")

    success, failed = await process_all(KANALLAR)

    # Kanalları ayrı dosyalar halinde yazdır
    write_individual_m3u8(success, OUTPUT_DIR_NAME)

    with open(DEBUG_FILE, "w", encoding="utf-8") as f:
        json.dump(failed, f, ensure_ascii=False, indent=2)

    print_report(KANALLAR, success, failed)
    print(f"✅ Başarıyla tamamlandı! Çalışan kanallar './{OUTPUT_DIR_NAME}/' klasörüne kaydedildi.\n")


if __name__ == "__main__":
    asyncio.run(main())
