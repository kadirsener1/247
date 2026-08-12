#!/usr/bin/env python3
"""
SportsBite.org - BeIN Sports 1 Turkey Stream Finder
Tek kanal için stream URL bulucu
"""

import re
import json
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
import cloudscraper
import base64

# Cloudflare bypass
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)

TARGET_URL = "https://sportsbite.org/watch/channel/bein-sports-1-turkey"
BASE_URL = "https://sportsbite.org"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,tr;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0',
}


def get_page(url, referer=None):
    """Sayfayı indir"""
    headers = HEADERS.copy()
    if referer:
        headers['Referer'] = referer
    
    try:
        print(f"\n📥 İndiriliyor: {url}")
        response = scraper.get(url, headers=headers, timeout=30)
        print(f"   Status: {response.status_code}")
        return response.text
    except Exception as e:
        print(f"   ❌ Hata: {e}")
        return None


def decode_base64(text):
    """Base64 decode dene"""
    try:
        # Padding düzelt
        missing_padding = len(text) % 4
        if missing_padding:
            text += '=' * (4 - missing_padding)
        decoded = base64.b64decode(text).decode('utf-8')
        return decoded
    except:
        return None


def find_stream_in_html(html, depth=0):
    """HTML içinde stream URL ara"""
    indent = "  " * depth
    found_urls = []
    
    # 1. Doğrudan m3u8/mpd linkleri
    m3u8_pattern = r'["\']?(https?://[^\s\'"<>]+\.m3u8[^\s\'"<>]*)["\']?'
    mpd_pattern = r'["\']?(https?://[^\s\'"<>]+\.mpd[^\s\'"<>]*)["\']?'
    
    for pattern, ptype in [(m3u8_pattern, 'm3u8'), (mpd_pattern, 'mpd')]:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for match in matches:
            clean = match.strip('"\'')
            print(f"{indent}✅ {ptype} bulundu: {clean[:100]}...")
            found_urls.append(clean)
    
    # 2. source/file/url değişkenleri
    var_patterns = [
        r'source\s*[=:]\s*["\']([^"\']+)["\']',
        r'file\s*[=:]\s*["\']([^"\']+)["\']',
        r'src\s*[=:]\s*["\']([^"\']+)["\']',
        r'"source"\s*:\s*"([^"]+)"',
        r'"file"\s*:\s*"([^"]+)"',
        r'"url"\s*:\s*"([^"]+)"',
        r'"src"\s*:\s*"([^"]+)"',
        r'"stream"\s*:\s*"([^"]+)"',
        r'"hls"\s*:\s*"([^"]+)"',
        r"source\s*[=:]\s*'([^']+)'",
        r"file\s*[=:]\s*'([^']+)'",
    ]
    
    for pattern in var_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for match in matches:
            if 'http' in match and ('.m3u8' in match or '.mpd' in match or '/live/' in match or '/stream/' in match):
                print(f"{indent}✅ Değişkenden bulundu: {match[:100]}...")
                found_urls.append(match)
    
    # 3. Base64 encoded URL'ler
    base64_patterns = [
        r'atob\(["\']([A-Za-z0-9+/=]+)["\']\)',
        r'decode\(["\']([A-Za-z0-9+/=]+)["\']\)',
        r'["\']([A-Za-z0-9+/=]{50,})["\']',  # Uzun base64 stringler
    ]
    
    for pattern in base64_patterns:
        matches = re.findall(pattern, html)
        for match in matches:
            decoded = decode_base64(match)
            if decoded and ('http' in decoded or '.m3u8' in decoded):
                print(f"{indent}✅ Base64 decoded: {decoded[:100]}...")
                found_urls.append(decoded)
    
    # 4. Escape edilmiş URL'ler
    escaped_patterns = [
        r'(https?:\\/\\/[^\s\'"<>]+\.m3u8[^\s\'"<>]*)',
        r'(https?%3A%2F%2F[^\s\'"<>]+)',
    ]
    
    for pattern in escaped_patterns:
        matches = re.findall(pattern, html)
        for match in matches:
            unescaped = match.replace('\\/', '/').replace('%3A', ':').replace('%2F', '/')
            if '.m3u8' in unescaped or '.mpd' in unescaped:
                print(f"{indent}✅ Escaped URL: {unescaped[:100]}...")
                found_urls.append(unescaped)
    
    return found_urls


def process_iframe(iframe_url, referer, depth=0):
    """iframe içeriğini işle"""
    indent = "  " * depth
    print(f"{indent}🔍 iframe işleniyor: {iframe_url}")
    
    # URL düzelt
    if iframe_url.startswith('//'):
        iframe_url = 'https:' + iframe_url
    elif not iframe_url.startswith('http'):
        iframe_url = urljoin(referer, iframe_url)
    
    html = get_page(iframe_url, referer=referer)
    if not html:
        return []
    
    found_urls = []
    
    # HTML içinde stream ara
    found_urls.extend(find_stream_in_html(html, depth))
    
    # Nested iframe'ler
    soup = BeautifulSoup(html, 'html.parser')
    iframes = soup.find_all('iframe')
    
    for iframe in iframes:
        src = iframe.get('src', '') or iframe.get('data-src', '')
        if src and depth < 5:  # Max 5 seviye derinlik
            nested_urls = process_iframe(src, iframe_url, depth + 1)
            found_urls.extend(nested_urls)
    
    # Embed/player linkleri
    embed_patterns = [
        r'(https?://[^\s\'"<>]+/embed[^\s\'"<>]*)',
        r'(https?://[^\s\'"<>]+/player[^\s\'"<>]*)',
        r'(https?://[^\s\'"<>]+/e/[^\s\'"<>]*)',
        r'(https?://[^\s\'"<>]+\.php\?[^\s\'"<>]*)',
    ]
    
    for pattern in embed_patterns:
        matches = re.findall(pattern, html)
        for match in matches:
            if match != iframe_url and depth < 5:
                print(f"{indent}🔗 Embed bulundu: {match}")
                nested_urls = process_iframe(match, iframe_url, depth + 1)
                found_urls.extend(nested_urls)
    
    return found_urls


