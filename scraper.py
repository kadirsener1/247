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
KANAL_SABLONLARI = [
    {"name": "usabc", "path": "/watch/abc-usa/", "group": "US"},
    {"name": "uscbs", "path": "/watch/cbs-usa/", "group": "US"},
    {"name": "usnbc", "path": "/watch/nbc-usa/", "group": "US"},
    {"name": "usfox", "path": "/watch/fox-usa/", "group": "US"},
    {"name": "usespn", "path": "/watch/espn-usa/", "group": "US"},
    {"name": "usespn2", "path": "/watch/espn-2/", "group": "US"},
    {"name": "ususa", "path": "/watch/usa-network/", "group": "US"},
    {"name": "usnflnetwork", "path": "/watch/nfl-network/", "group": "US"},
    {"name": "usnbatv", "path": "/watch/nba-tv/", "group": "US"},
    {"name": "ukskysportsmainevent", "path": "/watch/sky-sports-main-event/", "group": "UK"},
    {"name": "ukskysportspremierleague", "path": "/watch/sky-sports-premier-league/", "group": "UK"},
    {"name": "ukskysportsf1", "path": "/watch/sky-sports-f1/", "group": "UK"},
    {"name": "uktntsports1", "path": "/watch/tnt-sports-1-uk/", "group": "UK"},
    {"name": "uktntsports2", "path": "/watch/tnt-sports-2-uk/", "group": "UK"},
    {"name": "trbeinsports1", "path": "/watch/bein-sports-1-turkey/", "group": "TR"},
]

SEED_DOMAINS = [
    "https://tvnow247.top",
    "https://tvnow247.live",
    "https://tvnow247.one",
    "https://tvnow247.net"
]

# ─── SİSTEM AYARLARI ──────────────────────────────────────────────────────────
OUTPUT_DIR_NAME = "tvnow247"
DEBUG_FILE = "debug_failed.json"
MAX_CONCURRENT = 2              # Stabilite için eşzamanlı kanal taraması 2 yapıldı
PAGE_TIMEOUT = 25000            # Sayfa yükleme zaman aşımı (25 saniye)
SERVER_WAIT_TIMEOUT = 7         # Her bir sunucu (Server) denemesi için bekleme süresi

# Reklam engelleyici (Medya yürütülmesini engellememek için optimize edildi)
AD_BLOCK_LIST = [
    "google-analytics", "doubleclick", "adservice", "popads", "popcash",
    "histats", "adsterra", "exoclick", "onclickads", "propush", "monetag",
    "mgid", "yandex", "facebook", "twitter", "analytics", "adskeeper",
    "vidoomy", "ezodn", "witnessonmy", "adnxs", "jads", "banner"
]
BLOCKED_RESOURCES = {"image", "font"} # Sadece görsel ve fontları engelle (CSS engeli kaldırıldı)

# ──────────────────────────────────────────────────────────────────────────────

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


