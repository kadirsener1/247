import os
import sys
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

# ─────────────────────────────────────────────
# YAPILANDIRMA
# ─────────────────────────────────────────────
OUTPUT_FILE = "tv247tr.m3u"
CHANNELS_FILE = "channelstr.txt"
BASE_EMBED_URL = "https://tvnow247.top/embed-r4/"


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def get_token_stream_with_playwright(channel_slug):
    """
    Playwright kullanarak embed-r4 sayfasını açar, JavaScript'in 
    çalışmasını bekler ve ağ trafiğinden token'lı .m3u8 linkini yakalar.
    """
    target_url = f"{BASE_EMBED_URL}{channel_slug}"
    log(f"  Tarayıcı açılıyor ve taranıyor: {target_url}")
    
    captured_url = None

    with sync_playwright() as p:
        # Tarayıcıyı headless (arayüzsüz) modda başlatıyoruz
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        )

        # Ağ trafiğini (Network requests) dinle
        def handle_request(request):
            nonlocal captured_url
            url = request.url
            # .m3u8 içeren ve token parametresi barındıran gerçek yayın linkini yakala
            if ".m3u8" in url and ("token=" in url or "src=r4" in url):
                if not captured_url:
                    captured_url = url

        page.on("request", handle_request)

        try:
            # Sayfaya git ve JavaScript'in yüklenmesini bekle
            page.goto(target_url, timeout=40000, wait_until="networkidle")
            
            # Linkin düşmesi için birkaç saniye ek bekleme
            start_time = time.time()
            while not captured_url and (time.time() - start_time) < 10:
                time.sleep(0.5)
                
        except Exception as e:
            log(f"  Tarayıcı yükleme hatası: {e}")
        finally:
            browser.close()

    return captured_url


def load_channels():
    channels = []
    if os.path.exists(CHANNELS_FILE):
        with open(CHANNELS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('|')
                slug = parts[0].strip()
                name = parts[1].strip() if len(parts) > 1 else slug.replace('-', ' ').title()
                channels.append({'slug': slug, 'name': name})
    else:
        channels = [
            {'slug': 'bein-sports-1-turkey', 'name': 'beIN Sports 1'},
        ]
    return channels


def generate_m3u(results):
    lines = ['#EXTM3U']
    lines.append(f'# Updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}')
    lines.append('')
    
    for ch in results:
        if ch.get('url'):
            lines.append(
                f'#EXTINF:-1 tvg-id="{ch["slug"]}" '
                f'tvg-name="{ch["name"]}" '
                f'group-title="Bein-TV247-Server4",{ch["name"]}'
            )
            lines.append(ch['url'])
            lines.append('')
    
    content = '\n'.join(lines)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    
    log(f"\n✓ {OUTPUT_FILE} oluşturuldu")
    return content


def main():
    log("=" * 50)
    log("TV247 M3U Generator - Playwright Tarayıcı Sürümü")
    log("=" * 50)
    
    # Playwright bağımlılık kontrolü bilgilendirmesi
    log("[Bilgi] Bu kodun çalışması için sisteminizde Playwright kurulu olmalıdır.")
    log("[Bilgi] Kurulum komutu: pip install playwright && playwright install chromium\n")

    channels = load_channels()
    log(f"{len(channels)} kanal işlenecek\n")
    
    results = []
    
    for i, ch in enumerate(channels):
        log(f"\n[{i+1}/{len(channels)}] {ch['name']}")
        log("-" * 40)
        
        stream_url = get_token_stream_with_playwright(ch['slug'])
        
        results.append({
            'slug': ch['slug'],
            'name': ch['name'],
            'url': stream_url
        })
        
        if stream_url:
            log(f"✓ Yakalandı: {stream_url[:90]}...")
        else:
            log(f"✗ Token bulunamadı")
        
        time.sleep(1)
    
    log("\n" + "=" * 50)
    content = generate_m3u(results)
    print(f"\n{content}")
    
    found = sum(1 for r in results if r.get('url'))
    log(f"\nSONUÇ: {found}/{len(results)} kanal bulundu")
    
    return 0 if found > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
