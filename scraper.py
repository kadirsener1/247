#!/usr/bin/env python3
"""
SportsBite Hızlı Scraper
- Stream domain otomatik bulunur
- TÜM kanallar M3U'ya yazılır (yayın olmasa bile)
- embed atlanır, sadece track URL'leri
- Kanal adı + ülke bilgisi
"""

import subprocess
import sys
import re

def install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

try:
    import cloudscraper
except ImportError:
    install("cloudscraper")
    import cloudscraper

BASE_URL = "https://sportsbite.org"
FALLBACK_STREAM_BASE = "https://channels.forestgump.space"
OUTPUT_FILE = "tv247.m3u"

# =====================================================
# KANAL LİSTESİ
# format: (kanal_adı, ülke, ch_numarası, track_id)
# =====================================================
CHANNELS = [
    # USA
    ("ESPN", "USA", 1, 360),
    ("ESPN2", "USA", 1, 361),
    ("Fox Sports 1", "USA", 1, 362),


    # UK
    ("Sky Sports Main Event", "UK", 1, 380),
    ("Sky Sports Premier League", "UK", 1, 381),
    ("Sky Sports Football", "UK", 1, 382),
    ("Sky Sports F1", "UK", 1, 383),
    ("Sky Sports Cricket", "UK", 1, 384),
   

    # Türkiye
    ("beIN Sports 1", "TR", 1, 62),
    ("beIN Sports 2", "TR", 1, 63),
    ("beIN Sports 3", "TR", 1, 64),
    ("beIN Sports 4", "TR", 1, 67),
    ("beIN Sports 5", "TR", 1, 1010),
    ("TRT Spor", "TR", 1, 406),
    ("TRT Spor 2", "TR", 1, 407),

    # Hindistan / Pakistan
    ("Star Sports 1", "IN", 1, 410),
    ("Star Sports 2", "IN", 1, 411),
    ("Star Sports 3", "IN", 1, 412),
    ("Sony TEN 1", "IN", 1, 413),
    ("Sony TEN 2", "IN", 1, 414),
    ("Sony TEN 3", "IN", 1, 415),
    ("Willow Cricket", "IN", 1, 416),
    ("PTV Sports", "PK", 1, 417),
    ("Ten Sports", "PK", 1, 418),

    # Arap / MENA
    ("beIN Sports 1 AR", "AR", 1, 420),
    ("beIN Sports 2 AR", "AR", 1, 421),
    ("beIN Sports 3 AR", "AR", 1, 422),
    ("beIN Sports Premium 1", "AR", 1, 423),
    ("beIN Sports Premium 2", "AR", 1, 424),
    ("SSC 1", "SA", 1, 425),
    ("SSC 2", "SA", 1, 426),

    # Avrupa
    ("DAZN 1", "DE", 1, 430),
    ("DAZN 2", "DE", 1, 431),
    ("Canal+ Sport", "FR", 1, 432),
    ("Movistar Deportes", "ES", 1, 433),
    ("Sport TV 1", "PT", 1, 434),
    ("SuperSport", "ZA", 1, 435),
]


def create_scraper():
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )
    scraper.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': BASE_URL + '/',
    })
    return scraper


def find_stream_base(scraper):
    """Ana sayfadan stream domain'ini otomatik bul"""
    print("[*] Stream domain aranıyor...")

    try:
        resp = scraper.get(BASE_URL, timeout=30)
        html = resp.text

        # 1. preconnect / dns-prefetch linklerinden
        preconnect_urls = re.findall(
            r'<link[^>]+(?:preconnect|dns-prefetch)[^>]+href="(https?://[^"]+)"',
            html, re.IGNORECASE
        )

        skip = ['google', 'facebook', 'wsrv.nl', 'ibb.co', 'adsterra', 'piano', 'goog']
        candidates = []
        for url in preconnect_urls:
            url_clean = url.rstrip('/')
            if not any(s in url_clean.lower() for s in skip):
                candidates.append(url_clean)

        if candidates:
            print(f"  Adaylar: {candidates}")
            for candidate in candidates:
                test_url = f"{candidate}/ch1/track/360"
                try:
                    test = scraper.head(test_url, timeout=5, allow_redirects=True)
                    if test.status_code == 200:
                        print(f"  ✅ Domain bulundu: {candidate}")
                        return candidate
                except:
                    pass

        # 2. JS bundle içinden
        js_match = re.search(r'src="(/assets/index-[^"]+\.js)"', html)
        if js_match:
            js_url = BASE_URL + js_match.group(1)
            try:
                js_resp = scraper.get(js_url, timeout=20)
                js = js_resp.text
                domains = re.findall(r'(https?://[a-zA-Z0-9\-\.]+\.[a-z]{2,})/ch\d+/', js)
                if domains:
                    print(f"  ✅ JS'den domain: {domains[0]}")
                    return domains[0].rstrip('/')
            except:
                pass

    except Exception as e:
        print(f"  ⚠ Hata: {e}")

    print(f"  ⚠ Fallback: {FALLBACK_STREAM_BASE}")
    return FALLBACK_STREAM_BASE


def main():
    print("=" * 50)
    print("SportsBite Hızlı Scraper")
    print(f"Toplam {len(CHANNELS)} kanal")
    print("=" * 50)

    scraper = create_scraper()

    # 1. Domain bul
    stream_base = find_stream_base(scraper)
    print(f"[*] Stream domain: {stream_base}\n")

    # 2. Tüm kanalları M3U'ya yaz (kontrol etmeden)
    #    Çünkü bazı kanallar sadece yayın varken aktif
    print(f"[*] {len(CHANNELS)} kanal M3U'ya yazılıyor...")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n\n')

        for name, country, ch, track_id in CHANNELS:
            url = f"{stream_base}/ch{ch}/track/{track_id}"

            f.write(f'#EXTINF:-1 group-title="{country}" tvg-name="{name}",{name} ({country})\n')
            f.write(f'#EXTVLCOPT:http-referrer={BASE_URL}/\n')
            f.write(f'#EXTVLCOPT:http-user-agent=Mozilla/5.0\n')
            f.write(f'{url}\n\n')

            print(f"  ✅ {name} ({country}) → ch{ch}/track/{track_id}")

    print(f"\n{'='*50}")
    print(f"✅ {OUTPUT_FILE} oluşturuldu! ({len(CHANNELS)} kanal)")
    print(f"{'='*50}")

    # 3. Hızlı durum kontrolü (sadece bilgi amaçlı)
    print(f"\n[*] Hızlı durum kontrolü...")
    live_count = 0
    offline_count = 0

    for name, country, ch, track_id in CHANNELS:
        url = f"{stream_base}/ch{ch}/track/{track_id}"
        try:
            resp = scraper.head(url, timeout=3, allow_redirects=True)
            if resp.status_code == 200:
                live_count += 1
            else:
                offline_count += 1
        except:
            offline_count += 1

    print(f"\n  📺 Şu an yayında: {live_count}")
    print(f"  💤 Şu an kapalı:  {offline_count}")
    print(f"  📋 M3U'da toplam: {len(CHANNELS)}")


if __name__ == '__main__':
    main()
