import subprocess
import sys
import time
import re
from urllib.parse import urljoin

# Gerekirse otomatik kur
def install_playwright():
    subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
    subprocess.check_call(["playwright", "install", "chromium"])

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright bulunamadı, kuruluyor...")
    install_playwright()
    from playwright.sync_api import sync_playwright


# ============================================================
# AYARLAR
# ============================================================

PLAYER_NUMBER = 6
OUTPUT_FILE = "channels.m3u"

CHANNELS = [
    {"group": "Spor",   "id": "1010", "name": "beIN Sports 5 Turkey", "logo": ""},
    # {"group": "Spor", "id": "1011", "name": "Kanal 2", "logo": ""},
    # {"group": "Ulusal", "id": "1030", "name": "TRT 1", "logo": ""},
]


# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================

def abs_url(base, value):
    if not value:
        return None
    return urljoin(base, value)

def is_ad_or_noise(url: str) -> bool:
    u = url.lower()
    bad = [
        "doubleclick",
        "googlead",
        "googlesyndication",
        "chatango",
        "histats",
        "adexchangerapid",
        "dtscout",
        "rs4k-adbanner",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".css",
        ".woff",
        ".ttf",
        ".ico",
        "gprofile.xml",
    ]
    return any(x in u for x in bad)

def is_media_url(url: str) -> bool:
    u = url.lower()
    if is_ad_or_noise(u):
        return False
    return (".m3u8" in u) or (".mpd" in u)

