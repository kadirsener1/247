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
# ║  İstediğin kadar kanal ekle/çıkar                           ║
# ╚══════════════════════════════════════════════════════════════╝

CHANNELS = [
    # ────────── SPOR ──────────
    {"group": "Spor",   "id": "62", "name": "beIN Sports 1 TR", "logo": ""},
    {"group": "Spor",   "id": "63", "name": "beIN Sports 2 TR", "logo": ""},
    {"group": "Spor",   "id": "64", "name": "TRT Spor",         "logo": ""},
    # ────────── ULUSAL ──────────
    {"group": "Ulusal", "id": "1030", "name": "TRT 1",           "logo": ""},
    {"group": "Ulusal", "id": "1031", "name": "ATV",             "logo": ""},
    {"group": "Ulusal", "id": "1032", "name": "Show TV",         "logo": ""},
    # ────────── HABER ──────────
    {"group": "Haber",  "id": "1040", "name": "CNN Türk",        "logo": ""},
    {"group": "Haber",  "id": "1043", "name": "TRT Haber",       "logo": ""},
]

OUTPUT_FILE = "channels.m3u"
PLAYER_NUMBER = 6  # Sadece bu player'ın linki alınacak


def scrape_channel(page, channel):
    """Tek bir kanalın SADECE Player 6 m3u8 linkini bulur."""
    
    url = f"https://dlhd.st/watch.php?id={channel['id']}"
    
    print(f"\n  📡 Sayfa yükleniyor: {channel['name']} (ID: {channel['id']})")
    try:
        # Sadece sayfanın yüklenmesini bekle (ağ dinleyicisi HENÜZ kapalı)
        page.goto(url, wait_until="load", timeout=60000)
    except Exception as e:
        print(f"  ⚠️ Sayfa yüklenemedi: {e}")
        return None

    time.sleep(2)  # Butonların DOM'a yerleşmesi için bekle

    # ────────── PLAYER 6 BUTONUNU TIKLA ──────────
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
        # JavaScript ile zorla bul ve tıkla
        page.evaluate(f"""() => {{
            let found = false;
            document.querySelectorAll('a, button, div, span, li, td').forEach(el => {{
                let t = el.textContent.trim();
                if (t === 'Player {PLAYER_NUMBER}' || t === '{PLAYER_NUMBER}' || 
                    t.includes('Player {PLAYER_NUMBER}')) {{
                    el.click();
                    found = true;
                }}
            }});
        }}""")
        print(f"  ✅ Player {PLAYER_NUMBER} JS ile tıklandı")

    # ────────── SADECE ŞİMDİ DİNLEYİCİYİ AÇ ──────────
    # Bu sayede sayfa ilk açılırken gelen diğer player/reklam linkleri yakalanmaz!
    m3u8_links = []

    def handle_response(response):
        if ".m3u8" in response.url.lower():
            # Temizlik: Bariz reklam domainlerini ele
            if "doubleclick" not in response.url and "googlead" not in response.url:
                m3u8_links.append(response.url)
                print(f"  🎯 Player {PLAYER_NUMBER} yayın linki yakalandı!")

    page.on("response", handle_response)
    
    # Player 6'nın kendi yayın akışını çekmesi için bekle
    print(f"  ⏳ Player {PLAYER_NUMBER} yayını bekleniyor...")
    time.sleep(8) 
    
    # Dinleyiciyi kapat
    page.remove_listener("response", handle_response)

    if m3u8_links:
        # İlk yakalanan genellikle ana yayın linkidir
        return m3u8_links[0]
    else:
        print(f"  ❌ Player {PLAYER_NUMBER} linki bulunamadı!")
        return None


def main():
    print("=" * 60)
    print("🎬 DLHD.ST M3U Scraper (SADECE Player 6)")
    print(f"📋 Toplam kanal: {len(CHANNELS)}")
    print(f"📁 Çıktı: {OUTPUT_FILE}")
    print("=" * 60)

    results = []  

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )

        page = context.new_page()

        for i, channel in enumerate(CHANNELS, 1):
            print(f"\n{'─' * 50}")
            print(f"[{i}/{len(CHANNELS)}] {channel['group']} - {channel['name']}")
            
            link = scrape_channel(page, channel)
            
            if link:
                results.append((channel, link))
            
            time.sleep(2)  # Rate-limit koruması

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

    print(f"\n{'=' * 60}")
    print("📊 SONUÇ RAPORU")
    print(f"{'=' * 60}")
    print(f"  ✅ Bulunan   : {len(results)}/{len(CHANNELS)}")
    print(f"  📁 Dosya     : {OUTPUT_FILE}")
    print(f"{'=' * 60}")
    print("✅ Tamamlandı!")


if __name__ == "__main__":
    main()
