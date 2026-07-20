import subprocess
import sys
import os
import time

# Playwright yoksa otomatik kur
def install_playwright():
    subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
    subprocess.check_call(["playwright", "install", "chromium"])
    subprocess.check_call(["playwright", "install-deps", "chromium"])

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright bulunamadı, kuruluyor...")
    install_playwright()
    from playwright.sync_api import sync_playwright


# ╔══════════════════════════════════════════════════════════════╗
# ║                    KANAL LİSTESİ                             ║
# ╚══════════════════════════════════════════════════════════════╝

CHANNELS = [
    # ────────── SPOR ──────────
    {"group": "Spor",        "id": "62", "name": "beIN Sports 1 TR",     "logo": ""},
    {"group": "Spor",        "id": "63", "name": "beIN Sports 2 TR",     "logo": ""},
    {"group": "Spor",        "id": "64", "name": "beIN Sports 3 TR",     "logo": ""},
    # ────────── ULUSAL ──────────
    {"group": "Ulusal",      "id": "1030", "name": "TRT 1",               "logo": ""},
    {"group": "Ulusal",      "id": "1031", "name": "ATV",                 "logo": ""},
    # ────────── HABER ──────────
    {"group": "Haber",       "id": "1040", "name": "CNN Türk",            "logo": ""},
]

OUTPUT_FILE = "channels.m3u"
PLAYER_NUMBER = 6


def scrape_channel(page, channel):
    """Tek bir kanalın sadece Player 6 m3u8 linkini bulur."""
    
    url = f"https://dlhd.st/watch.php?id={channel['id']}"
    m3u8_links = []

    def handle_response(response):
        if ".m3u8" in response.url.lower():
            m3u8_links.append(response.url)

    page.on("response", handle_response)

    print(f"\n  📡 Yükleniyor: {channel['name']} (ID: {channel['id']})")
    
    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
    except Exception as e:
        print(f"  ⚠️ Sayfa yüklenemedi: {e}")
        page.remove_listener("response", handle_response)
        return None

    time.sleep(3)

    # ╔══════════════════════════════════════════════════════════════╗
    # ║ KRİTİK NOKTA: Player 6 öncesi yakalanan tüm linkleri sil!    ║
    # ║ Böylece sayfa açılışındaki varsayılan player linki yok olur. ║
    # ╚══════════════════════════════════════════════════════════════╝
    m3u8_links.clear()

    # Player butonunu tıkla
    selectors = [
        f"text=Player {PLAYER_NUMBER}",
        f"text=PLAYER {PLAYER_NUMBER}",
        f"text=Source {PLAYER_NUMBER}",
        f"[data-id='{PLAYER_NUMBER}']",
        f"[data-player='{PLAYER_NUMBER}']",
    ]

    clicked = False
    for selector in selectors:
        try:
            if page.locator(selector).count() > 0:
                page.locator(selector).first.click(timeout=5000)
                print(f"  ✅ Player {PLAYER_NUMBER} tıklandı")
                clicked = True
                break
        except:
            continue

    if not clicked:
        page.evaluate(f"""() => {{
            document.querySelectorAll('a, button, div, span, li, td').forEach(el => {{
                let t = el.textContent.trim();
                if (t === 'Player {PLAYER_NUMBER}' || t === '{PLAYER_NUMBER}' || 
                    t.includes('Player {PLAYER_NUMBER}')) {{
                    el.click();
                }}
            }});
        }}""")

    # Player 6 tıklandıktan sonra linkin yüklenmesini bekle (Max 15 saniye)
    timeout = 15
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if m3u8_links:
            break
        time.sleep(1)

    page.remove_listener("response", handle_response)

    if m3u8_links:
        best_link = m3u8_links[-1]
        print(f"  🎯 Link bulundu: {best_link[:80]}...")
        return best_link
    else:
        print(f"  ❌ Link bulunamadı!")
        return None


def main():
    print("=" * 60)
    print("🎬 DLHD.ST M3U Scraper - Sadece Player 6")
    print(f"📋 Toplam kanal: {len(CHANNELS)}")
    print(f"📁 Çıktı: {OUTPUT_FILE}")
    print("=" * 60)

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )

        page = context.new_page()

        for i, channel in enumerate(CHANNELS, 1):
            print(f"\n{'─' * 50}")
            print(f"[{i}/{len(CHANNELS)}] {channel['group']} - {channel['name']}")
            
            link = scrape_channel(page, channel)
            
            if link:
                results.append((channel, link))
            
            # Rate limit koruması için kanallar arası kısa bekleme
            time.sleep(2)

        browser.close()

    # ────────── M3U DOSYASI OLUŞTUR ──────────
    print(f"\n{'=' * 60}")
    print("📝 M3U dosyası oluşturuluyor...")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U url-tvg="http://epg.streamstv.me/epg/guide-turkey.xml.gz"\n\n')

        results.sort(key=lambda x: (x[0]["group"], x[0]["name"]))

        for channel, link in results:
            group = channel["group"]
            name = channel["name"]
            logo = channel.get("logo", "")
            
            f.write(f'#EXTINF:-1 group-title="{group}"')
            if logo:
                f.write(f' tvg-logo="{logo}"')
            f.write(f' tvg-name="{name}",{name}\n')
            f.write(f'{link}\n\n')

    # ────────── ÖZET ──────────
    found = len(results)
    total = len(CHANNELS)
    failed = total - found

    print(f"\n{'=' * 60}")
    print("📊 SONUÇ RAPORU")
    print(f"{'=' * 60}")
    print(f"  ✅ Bulunan   : {found}/{total}")
    print(f"  ❌ Başarısız  : {failed}/{total}")
    print(f"  📁 Dosya      : {OUTPUT_FILE}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
