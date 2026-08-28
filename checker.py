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
    # ... (Mevcut tüm kanal listeniz buraya eklenecek, aynı kalıyor)
    # Yer kaplamaması için tekrar yazmıyorum, sizdeki liste geçerli.
]

# ─── SİSTEM AYARLARI ──────────────────────────────────────────────────────────
OUTPUT_FILE_NAME = "cdn.m3u"          # Ana çıktı dosyası
PLAYLIST_FILE_NAME = "playlist.m3u"   # Güncellenecek uzak liste
PLAYLIST_URL = "https://raw.githubusercontent.com/kadirsener1/avva/refs/heads/main/playlist.m3u"
DEBUG_FILE = "debug_failed.json"

TIMEOUT = 15000
FIRST_WAIT = 3.0
RELOAD_WAIT = 4.5
MAX_CONCURRENT = 4

# ⚡ TiviMate ve diğer profesyonel oynatıcılar için HTTP Header koruması
STREAM_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
STREAM_REFERER = "https://cdnlivetv.tv/"
STREAM_ORIGIN = "https://cdnlivetv.tv"

HEADERS = {
    "User-Agent": STREAM_USER_AGENT,
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8",
    "Referer": STREAM_REFERER,
    "Origin": STREAM_ORIGIN,
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
        browser = await pw.chromium.launch(headless=True, args=BROWSER_ARGS)

        async def handle(ch):
            nonlocal done_count
            name = str(ch.get("name", "?")).strip()
            player_url = str(ch.get("url", "")).strip()
            image = str(ch.get("image", "")).strip()
            group = str(ch.get("group", "GENEL")).strip().upper()

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


def build_stream_block(stream_url: str) -> str:
    """
    TiviMate, IPTV Smarters vb. oynatıcılarda 403 hatası almamak için 
    User-Agent, Referer ve Origin başlıklarını entegre eder.
    """
    lines = []
    lines.append(f'#EXTVLCOPT:http-user-agent={STREAM_USER_AGENT}')
    lines.append(f'#EXTVLCOPT:http-referrer={STREAM_REFERER}')
    lines.append(f'#EXTVLCOPT:http-origin={STREAM_ORIGIN}')
    lines.append(f'#KODIPROP:inputstream.adaptive.stream_headers=User-Agent={STREAM_USER_AGENT}&Referer={STREAM_REFERER}&Origin={STREAM_ORIGIN}')
    stream_with_headers = f'{stream_url}|User-Agent={STREAM_USER_AGENT}&Referer={STREAM_REFERER}&Origin={STREAM_ORIGIN}'
    lines.append(stream_with_headers)
    return "\n".join(lines)


def write_single_m3u(items: list, file_name: str = "cdn.m3u"):
    """Bulunan tüm kanalları TiviMate uyumlu M3U formatında kaydeder."""
    base_path = Path(__file__).parent.resolve()
    file_path = base_path / file_name
    print(f"\n📂 Yazma İşlemi Başlatıldı (Dosya: {file_path})")

    if not items:
        print("   ⚠️ Yazılacak başarılı kanal bulunamadı.")
        return

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for ch in items:
                name = ch["name"]
                stream = ch["stream_url"]
                group = ch.get("group", "GENEL")
                image = ch.get("image", "")

                f.write(f'#EXTINF:-1 tvg-id="{name}" tvg-name="{name}" tvg-logo="{image}" group-title="{group}",{name}\n')
                f.write(build_stream_block(stream) + "\n")
                
        print(f"   💾 Başarıyla Yazıldı: {file_name} ({len(items)} Kanal)")
    except Exception as e:
        print(f"   ❌ Dosya yazma hatası ({file_name}): {e}")


# ─── PLAYLIST.M3U BİREBİR EŞLEŞTİRME VE GÜNCELLEME ─────────────────────────────
def get_playlist_identifiers(extinf_line: str) -> list:
    """
    EXTINF satırından tvg-id, tvg-name ve display name'i 
    olduğu gibi (herhangi bir harf dönüştürmesi yapmadan) çeker.
    """
    identifiers = []
    
    # tvg-id="..." içindeki değer
    id_match = re.search(r'tvg-id="([^"]+)"', extinf_line, re.IGNORECASE)
    if id_match:
        identifiers.append(id_match.group(1).strip())
        
    # tvg-name="..." içindeki değer
    name_match = re.search(r'tvg-name="([^"]+)"', extinf_line, re.IGNORECASE)
    if name_match:
        identifiers.append(name_match.group(1).strip())
        
    # Virgülden sonraki kanal adı değeri (Örn: #EXTINF:...,Kanal Adı)
    if "," in extinf_line:
        display_name = extinf_line.rsplit(",", 1)[-1].strip()
        identifiers.append(display_name)
        
    return list(set(identifiers)) # Çift kayıtları temizle


def update_playlist_m3u(success_channels: list):
    """
    playlist.m3u dosyasını indirir, mevcut yapı ve sırayı KORUYARAK
    sadece taranan ismin BİREBİR aynısı olan kanalların linklerini günceller.
    """
    print(f"\n🔄 Uzak Playlist Senkronizasyonu Başlatıldı...")
    print(f"   🌐 Kaynak: {PLAYLIST_URL}")

    try:
        r = requests.get(PLAYLIST_URL, timeout=30)
        r.raise_for_status()
        remote_content = r.text
    except Exception as e:
        print(f"   ❌ Uzak playlist indirilemedi: {e}")
        return

    # Başarılı kanalları isme göre sözlüğe ekle (Birebir eşleşme için)
    # Taramadaki 'name' değerleri (Örn: "uktntsports1") anahtar olarak kullanılır.
    channel_map = {ch["name"].strip(): ch["stream_url"] for ch in success_channels}

    lines = remote_content.splitlines()
    new_lines = []
    updated_count = 0
    total_channels_in_playlist = 0
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("#EXTINF"):
            total_channels_in_playlist += 1
            new_lines.append(line)

            # EXTINF satırından tvg-id, tvg-name ve kanal adını çek
            identifiers = get_playlist_identifiers(stripped)

            # Sonraki satırlardan asıl URL'yi bul (aradaki eski #EXTVLCOPT'ları geç)
            j = i + 1
            url_line_index = -1
            while j < len(lines):
                next_line = lines[j].strip()
                if not next_line:
                    j += 1
                    continue
                if next_line.startswith("#EXTINF") or next_line.startswith("#EXTM3U"):
                    break
                if next_line.startswith("#"):
                    j += 1
                    continue
                if next_line.startswith("http"):
                    url_line_index = j
                    break
                j += 1

            # Birebir eşleşme kontrolü (Taramadaki isimle birebir uyumlu mu?)
            matched_stream = None
            for identifier in identifiers:
                if identifier in channel_map:
                    matched_stream = channel_map[identifier]
                    break

            if matched_stream and url_line_index != -1:
                # ✅ Birebir Eşleşti: Yeni linki ve TiviMate başlıklarını yaz
                new_lines.append(build_stream_block(matched_stream))
                updated_count += 1
                i = url_line_index + 1
            elif url_line_index != -1:
                # ⚠️ Eşleşmedi: Eski başlık ve eski URL bloğunu olduğu gibi koru
                for k in range(i + 1, url_line_index + 1):
                    new_lines.append(lines[k])
                i = url_line_index + 1
            else:
                i += 1
        else:
            new_lines.append(line)
            i += 1

    # Yerel playlist.m3u dosyasına kaydet
    base_path = Path(__file__).parent.resolve()
    file_path = base_path / PLAYLIST_FILE_NAME
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines))
            if not new_lines or not new_lines[-1].endswith("\n"):
                f.write("\n")
        print(f"   ✅ playlist.m3u başarıyla güncellendi.")
        print(f"   📊 Playlist'teki toplam kanal: {total_channels_in_playlist}")
        print(f"   🔄 Güncellenen link sayısı   : {updated_count}")
        print(f"   💾 Kaydedildi: {file_path}")
    except Exception as e:
        print(f"   ❌ playlist.m3u yazılamadı: {e}")


