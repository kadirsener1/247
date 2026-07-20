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
# ║  group: M3U'daki grup adı                                   ║
# ║  id: dlhd.st'deki kanal ID'si                               ║
# ║  name: Kanalın görünen adı                                  ║
# ║  logo: (opsiyonel) Kanal logosu URL'si                      ║
# ╚══════════════════════════════════════════════════════════════╝

CHANNELS = [
    # ────────── SPOR ──────────
    {"group": "Spor",        "id": "62", "name": "beIN Sports 1 TR",     "logo": ""},
    {"group": "Spor",        "id": "63", "name": "beIN Sports 2 TR",     "logo": ""},
    {"group": "Spor",        "id": "64", "name": "beIN Sports 3 TR",     "logo": ""},
    {"group": "Spor",        "id": "67", "name": "beIN Sports 4 TR",     "logo": ""},
    {"group": "Spor",        "id": "1014", "name": "S Sport",              "logo": ""},
    {"group": "Spor",        "id": "1015", "name": "S Sport 2",            "logo": ""},
    {"group": "Spor",        "id": "1016", "name": "TRT Spor",             "logo": ""},
    {"group": "Spor",        "id": "1017", "name": "TRT Spor 2",           "logo": ""},
    {"group": "Spor",        "id": "1018", "name": "ESPN",                 "logo": ""},
    {"group": "Spor",        "id": "1019", "name": "Eurosport",            "logo": ""},

    # ────────── FUTBOL ──────────
    {"group": "Futbol",      "id": "1020", "name": "beIN Sports Max 1",    "logo": ""},
    {"group": "Futbol",      "id": "1021", "name": "beIN Sports Max 2",    "logo": ""},
    {"group": "Futbol",      "id": "1022", "name": "beIN Sports Haber",    "logo": ""},

    # ────────── ULUSAL ──────────
    {"group": "Ulusal",      "id": "1030", "name": "TRT 1",               "logo": ""},
    {"group": "Ulusal",      "id": "1031", "name": "ATV",                 "logo": ""},
    {"group": "Ulusal",      "id": "1032", "name": "Show TV",             "logo": ""},
    {"group": "Ulusal",      "id": "1033", "name": "Star TV",             "logo": ""},
    {"group": "Ulusal",      "id": "1034", "name": "Kanal D",             "logo": ""},
    {"group": "Ulusal",      "id": "1035", "name": "Fox TV",              "logo": ""},
    {"group": "Ulusal",      "id": "1036", "name": "TV8",                 "logo": ""},

    # ────────── HABER ──────────
    {"group": "Haber",       "id": "1040", "name": "CNN Türk",            "logo": ""},
    {"group": "Haber",       "id": "1041", "name": "NTV",                 "logo": ""},
    {"group": "Haber",       "id": "1042", "name": "Habertürk TV",        "logo": ""},
    {"group": "Haber",       "id": "1043", "name": "TRT Haber",           "logo": ""},

    # ────────── SİNEMA ──────────
    {"group": "Sinema",      "id": "1050", "name": "FX",                  "logo": ""},
    {"group": "Sinema",      "id": "1051", "name": "TV2",                 "logo": ""},
    {"group": "Sinema",      "id": "1052", "name": "Kanal 7",             "logo": ""},

    # ────────── YABANCI SPOR ──────────
    {"group": "Yabancı Spor","id": "1060", "name": "Sky Sports Premier League", "logo": ""},
    {"group": "Yabancı Spor","id": "1061", "name": "Sky Sports Football",       "logo": ""},
    {"group": "Yabancı Spor","id": "1062", "name": "BT Sport 1",                "logo": ""},
    {"group": "Yabancı Spor","id": "1063", "name": "BT Sport 2",                "logo": ""},
    {"group": "Yabancı Spor","id": "1064", "name": "DAZN 1",                    "logo": ""},
]


OUTPUT_FILE = "channels.m3u"
PLAYER_NUMBER = 6


def scrape_channel(page, channel):
    """Tek bir kanalın m3u8 linkini bulur."""
    
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
                time.sleep(5)
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
        time.sleep(6)

    time.sleep(3)

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
    print("🎬 DLHD.ST M3U Scraper - Çoklu Kanal")
    print(f"📋 Toplam kanal: {len(CHANNELS)}")
    print(f"🎯 Player: {PLAYER_NUMBER}")
    print(f"📁 Çıktı: {OUTPUT_FILE}")
    print("=" * 60)

    results = []  # (channel, link) listesi

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
            
            # Rate limit koruması
            time.sleep(2)

        browser.close()

    # ────────── M3U DOSYASI OLUŞTUR ──────────
    print(f"\n{'=' * 60}")
    print("📝 M3U dosyası oluşturuluyor...")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U url-tvg="http://epg.streamstv.me/epg/guide-turkey.xml.gz"\n\n')

        # Gruplara göre sırala
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

    # Grupları listele
    groups = {}
    for ch, link in results:
        g = ch["group"]
        groups[g] = groups.get(g, 0) + 1

    print("\n  📂 Grup Dağılımı:")
    for g, count in sorted(groups.items()):
        print(f"     {g}: {count} kanal")

    print(f"\n{'=' * 60}")
    print("✅ Tamamlandı!")

    if failed > 0:
        print("\n  ⚠️ Bulunamayan kanallar:")
        found_ids = {ch["id"] for ch, _ in results}
        for ch in CHANNELS:
            if ch["id"] not in found_ids:
                print(f"     ❌ [{ch['group']}] {ch['name']} (ID: {ch['id']})")


if __name__ == "__main__":
    main()
