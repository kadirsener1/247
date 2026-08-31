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


# ─── MASTER KANAL LİSTESİ (LIVELIVE24 FORMATI) ────────────────────────────────
# Yeni eklemek istediğiniz kanalları buradaki formata göre ekleyebilirsiniz.
MASTER_CHANNELS = [
    {
        "name": "3sat DE",
        "url": "https://livelive24.com/?channel=3sat-de-",
        "group": "DE"
    },
    {
        "name": "ARD Das Erste",
        "url": "https://livelive24.com/?channel=ard-de-",
        "group": "DE"
    },
    {
        "name": "ZDF HD",
        "url": "https://livelive24.com/?channel=zdf-de-",
        "group": "DE"
    },
    {
        "name": "RTL",
        "url": "https://livelive24.com/?channel=rtl-de-",
        "group": "DE"
    },
    {
        "name": "ProSieben",
        "url": "https://livelive24.com/?channel=pro7-de-",
        "group": "DE"
    },
    {
        "name": "Sky Sport News",
        "url": "https://livelive24.com/?channel=sky-sport-news-de-",
        "group": "DE-SPORT"
    },
    {
        "name": "DAZN 1 DE",
        "url": "https://livelive24.com/?channel=dazn-1-de-",
        "group": "DE-SPORT"
    },
    {
        "name": "Sky Sport Bundesliga 1",
        "url": "https://livelive24.com/?channel=sky-sport-bundesliga-1-de-",
        "group": "DE-SPORT"
    }
]

# ─── SİSTEM AYARLARI ──────────────────────────────────────────────────────────
OUTPUT_FILE_NAME   = "livelive24.m3u"
PLAYLIST_FILE_NAME = "playlist.m3u"
PLAYLIST_URL       = "https://raw.githubusercontent.com/kadirsener1/avva/refs/heads/main/playlist.m3u"
DEBUG_FILE         = "debug_failed.json"

TIMEOUT      = 15000
FIRST_WAIT   = 3.5   # İlk yüklemede bekleme (saniye)
RELOAD_WAIT  = 4.0   # Her retry sonrası bekleme (saniye)
MAX_RETRIES  = 15    # Maksimum yenileme denemesi
RETRY_WAIT   = 2.0   # Denemeler arası ek bekleme (saniye)
MAX_CONCURRENT = 3   # Eşzamanlı sekme sayısı (Livelive24 korumaları için 3 idealdir)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8",
    "Referer": "https://livelive24.com/",
    "Origin": "https://livelive24.com",
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

# Sitedeki hata mesajları
STREAM_ERROR_TEXTS = [
    "Stream loading failed",
    "Stream Error",
    "Please refresh",
    "stream-error",
    "offline",
    "not found"
]

# ──────────────────────────────────────────────────────────────────────────────


