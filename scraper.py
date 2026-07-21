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
MAX_WORKERS = 4
TIMEOUT     = 15
BASE_URL    = "https://tvnow247.top"


# ============================================================
# KANAL LİSTESİ
# slug = URL'deki son kısım: tvnow247.top/watch/{slug}/
# ============================================================

CHANNELS = [
    # ──────── SPOR ────────
    {"group": "Spor", "slug": "bein-sports-1-turkey",  "name": "bein-sports-1-turkey",    "logo": ""},
    {"group": "Spor", "slug": "bein-sports-2-turkey",  "name": "beIN Sports 2 TR",    "logo": ""},
    {"group": "Spor", "slug": "bein-sports-3-turkey",  "name": "beIN Sports 3 TR",    "logo": ""},
    {"group": "Spor", "slug": "bein-sports-4-turkey",  "name": "beIN Sports 4 TR",    "logo": ""},
    {"group": "Spor", "slug": "bein-sports-5-turkey",  "name": "beIN Sports 5 TR",    "logo": ""},

]


# ============================================================
# YARDIMCILAR
# ============================================================

SKIP = [
    "doubleclick", "googlead", "googlesyndication", "chatango",
    "histats", "adexchange", "dtscout", "popunder", "popads",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".css",
    ".woff", ".ttf", ".ico", "ads",
]

def is_noise(url):
    u = url.lower()
    return any(s in u for s in SKIP)

def is_m3u8(url):
    return ".m3u8" in url.lower() and not is_noise(url)

def is_good_m3u8(url):
    u = url.lower()
    bad = ["track", "mono", "audio", "seg-", "segment", "frag", "subtitle"]
    return is_m3u8(url) and not any(b in u for b in bad)

def pick_best(urls):
    good = [u for u in urls if is_good_m3u8(u)]
    if good:
        for u in good:
            if "index.m3u8" in u.lower() or "master" in u.lower():
                return u
        return good[0]
    m3u = [u for u in urls if is_m3u8(u)]
    return m3u[0] if m3u else None


# ============================================================
# SERVER TIKLAMA
# ============================================================

def click_server(page, server_num):
    """Server N butonunu tıklar"""
    for sel in [f"text=Server {server_num}", 
                f"text=SERVER {server_num}", 
                f"text=server {server_num}"]:
        try:
            btn = page.locator(sel).first
            if btn.count() > 0:
                btn.click(force=True, timeout=3000)
                return True
        except:
            continue

    # JS fallback
    result = page.evaluate(f"""
        (() => {{
            const el = [...document.querySelectorAll('a, button, div, span, li, td')]
                .find(e => /server\\s*{server_num}/i.test(e.textContent.trim()));
            if (el) {{ el.click(); return true; }}
            return false;
        }})()
    """)
    return result


# ============================================================
# IFRAME İÇİNDEN M3U8 YAKALA
# ============================================================

def capture_from_iframes(ctx, page, page_url, found):
    """Sayfadaki iframe'leri açıp m3u8 arar"""
    try:
        iframes = page.evaluate("""
            () => [...document.querySelectorAll('iframe')]
                .map(f => f.src || f.getAttribute('src') || '')
                .filter(s => s && s !== 'javascript:false')
        """)
    except:
        return

    for src in iframes:
        if is_noise(src):
            continue
        sub = ctx.new_page()
        sub.on("response", lambda r: found.append(r.url) if is_m3u8(r.url) else None)
        try:
            sub.goto(src, referer=page_url,
                     wait_until="domcontentloaded", timeout=TIMEOUT * 1000)
            sub.wait_for_timeout(4000)
            try:
                sub.locator("video").click(force=True, timeout=2000)
            except:
                pass
            sub.wait_for_timeout(2000)
        except:
            pass
        sub.close()


# ============================================================
# TEK KANAL TARA
# ============================================================

def scrape_channel(channel):
    slug = channel["slug"]
    name = channel["name"]
    url  = f"{BASE_URL}/watch/{slug}/"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox",
                  "--disable-dev-shm-usage", "--disable-gpu"]
        )
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 720},
        )
        ctx.add_init_script("""
            Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
            window.chrome={runtime:{}};
        """)

        page = ctx.new_page()
        found = []

        page.on("response", lambda r: found.append(r.url) if is_m3u8(r.url) else None)

        # Sayfayı aç
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT * 1000)
        except:
            browser.close()
            print(f"  ❌ {name}: Sayfa açılamadı")
            return None

        page.wait_for_timeout(3000)

        # ── SERVER 1 ──
        click_server(page, 1)
        page.wait_for_timeout(3000)
        try:
            page.locator("video").click(force=True, timeout=2000)
        except:
            pass
        page.wait_for_timeout(2000)

        # iframe kontrol
        capture_from_iframes(ctx, page, url, found)

        best = pick_best(found)
        if best:
            browser.close()
            print(f"  ✅ {name} (Server 1): {best[:70]}...")
            return (channel, best)

        # ── SERVER 1 BAŞARISIZ → SERVER 2 ──
        print(f"  ⚠️ {name}: Server 1 boş → Server 2...")
        found.clear()

        click_server(page, 2)
        page.wait_for_timeout(3000)
        try:
            page.locator("video").click(force=True, timeout=2000)
        except:
            pass
        page.wait_for_timeout(2000)

        # iframe kontrol
        capture_from_iframes(ctx, page, url, found)

        best = pick_best(found)
        if best:
            browser.close()
            print(f"  ✅ {name} (Server 2): {best[:70]}...")
            return (channel, best)

        browser.close()
        print(f"  ❌ {name}: Bulunamadı")
        return None


# ============================================================
# PARALEL TARAMA
# ============================================================

def scrape_all():
    print("=" * 60)
    print(f"🚀 TVNow247 Scraper")
    print(f"📋 Kanal: {len(CHANNELS)} | Worker: {MAX_WORKERS}")
    print("=" * 60 + "\n")

    results = []
    start = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(scrape_channel, ch): ch for ch in CHANNELS}
        for f in as_completed(futures):
            r = f.result()
            if r:
                results.append(r)

    print(f"\n⏱️ Süre: {time.time() - start:.1f}s")
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
    print(f"📁 {OUTPUT_FILE} → {len(results)} kanal")


# ============================================================
# MAIN
# ============================================================

def main():
    results = scrape_all()
    if results:
        write_m3u(results)

    print("\n" + "=" * 60)
    print(f"✅ {len(results)}/{len(CHANNELS)} kanal bulundu")

    if len(results) < len(CHANNELS):
        found_slugs = {c["slug"] for c, _ in results}
        print("\n❌ Bulunamayanlar:")
        for c in CHANNELS:
            if c["slug"] not in found_slugs:
                print(f"   - {c['name']} ({c['slug']})")
    print("=" * 60)


if __name__ == "__main__":
    main()
