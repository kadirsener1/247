#!/usr/bin/env python3
"""
SportsBite Scraper - Sadece forestgump.space iframe'lerini bulur
İlk test: sadece 5-usa kanalı
"""

import re
import time
import cloudscraper
from bs4 import BeautifulSoup

BASE_URL = "https://sportsbite.org"
OUTPUT_FILE = "tv247.m3u"

# ŞİMDİLİK SADECE BU KANAL
TEST_CHANNELS = [
    {"slug": "5-usa", "name": "Channel 5 USA"},
]


def create_scraper():
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )
    scraper.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/120.0.0.0 Safari/537.36',
        'Referer': BASE_URL,
    })
    return scraper


def find_forestgump_iframe(scraper, channel_slug):
    """
    Kanal sayfasını aç, SADECE forestgump.space iframe URL'sini bul.
    """
    url = f"{BASE_URL}/watch/channel/{channel_slug}"
    print(f"\n[*] Sayfa açılıyor: {url}")

    try:
        resp = scraper.get(url, timeout=30)
        print(f"[*] HTTP Status: {resp.status_code}")

        if resp.status_code != 200:
            print(f"[!] Sayfa açılamadı")
            return None

        html = resp.text
        print(f"[*] Sayfa boyutu: {len(html)} karakter")

        # --- YÖNTEM 1: BeautifulSoup ile iframe bul ---
        soup = BeautifulSoup(html, 'html.parser')
        iframes = soup.find_all('iframe')
        print(f"[*] Toplam iframe sayısı: {len(iframes)}")

        for i, iframe in enumerate(iframes):
            src = iframe.get('src', '') or iframe.get('data-src', '')
            print(f"    iframe[{i}] src = {src}")

            if 'forestgump.space' in src:
                print(f"[✓] forestgump iframe BULUNDU: {src}")
                return src

        # --- YÖNTEM 2: Regex ile HTML içinde ara ---
        print(f"[*] Regex ile forestgump URL aranıyor...")
        pattern = r'(https?://[^\s"\'<>]*forestgump\.space[^\s"\'<>]*)'
        matches = re.findall(pattern, html, re.IGNORECASE)

        if matches:
            for m in matches:
                print(f"    regex buldu: {m}")
            # İlk eşleşmeyi döndür
            clean_url = matches[0].rstrip('\\').rstrip("'").rstrip('"')
            print(f"[✓] forestgump URL BULUNDU: {clean_url}")
            return clean_url

        # --- YÖNTEM 3: JS değişkenlerinde ara ---
        print(f"[*] JS değişkenlerinde aranıyor...")
        js_patterns = [
            r'src\s*[=:]\s*["\']([^"\']*forestgump\.space[^"\']*)["\']',
            r'url\s*[=:]\s*["\']([^"\']*forestgump\.space[^"\']*)["\']',
            r'source\s*[=:]\s*["\']([^"\']*forestgump\.space[^"\']*)["\']',
            r'iframe\.src\s*=\s*["\']([^"\']*forestgump\.space[^"\']*)["\']',
        ]

        for pat in js_patterns:
            match = re.search(pat, html, re.IGNORECASE)
            if match:
                found_url = match.group(1)
                print(f"[✓] JS'de forestgump URL BULUNDU: {found_url}")
                return found_url

        # Bulunamadıysa debug bilgisi ver
        print(f"[!] forestgump.space iframe bulunamadı!")
        print(f"[DEBUG] 'forestgump' kelimesi HTML'de var mı: {'forestgump' in html.lower()}")
        print(f"[DEBUG] 'iframe' kelimesi HTML'de var mı: {'iframe' in html.lower()}")
        print(f"[DEBUG] 'embed' kelimesi HTML'de var mı: {'embed' in html.lower()}")

        # İlk 5000 karakteri debug için göster
        if 'iframe' in html.lower():
            print(f"\n[DEBUG] iframe içeren satırlar:")
            for line in html.split('\n'):
                if 'iframe' in line.lower():
                    print(f"  >>> {line.strip()[:200]}")

        return None

    except Exception as e:
        print(f"[!] HATA: {e}")
        return None


def find_m3u8_in_iframe(scraper, iframe_url, referer):
    """
    forestgump iframe sayfasına gir, m3u8 URL'si varsa bul.
    """
    print(f"\n[*] iframe sayfası açılıyor: {iframe_url}")

    try:
        resp = scraper.get(iframe_url, timeout=30, headers={
            'Referer': referer,
        })
        print(f"[*] iframe HTTP Status: {resp.status_code}")

        if resp.status_code != 200:
            return None

        html = resp.text
        print(f"[*] iframe sayfa boyutu: {len(html)} karakter")

        # m3u8 URL'si ara
        m3u8_pattern = r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)'
        matches = re.findall(m3u8_pattern, html)

        if matches:
            for m in matches:
                print(f"    m3u8 bulundu: {m}")
            return matches[0]

        print(f"[*] m3u8 bulunamadı, iframe URL'si direkt kullanılacak")
        return None

    except Exception as e:
        print(f"[!] iframe HATA: {e}")
        return None


def write_m3u(results):
    """Sonuçları M3U dosyasına yaz."""
    lines = ['#EXTM3U']
    lines.append('')

    for ch in results:
        name = ch['name']
        stream = ch['stream_url']
        referer = ch['page_url']

        lines.append(f'#EXTINF:-1 group-title="Sports" tvg-name="{name}",{name}')
        lines.append(f'#EXTVLCOPT:http-referrer={referer}')
        lines.append(f'#EXTVLCOPT:http-user-agent=Mozilla/5.0')
        lines.append(stream)
        lines.append('')

    content = '\n'.join(lines)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"\n[✓] {OUTPUT_FILE} yazıldı ({len(results)} kanal)")


def main():
    print("=" * 50)
    print("SportsBite Scraper - forestgump.space")
    print("=" * 50)

    scraper = create_scraper()
    results = []

    for channel in TEST_CHANNELS:
        slug = channel['slug']
        name = channel['name']
        page_url = f"{BASE_URL}/watch/channel/{slug}"

        print(f"\n{'─' * 40}")
        print(f"Kanal: {name} ({slug})")
        print(f"{'─' * 40}")

        # 1. Sayfadaki forestgump iframe'ini bul
        iframe_url = find_forestgump_iframe(scraper, slug)

        if not iframe_url:
            print(f"[✗] {name}: iframe bulunamadı")
            continue

        # 2. iframe içinde m3u8 var mı bak
        m3u8_url = find_m3u8_in_iframe(scraper, iframe_url, page_url)

        # m3u8 bulunduysa onu, bulunamadıysa iframe URL'sini kullan
        stream_url = m3u8_url if m3u8_url else iframe_url

        results.append({
            'name': name,
            'stream_url': stream_url,
            'page_url': page_url,
            'iframe_url': iframe_url,
        })

        print(f"\n[✓] {name}")
        print(f"    iframe : {iframe_url}")
        print(f"    stream : {stream_url}")

        time.sleep(1)

    # 3. M3U yaz
    print(f"\n{'=' * 50}")
    if results:
        write_m3u(results)
        print("\nOluşan M3U içeriği:")
        print("─" * 40)
        with open(OUTPUT_FILE, 'r') as f:
            print(f.read())
    else:
        print("[✗] Hiç sonuç bulunamadı!")


if __name__ == '__main__':
    main()