def main():
    print("=" * 70)
    print("🎯 BeIN Sports 1 Turkey Stream Finder")
    print(f"🔗 URL: {TARGET_URL}")
    print("=" * 70)
    
    # Ana sayfayı indir
    html = get_page(TARGET_URL)
    if not html:
        print("❌ Ana sayfa yüklenemedi!")
        return
    
    # Sayfayı kaydet (debug için)
    with open('debug_page.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("📄 Sayfa debug_page.html olarak kaydedildi")
    
    all_streams = []
    
    # 1. Ana sayfada doğrudan stream ara
    print("\n" + "=" * 50)
    print("📡 Ana sayfada stream aranıyor...")
    print("=" * 50)
    all_streams.extend(find_stream_in_html(html, 0))
    
    # 2. iframe'leri işle
    print("\n" + "=" * 50)
    print("🖼️ iframe'ler işleniyor...")
    print("=" * 50)
    
    soup = BeautifulSoup(html, 'html.parser')
    iframes = soup.find_all('iframe')
    
    print(f"📊 {len(iframes)} iframe bulundu")
    
    for i, iframe in enumerate(iframes, 1):
        src = iframe.get('src', '') or iframe.get('data-src', '') or iframe.get('data-lazy-src', '')
        
        # data-* attribute'larını da kontrol et
        for attr, value in iframe.attrs.items():
            if 'src' in attr.lower() and value and value.startswith(('http', '//')):
                src = value
                break
        
        if src:
            print(f"\n--- iframe {i}/{len(iframes)} ---")
            print(f"src: {src}")
            streams = process_iframe(src, TARGET_URL, 1)
            all_streams.extend(streams)
        else:
            print(f"\niframe {i}: src bulunamadı")
            print(f"Attributes: {iframe.attrs}")
    
    # 3. Script tag'lerini kontrol et
    print("\n" + "=" * 50)
    print("📜 Script tag'leri kontrol ediliyor...")
    print("=" * 50)
    
    scripts = soup.find_all('script')
    for i, script in enumerate(scripts):
        if script.string:
            streams = find_stream_in_html(script.string, 1)
            all_streams.extend(streams)
            
            # Özel pattern'ler
            # jwplayer, video.js, hls.js vb.
            player_patterns = [
                r'jwplayer\([^)]+\)\.setup\(\{[^}]*file\s*:\s*["\']([^"\']+)["\']',
                r'Clappr\.Player\([^)]*source\s*:\s*["\']([^"\']+)["\']',
                r'videojs\([^)]+\)\.src\(["\']([^"\']+)["\']',
                r'hls\.loadSource\(["\']([^"\']+)["\']',
                r'new\s+Hls\(\).*?\.loadSource\(["\']([^"\']+)["\']',
                r'player\.load\(["\']([^"\']+)["\']',
                r'source:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            ]
            
            for pattern in player_patterns:
                matches = re.findall(pattern, script.string, re.DOTALL | re.IGNORECASE)
                for match in matches:
                    print(f"  ✅ Player'dan bulundu: {match[:100]}...")
                    all_streams.append(match)
    
    # 4. Sonuçları göster
    print("\n" + "=" * 70)
    print("📊 SONUÇLAR")
    print("=" * 70)
    
    # Duplicate'ları kaldır
    unique_streams = list(set(all_streams))
    
    if unique_streams:
        print(f"\n✅ {len(unique_streams)} stream URL bulundu:\n")
        for i, stream in enumerate(unique_streams, 1):
            print(f"{i}. {stream}")
        
        # M3U dosyası oluştur
        m3u_content = '#EXTM3U\n'
        m3u_content += '#EXTINF:-1 tvg-name="BeIN Sports 1 Turkey",BeIN Sports 1 Turkey\n'
        m3u_content += unique_streams[0] + '\n'
        
        with open('tv247.m3u', 'w', encoding='utf-8') as f:
            f.write(m3u_content)
        print(f"\n📁 tv247.m3u dosyası oluşturuldu")
        
    else:
        print("\n❌ Stream URL bulunamadı!")
        print("\n🔍 Debug bilgisi:")
        print(f"   - Sayfa boyutu: {len(html)} karakter")
        print(f"   - iframe sayısı: {len(iframes)}")
        print(f"   - script sayısı: {len(scripts)}")
        
        # iframe detayları
        print("\n   iframe detayları:")
        for i, iframe in enumerate(iframes, 1):
            print(f"   {i}. {dict(iframe.attrs)}")


if __name__ == '__main__':
    main()
