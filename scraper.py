#!/usr/bin/env python3
"""
SportsBite React SPA Scraper
JS bundle ve API'lerden stream URL'lerini bulur
"""

import re
import json
import cloudscraper
from urllib.parse import urljoin

BASE_URL = "https://sportsbite.org"
CHANNEL_SLUG = "5-usa"
OUTPUT_FILE = "tv247.m3u"

def create_scraper():
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )
    scraper.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': BASE_URL + '/',
        'Origin': BASE_URL,
    })
    return scraper

def get_js_bundle_urls(html):
    """Ana sayfadan JS bundle URL'lerini çıkar"""
    patterns = [
        r'src="(/assets/[^"]+\.js)"',
        r'href="(/assets/[^"]+\.js)"',
    ]
    urls = []
    for pat in patterns:
        matches = re.findall(pat, html)
        urls.extend(matches)
    return list(set(urls))

def find_channel_config(js_content):
    """JS içinden kanal konfigürasyonlarını bul"""
    results = []
    
    # forestgump URL pattern'leri
    patterns = [
        # Tam URL
        r'(https?://channels\.forestgump\.space/ch\d+/(?:track|embed)/\d+)',
        # URL template'leri
        r'["\']?(channels\.forestgump\.space/ch\d+/(?:track|embed)/\d+)["\']?',
        # Parçalı URL oluşturma
        r'forestgump\.space["\']?\s*\+\s*["\']?(/ch\d+/(?:track|embed)/\d+)',
        # Channel mapping objeleri
        r'["\']?5-usa["\']?\s*:\s*["\']?([^"\'}\s]+)["\']?',
        r'["\']?5-usa["\']?\s*:\s*\{[^}]*url["\']?\s*:\s*["\']?([^"\'}\s]+)["\']?',
        # ch1, track, 360 pattern'leri
        r'/ch(\d+)/track/(\d+)',
        r'/ch(\d+)/embed/(\d+)',
    ]
    
    for pat in patterns:
        matches = re.findall(pat, js_content, re.IGNORECASE)
        for m in matches:
            if isinstance(m, tuple):
                results.append(m)
            else:
                results.append(m)
    
    return results

def find_api_endpoints(js_content):
    """JS içinden API endpoint'lerini bul"""
    patterns = [
        r'(https?://api\.[^"\'<>\s]+)',
        r'["\']?(api\.watchfooty\.[^"\'<>\s]+)["\']?',
        r'fetch\s*\(\s*["\']([^"\']+)["\']',
        r'axios\.[a-z]+\s*\(\s*["\']([^"\']+)["\']',
    ]
    
    endpoints = []
    for pat in patterns:
        matches = re.findall(pat, js_content)
        endpoints.extend(matches)
    
    return list(set(endpoints))

def find_channel_mappings(js_content):
    """Kanal slug -> stream ID eşleşmelerini bul"""
    mappings = {}
    
    # Object literal pattern: {"5-usa": "360", "6-usa": "361"}
    obj_pattern = r'\{[^{}]*["\']?(\d+-usa)["\']?\s*:\s*["\']?(\d+)["\']?[^{}]*\}'
    matches = re.findall(obj_pattern, js_content)
    for slug, stream_id in matches:
        mappings[slug] = stream_id
    
    # Array/switch case pattern
    case_pattern = r'case\s*["\']?5-usa["\']?\s*:\s*return\s*["\']?(\d+)["\']?'
    matches = re.findall(case_pattern, js_content)
    for stream_id in matches:
        mappings['5-usa'] = stream_id
    
    # channelId, streamId değişkenleri
    var_patterns = [
        r'channelId\s*=\s*["\']?(\d+)["\']?',
        r'streamId\s*=\s*["\']?(\d+)["\']?',
        r'chId\s*=\s*["\']?(\d+)["\']?',
    ]
    
    for pat in var_patterns:
        matches = re.findall(pat, js_content)
        if matches:
            print(f"  Bulunan ID'ler ({pat}): {matches[:5]}")
    
    return mappings

def try_known_api_endpoints(scraper):
    """Bilinen API endpoint'lerini dene"""
    # HTML'de gördüğümüz preconnect domain'lerinden
    endpoints = [
        "https://api.watchfooty.st/channels",
        "https://api.watchfooty.st/channels/5-usa",
        "https://api.watchfooty.st/streams",
        "https://api.watchfooty.st/tv",
        "https://api.watchfooty.st/tv/channels",
    ]
    
    print("\n" + "="*50)
    print("API ENDPOINT'LERİ DENENİYOR:")
    print("="*50)
    
    for endpoint in endpoints:
        try:
            resp = scraper.get(endpoint, timeout=10)
            print(f"\n[{resp.status_code}] {endpoint}")
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    print(f"  JSON: {json.dumps(data, indent=2)[:500]}")
                    return data
                except:
                    print(f"  Text: {resp.text[:300]}")
        except Exception as e:
            print(f"[ERR] {endpoint}: {e}")
    
    return None

