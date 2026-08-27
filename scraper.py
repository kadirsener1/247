#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re
import asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta
from playwright.async_api import async_playwright

# ─── KANAL LİSTESİ (SADECE PATH YAPILARI) ──────────────────────────────────────
# Domain değişebileceği için sadece sayfa yollarını (path) tanımlıyoruz.
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

# Başlangıç/Alternatif Domainler (Eğer ana site değişirse sırayla kontrol edilir)
SEED_DOMAINS = [
    "https://tvnow247.top",
    "https://tvnow247.live",
    "https://tvnow247.one",
    "https://tvnow247.net"
]

# ─── AYARLAR ──────────────────────────────────────────────────────────────────
OUTPUT_DIR_NAME = "tvnow247"
DEBUG_FILE = "debug_failed.json"
MAX_CONCURRENT = 3              # Engellemeler sayesinde 3 sekme kasmadan çalışır
PAGE_TIMEOUT = 20000            # Maksimum sayfa yükleme süresi (20 saniye)
SCAN_WAIT = 8                   # Yayın linkini yakalama sabır süresi (8 saniye)

# Reklam engelleyici kara listesi (Bu kelimeleri içeren hiçbir istek yüklenmez - Hız kazandırır)
AD_BLOCK_LIST = [
    "google-analytics", "doubleclick", "adservice", "popads", "popcash",
    "histats", "adsterra", "exoclick", "onclickads", "propush", "monetag",
    "mgid", "yandex", "facebook", "twitter", "analytics", "adskeeper",
    "vidoomy", "ezodn", "witnessonmy", "adnxs", "jads", "banner"
]

# Görsel, yazı tipi ve stil dosyalarını engelle (Yükleme hızını tavan yaptırır)
BLOCKED_RESOURCES = {"image", "font", "stylesheet", "media"}

# ──────────────────────────────────────────────────────────────────────────────

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


def is_valid_m3u8(url: str) -> bool:
    """Gerçek yayın m3u8 adresi olup olmadığını doğrular."""
    if not url or not isinstance(url, str):
        return False
    
    url_low = url.lower().split("?")[0]
    
    # Reklam videolarını ve alakasız m3u8'leri ele
    if any(ad in url_low for ad in AD_BLOCK_LIST):
        return False
    
    # Sadece canlı yayın HLS/DASH uzantılarına izin ver
    if url_low.endswith(".m3u8") or ".m3u8" in url_low or url_low.endswith(".mpd"):
        return True
        
    return False


async def discover_active_domain() -> str:
    """Sitenin şu an aktif olan güncel adresini bulur."""
    print("🔍 Aktif alan adı (domain) sorgulanıyor...")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        active_domain = ""
        for seed in SEED_DOMAINS:
            try:
                # Yönlendirmeleri takip etmesi için sayfayı açıyoruz
                response = await page.goto(seed, timeout=12000, wait_until="commit")
                if response and response.status < 400:
                    # Yönlenilen son URL'yi al ve ana domaini çıkar
                    final_url = page.url
                    match = re.match(r'(https?://[^/]+)', final_url)
                    if match:
                        active_domain = match.group(1)
                        print(f"🎯 Güncel Aktif Domain Tespit Edildi: {active_domain}")
                        break
            except Exception:
                continue
        
        await browser.close()
        
        # Eğer hiçbir siteye erişilemezse varsayılanı kullan
        if not active_domain:
            active_domain = SEED_DOMAINS[0]
            print(f"⚠️  Aktif domain tespit edilemedi! Varsayılan kullanılıyor: {active_domain}")
        
        return active_domain


async def get_channel_stream(browser, page_url: str, active_domain: str) -> str:
    """Sayfayı açar, reklamları filtreler ve doğrudan yayının .m3u8 linkini yakalar."""
    stream_url = ""
    found_event = asyncio.Event()

    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1024, "height": 768},
        ignore_https_errors=True,
    )

    page = await context.new_page()

    # Otomatik açılan reklam pencerelerini anında imha et
    page.on("popup", lambda p: asyncio.create_task(p.close()))

    # ⚡ HIZLANDIRICI VE REKLAM ENGELLEYİCİ FİLTRE
    async def route_filter(route):
        req = route.request
        url_low = req.url.lower()

        # Eğer yayın linkiyse asla engelleme
        if is_valid_m3u8(req.url):
            await route.continue_()
            return

        # Reklam siteleri ve gereksiz kaynakları engelle (Hız kazandırır)
        if any(ad in url_low for ad in AD_BLOCK_LIST) or req.resource_type in BLOCKED_RESOURCES:
            await route.abort()
        else:
            await route.continue_()

    await page.route("**/*", route_filter)

    # 🔍 AĞ TRAFİĞİNDEN YAYIN YAKALAYICI
    async def handle_response(response):
        nonlocal stream_url
        if stream_url:
            return

        url = response.url
        if is_valid_m3u8(url):
            stream_url = url
            found_event.set()
            return

        # Bazı gizlenmiş m3u8'leri içerik analizinden yakala
        content_type = response.headers.get("content-type", "").lower()
        if "mpegurl" in content_type or "application/x-mpegurl" in content_type:
            stream_url = url
            found_event.set()
            return

    page.on("response", handle_response)

    try:
        # Sayfayı çok hızlı yükle
        await page.goto(page_url, timeout=PAGE_TIMEOUT, wait_until="commit")
        await asyncio.sleep(1.5)

        # Oynatıcıyı çalıştırmak ve reklam engellerini aşmak için akıllı tıklama
        for _ in range(2):
            if stream_url:
                break
            try:
                # Ekranın ortasına tıkla (reklamı tetiklerse popup-killer anında kapatır)
                await page.mouse.click(512, 384)
            except Exception:
                pass

            # Iframe içindeki oynatıcıyı tetikle
            for frame in page.frames:
                try:
                    await frame.evaluate("""() => {
                        document.querySelectorAll('video').forEach(v => {
                            v.muted = true;
                            v.play().catch(()=>{});
                        });
                        const btn = document.querySelector('.vjs-big-play-button, .jw-display-icon-container, button');
                        if (btn) btn.click();
                    }""")
                except Exception:
                    pass
            await asyncio.sleep(1.2)

        # Yayın yakalanana kadar bekle
        try:
            await asyncio.wait_for(found_event.wait(), timeout=SCAN_WAIT)
        except asyncio.TimeoutError:
            pass

        # Yedek Plan: Global JS değişkenlerini tara
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
            # Dinamik olarak güncel domain ve sayfa yolunu birleştiriyoruz
            url = f"{active_domain}{ch['path']}"

            async with semaphore:
                stream_url = await get_channel_stream(browser, url, active_domain)

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
    print("   📺 TVNOW247 - OTOMATİK DOMAIN UYUMLU ULTRA HIZLI SCRAPER")
    print("=" * 65 + "\n")

    # 1. Adım: Sitenin güncel aktif adresini bul
    active_domain = await discover_active_domain()
    print(f"🔗 Kullanılacak Yayın Kaynağı: {active_domain}\n")

    # 2. Adım: Kanalları tara
    success, failed = await process_all(KANAL_SABLONLARI, active_domain)

    # 3. Adım: Dosyaları kaydet
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
