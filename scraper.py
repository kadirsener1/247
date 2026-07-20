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


# ============================================================
# KANAL LİSTESİ
# 
# source: "dlhd" veya "tvnow"
# 
# dlhd kanalları   → id: "1010" şeklinde
# tvnow kanalları  → slug: "bein-sports-1-turkey" şeklinde
# ============================================================

CHANNELS = [
    # ──────── DLHD KANALLARI ───────{"group": "Spor",   "id": "62", "name": "beIN Sports 1 Turkey", "logo": ""},
    {"group": "Spor",   "id": "63", "name": "beIN Sports 2 Turkey", "logo": ""},
    {"group": "Spor",   "id": "64", "name": "beIN Sports 3 Turkey", "logo": ""},
    {"group": "Spor", "id": "67", "name": "beIN Sports 4 Turkey",                "logo": ""},
    {"group": "Spor", "id": "1010", "name": "beIN Sports 5 Turkey",                  "logo": ""},
    {"group": "Spor", "id": "1011", "name": "A Spor Turkey",                  "logo": ""},


    # ──────── TVNOW247 KANALLARI ────────
    {"source": "tvnow", "group": "Spor",   "slug": "bein-sports-1-turkey",  "name": "beIN Sports 1 TR (tvnow)",  "logo": ""},
    {"source": "tvnow", "group": "Spor",   "slug": "bein-sports-2-turkey",  "name": "beIN Sports 2 TR (tvnow)",  "logo": ""},
    {"source": "tvnow", "group": "Spor",   "slug": "bein-sports-3-turkey",  "name": "beIN Sports 3 TR (tvnow)",  "logo": ""},
    {"source": "tvnow", "group": "Spor",   "slug": "bein-sports-4-turkey",  "name": "beIN Sports 4 TR (tvnow)",  "logo": ""},
    {"source": "tvnow", "group": "Spor",   "slug": "bein-sports-5-turkey",  "name": "beIN Sports 5 TR (tvnow)",  "logo": ""},

]


# ============================================================
# ORTAK YARDIMCILAR
# ============================================================

SKIP = [
    "doubleclick", "googlead", "googlesyndication", "chatango",
    "histats", "adexchangerapid", "dtscout", "rs4k-adbanner",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".woff",
    ".ttf", ".ico", "gprofile.xml", "ads", "popunder", "popads",
]

def is_noise(url):
    u = url.lower()
    return any(s in u for s in SKIP)

def is_m3u8(url):
    return ".m3u8" in url.lower() and not is_noise(url)

def is_good_m3u8(url):
    """Audio/segment değil, ana playlist mi?"""
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
# DLHD SCRAPER (AYNI - HIZLI)
# ============================================================

def scrape_dlhd(channel):
    cid  = channel["id"]
    name = channel["name"]
    ref  = f"https://dlhd.st/watch.php?id={cid}"

    possible = [
        f"https://dlhd.st/player/stream-{cid}.php",
        f"https://dlhd.st/stream/stream-{cid}.php",
        f"https://dlhd.st/embed/stream-{cid}.php",
    ]

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
        page = ctx.new_page()
        found = []

        def on_resp(r):
            if is_m3u8(r.url):
                found.append(r.url)

        page.on("response", on_resp)

        for url in possible:
            found.clear()
            try:
                page.goto(url, referer=ref, wait_until="domcontentloaded",
                          timeout=TIMEOUT * 1000)
                page.wait_for_timeout(3000)
                try: page.locator("video").click(force=True, timeout=2000)
                except: pass
                page.wait_for_timeout(2000)

                best = pick_best(found)
                if best:
                    browser.close()
                    print(f"  ✅ [dlhd] {name}: {best[:70]}...")
                    return (channel, best)
            except:
                continue

        browser.close()
        print(f"  ❌ [dlhd] {name}: Bulunamadı")
        return None


# ============================================================
# TVNOW247 SCRAPER
# ============================================================

