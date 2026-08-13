#!/usr/bin/env python3
"""
SportsBite Hızlı Scraper
- STREAM_BASE domain'i otomatik bulur (değişse bile çalışır)
- Sadece track URL'lerini yazar (embed atlanır)
- Kanal adı + ülke bilgisi yazar
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
    # USA Kanalları
    ("ESPN", "USA", 1, 360),
    ("ESPN2", "USA", 1, 361),
    ("Fox Sports 1", "USA", 1, 362),
    ("Fox Sports 2", "USA", 1, 363),
    ("CBS Sports", "USA", 1, 364),
    ("NBC Sports", "USA", 1, 365),
    ("TNT Sports", "USA", 1, 366),
    ("USA Network", "USA", 1, 367),
    ("NFL Network", "USA", 1, 368),
    ("NBA TV", "USA", 1, 369),
    ("MLB Network", "USA", 1, 370),
    ("NHL Network", "USA", 1, 371),
    ("ESPN News", "USA", 1, 372),
    ("ESPNU", "USA", 1, 373),
    ("ESPN Deportes", "USA", 1, 374),
    ("Fox Deportes", "USA", 1, 375),
    ("beIN Sports", "USA", 1, 376),
    ("beIN Sports 2", "USA", 1, 377),

    # UK Kanalları
    ("Sky Sports Main Event", "UK", 1, 380),
    ("Sky Sports Premier League", "UK", 1, 381),
    ("Sky Sports Football", "UK", 1, 382),
    ("Sky Sports F1", "UK", 1, 383),
    ("Sky Sports Cricket", "UK", 1, 384),
    ("Sky Sports Golf", "UK", 1, 385),
    ("Sky Sports Tennis", "UK", 1, 386),
    ("Sky Sports NFL", "UK", 1, 387),
    ("Sky Sports Arena", "UK", 1, 388),
    ("Sky Sports Action", "UK", 1, 389),
    ("TNT Sports 1", "UK", 1, 390),
    ("TNT Sports 2", "UK", 1, 391),
    ("TNT Sports 3", "UK", 1, 392),
    ("TNT Sports 4", "UK", 1, 393),
    ("EuroSport 1", "UK", 1, 394),
    ("EuroSport 2", "UK", 1, 395),

    # Türkiye
    ("beIN Sports 1", "TR", 1, 62),
    ("beIN Sports 2", "TR", 1, 63),
    ("beIN Sports 3", "TR", 1, 64),
    ("beIN Sports 4", "TR", 1, 67),
    ("beIN Sports 5", "TR", 1, 1010),
    ("S Sport 2", "TR", 1, 405),
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
    """
    Ana sayfadan STREAM_BASE domain'ini otomatik bul.
    3 yöntem dener:
      1. HTML preconnect linklerinden
      2. JS bundle içinden
      3. Fallback (bilinen son domain)
    """
    print("\n[*] Stream domain otomatik aranıyor...")

    try:
        resp = scraper.get(BASE_URL, timeout=30)
        html = resp.text

        # --- Yöntem 1: preconnect / dns-prefetch linklerinden ---
        # <link rel="preconnect" href="https://channels.forestgump.space" />
        preconnect_urls = re.findall(
            r'<link[^>]+(?:preconnect|dns-prefetch)[^>]+href="(https?://[^"]+)"',
            html, re.IGNORECASE
        )

        # Bilinen gereksiz domain'leri filtrele
        skip = ['google', 'facebook', 'wsrv.nl', 'ibb.co', 'adsterra', 'piano']
        candidates = []
        for url in preconnect_urls:
            url_clean = url.rstrip('/')
            if not any(s in url_clean.lower() for s in skip):
                candidates.append(url_clean)

        if candidates:
            print(f"  Preconnect adayları: {candidates}")

            # Her adayı ch1/track/360 ile test et
            for candidate in candidates:
                test_url = f"{candidate}/ch1/track/360"
                try:
                    test = scraper.head(test_url, timeout=5, allow_redirects=True)
                    if test.status_code == 200:
                        print(f"  ✅ Çalışan domain bulundu: {candidate}")
                        return candidate
                except:
                    pass
                print(f"  ❌ {candidate} çalışmıyor")

        # --- Yöntem 2: JS bundle içinden ---
        js_match = re.search(r'src="(/assets/index-[^"]+\.js)"', html)
        if js_match:
            js_url = BASE_URL + js_match.group(1)
            print(f"  JS bundle kontrol ediliyor: {js_url}")
            try:
                js_resp = scraper.get(js_url, timeout=20)
                js = js_resp.text

                # https://XXXXX.YYYYY.ZZZ/ch formatında URL ara
                stream_domains = re.findall(
                    r'(https?://[a-zA-Z0-9\-\.]+\.[a-z]{2,})/ch\d+/',
                    js
                )
                if stream_domains:
                    domain = stream_domains[0].rstrip('/')
                    print(f"  ✅ JS'den domain bulundu: {domain}")
                    return domain

                # "channels." ile başlayan domain'leri ara
                ch_domains = re.findall(
                    r'(https?://channels\.[a-zA-Z0-9\-\.]+)',
                    js
                )
                if ch_domains:
                    domain = ch_domains[0].rstrip('/')
                    print(f"  ✅ JS'den channels domain bulundu: {domain}")
                    return domain
            except:
                pass

    except Exception as e:
        print(f"  ⚠ Hata: {e}")

    # --- Yöntem 3: Fallback ---
    print(f"  ⚠ Otomatik bulunamadı, fallback kullanılıyor: {FALLBACK_STREAM_BASE}")
    return FALLBACK_STREAM_BASE


def check_stream(scraper, stream_base, ch, track_id):
    """Tek bir stream URL'sini kontrol et - sadece track formatı"""
    url = f"{stream_base}/ch{ch}/track/{track_id}"
    try:
        resp = scraper.head(url, timeout=5, allow_redirects=True)
        return resp.status_code == 200, url
    except:
        return False, url


