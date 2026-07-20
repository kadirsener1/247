from playwright.sync_api import sync_playwright
import time
import re

def get_dlhd_player6_m3u(url: str = "https://dlhd.st/watch.php?id=1010", output_file: str = "player6.m3u"):
    m3u8_links = []

    def handle_response(response):
        if ".m3u8" in response.url.lower():
            m3u8_links.append(response.url)
            print(f"✅ m3u8 bulundu: {response.url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()
        page.on("response", handle_response)

        print("Sayfa yükleniyor...")
        page.goto(url, wait_until="networkidle", timeout=60000)

        print("Player 6 butonu aranıyor ve tıklanıyor...")

        # Player 6 butonunu bulmak için birden fazla yöntem
        clicked = False
        selectors = [
            "text=Player 6",
            "text=PLAYER 6",
            "text=player 6",
            "//a[contains(., 'Player 6')]",
            "//button[contains(., 'Player 6')]",
            "//div[contains(., 'Player 6')]"
        ]

        for selector in selectors:
            try:
                element = page.locator(selector).first
                if element.is_visible() and element.count() > 0:
                    element.click(timeout=8000)
                    print(f"✅ '{selector}' ile Player 6 tıklandı.")
                    clicked = True
                    time.sleep(5)
                    break
            except:
                continue

        if not clicked:
            # Son çare: JavaScript ile tıkla
            print("JavaScript ile Player 6 aranıyor...")
            page.evaluate("""() => {
                let found = false;
                document.querySelectorAll('a, button, div, span').forEach(el => {
                    if (el.textContent.trim() === 'Player 6' || el.textContent.trim() === '6') {
                        el.click();
                        found = true;
                    }
                });
                return found;
            }""")
            time.sleep(6)

        # Biraz daha bekleyelim
        time.sleep(4)

        if m3u8_links:
            # Genellikle son bulunan en kaliteli veya Player 6'ya ait olan link olur
            stream_url = m3u8_links[-1]
            
            print("\n" + "="*60)
            print("🎯 Player 6 Yayın Linki Bulundu!")
            print("="*60)
            print(stream_url)
            print("="*60)

            # M3U dosyasına yaz
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                f.write("#EXTINF:-1,Player 6 - dlhd.st\n")
                f.write(stream_url + "\n")

            print(f"\n📁 Dosya kaydedildi: {output_file}")
            browser.close()
            return stream_url
        else:
            print("❌ m3u8 linki bulunamadı.")
            browser.close()
            return None


if __name__ == "__main__":
    get_dlhd_player6_m3u()
