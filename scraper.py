import subprocess
import sys
import os

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

import time
import re

def get_dlhd_player6_m3u(url: str = "https://dlhd.st/watch.php?id=1010", 
                          output_file: str = "player6.m3u",
                          player_number: int = 6):
    
    m3u8_links = []
    all_stream_links = []

    def handle_response(response):
        resp_url = response.url.lower()
        if ".m3u8" in resp_url or "stream" in resp_url or "live" in resp_url:
            all_stream_links.append(response.url)
            if ".m3u8" in resp_url:
                m3u8_links.append(response.url)
                print(f"✅ m3u8 bulundu: {response.url}")

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
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        
        page = context.new_page()
        page.on("response", handle_response)

        print(f"📡 Sayfa yükleniyor: {url}")
        
        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
        except Exception as e:
            print(f"⚠️ Yükleme hatası (devam ediliyor): {e}")
        
        time.sleep(3)

        print(f"🔍 Player {player_number} butonu aranıyor...")

        # Tüm butonları listele (debug)
        buttons = page.evaluate("""() => {
            let elements = [];
            document.querySelectorAll('a, button, div, span, li').forEach(el => {
                let text = el.textContent.trim();
                if (text.length < 30 && text.length > 0) {
                    elements.push({
                        tag: el.tagName,
                        text: text,
                        class: el.className,
                        href: el.href || ''
                    });
                }
            });
            return elements;
        }""")
        
        print("\n🔍 Sayfadaki butonlar:")
        for btn in buttons:
            if any(keyword in btn['text'].lower() for keyword in ['player', 'source', 'stream', 'link', str(player_number)]):
                print(f"  [{btn['tag']}] '{btn['text']}' class='{btn['class']}'")

        # Player 6 tıklama denemeleri
        clicked = False
        
        selectors_to_try = [
            f"text=Player {player_number}",
            f"text=PLAYER {player_number}",
            f"text=Source {player_number}",
            f"text=Link {player_number}",
            f"text=Stream {player_number}",
            f"[data-id='{player_number}']",
            f"[data-player='{player_number}']",
            f".player-{player_number}",
            f"#player-{player_number}",
        ]

        for selector in selectors_to_try:
            try:
                count = page.locator(selector).count()
                if count > 0:
                    page.locator(selector).first.click(timeout=5000)
                    print(f"✅ '{selector}' ile tıklandı!")
                    clicked = True
                    time.sleep(5)
                    break
            except Exception as e:
                continue

        if not clicked:
            # JavaScript ile zorla tıkla
            print("⚠️ Normal yöntem çalışmadı, JavaScript ile deneniyor...")
            result = page.evaluate(f"""() => {{
                let allElements = document.querySelectorAll('a, button, div, span, li, td');
                for (let el of allElements) {{
                    let text = el.textContent.trim();
                    if (text === 'Player {player_number}' || 
                        text === 'SOURCE {player_number}' ||
                        text === '{player_number}' ||
                        text.includes('Player {player_number}')) {{
                        el.click();
                        return 'clicked: ' + text;
                    }}
                }}
                return 'not found';
            }}""")
            print(f"JS sonucu: {result}")
            time.sleep(6)

        # Iframe içindeki linkleri de kontrol et
        print("\n🔍 Iframe kaynakları kontrol ediliyor...")
        iframes = page.evaluate("""() => {
            let frames = [];
            document.querySelectorAll('iframe').forEach(iframe => {
                frames.push({
                    src: iframe.src,
                    id: iframe.id,
                    name: iframe.name
                });
            });
            return frames;
        }""")
        
        for iframe in iframes:
            print(f"  Iframe: {iframe}")

        time.sleep(3)

        print(f"\n📊 Toplam bulunan linkler: {len(all_stream_links)}")
        print(f"📊 m3u8 linkleri: {len(m3u8_links)}")

        if m3u8_links:
            # En uygun linki seç
            stream_url = m3u8_links[-1]
            
            print("\n" + "="*60)
            print("🎯 Yayın Linki Bulundu!")
            print("="*60)
            for i, link in enumerate(m3u8_links, 1):
                print(f"{i}. {link}")
            print("="*60)

            # M3U dosyasına yaz
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for i, link in enumerate(m3u8_links, 1):
                    f.write(f"#EXTINF:-1,Player Stream {i} - dlhd.st\n")
                    f.write(link + "\n")

            print(f"\n📁 Dosya kaydedildi: {output_file}")
            browser.close()
            return m3u8_links
        
        else:
            print("❌ m3u8 linki bulunamadı!")
            # Tüm stream linklerini yaz
            if all_stream_links:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write("#EXTM3U\n")
                    for i, link in enumerate(all_stream_links, 1):
                        f.write(f"#EXTINF:-1,Stream {i}\n")
                        f.write(link + "\n")
                print(f"📁 Alternatif linkler kaydedildi: {output_file}")
            
            browser.close()
            return []


if __name__ == "__main__":
    # Kanal ID'leri - istediğin kadar ekleyebilirsin
    channels = [
        {"id": "1010", "name": "Kanal 1"},
    ]
    
    all_streams = []
    
    for channel in channels:
        url = f"https://dlhd.st/watch.php?id={channel['id']}"
        print(f"\n{'='*60}")
        print(f"🎬 İşleniyor: {channel['name']} (ID: {channel['id']})")
        print(f"{'='*60}")
        
        links = get_dlhd_player6_m3u(url, f"player6_{channel['id']}.m3u")
        all_streams.extend(links)
    
    # Ana M3U dosyası oluştur
    with open("streams.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for i, link in enumerate(all_streams, 1):
            f.write(f"#EXTINF:-1,Stream {i}\n")
            f.write(link + "\n")
    
    print("\n✅ Tüm işlemler tamamlandı!")
    print(f"📁 Ana dosya: streams.m3u")