def is_valid_stream_url(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return False
    invalid_chars = [" ", "{", "}", "<", ">", '"', "'", "`", ";", "(", ")",
                     "\\", "\n", "\r", "\t", "&&", "||", "import", "function"]
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


def has_stream_error(content: str) -> bool:
    """Sayfa içeriğinde stream hatası var mı kontrol et."""
    return any(err in content.lower() for err in STREAM_ERROR_TEXTS)


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
        await page.mouse.click(300, 300)
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
    page    = None

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

        page.on("request",  on_request)
        page.on("response", on_response)

        # ── İlk yükleme ──────────────────────────────────────────────────────
        try:
            await page.goto(player_url, timeout=TIMEOUT, wait_until="domcontentloaded")
        except Exception:
            pass

        await try_trigger_play(page)

        try:
            await asyncio.wait_for(found_event.wait(), timeout=FIRST_WAIT)
        except asyncio.TimeoutError:
            pass

        # ── Retry döngüsü ────────────────────────────────────────────────────
        for attempt in range(1, MAX_RETRIES + 1):

            if stream_url and is_valid_stream_url(stream_url):
                break  # URL bulundu, döngüden çık

            page_has_error = False
            try:
                content = await page.content()

                if has_stream_error(content):
                    page_has_error = True
                else:
                    found = extract_from_html(content, player_url)
                    if is_valid_stream_url(found):
                        stream_url = found
                        break

                    js_url = await extract_from_js(page)
                    if is_valid_stream_url(js_url):
                        stream_url = js_url
                        break
            except Exception:
                page_has_error = True

            status = "Stream Error — yenileniyor" if page_has_error else "URL yok — yenileniyor"
            print(f"    🔄 [{attempt:02d}/{MAX_RETRIES}] {channel_name}: {status}")

            await asyncio.sleep(RETRY_WAIT)
            found_event.clear()

            try:
                await page.reload(timeout=TIMEOUT, wait_until="domcontentloaded")
                await try_trigger_play(page)
                await asyncio.wait_for(found_event.wait(), timeout=RELOAD_WAIT)
            except (asyncio.TimeoutError, Exception):
                pass

        # ── Son çare: frame taraması (Livelive24 iframe kullandığı için önemlidir) ──
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
    success    = []
    failed     = []
    semaphore  = asyncio.Semaphore(MAX_CONCURRENT)
    total      = len(channels)
    done_count = 0
    lock       = asyncio.Lock()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=BROWSER_ARGS)

        async def handle(ch):
            nonlocal done_count
            name       = str(ch.get("name",  "?")).strip()
            player_url = str(ch.get("url",   "")).strip()
            image      = str(ch.get("image", "")).strip()
            group      = str(ch.get("group", "GENEL")).strip().upper()

            if not player_url:
                async with lock:
                    done_count += 1
                    failed.append({"name": name, "player_url": "", "image": image,
                                   "group": group, "reason": "URL yok"})
                return

            async with semaphore:
                stream_url = await get_stream_url(browser, player_url, name)

            async with lock:
                done_count += 1
                prefix = f"[{done_count:03d}/{total}]"
                if stream_url and is_valid_stream_url(stream_url):
                    print(f"  ✅ {prefix} {name} → {stream_url[:65]}...")
                    success.append({
                        "name":       name,
                        "stream_url": stream_url,
                        "player_url": player_url,
                        "image":      image,
                        "group":      group,
                    })
                else:
                    print(f"  ❌ {prefix} {name} (Başarısız / Token Alınamadı)")
                    failed.append({
                        "name":       name,
                        "player_url": player_url,
                        "image":      image,
                        "group":      group,
                        "reason":     "Geçerli stream URL bulunamadı",
                    })

        await asyncio.gather(*[handle(ch) for ch in channels], return_exceptions=True)

        try:
            await browser.close()
        except Exception:
            pass

    return success, failed


def write_single_m3u(items: list, file_name: str = "livelive24.m3u"):
    base_path = Path(__file__).parent.resolve()
    file_path = base_path / file_name
    print(f"\n📂 {file_name} Yazılıyor (Dosya: {file_path})")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for ch in items:
                name   = ch["name"]
                stream = ch["stream_url"]
                group  = ch.get("group", "GENEL")
                image  = ch.get("image", "")
                f.write(f'#EXTINF:-1 tvg-id="{name}" tvg-name="{name}" tvg-logo="{image}" group-title="{group}",{name}\n')
                f.write(f"{stream}\n")
        print(f"   💾 Başarıyla Yazıldı: {file_name} ({len(items)} Kanal)")
    except Exception as e:
        print(f"   ❌ Dosya yazma hatası ({file_name}): {e}")


def get_playlist_identifiers(extinf_line: str) -> list:
    identifiers = []
    id_match = re.search(r'tvg-id="([^"]+)"', extinf_line, re.IGNORECASE)
    if id_match:
        identifiers.append(id_match.group(1).strip())
    name_match = re.search(r'tvg-name="([^"]+)"', extinf_line, re.IGNORECASE)
    if name_match:
        identifiers.append(name_match.group(1).strip())
    if "," in extinf_line:
        display_name = extinf_line.rsplit(",", 1)[-1].strip()
        identifiers.append(display_name)
    return identifiers


def get_local_or_remote_playlist() -> str:
    local_file = Path(__file__).parent.resolve() / PLAYLIST_FILE_NAME
    if local_file.exists():
        try:
            content = local_file.read_text(encoding="utf-8")
            if content.strip():
                print(f"   📂 Lokal '{PLAYLIST_FILE_NAME}' dosyası başarıyla okundu.")
                return content
        except Exception:
            pass
    print(f"   🌐 Lokal dosya bulunamadı, uzak adresten indiriliyor: {PLAYLIST_URL}")
    try:
        r = requests.get(PLAYLIST_URL, timeout=15)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"   ❌ Uzak playlist indirilemedi: {e}")
        return ""


