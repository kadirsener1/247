#!/usr/bin/env python3
"""
SportsBite Otomatik Scraper
1. JS bundle'dan tüm kanal bilgilerini çıkarır
2. forestgump.space/chX/track/Y URL'lerini kontrol eder
3. Çalışanları tv247.m3u'ya yazar (embed atlanır)
"""

import subprocess
import sys

def install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

try:
    import cloudscraper
except ImportError:
    install("cloudscraper")
    import cloudscraper

try:
    from bs4 import BeautifulSoup
except ImportError:
    install("beautifulsoup4")
    from bs4 import BeautifulSoup

import re
import json

BASE_URL = "https://sportsbite.org"
STREAM_BASE = "https://channels.forestgump.space"
OUTPUT_FILE = "tv247.m3u"


def create_scraper():
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )
    scraper.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': BASE_URL + '/',
    })
    return scraper


def get_js_bundle(scraper):
    """Ana sayfadan JS bundle URL'sini bul ve indir (sadece 1 kere)"""
    print("[1] Ana sayfa çekiliyor...")
    resp = scraper.get(BASE_URL, timeout=30)
    html = resp.text

    # index-XXXX.js dosyasını bul (ana bundle)
    match = re.search(r'src="(/assets/index-[^"]+\.js)"', html)
    if not match:
        print("  ❌ JS bundle bulunamadı")
        return None

    js_url = BASE_URL + match.group(1)
    print(f"  JS bundle: {js_url}")

    print("[2] JS bundle indiriliyor...")
    js_resp = scraper.get(js_url, timeout=30)
    js = js_resp.text
    print(f"  Boyut: {len(js)} karakter")
    return js


def extract_channels_from_js(js):
    """
    JS bundle içinden kanal bilgilerini çıkar
    Aranacak pattern'ler:
    - forestgump.space URL'leri
    - ch/track/ID kombinasyonları
    - Kanal adı + ID eşleşmeleri
    """
    print("\n[3] JS bundle analiz ediliyor...")
    channels = []

    # Pattern 1: Tam forestgump track URL'leri
    track_urls = re.findall(
        r'https?://channels\.forestgump\.space/ch(\d+)/track/(\d+)',
        js
    )
    if track_urls:
        print(f"  ✓ {len(track_urls)} track URL bulundu")
        for ch, track_id in track_urls:
            channels.append({
                'ch': int(ch),
                'track_id': int(track_id),
                'name': f'Channel {track_id}',
                'country': '',
                'url': f'{STREAM_BASE}/ch{ch}/track/{track_id}'
            })

    # Pattern 2: ch + track pattern'leri (URL'siz)
    ch_tracks = re.findall(r'/ch(\d+)/track/(\d+)', js)
    if ch_tracks:
        print(f"  ✓ {len(ch_tracks)} ch/track pattern bulundu")
        for ch, track_id in ch_tracks:
            url = f'{STREAM_BASE}/ch{ch}/track/{track_id}'
            if not any(c['url'] == url for c in channels):
                channels.append({
                    'ch': int(ch),
                    'track_id': int(track_id),
                    'name': f'Channel {track_id}',
                    'country': '',
                    'url': url
                })

    # Pattern 3: Kanal slug -> ID mapping objeleri
    # Örnek: {"5-usa":360,"espn":361} veya "5-usa":360
    slug_mappings = re.findall(
        r'["\']([a-zA-Z0-9\-]+)["\']?\s*:\s*(\d{2,4})',
        js
    )

    # Pattern 4: Kanal adı ile birlikte olan objeler
    # {name:"ESPN",id:360,country:"USA"} gibi
    name_patterns = [
        r'\{[^{}]*name\s*:\s*["\']([^"\']+)["\'][^{}]*(?:id|track|channel)\s*:\s*(\d+)[^{}]*\}',
        r'\{[^{}]*(?:id|track|channel)\s*:\s*(\d+)[^{}]*name\s*:\s*["\']([^"\']+)["\'][^{}]*\}',
    ]

    for pat in name_patterns:
        matches = re.findall(pat, js, re.IGNORECASE)
        if matches:
            print(f"  ✓ {len(matches)} isimli kanal bulundu")
            for m in matches:
                if len(m) == 2:
                    name, track_id = (m[0], m[1]) if not m[0].isdigit() else (m[1], m[0])
                    url = f'{STREAM_BASE}/ch1/track/{track_id}'
                    if not any(c['url'] == url for c in channels):
                        channels.append({
                            'ch': 1,
                            'track_id': int(track_id),
                            'name': name,
                            'country': '',
                            'url': url
                        })

    # Pattern 5: Ülke bilgisi arama
    country_pattern = r'country\s*:\s*["\']([A-Z]{2,3})["\']'
    countries_found = re.findall(country_pattern, js)
    if countries_found:
        print(f"  ✓ Ülke kodları: {list(set(countries_found))[:10]}")

    # Pattern 6: Büyük kanal listesi objeleri
    # [{slug:"espn",name:"ESPN",trackId:360,ch:1,country:"US"}]
    list_patterns = [
        r'slug\s*:\s*["\']([^"\']+)["\'][^{}]*?track(?:Id)?\s*:\s*(\d+)',
        r'track(?:Id)?\s*:\s*(\d+)[^{}]*?slug\s*:\s*["\']([^"\']+)["\']',
        r'["\']([a-z0-9\-]+)["\']\s*,\s*["\']([^"\']+)["\']\s*,\s*(\d+)',
    ]

    for pat in list_patterns:
        matches = re.findall(pat, js, re.IGNORECASE)
        if matches:
            print(f"  ✓ Slug-track eşleşme: {len(matches)} adet")

    # Eğer hiç bulamadıysak brute force range dene
    if not channels:
        print("  ⚠ JS'den kanal çıkarılamadı, brute force tarama yapılacak")

    return channels