def try_direct_stream_urls(scraper):
    """Bilinen stream URL formatlarını dene"""
    # HTML'de forestgump.space ve cr7siuu.xyz gördük
    stream_bases = [
        "https://channels.forestgump.space",
        "https://embed.cr7siuu.xyz",
    ]
    
    # Muhtemel channel/stream kombinasyonları
    # 5-usa için ch1/track/360 olduğunu biliyoruz
    paths = [
        "/ch1/track/360",
        "/ch1/embed/360",
        "/ch5/track/360",
        "/ch5/embed/360",
        "/5-usa/stream",
        "/stream/5-usa",
    ]
    
    print("\n" + "="*50)
    print("STREAM URL'LERİ DENENİYOR:")
    print("="*50)
    
    working_urls = []
    
    for base in stream_bases:
        for path in paths:
            url = base + path
            try:
                resp = scraper.head(url, timeout=5, allow_redirects=True)
                status = resp.status_code
                print(f"[{status}] {url}")
                
                if status in [200, 301, 302]:
                    working_urls.append({
                        'url': url,
                        'status': status,
                        'final_url': resp.url if hasattr(resp, 'url') else url
                    })
            except Exception as e:
                print(f"[ERR] {url}: {str(e)[:50]}")
    
    return working_urls

def main():
    print("="*60)
    print("SportsBite React SPA Scraper")
    print("="*60)
    
    scraper = create_scraper()
    
    # 1. Ana sayfayı çek ve JS bundle URL'lerini bul
    print("\n[1] Ana sayfa çekiliyor...")
    resp = scraper.get(BASE_URL, timeout=30)
    html = resp.text
    
    js_urls = get_js_bundle_urls(html)
    print(f"  JS bundle sayısı: {len(js_urls)}")
    for url in js_urls:
        print(f"    → {url}")
    
    # 2. Ana JS bundle'ı çek ve analiz et
    print("\n[2] JS bundle analiz ediliyor...")
    all_stream_urls = []
    
    for js_path in js_urls:
        if 'index' in js_path or 'vendor' not in js_path:  # Ana bundle'ı öncelikle al
            js_url = urljoin(BASE_URL, js_path)
            print(f"\n  Çekiliyor: {js_url}")
            
            try:
                js_resp = scraper.get(js_url, timeout=30)
                js_content = js_resp.text
                print(f"  Boyut: {len(js_content)} karakter")
                
                # forestgump URL'lerini ara
                fg_urls = re.findall(
                    r'https?://channels\.forestgump\.space/[^\s"\'<>\\]+',
                    js_content
                )
                if fg_urls:
                    print(f"  ✓ forestgump URL'leri bulundu: {fg_urls}")
                    all_stream_urls.extend(fg_urls)
                
                # cr7siuu URL'lerini ara
                cr7_urls = re.findall(
                    r'https?://embed\.cr7siuu\.xyz/[^\s"\'<>\\]+',
                    js_content
                )
                if cr7_urls:
                    print(f"  ✓ cr7siuu URL'leri bulundu: {cr7_urls}")
                    all_stream_urls.extend(cr7_urls)
                
                # Channel config'leri bul
                configs = find_channel_config(js_content)
                if configs:
                    print(f"  ✓ Channel config'ler: {configs[:10]}")
                
                # Channel mapping'leri bul
                mappings = find_channel_mappings(js_content)
                if mappings:
                    print(f"  ✓ Channel mappings: {mappings}")
                
                # API endpoint'leri bul
                apis = find_api_endpoints(js_content)
                if apis:
                    print(f"  ✓ API endpoints: {apis[:5]}")
                
            except Exception as e:
                print(f"  Hata: {e}")
    
    # 3. Bilinen API endpoint'lerini dene
    api_data = try_known_api_endpoints(scraper)
    
    # 4. Bilinen stream URL'lerini dene
    working_streams = try_direct_stream_urls(scraper)
    
    # 5. Sonuçları topla
    print("\n" + "="*60)
    print("SONUÇLAR:")
    print("="*60)
    
    final_urls = list(set(all_stream_urls))
    
    # Çalışan URL'leri ekle
    for ws in working_streams:
        if ws['url'] not in final_urls:
            final_urls.append(ws['url'])
    
    if final_urls:
        print(f"\n✓ {len(final_urls)} stream URL bulundu:")
        for url in final_urls:
            print(f"  → {url}")
        
        # M3U dosyası oluştur
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U\n\n')
            for i, url in enumerate(final_urls):
                f.write(f'#EXTINF:-1 group-title="Sports" tvg-name="Channel {i+1}",Channel {i+1}\n')
                f.write(f'#EXTVLCOPT:http-referrer={BASE_URL}/\n')
                f.write(f'#EXTVLCOPT:http-user-agent=Mozilla/5.0\n')
                f.write(f'{url}\n\n')
        
        print(f"\n✓ {OUTPUT_FILE} oluşturuldu!")
        
    else:
        print("\n✗ Stream URL bulunamadı")
        
        # Bilinen URL'yi manuel ekle (test için)
        known_url = "https://channels.forestgump.space/ch1/track/360"
        print(f"\n[!] Bilinen URL manuel ekleniyor: {known_url}")
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('#EXTM3U\n\n')
            f.write('#EXTINF:-1 group-title="Sports" tvg-name="5 USA",5 USA\n')
            f.write(f'#EXTVLCOPT:http-referrer={BASE_URL}/watch/channel/5-usa\n')
            f.write('#EXTVLCOPT:http-user-agent=Mozilla/5.0\n')
            f.write(f'{known_url}\n')
        
        print(f"✓ {OUTPUT_FILE} oluşturuldu (manuel URL ile)")

if __name__ == '__main__':
    main()
