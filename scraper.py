import subprocess
import sys
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
    subprocess.check_call(["playwright", "install", "chromium"])
    from playwright.sync_api import sync_playwright


# ============================================================
# AYARLAR
# ============================================================

OUTPUT_FILE = "channels.m3u"
MAX_WORKERS = 4  # Paralel tarama sayısı (GitHub Actions için 4 ideal)
TIMEOUT     = 15  # Saniye

CHANNELS = [
    {"group": "Spor",   "id": "62", "name": "beIN Sports 1 Turkey", "logo": ""},
    {"group": "Spor",   "id": "63", "name": "beIN Sports 2 Turkey", "logo": ""},
    {"group": "Spor",   "id": "64", "name": "beIN Sports 3 Turkey", "logo": ""},
    {"group": "Ulusal", "id": "1030", "name": "TRT 1",                "logo": ""},
    {"group": "Ulusal", "id": "1031", "name": "ATV",                  "logo": ""},
]


# ============================================================
# PLAYER 6 URL PATTERN'LERİ (Tahmin)
# ============================================================

def get_possible_urls(channel_id):
    """Player 6 için olası URL'ler"""
    return [
        f"https://dlhd.st/player/stream-{channel_id}.php",
        f"https://dlhd.st/stream/stream-{channel_id}.php",
        f"https://dlhd.st/embed/stream-{channel_id}.php",
    ]


# ============================================================
# TEK KANAL - HIZLI TARAMA
# ============================================================

def scrape_single_channel(channel):
    """Tek kanalı tarar, m3u8 döner veya None"""
    
    channel_id = channel["id"]
    channel_name = channel["name"]
    referer = f"https://dlhd.st/watch.php?id={channel_id}"
    
    possible_urls = get_possible_urls(channel_id)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", 
                  "--disable-dev-shm-usage", "--disable-gpu"]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 720},
        )
        
        page = context.new_page()
        
        m3u8_found = []
        
        def on_response(resp):
            url = resp.url.lower()
            if ".m3u8" in url:
                # Filtrele: reklam/audio değilse al
                skip = ["track", "mono", "audio", "ads", "googlead", "doubleclick"]
                if not any(s in url for s in skip):
                    m3u8_found.append(resp.url)
        
        page.on("response", on_response)
        
        # Her olası URL'yi dene
        for stream_url in possible_urls:
            m3u8_found.clear()
            
            try:
                page.goto(stream_url, referer=referer, 
                         wait_until="domcontentloaded", timeout=TIMEOUT*1000)
                
                # Kısa bekle
                page.wait_for_timeout(3000)
                
                # Video tıkla (autoplay tetikle)
                try:
                    page.locator("video").click(force=True, timeout=2000)
                except:
                    pass
                
                page.wait_for_timeout(2000)
                
                if m3u8_found:
                    # En iyi linki seç (index.m3u8 öncelikli)
                    best = None
                    for url in m3u8_found:
                        if "index.m3u8" in url.lower():
                            best = url
                            break
                    if not best:
                        best = m3u8_found[0]
                    
                    browser.close()
                    print(f"  ✅ {channel_name}: {best[:60]}...")
                    return (channel, best)
                    
            except Exception as e:
                continue
        
        browser.close()
        print(f"  ❌ {channel_name}: Bulunamadı")
        return None


# ============================================================
# PARALEL TARAMA
# ============================================================

def scrape_all_parallel():
    """Tüm kanalları paralel tarar"""
    
    print("=" * 60)
    print(f"🚀 HIZLI TARAMA BAŞLIYOR")
    print(f"📋 Kanal: {len(CHANNELS)} | Worker: {MAX_WORKERS}")
    print("=" * 60 + "\n")
    
    results = []
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(scrape_single_channel, ch): ch 
            for ch in CHANNELS
        }
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
    
    elapsed = time.time() - start_time
    print(f"\n⏱️ Toplam süre: {elapsed:.1f} saniye")
    
    return results


# ============================================================
# M3U YAZ
# ============================================================

def write_m3u(results):
    results.sort(key=lambda x: (x[0]["group"], x[0]["name"]))
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")
        
        for ch, link in results:
            logo = ch.get("logo", "")
            
            f.write(f'#EXTINF:-1 group-title="{ch["group"]}"')
            if logo:
                f.write(f' tvg-logo="{logo}"')
            f.write(f' tvg-name="{ch["name"]}",{ch["name"]}\n')
            f.write(f'{link}\n\n')
    
    print(f"📁 {OUTPUT_FILE} kaydedildi ({len(results)} kanal)")


# ============================================================
# MAIN
# ============================================================

def main():
    results = scrape_all_parallel()
    
    if results:
        write_m3u(results)
    
    print("\n" + "=" * 60)
    print(f"✅ {len(results)}/{len(CHANNELS)} kanal bulundu")
    
    if len(results) < len(CHANNELS):
        found_ids = {c["id"] for c, _ in results}
        print("\n❌ Bulunamayanlar:")
        for c in CHANNELS:
            if c["id"] not in found_ids:
                print(f"   - {c['name']} (ID:{c['id']})")
    
    print("=" * 60)


if __name__ == "__main__":
    main()