def media_score(url: str) -> int:
    """
    En iyi linki seçmek için puanlama.
    Master playlist'leri öne alır, audio track / chunk linklerini geri atar.
    """
    u = url.lower()
    score = 0

    if "master" in u:
        score += 100
    if "index.m3u8" in u:
        score += 90
    if u.endswith(".m3u8"):
        score += 40
    if ".mpd" in u:
        score += 20

    # İstemediğimiz alt playlist / audio track / segment benzeri linkler
    if "tracks-" in u:
        score -= 120
    if "mono.m3u8" in u:
        score -= 120
    if "/audio/" in u:
        score -= 120
    if "audio" in u:
        score -= 80
    if "chunklist" in u:
        score -= 60
    if "media_" in u:
        score -= 60
    if "seg-" in u or "segment" in u or "frag" in u:
        score -= 60

    # Çok uzun query bazen alt kalite / tokenlı varyant olabilir ama tamamen eleme yok
    score -= min(len(u) // 50, 20)

    return score

def pick_best_media(urls):
    urls = list(dict.fromkeys(urls))  # uniq
    urls = [u for u in urls if is_media_url(u)]
    if not urls:
        return None
    urls.sort(key=media_score, reverse=True)
    return urls[0]

def extract_media_from_html(html: str):
    found = []

    # Direkt .m3u8 / .mpd linkleri
    for m in re.findall(r'https?://[^\'"\s<>]+(?:\.m3u8|\.mpd)[^\'"\s<>]*', html, flags=re.I):
        found.append(m)

    return found


# ============================================================
# PLAYER 6 IFRAME BULMA
# ============================================================

def get_player6_iframe_url(page, watch_url: str, player_number: int = 6):
    print(f"  📡 Açılıyor: {watch_url}")
    page.goto(watch_url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)

    # İlk iframe src
    try:
        old_src = page.locator("iframe#playerFrame").get_attribute("src")
    except:
        old_src = None

    old_src_abs = abs_url(watch_url, old_src) if old_src else None
    print(f"  ℹ️ İlk iframe: {old_src_abs}")

    # Player 6 butonu
    button = page.locator("button.player-btn").filter(has_text=f"Player {player_number}").first
    if button.count() == 0:
        print(f"  ❌ Player {player_number} butonu bulunamadı")
        return None

    # Tıklama denemeleri
    clicked = False
    for attempt in range(3):
        try:
            if attempt == 0:
                button.click(timeout=5000)
            elif attempt == 1:
                button.click(timeout=5000, force=True)
            else:
                page.evaluate(
                    """(n) => {
                        const btn = [...document.querySelectorAll('button.player-btn')]
                            .find(b => b.textContent.trim() === `Player ${n}`);
                        if (btn) btn.click();
                    }""",
                    player_number
                )
            clicked = True
            break
        except Exception:
            pass

    if not clicked:
        print(f"  ❌ Player {player_number} tıklanamadı")
        return None

    print(f"  ✅ Player {player_number} tıklandı, iframe değişimi bekleniyor...")
    page.wait_for_timeout(2000)

    last_src = old_src_abs
    became_active = False

    for _ in range(30):
        state = page.evaluate(
            """(n) => {
                const btn = [...document.querySelectorAll('button.player-btn')]
                    .find(b => b.textContent.trim() === `Player ${n}`);
                const iframe = document.querySelector('iframe#playerFrame');
                return {
                    active: !!(btn && btn.className.includes('is-active')),
                    iframeSrc: iframe ? (iframe.getAttribute('src') || iframe.src || '') : ''
                };
            }""",
            player_number
        )

        iframe_src = state.get("iframeSrc") or ""
        if iframe_src and iframe_src != "javascript:false":
            last_src = abs_url(watch_url, iframe_src)

        if state.get("active"):
            became_active = True

        # aktif olduysa ve geçerli bir iframe src varsa dön
        if became_active and last_src:
            print(f"  🎯 Player {player_number} iframe: {last_src}")
            return last_src

        page.wait_for_timeout(500)

    print(f"  ❌ Player {player_number} için iframe bulunamadı")
    return None


# ============================================================
# IFRAME SAYFASINDAN GERÇEK YAYINI YAKALA
# ============================================================

def capture_media_from_page(context, page_url: str, depth: int = 0, max_depth: int = 2):
    if depth > max_depth:
        return None

    indent = "    " + ("  " * depth)
    page = context.new_page()

    media_urls = []

    def on_response(response):
        url = response.url
        if is_media_url(url):
            media_urls.append(url)
            print(f"{indent}🎯 Media yakalandı: {url}")

    page.on("response", on_response)

    try:
        print(f"{indent}📄 Açılıyor: {page_url}")
        page.goto(page_url, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        print(f"{indent}⚠️ Açma hatası: {e}")
        page.close()
        return None

    # Biraz bekle
    for i in range(20):
        if i in (3, 8, 12):
            # autoplay tetiklemek için hafif tıklama
            try:
                page.locator("body").click(timeout=1000, force=True)
            except:
                pass
        page.wait_for_timeout(500)

    # HTML içinden de tara
    try:
        html = page.content()
        for u in extract_media_from_html(html):
            if is_media_url(u):
                media_urls.append(u)
    except:
        pass

    best = pick_best_media(media_urls)
    if best:
        print(f"{indent}✅ En iyi yayın: {best}")
        page.close()
        return best

    # Nested iframe fallback
    try:
        iframe_urls = page.evaluate(
            """() => Array.from(document.querySelectorAll('iframe'))
                .map(f => f.getAttribute('src') || f.src || '')
                .filter(Boolean)"""
        )
    except:
        iframe_urls = []

    iframe_urls = [abs_url(page_url, u) for u in iframe_urls if u and u != "javascript:false"]
    iframe_urls = [u for u in iframe_urls if not is_ad_or_noise(u)]

    page.close()

    for iframe_url in iframe_urls[:5]:
        nested = capture_media_from_page(context, iframe_url, depth + 1, max_depth)
        if nested:
            return nested

    return None


# ============================================================
# TEK KANALI İŞLE
# ============================================================

def scrape_channel(context, channel):
    watch_url = f"https://dlhd.st/watch.php?id={channel['id']}"
    page = context.new_page()

    try:
        iframe_url = get_player6_iframe_url(page, watch_url, PLAYER_NUMBER)
    except Exception as e:
        print(f"  ❌ Kanal işlenemedi: {e}")
        page.close()
        return None

    page.close()

    if not iframe_url:
        return None

    media_url = capture_media_from_page(context, iframe_url)
    return media_url


# ============================================================
# M3U YAZ
# ============================================================

def write_m3u(results, output_file):
    with open(output_file, "w", encoding="utf-8") as f:
        f.write('#EXTM3U\n\n')

        results.sort(key=lambda x: (x[0]["group"], x[0]["name"]))

        for channel, link in results:
            name = channel["name"]
            group = channel["group"]
            logo = channel.get("logo", "")

            line = f'#EXTINF:-1 group-title="{group}"'
            if logo:
                line += f' tvg-logo="{logo}"'
            line += f' tvg-name="{name}",{name}\n'

            f.write(line)
            f.write(link + "\n\n")


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("DLHD Player 6 Scraper")
    print(f"Toplam kanal: {len(CHANNELS)}")
    print(f"Seçilen player: {PLAYER_NUMBER}")
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
                "--disable-blink-features=AutomationControlled",
            ]
        )

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 720},
            locale="tr-TR",
            timezone_id="Europe/Istanbul"
        )

        # Basit anti-bot iyileştirme
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'languages', {get: () => ['tr-TR', 'tr', 'en-US', 'en']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4]});
            window.chrome = { runtime: {} };
        """)

        for i, channel in enumerate(CHANNELS, 1):
            print("\n" + "─" * 60)
            print(f"[{i}/{len(CHANNELS)}] {channel['group']} - {channel['name']} (ID: {channel['id']})")

            try:
                media_link = scrape_channel(context, channel)
            except Exception as e:
                print(f"  ❌ Hata: {e}")
                media_link = None

            if media_link:
                results.append((channel, media_link))
            else:
                print("  ❌ Player 6 ana link bulunamadı")

            time.sleep(2)

        browser.close()

    write_m3u(results, OUTPUT_FILE)

    print("\n" + "=" * 60)
    print("SONUÇ")
    print(f"Bulunan kanal: {len(results)}/{len(CHANNELS)}")
    print(f"M3U dosyası  : {OUTPUT_FILE}")
    print("=" * 60)

    if len(results) < len(CHANNELS):
        found_ids = {c["id"] for c, _ in results}
        print("Bulunamayanlar:")
        for c in CHANNELS:
            if c["id"] not in found_ids:
                print(f" - [{c['group']}] {c['name']} ({c['id']})")


if __name__ == "__main__":
    main()
