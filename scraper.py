#!/usr/bin/env python3
"""
SportsBite - Path Bulucu Debug
ch1, track, 360 gibi parçaların nerede olduğunu bulur
"""

import re
import cloudscraper
from bs4 import BeautifulSoup

URL = "https://sportsbite.org/watch/channel/5-usa"

def create_scraper():
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )
    scraper.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://sportsbite.org/',
    })
    return scraper

def main():
    scraper = create_scraper()
    resp = scraper.get(URL, timeout=30)
    html = resp.text
    
    print(f"[*] Sayfa boyutu: {len(html)} karakter")
    print(f"[*] 'forestgump' var mı: {'forestgump' in html.lower()}")
    print(f"[*] 'track' var mı: {'track' in html.lower()}")
    print(f"[*] '/ch1' var mı: {'/ch1' in html.lower()}")
    print(f"[*] '360' var mı: {'360' in html}")
    
    # ===============================
    # 1. forestgump içeren her şey
    # ===============================
    print("\n" + "="*50)
    print("FORESTGUMP İÇEREN SATIRLAR:")
    print("="*50)
    
    for i, line in enumerate(html.split('\n')):
        if 'forestgump' in line.lower():
            print(f"[Satır {i}]: {line.strip()[:300]}")
    
    # ===============================
    # 2. ch + sayı pattern'leri
    # ===============================
    print("\n" + "="*50)
    print("CH + SAYI PATTERNLERİ:")
    print("="*50)
    
    ch_patterns = [
        r'ch\d+',
        r'channel\s*[=:]\s*["\']?(\d+)',
        r'ch\s*[=:]\s*["\']?(\d+)',
    ]
    
    for pat in ch_patterns:
        matches = re.findall(pat, html, re.IGNORECASE)
        if matches:
            print(f"  {pat}: {matches[:10]}")
    
    # ===============================
    # 3. track veya embed içeren
    # ===============================
    print("\n" + "="*50)
    print("TRACK/EMBED İÇEREN SATIRLAR:")
    print("="*50)
    
    for i, line in enumerate(html.split('\n')):
        if 'track' in line.lower() or 'embed' in line.lower():
            # Sadece ilgili olanları göster
            if any(x in line.lower() for x in ['src', 'url', 'http', 'channel', '/']):
                print(f"[Satır {i}]: {line.strip()[:300]}")
    
    # ===============================
    # 4. 360 sayısı geçen yerler
    # ===============================
    print("\n" + "="*50)
    print("'360' SAYISI GEÇEN SATIRLAR:")
    print("="*50)
    
    for i, line in enumerate(html.split('\n')):
        if '360' in line:
            print(f"[Satır {i}]: {line.strip()[:300]}")
    
    # ===============================
    # 5. JavaScript değişkenleri
    # ===============================
    print("\n" + "="*50)
    print("ÖNEMLİ JS DEĞİŞKENLERİ:")
    print("="*50)
    
    js_patterns = [
        r'(var\s+\w+\s*=\s*["\'][^"\']*(?:ch|track|channel|stream)[^"\']*["\'])',
        r'(let\s+\w+\s*=\s*["\'][^"\']*(?:ch|track|channel|stream)[^"\']*["\'])',
        r'(const\s+\w+\s*=\s*["\'][^"\']*(?:ch|track|channel|stream)[^"\']*["\'])',
        r'(\w+\s*:\s*["\'][^"\']*(?:ch\d|track|channel)[^"\']*["\'])',
        r'(src\s*=\s*["\'][^"\']+["\'])',
        r'(iframe\.src\s*=\s*[^;]+)',
    ]
    
    for pat in js_patterns:
        matches = re.findall(pat, html, re.IGNORECASE)
        for m in matches[:5]:
            print(f"  → {m[:200]}")
    
    # ===============================
    # 6. Tüm script içerikleri
    # ===============================
    print("\n" + "="*50)
    print("SCRIPT TAG İÇERİKLERİ (forestgump/track/ch içerenler):")
    print("="*50)
    
    soup = BeautifulSoup(html, 'html.parser')
    scripts = soup.find_all('script')
    
    for i, script in enumerate(scripts):
        content = script.string or ''
        if any(x in content.lower() for x in ['forestgump', 'track', '/ch']):
            print(f"\n[Script {i}] ({len(content)} char):")
            print("-" * 40)
            # İlgili satırları göster
            for line in content.split('\n'):
                if any(x in line.lower() for x in ['forestgump', 'track', '/ch', 'channel', 'src']):
                    print(f"  {line.strip()[:250]}")
    
    # ===============================
    # 7. URL oluşturma pattern'leri
    # ===============================
    print("\n" + "="*50)
    print("URL BİRLEŞTİRME PATTERNLERİ:")
    print("="*50)
    
    # Bazen URL parçalara bölünmüş olur: baseUrl + "/ch" + channelId + "/track/" + streamId
    concat_patterns = [
        r'(["\'][^"\']*forestgump[^"\']*["\']\s*\+\s*[^;]+)',
        r'(\+\s*["\']/ch[^;]+)',
        r'(baseUrl[^;]+)',
        r'(streamUrl[^;]+)',
        r'(iframeUrl[^;]+)',
        r'(embedUrl[^;]+)',
    ]
    
    for pat in concat_patterns:
        matches = re.findall(pat, html, re.IGNORECASE)
        for m in matches[:3]:
            print(f"  → {m[:200]}")
    
    # ===============================
    # 8. HTML dosyasını kaydet
    # ===============================
    with open('debug_full.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"\n[*] Tam HTML 'debug_full.html' dosyasına kaydedildi")
    print("[*] Bu dosyayı manuel inceleyebilirsin")

if __name__ == '__main__':
    main()
