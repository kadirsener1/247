import subprocess
import sys
import time
import re
from urllib.parse import urljoin

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
    subprocess.check_call(["playwright", "install", "chromium"])
    from playwright.sync_api import sync_playwright


# ============================================================
# AYARLAR
# ============================================================

PLAYER_NUMBER = 6
OUTPUT_FILE   = "channels.m3u"
BASE_URL      = "https://dlhd.st"

CHANNELS = [
    {"group": "Spor",   "id": "62", "name": "beIN Sports 1 Turkey", "logo": ""},
    {"group": "Spor",   "id": "63", "name": "beIN Sports 2 Turkey", "logo": ""},
    {"group": "Spor",   "id": "64", "name": "beIN Sports 3 Turkey", "logo": ""},
    {"group": "Spor",   "id": "67", "name": "beIN Sports 4 Turkey", "logo": ""},
    {"group": "Spor",   "id": "1010", "name": "beIN Sports 5 Turkey", "logo": ""},
    {"group": "Spor",   "id": "1011", "name": "A Spor", "logo": ""}
    {"group": "Ulusal", "id": "1000", "name": "Atv",                "logo": ""},
{"group": "Ulusal", "id": "1001", "name": "Kanal D",                "logo": ""},
{"group": "Ulusal", "id": "1002", "name": "Show Tv",                "logo": ""},
{"group": "Ulusal", "id": "1003", "name": "Now",                "logo": ""},
{"group": "Ulusal", "id": "1004", "name": "Star Tv",                "logo": ""},
{"group": "Ulusal", "id": "1005", "name": "Tv 8",                "logo": ""},
]


# ============================================================
# YARDIMCI
# ============================================================

SKIP_DOMAINS = [
    "doubleclick", "googlead", "googlesyndication",
    "chatango", "histats", "adexchangerapid", "dtscout",
    "rs4k-adbanner", ".png", ".jpg", ".jpeg", ".gif",
    ".svg", ".css", ".woff", ".ttf", ".ico", "gprofile.xml",
    "phantemlis",   # reklam CDN
]

def is_noise(url: str) -> bool:
    u = url.lower()
    return any(x in u for x in SKIP_DOMAINS)

def is_media(url: str) -> bool:
    if is_noise(url):
        return False
    u = url.lower()
    return ".m3u8" in u or ".mpd" in u

def media_score(url: str) -> int:
    u = url.lower()
    score = 0
    if "master"   in u: score += 100
    if "index.m3u8" in u: score += 90
    if u.endswith(".m3u8"): score += 40
    # Ceza: audio / segment alt playlistler
    for bad in ["tracks-", "mono.m3u8", "/audio/", "chunklist",
                "media_", "seg-", "segment", "frag"]:
        if bad in u:
            score -= 120
    return score

def best_media(urls):
    urls = list(dict.fromkeys(u for u in urls if is_media(u)))
    if not urls:
        return None
    urls.sort(key=media_score, reverse=True)
    return urls[0]


# ============================================================
# PLAYER-N IFRAME URL'Sİ BUL
# ============================================================

def get_stream_php_url(page, channel_id: str, player_n: int = 6):
    """
    watch.php sayfasını açar, Player N butonuna tıklar,
    playerFrame iframe'inin src'sini döner.
    """
    watch_url = f"{BASE_URL}/watch.php?id={channel_id}"
    print(f"  📡 watch.php açılıyor: {watch_url}")

    page.goto(watch_url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)

    # Player N butonunu bul
    btn = page.locator(f"button.player-btn >> text=Player {player_n}").first
    if btn.count() == 0:
        print(f"  ❌ Player {player_n} butonu yok")
        return None

    # Tıkla
    try:
        btn.click(force=True, timeout=5000)
    except:
        page.evaluate(f"""
            [...document.querySelectorAll('button.player-btn')]
            .find(b => b.textContent.trim() === 'Player {player_n}')
            ?.click()
        """)

    print(f"  ✅ Player {player_n} tıklandı, iframe bekleniyor...")

    # iframe src değişene kadar bekle (max 10 sn)
    stream_url = None
    for _ in range(20):
        page.wait_for_timeout(500)
        src = page.evaluate("""
            () => {
                const f = document.querySelector('iframe#playerFrame');
                return f ? (f.getAttribute('src') || f.src || '') : '';
            }
        """)
        if src and src != "javascript:false" and "stream-" in src:
            stream_url = urljoin(BASE_URL, src)
            break

    if stream_url:
        print(f"  🎯 Stream PHP: {stream_url}")
    else:
        print(f"  ❌ Stream PHP URL bulunamadı")

    return stream_url


# ============================================================
# STREAM.PHP SAYFASINDAN M3U8 YAKALA
# ============================================================