def is_valid_m3u8(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    url_low = url.lower().split("?")[0]
    if any(ad in url_low for ad in AD_BLOCK_LIST):
        return False
    if url_low.endswith(".m3u8") or ".m3u8" in url_low or url_low.endswith(".mpd"):
        return True
    return False


async def discover_active_domain() -> str:
    print("🔍 Aktif alan adı (domain) sorgulanıyor...")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        active_domain = ""
        for seed in SEED_DOMAINS:
            try:
                response = await page.goto(seed, timeout=12000, wait_until="commit")
                if response and response.status < 400:
                    final_url = page.url
                    match = re.match(r'(https?://[^/]+)', final_url)
                    if match:
                        active_domain = match.group(1)
                        print(f"🎯 Güncel Aktif Domain Tespit Edildi: {active_domain}")
                        break
            except Exception:
                continue
        
        await browser.close()
        if not active_domain:
            active_domain = SEED_DOMAINS[0]
            print(f"⚠️ Aktif domain tespit edilemedi! Varsayılan kullanılıyor: {active_domain}")
        return active_domain


async def try_trigger_play(page):
    """Sayfa genelindeki tüm oynatma mekanizmalarını tetikler."""
    try:
        await page.mouse.click(512, 384) # Merkeze tıkla
    except Exception:
        pass

    for frame in page.frames:
        try:
            await frame.evaluate("""() => {
                // Video elementlerini bul ve oynatmayı zorla
                document.querySelectorAll('video').forEach(v => {
                    v.muted = true;
                    v.play().catch(()=>{});
                });
                // Bilinen tüm oynat butonlarına tıkla
                const btns = document.querySelectorAll(
                    '.vjs-big-play-button, .jw-display-icon-container, .play-icon, #player, button[class*="play" i]'
                );
                btns.forEach(btn => btn.click());
            }""")
        except Exception:
            pass


async def switch_server_on_page(page, server_number: int) -> bool:
    """Sayfa veya iframe'lerdeki 'Server 1', 'Server 2' butonlarını arar ve tıklar."""
    switched = False
    
    # Hem ana sayfada hem de alt iframe'lerde buton araması yapar
    for frame in page.frames:
        try:
            success = await frame.evaluate("""(num) => {
                const elements = Array.from(document.querySelectorAll('button, a, div, li, span'));
                const rx = new RegExp('(server|source|stream|yayın|kaynak)\\\\s*' + num + '|^' + num + '$', 'i');
                
                // 1. Aşama: Metin eşleşmeli butonlar
                for (let el of elements) {
                    const text = (el.innerText || el.textContent || "").trim();
                    if (rx.test(text) && el.offsetWidth > 0 && el.offsetHeight > 0) {
                        el.click();
                        return true;
                    }
                }
                
                // 2. Aşama: Sınıf isimlerinde server kelimesi geçenler
                const potentialSelects = document.querySelectorAll('[class*="server" i], [class*="source" i], [class*="btn" i]');
                for (let el of potentialSelects) {
                    if (el.textContent.includes(String(num))) {
                        el.click();
                        return true;
                    }
                }
                return false;
            }""", server_number)
            if success:
                switched = True
        except Exception:
            pass
            
    return switched


async def get_channel_stream(browser, page_url: str) -> str:
    stream_url = ""
    found_event = asyncio.Event()

    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True,
    )

    page = await context.new_page()
    page.on("popup", lambda p: asyncio.create_task(p.close())) # Reklam popup engeli

    # Ağ Filtreleyici (Performans ve reklam koruması)
    async def route_filter(route):
        req = route.request
        url_low = req.url.lower()
        if is_valid_m3u8(req.url):
            await route.continue_()
            return
        if any(ad in url_low for ad in AD_BLOCK_LIST) or req.resource_type in BLOCKED_RESOURCES:
            await route.abort()
        else:
            await route.continue_()

    await page.route("**/*", route_filter)

    # Ağ Trafiğini İzle
    async def handle_response(response):
        nonlocal stream_url
        if stream_url:
            return
        url = response.url
        if is_valid_m3u8(url):
            stream_url = url
            found_event.set()
            return

        content_type = response.headers.get("content-type", "").lower()
        if "mpegurl" in content_type or "application/x-mpegurl" in content_type:
            stream_url = url
            found_event.set()
            return

    page.on("response", handle_response)

    try:
        # 1. Sayfayı Yükle
        await page.goto(page_url, timeout=PAGE_TIMEOUT, wait_until="commit")
        await asyncio.sleep(2)

        # 🚀 [AŞAMA 1] - Server 1 (Varsayılan Kaynak) Denemesi
        await try_trigger_play(page)
        try:
            await asyncio.wait_for(found_event.wait(), timeout=SERVER_WAIT_TIMEOUT)
        except asyncio.TimeoutError:
            pass

        # 🚀 [AŞAMA 2] - Eğer Server 1 Başarısız Olursa Server 2'ye Geçiş Yap
        if not stream_url:
            print(f"    🔄 {page_url.split('/')[-2]} -> Server 1 başarısız. Server 2 deneniyor...")
            has_switched = await switch_server_on_page(page, 2)
            
            if has_switched:
                await asyncio.sleep(2) # Yeni sunucu iframe yükleme payı
                await try_trigger_play(page)
                try:
                    await asyncio.wait_for(found_event.wait(), timeout=SERVER_WAIT_TIMEOUT)
                except asyncio.TimeoutError:
                    pass
            else:
                print("    ⚠️  Server 2 butonu bulunamadı veya tıklanamadı.")

        # 🚀 [AŞAMA 3] - Son Yedek Plan: Global JS Değişkenleri
        if not stream_url:
            for frame in page.frames:
                try:
                    val = await frame.evaluate("""() => {
                        try { if (typeof jwplayer !== 'undefined') return jwplayer().getPlaylist()[0].file; } catch(e){}
                        try { if (typeof player !== 'undefined' && player.src) return player.src(); } catch(e){}
                        const v = document.querySelector('video');
                        if (v && v.src && v.src.startsWith('http')) return v.src;
                        return null;
                    }""")
                    if val and is_valid_m3u8(val):
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


