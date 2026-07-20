import subprocess
import sys
import time

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
    subprocess.check_call(["playwright", "install", "chromium"])
    from playwright.sync_api import sync_playwright


def debug_page(url="https://dlhd.st/watch.php?id=1010"):
    
    all_requests = []
    all_responses = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", 
                  "--disable-dev-shm-usage", "--disable-gpu"]
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )

        page = context.new_page()

        # TÜM istek ve cevapları kaydet
        def on_request(request):
            all_requests.append(request.url)

        def on_response(response):
            all_responses.append(response.url)

        page.on("request", on_request)
        page.on("response", on_response)

        print(f"📡 Sayfa yükleniyor: {url}")
        try:
            page.goto(url, wait_until="load", timeout=60000)
        except Exception as e:
            print(f"⚠️ Hata: {e}")

        time.sleep(5)

        # ── SAYFA HTML'İNİ KAYDET ──
        html = page.content()
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("✅ Sayfa HTML'i kaydedildi: debug_page.html")

        # ── TÜM BUTON/LINK METİNLERİNİ GÖSTER ──
        print("\n" + "="*60)
        print("🔍 SAYFADAKİ TÜM TIKANILABILIR ELEMENTLER:")
        print("="*60)
        elements = page.evaluate("""() => {
            let results = [];
            document.querySelectorAll('a, button, div, span, li, td, input').forEach(el => {
                let text = el.textContent.trim();
                let onclick = el.getAttribute('onclick') || '';
                let href = el.getAttribute('href') || '';
                let cls = el.className || '';
                let id = el.id || '';
                let dataSrc = el.getAttribute('data-src') || '';
                let dataId = el.getAttribute('data-id') || '';
                
                if (text.length > 0 && text.length < 50) {
                    results.push({
                        tag: el.tagName,
                        text: text,
                        class: cls.substring(0, 50),
                        id: id,
                        onclick: onclick.substring(0, 100),
                        href: href.substring(0, 100),
                        dataSrc: dataSrc.substring(0, 100),
                        dataId: dataId
                    });
                }
            });
            return results;
        }""")

        for el in elements:
            if any(k in str(el).lower() for k in ['player', 'source', 'stream', 'link', 'btn', 'tab']):
                print(f"\n  TAG     : {el['tag']}")
                print(f"  TEXT    : {el['text']}")
                print(f"  CLASS   : {el['class']}")
                print(f"  ID      : {el['id']}")
                print(f"  ONCLICK : {el['onclick']}")
                print(f"  HREF    : {el['href']}")
                print(f"  DATA-SRC: {el['dataSrc']}")
                print(f"  DATA-ID : {el['dataId']}")

        # ── IFRAME KAYNAKLARINI GÖSTER ──
        print("\n" + "="*60)
        print("🔍 IFRAME KAYNAKLARI:")
        print("="*60)
        iframes = page.evaluate("""() => {
            let frames = [];
            document.querySelectorAll('iframe').forEach(iframe => {
                frames.push({
                    src: iframe.src,
                    id: iframe.id,
                    name: iframe.name,
                    class: iframe.className
                });
            });
            return frames;
        }""")
        for iframe in iframes:
            print(f"  {iframe}")

        # ── M3U8 ve STREAM LİNKLERİNİ GÖSTER ──
        print("\n" + "="*60)
        print("🔍 BULUNAN TÜM STREAM LİNKLERİ (sayfa yüklenirken):")
        print("="*60)
        stream_keywords = ['.m3u8', 'stream', 'live', 'playlist', 'chunklist', 'index.m3']
        for url in all_responses:
            if any(kw in url.lower() for kw in stream_keywords):
                print(f"  ✅ {url}")

        # ── ŞİMDİ PLAYER 6'YI TIKLA VE YENİ LİNKLERİ YAKALA ──
        print("\n" + "="*60)
        print("🔍 PLAYER 6 TIKLANIYOR, YENİ LİNKLER ARANIY OR...")
        print("="*60)

        after_click_responses = []

        def on_response_after(response):
            after_click_responses.append(response.url)

        page.on("response", on_response_after)

        # Tüm elementleri tıklamayı dene
        clicked_element = page.evaluate("""() => {
            let found = [];
            document.querySelectorAll('*').forEach(el => {
                let text = el.textContent.trim();
                if (text === 'Player 6' || text === '6' || 
                    text === 'SOURCE 6' || text === 'Source 6' ||
                    text === 'Stream 6' || text === 'Link 6' ||
                    text === 'PLAYER 6') {
                    found.push({
                        tag: el.tagName,
                        text: text,
                        class: el.className,
                        onclick: el.getAttribute('onclick') || '',
                        href: el.getAttribute('href') || ''
                    });
                    el.click();
                }
            });
            return found;
        }""")
        
        print(f"  Tıklanan element: {clicked_element}")

        time.sleep(8)

        print("\n  Tıklama sonrası gelen yeni linkler:")
        for url in after_click_responses:
            if any(kw in url.lower() for kw in ['.m3u8', 'stream', 'live', 'playlist']):
                print(f"  🎯 {url}")
            
        # ── TÜM LİNKLERİ DOSYAYA KAYDET ──
        with open("debug_all_urls.txt", "w", encoding="utf-8") as f:
            f.write("=== TÜM İSTEKLER ===\n")
            for u in all_requests:
                f.write(u + "\n")
            f.write("\n=== TIKLAMADAN SONRA GELEN YANITLAR ===\n")
            for u in after_click_responses:
                f.write(u + "\n")
        
        print("\n✅ Tüm URL'ler kaydedildi: debug_all_urls.txt")

        # ── EKRAN GÖRÜNTÜSÜ ──
        page.screenshot(path="debug_screenshot.png", full_page=True)
        print("✅ Ekran görüntüsü kaydedildi: debug_screenshot.png")

        browser.close()


if __name__ == "__main__":
    debug_page("https://dlhd.st/watch.php?id=1010")