def brute_force_scan(scraper, start=1, end=500, ch=1):
    """
    Belirli bir aralıkta track ID'lerini hızlıca dener
    HEAD request kullanır (çok hızlı)
    """
    print(f"\n[4] Brute force tarama: ch{ch}/track/{start}-{end}")
    working = []

    for track_id in range(start, end + 1):
        url = f"{STREAM_BASE}/ch{ch}/track/{track_id}"
        try:
            resp = scraper.head(url, timeout=3, allow_redirects=True)
            if resp.status_code == 200:
                working.append({
                    'ch': ch,
                    'track_id': track_id,
                    'name': f'Channel {track_id}',
                    'country': '',
                    'url': url
                })
                print(f"  ✅ {url}")
        except:
            pass

        # Her 50'de bir durum bildir
        if track_id % 50 == 0:
            print(f"  ... {track_id}/{end} tarandı ({len(working)} bulundu)")

    return working


def enrich_channel_names(channels, js):
    """
    Bulunan track ID'leri için JS'den kanal adlarını eşleştir
    """
    print(f"\n[5] Kanal adları eşleştiriliyor...")

    # JS'den bilinen kanal isimlerini çıkar
    name_map = {}

    # "ESPN": 360 veya espn: 360 formatları
    pairs = re.findall(
        r'["\']?([A-Za-z][A-Za-z0-9\s\-\.]+)["\']?\s*[:,]\s*(\d{2,4})',
        js
    )
    for name, track_id in pairs:
        name = name.strip()
        if len(name) > 2 and len(name) < 40:
            name_map[int(track_id)] = name

    # 360: "ESPN" formatı
    pairs2 = re.findall(
        r'(\d{2,4})\s*[:,]\s*["\']([A-Za-z][A-Za-z0-9\s\-\.]+)["\']',
        js
    )
    for track_id, name in pairs2:
        name = name.strip()
        if len(name) > 2 and len(name) < 40:
            name_map[int(track_id)] = name

    # Ülke eşleştirme
    country_map = {}
    country_pairs = re.findall(
        r'(\d{2,4})[^{}]*?country\s*:\s*["\']([A-Z]{2,3})["\']',
        js
    )
    for track_id, country in country_pairs:
        country_map[int(track_id)] = country

    # Kanalları güncelle
    updated = 0
    for ch in channels:
        tid = ch['track_id']
        if tid in name_map and ch['name'].startswith('Channel '):
            ch['name'] = name_map[tid]
            updated += 1
        if tid in country_map and not ch['country']:
            ch['country'] = country_map[tid]

    print(f"  {updated} kanal adı eşleştirildi")
    return channels


def write_m3u(channels):
    """M3U dosyasına yaz - sadece track URL'leri, embed atlanır"""
    # Tekrar eden URL'leri temizle
    seen = set()
    unique = []
    for ch in channels:
        if ch['url'] not in seen and '/track/' in ch['url']:
            seen.add(ch['url'])
            unique.append(ch)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n\n')

        for ch in unique:
            name = ch['name']
            country = ch['country']
            url = ch['url']

            group = country if country else "Sports"
            display = f"{name} ({country})" if country else name

            f.write(f'#EXTINF:-1 group-title="{group}" tvg-name="{name}",{display}\n')
            f.write(f'#EXTVLCOPT:http-referrer={BASE_URL}/\n')
            f.write(f'#EXTVLCOPT:http-user-agent=Mozilla/5.0\n')
            f.write(f'{url}\n\n')

    print(f"\n✅ {OUTPUT_FILE} oluşturuldu! ({len(unique)} kanal)")


def main():
    print("=" * 50)
    print("SportsBite Otomatik Scraper")
    print("=" * 50)

    scraper = create_scraper()
    all_channels = []

    # Adım 1-2: JS bundle indir
    js = get_js_bundle(scraper)

    if js:
        # Adım 3: JS'den kanal bilgilerini çıkar
        js_channels = extract_channels_from_js(js)
        all_channels.extend(js_channels)

    # Adım 4: Brute force tarama (JS'den bulunamayanlar için)
    # ch1/track/1 - ch1/track/500 aralığını tara
    bf_channels = brute_force_scan(scraper, start=1, end=500, ch=1)
    
    # JS'den bulunanlarla birleştir (tekrar olmasın)
    existing_urls = {c['url'] for c in all_channels}
    for ch in bf_channels:
        if ch['url'] not in existing_urls:
            all_channels.append(ch)

    if not all_channels:
        print("\n❌ Hiç kanal bulunamadı!")
        return

    # Adım 5: Kanal adlarını eşleştir
    if js:
        all_channels = enrich_channel_names(all_channels, js)

    # Adım 6: M3U yaz
    print(f"\n{'='*50}")
    print(f"Toplam: {len(all_channels)} kanal bulundu")
    print(f"{'='*50}")

    for ch in all_channels:
        status = "✅" if '/track/' in ch['url'] else "⏭️"
        print(f"  {status} {ch['name']:30s} {ch.get('country',''):5s} {ch['url']}")

    write_m3u(all_channels)


if __name__ == '__main__':
    main()