async def process_all(channels: list, active_domain: str) -> tuple:
    success = []
    failed = []
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    total = len(channels)
    done_count = 0
    lock = asyncio.Lock()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--mute-audio"
            ]
        )

        async def handle(ch):
            nonlocal done_count
            name = ch["name"]
            url = f"{active_domain}{ch['path']}"

            async with semaphore:
                stream_url = await get_channel_stream(browser, url)

            async with lock:
                done_count += 1
                prefix = f"[{done_count:02d}/{total}]"

                if stream_url:
                    print(f"  ✅ {prefix} {name} → Yayın Bulundu!")
                    success.append({"name": name, "stream_url": stream_url})
                else:
                    print(f"  ❌ {prefix} {name} → Yayın linki bulunamadı.")
                    failed.append({"name": name, "page_url": url})

        await asyncio.gather(*[handle(ch) for ch in channels], return_exceptions=True)
        await browser.close()

    return success, failed


def write_to_m3u8_files(items: list, output_dir: str):
    base_path = Path(__file__).parent.resolve()
    target_dir = base_path / output_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📂 Kaydetme İşlemi Başlatıldı ({target_dir})")

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
            print(f"   💾 Yazıldı: {file_path.name}")
        except Exception as e:
            print(f"   ❌ Dosya Hatası ({safe_name}): {e}")


async def main():
    print("=" * 65)
    print("   📺 TVNOW247 - OTOMATİK ÇOKLU SUNUCU (MULTI-SERVER) DESTEKLİ BOT")
    print("=" * 65 + "\n")

    # 1. Güncel Domaini Tespit Et
    active_domain = await discover_active_domain()
    print(f"🔗 Kullanılacak Aktif Yayın Kaynağı: {active_domain}\n")

    # 2. Tüm Kanalları Çift Sunucu Destekli Tara
    success, failed = await process_all(KANAL_SABLONLARI, active_domain)

    # 3. Dosyaları Kaydet
    write_to_m3u8_files(success, OUTPUT_DIR_NAME)

    with open(DEBUG_FILE, "w", encoding="utf-8") as f:
        json.dump(failed, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 65}")
    print(f"📊 ÖZET RAPOR:")
    print(f"  Aktif Domain : {active_domain}")
    print(f"  Toplam Kanal : {len(KANAL_SABLONLARI)}")
    print(f"  Başarılı     : {len(success)}")
    print(f"  Başarısız    : {len(failed)}")
    print(f"  Klasör Yolu  : ./{OUTPUT_DIR_NAME}/")
    print(f"{'=' * 65}\n")


if __name__ == "__main__":
    asyncio.run(main())
