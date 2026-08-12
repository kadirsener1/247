#!/usr/bin/env python3
"""
SportsBite Scraper - DEBUG VERSION
Sayfadaki tüm forestgump linklerini bulur
"""

import re
import cloudscraper
from bs4 import BeautifulSoup

BASE_URL = "https://sportsbite.org"
CHANNEL_URL = f"{BASE_URL}/watch/channel/5-usa"


def create_scraper():
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )
    scraper.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': BASE_URL,
    })
    return scraper


def debug_page(scraper):
    print(f"\n{'='*60}")
    print(f"DEBUG: {CHANNEL_URL}")
    print(f"{'='*60}\n")

    resp = scraper.get(CHANNEL_URL, timeout=30)
    print(f"[*] Status: {resp.status_code}")
    print(f"[*] Content-Length: {len(resp.text)} chars\n")

    html = resp.text

    # 1. Tüm iframe'leri listele
    print("=" * 40)
    print("TÜM IFRAME'LER:")
    print("=" * 40)
    soup = BeautifulSoup(html, 'html.parser')
    iframes = soup.find_all('iframe')
    
    if iframes:
        for i, iframe in enumerate(iframes):
            print(f"\n[iframe {i}]")
            for attr in ['src', 'data-src', 'data-lazy-src', 'data-url']:
                val = iframe.get(attr)
                if val:
                    print(f"  {attr}: {val}")
            # Tüm attribute'ları göster
            print(f"  all attrs: {dict(iframe.attrs)}")
    else:
        print("  Hiç iframe bulunamadı!")

    # 2. forestgump.space içeren TÜM URL'leri bul
    print("\n" + "=" * 40)
    print("FORESTGUMP.SPACE İÇEREN TÜM URL'LER:")
    print("=" * 40)
    
    # Geniş regex - tüm forestgump linklerini yakala
    patterns = [
        r'https?://[^\s"\'<>\\\)]+forestgump\.space[^\s"\'<>\\\)]*',
        r'channels\.forestgump\.space[^\s"\'<>\\\)]*',
    ]
    
    all_matches = set()
    for pat in patterns:
        matches = re.findall(pat, html, re.IGNORECASE)
        all_matches.update(matches)
    
    if all_matches:
        for url in sorted(all_matches):
            print(f"  → {url}")
    else:
        print("  Hiç forestgump URL'si bulunamadı!")

    # 3. "track" veya "embed" içeren satırları göster
    print("\n" + "=" * 40)
    print("'track' VEYA 'embed' İÇEREN SATIRLAR:")
    print("=" * 40)
    
    for line in html.split('\n'):
        line_lower = line.lower()
        if 'track' in line_lower or 'embed' in line_lower:
            if 'forestgump' in line_lower or 'channels' in line_lower:
                print(f"  {line.strip()[:150]}")

    # 4. Script taglarını kontrol et
    print("\n" + "=" * 40)
    print("SCRIPT İÇİNDE FORESTGUMP/CHANNELS:")
    print("=" * 40)
    
    scripts = soup.find_all('script')
    for i, script in enumerate(scripts):
        text = script.string or ''
        if 'forestgump' in text.lower() or 'channels' in text.lower():
            print(f"\n[script {i}]")
            # İlgili satırları göster
            for line in text.split('\n'):
                if 'forestgump' in line.lower() or 'channels' in line.lower():
                    print(f"  {line.strip()[:200]}")

    # 5. ch1, ch2, track, embed pattern'leri
    print("\n" + "=" * 40)
    print("CH + TRACK/EMBED PATTERNLERİ:")
    print("=" * 40)
    
    ch_patterns = [
        r'["\'/](ch\d+/track/\d+)["\'\s]',
        r'["\'/](ch\d+/embed/\d+)["\'\s]',
        r'(ch\d+/track/\d+)',
        r'(ch\d+/embed/\d+)',
    ]
    
    for pat in ch_patterns:
        matches = re.findall(pat, html)
        if matches:
            print(f"  Pattern '{pat}':")
            for m in matches:
                print(f"    → {m}")

    # 6. HTML'in ilk 2000 karakterini göster
    print("\n" + "=" * 40)
    print("HTML BAŞ KISMI (ilk 2000 char):")
    print("=" * 40)
    print(html[:2000])

    # 7. "player" veya "video" içeren bölümler
    print("\n" + "=" * 40)
    print("PLAYER/VIDEO İÇEREN BÖLÜMLER:")
    print("=" * 40)
    
    player_patterns = [
        r'player[^\n]{0,200}',
        r'video[^\n]{0,200}',
        r'source[^\n]{0,200}',
        r'stream[^\n]{0,200}',
    ]
    
    for pat in player_patterns:
        matches = re.findall(pat, html, re.IGNORECASE)
        for m in matches[:3]:  # Her pattern için max 3 sonuç
            if 'http' in m.lower() or 'src' in m.lower():
                print(f"  {m.strip()}")

    # 8. HTML'i dosyaya kaydet (tam inceleme için)
    with open('debug_page.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"\n[*] Tam HTML 'debug_page.html' dosyasına kaydedildi")


def main():
    scraper = create_scraper()
    debug_page(scraper)


if __name__ == '__main__':
    main()