def print_report(channels: list, success: list, failed: list):
    turkey_tz = timezone(timedelta(hours=3))
    now = datetime.now(turkey_tz).strftime("%d.%m.%Y %H:%M:%S")
    print(f"\n{'═'*65}")
    print(f"📊 SONUÇ RAPORU")
    print(f"{'═'*65}")
    print(f"  📺 Girilen kanal sayısı  : {len(channels)}")
    print(f"  ✅ Başarıyla çözülen     : {len(success)}")
    print(f"  ❌ Başarısız olan        : {len(failed)}")
    print(f"  📁 Ana Dosya            : ./{OUTPUT_FILE_NAME}")
    print(f"  📁 Playlist Dosyası      : ./{PLAYLIST_FILE_NAME}")
    print(f"  🕐 Güncelleme zamanı     : {now}")
    print(f"{'═'*65}\n")


async def main():
    print("═" * 65)
    print("   📺 CDN LIVE TV — BİREBİR EŞLEŞTİRMELİ SENKRONİZASYON SİTEMİ")
    print("═" * 65 + "\n")

    if not KANALLAR:
        print("⚠️  Lütfen 'KANALLAR' listesine en az bir kanal ekleyin.")
        return

    print(f"📋 İşlenecek kanal sayısı: {len(KANALLAR)}")
    print(f"⚡ Eşzamanlı Sekme       : {MAX_CONCURRENT}")
    print(f"📁 Ana Hedef             : ./{OUTPUT_FILE_NAME}")
    print(f"📁 Playlist Hedefi       : ./{PLAYLIST_FILE_NAME}\n")

    success, failed = await process_all(KANALLAR)

    write_single_m3u(success, OUTPUT_FILE_NAME)

    if success:
        update_playlist_m3u(success)

    with open(DEBUG_FILE, "w", encoding="utf-8") as f:
        json.dump(failed, f, ensure_ascii=False, indent=2)

    print_report(KANALLAR, success, failed)
    print(f"✅ Başarıyla tamamlandı!\n")


if __name__ == "__main__":
    asyncio.run(main())