def capture_m3u8(context, stream_php_url: str, referer: str):
    """
    stream-XXXX.php sayfasını DOĞRU Referer ile açar,
    içindeki m3u8 linkini yakalar.
    """
    page = context.new_page()
    media_found = []

    def on_response(resp):
        if is_media(resp.url):
            media_found.append(resp.url)
            print(f"    🎯 m3u8 yakalandı: {resp.url}")

    page.on("response", on_response)

    print(f"  📄 Stream sayfası açılıyor (referer={referer})")

    try:
        page.goto(
            stream_php_url,
            wait_until="domcontentloaded",
            timeout=60000,
            # Referer header'ını watch.php olarak gönder
            referer=referer
        )
    except Exception as e:
        print(f"  ⚠️ Açma hatası: {e}")
        page.close()
        return None

    # Yayının başlaması için bekle (autoplay tetikle)
    for i in range(20):
        page.wait_for_timeout(500)
        if i == 3:
            try:
                page.locator("body").click(force=True, timeout=1000)
            except:
                pass
        if i == 8:
            # play butonunu tıklamayı dene
            try:
                page.locator("video").click(force=True, timeout=1000)
            except:
                pass

    # Sayfanın HTML'inden de tara
    try:
        html = page.content()
        for m in re.findall(
            r'https?://[^\s\'"<>]+\.m3u8[^\s\'"<>]*', html, flags=re.I
        ):
            if is_media(m):
                media_found.append(m)
    except:
        pass

    # Nested iframe varsa onları da dene
    if not media_found:
        try:
            iframe_srcs = page.evaluate("""
                () => [...document.querySelectorAll('iframe')]
                    .map(f => f.getAttribute('src') || f.src || '')
                    .filter(Boolean)
            """)
            for src in iframe_srcs:
                if src and src != "javascript:false" and not is_noise(src):
                    nested_url = urljoin(stream_php_url, src)
                    print(f"  🔍 Nested iframe deneniyor: {nested_url}")
                    nested = capture_m3u8(context, nested_url, referer=stream_php_url)
                    if nested:
                        media_found.append(nested)
                        break
        except:
            pass

    page.close()

    return best_media(media_found)


# ============================================================
# TEK KANALI İŞLE
# ============================================================

def scrape_channel(context, channel):
    channel_id = channel["id"]
    watch_url   = f"{BASE_URL}/watch.php?id={channel_id}"

    # 1) watch.php üzerinden Player 6 iframe URL'sini al
    nav_page = context.new_page()
    stream_php = get_stream_php_url(nav_page, channel_id, PLAYER_NUMBER)
    nav_page.close()

    if not stream_php:
        # Fallback: Player 6 için stream URL'yi tahmin et
        guessed = f"{BASE_URL}/player/stream-{channel_id}.php"
        print(f"  ⚠️ Fallback URL deneniyor: {guessed}")
        stream_php = guessed

    # 2) Stream sayfasını DOĞRU Referer ile aç ve m3u8 yakala
    media_url = capture_m3u8(context, stream_php, referer=watch_url)
    return media_url


# ============================================================
# M3U DOSYASI YAZ
# ============================================================

def write_m3u(results):
    results.sort(key=lambda x: (x[0]["group"], x[0]["name"]))
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")
        for ch, link in results:
            logo = ch.get("logo", "")
            line = f'#EXTINF:-1 group-title="{ch["group"]}"'
            if logo:
                line += f' tvg-logo="{logo}"'
            line += f' tvg-name="{ch["name"]}",{ch["name"]}\n'
            f.write(line)
            f.write(link + "\n\n")
    print(f"\n📁 {OUTPUT_FILE} yazıldı ({len(results)} kanal)")


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print(f"DLHD Player {PLAYER_NUMBER} Scraper")
    print(f"Toplam kanal : {len(CHANNELS)}")
    print(f"Çıktı        : {OUTPUT_FILE}")
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
            timezone_id="Europe/Istanbul",
        )
        context.add_init_script("""
            Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
            Object.defineProperty(navigator,'languages',{get:()=>['tr-TR','tr','en-US','en']});
            window.chrome={runtime:{}};
        """)

        for i, ch in enumerate(CHANNELS, 1):
            print(f"\n{'─'*60}")
            print(f"[{i}/{len(CHANNELS)}] {ch['group']} – {ch['name']} (ID:{ch['id']})")
            try:
                link = scrape_channel(context, ch)
            except Exception as e:
                print(f"  ❌ Hata: {e}")
                link = None

            if link:
                print(f"  ✅ BULUNDU: {link}")
                results.append((ch, link))
            else:
                print(f"  ❌ Link bulunamadı")

            time.sleep(2)

        browser.close()

    write_m3u(results)

    print("\n" + "=" * 60)
    print(f"✅ Tamamlandı: {len(results)}/{len(CHANNELS)} kanal bulundu")
    if len(results) < len(CHANNELS):
        found = {c["id"] for c, _ in results}
        for c in CHANNELS:
            if c["id"] not in found:
                print(f"  ❌ {c['name']} (ID:{c['id']})")
    print("=" * 60)


if __name__ == "__main__":
    main()