def scrape_tvnow(channel):
    slug = channel["slug"]
    name = channel["name"]
    page_url = f"https://tvnow247.top/watch/{slug}/"

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

        def on_resp(r):
            if is_m3u8(r.url):
                found.append(r.url)

        page.on("response", on_resp)

        print(f"  📡 [tvnow] {name}: {page_url}")

        try:
            page.goto(page_url, wait_until="domcontentloaded", timeout=TIMEOUT * 1000)
        except Exception as e:
            print(f"  ⚠️ [tvnow] Sayfa açılamadı: {e}")
            browser.close()
            return None

        page.wait_for_timeout(3000)

        # ── SERVER 1'İ DENE ──
        # Önce autoplay ile gelen linki bekle
        try: page.locator("video").click(force=True, timeout=2000)
        except: pass
        page.wait_for_timeout(3000)

        # Server 1 butonunu tıkla (zaten aktif olabilir)
        for sel in ["text=Server 1", "text=SERVER 1", "text=server 1"]:
            try:
                btn = page.locator(sel).first
                if btn.count() > 0:
                    btn.click(force=True, timeout=3000)
                    page.wait_for_timeout(4000)
                    try: page.locator("video").click(force=True, timeout=2000)
                    except: pass
                    page.wait_for_timeout(2000)
                    break
            except:
                continue

        # JS ile de dene
        page.evaluate("""
            [...document.querySelectorAll('a, button, div, span, li, td')]
            .find(el => /server\\s*1/i.test(el.textContent.trim()))
            ?.click()
        """)
        page.wait_for_timeout(3000)

        # iframe içindeki linki de yakala
        try:
            iframes = page.evaluate("""
                () => [...document.querySelectorAll('iframe')]
                    .map(f => f.src || f.getAttribute('src') || '')
                    .filter(s => s && s !== 'javascript:false')
            """)
            for iframe_src in iframes:
                if not is_noise(iframe_src):
                    sub = ctx.new_page()
                    sub.on("response", on_resp)
                    try:
                        sub.goto(iframe_src, referer=page_url,
                                wait_until="domcontentloaded", timeout=TIMEOUT * 1000)
                        sub.wait_for_timeout(4000)
                        try: sub.locator("video").click(force=True, timeout=2000)
                        except: pass
                        sub.wait_for_timeout(2000)
                    except:
                        pass
                    sub.close()
        except:
            pass

        # Server 1 sonucu
        best = pick_best(found)
        if best:
            browser.close()
            print(f"  ✅ [tvnow] {name} (Server 1): {best[:70]}...")
            return (channel, best)

        # ── SERVER 1 BAŞARISIZ → SERVER 2'Yİ DENE ──
        print(f"  ⚠️ [tvnow] {name}: Server 1 boş, Server 2 deneniyor...")
        found.clear()

        for sel in ["text=Server 2", "text=SERVER 2", "text=server 2"]:
            try:
                btn = page.locator(sel).first
                if btn.count() > 0:
                    btn.click(force=True, timeout=3000)
                    page.wait_for_timeout(4000)
                    try: page.locator("video").click(force=True, timeout=2000)
                    except: pass
                    page.wait_for_timeout(2000)
                    break
            except:
                continue

        page.evaluate("""
            [...document.querySelectorAll('a, button, div, span, li, td')]
            .find(el => /server\\s*2/i.test(el.textContent.trim()))
            ?.click()
        """)
        page.wait_for_timeout(3000)

        # Server 2 iframe
        try:
            iframes = page.evaluate("""
                () => [...document.querySelectorAll('iframe')]
                    .map(f => f.src || f.getAttribute('src') || '')
                    .filter(s => s && s !== 'javascript:false')
            """)
            for iframe_src in iframes:
                if not is_noise(iframe_src):
                    sub = ctx.new_page()
                    sub.on("response", on_resp)
                    try:
                        sub.goto(iframe_src, referer=page_url,
                                wait_until="domcontentloaded", timeout=TIMEOUT * 1000)
                        sub.wait_for_timeout(4000)
                        try: sub.locator("video").click(force=True, timeout=2000)
                        except: pass
                        sub.wait_for_timeout(2000)
                    except:
                        pass
                    sub.close()
        except:
            pass

        best = pick_best(found)
        if best:
            browser.close()
            print(f"  ✅ [tvnow] {name} (Server 2): {best[:70]}...")
            return (channel, best)

        browser.close()
        print(f"  ❌ [tvnow] {name}: Bulunamadı")
        return None


# ============================================================
# DAĞITICI: Kaynağa göre doğru scraper'ı çağır
# ============================================================

def scrape_channel(channel):
    source = channel.get("source", "")
    if source == "dlhd":
        return scrape_dlhd(channel)
    elif source == "tvnow":
        return scrape_tvnow(channel)
    else:
        print(f"  ❌ Bilinmeyen kaynak: {source}")
        return None


# ============================================================
# PARALEL TARAMA
# ============================================================

def scrape_all():
    print("=" * 60)
    print(f"🚀 HIZLI TARAMA")
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

    print(f"\n⏱️ Süre: {time.time()-start:.1f}s")
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
        found_ids = set()
        for c, _ in results:
            found_ids.add(c.get("id") or c.get("slug"))
        print("\n❌ Bulunamayanlar:")
        for c in CHANNELS:
            key = c.get("id") or c.get("slug")
            if key not in found_ids:
                print(f"   - [{c['source']}] {c['name']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