def main():
    print("=" * 50)
    print("SportsBite Hızlı Scraper")
    print("=" * 50)

    scraper = create_scraper()

    # 1. Stream domain'i otomatik bul
    stream_base = find_stream_base(scraper)
    print(f"\n[*] Kullanılan stream domain: {stream_base}")

    # 2. Kanalları tara
    print(f"\n[*] {len(CHANNELS)} kanal taranıyor...")
    working = []
    failed = []

    for name, country, ch, track_id in CHANNELS:
        ok, url = check_stream(scraper, stream_base, ch, track_id)
        if ok:
            working.append((name, country, url))
            print(f"  ✅ {name} ({country})")
        else:
            failed.append((name, country, url))
            print(f"  ❌ {name} ({country})")

    # 3. M3U dosyası oluştur
    print(f"\n{'='*50}")
    print(f"  ✅ Çalışan: {len(working)}")
    print(f"  ❌ Çalışmayan: {len(failed)}")
    print(f"{'='*50}")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n\n')

        for name, country, url in working:
            if '/embed/' in url:
                continue

            f.write(f'#EXTINF:-1 group-title="{country}" tvg-name="{name}",{name} ({country})\n')
            f.write(f'#EXTVLCOPT:http-referrer={BASE_URL}/\n')
            f.write(f'#EXTVLCOPT:http-user-agent=Mozilla/5.0\n')
            f.write(f'{url}\n\n')

    print(f"\n✅ {OUTPUT_FILE} oluşturuldu! ({len(working)} kanal)")

    # 4. Başarısız kanalları logla
    if failed:
        print(f"\n⚠ Çalışmayan kanallar:")
        for name, country, url in failed:
            print(f"  - {name} ({country}): {url}")


if __name__ == '__main__':
    main()