def update_playlist_m3u(success_channels: list, content: str):
    if not content:
        print("   ⚠️ Güncellenecek playlist.m3u içeriği bulunamadı!")
        return

    print(f"\n🔄 Playlist Senkronizasyonu Başlatıldı...")

    channel_map = {}
    for ch in success_channels:
        ch_name = ch["name"].strip()
        channel_map[ch_name]            = ch["stream_url"]
        channel_map[ch_name.lower()]    = ch["stream_url"]

    lines         = content.splitlines()
    new_lines     = []
    updated_count = 0
    total_channels = 0

    i = 0
    while i < len(lines):
        line    = lines[i]
        stripped = line.strip()

        if stripped.startswith("#EXTINF"):
            total_channels += 1
            new_lines.append(line)
            identifiers = get_playlist_identifiers(stripped)

            j = i + 1
            url_line_index = -1
            while j < len(lines):
                next_line = lines[j].strip()
                if not next_line:
                    j += 1
                    continue
                if next_line.startswith("#EXTINF") or next_line.startswith("#EXTM3U"):
                    break
                if next_line.startswith("http://") or next_line.startswith("https://"):
                    url_line_index = j
                    break
                j += 1

            matched_stream = None
            matched_id     = ""
            for ident in identifiers:
                if ident in channel_map:
                    matched_stream = channel_map[ident]
                    matched_id     = ident
                    break
                elif ident.lower() in channel_map:
                    matched_stream = channel_map[ident.lower()]
                    matched_id     = ident
                    break

            if matched_stream:
                new_lines.append(matched_stream)
                updated_count += 1
                print(f"   ✨ Eşleşti ve Güncellendi: {matched_id}")
                i = (url_line_index + 1) if url_line_index != -1 else (i + 1)
            else:
                if url_line_index != -1:
                    for k in range(i + 1, url_line_index + 1):
                        new_lines.append(lines[k])
                    i = url_line_index + 1
                else:
                    i += 1
        else:
            new_lines.append(line)
            i += 1

    file_path = Path(__file__).parent.resolve() / PLAYLIST_FILE_NAME
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")
        print(f"\n   💾 {PLAYLIST_FILE_NAME} başarıyla kaydedildi!")
        print(f"   📊 Toplam Kanal: {total_channels} | Güncellenen: {updated_count}")
    except Exception as e:
        print(f"   ❌ playlist.m3u kaydedilemedi: {e}")


def print_report(channels: list, success: list, failed: list):
    turkey_tz = timezone(timedelta(hours=3))
    now = datetime.now(turkey_tz).strftime("%d.%m.%Y %H:%M:%S")
    print(f"\n{'═'*65}")
    print(f"📊 SONUÇ RAPORU")
    print(f"{'═'*65}")
    print(f"  📺 Taranan kanal sayısı  : {len(channels)}")
    print(f"  ✅ Başarıyla çözülen     : {len(success)}")
    print(f"  ❌ Başarısız olan        : {len(failed)}")
    print(f"  📁 {OUTPUT_FILE_NAME}         : Güncellendi ({len(success)} kanal)")
    print(f"  📁 playlist.m3u          : Senkronize Edildi")
    print(f"  🕐 Güncelleme zamanı     : {now}")
    print(f"{'═'*65}\n")


async def main():
    print("═" * 65)
    print("   📺 LIVELIVE24 — ÇOKLU LİSTE GÜNCELLEME SİSTEMİ")
    print("═" * 65 + "\n")

    playlist_content = get_local_or_remote_playlist()

    print(f"🚀 Taranacak Kanal Sayısı : {len(MASTER_CHANNELS)}")
    print(f"⚡ Eşzamanlı Sekme        : {MAX_CONCURRENT}")
    print(f"🔁 Max Retry / Kanal      : {MAX_RETRIES}\n")

    success, failed = await process_all(MASTER_CHANNELS)

    write_single_m3u(success, OUTPUT_FILE_NAME)

    if success:
        update_playlist_m3u(success, playlist_content)

    with open(DEBUG_FILE, "w", encoding="utf-8") as f:
        json.dump(failed, f, ensure_ascii=False, indent=2)

    print_report(MASTER_CHANNELS, success, failed)


if __name__ == "__main__":
    asyncio.run(main())
