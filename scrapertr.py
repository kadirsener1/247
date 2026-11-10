import re
import os
import sys
import json
import time
import requests
from urllib.parse import urljoin
from datetime import datetime

# ─────────────────────────────────────────────
# YAPILANDIRMA
# ─────────────────────────────────────────────
BASE_URL = "https://tvnow247.top/"
OUTPUT_FILE = "tv247tr.m3u"
CHANNELS_FILE = "channelstr.txt"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://tvnow247.top/",
}


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def find_token_stream_for_channel(channel_slug):
    """
    Doğrudan https://tvnow247.top/embed-r4/{slug} adresini ziyaret eder,
    sayfa içeriğindeki ve iframe'lerdeki token parametreli .m3u8 linkini yakalar.
    """
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # Server 4 özel embed adresi
    embed_url = f"{BASE_URL}embed-r4/{channel_slug}"
    log(f"  Embed adresi taranıyor: {embed_url}")
    
    try:
        resp = session.get(embed_url, timeout=30)
        html = resp.text
        
        # Token içeren veya .m3u8 uzantılı tüm linkleri yakalayan esnek regex
        # Örn: https://.../index.m3u8?token=... veya benzeri token'lı link yapısı
        token_pattern = r'(https?://[^\s"\'<>]+?(?:\.m3u8|\?token=)[^\s"\'<>]*?)'
        
        # 1. Embed sayfasının kendi HTML'inde ara
        matches = re.findall(token_pattern, html)
        if matches:
            for link in matches:
                log(f"  ✓ Token'lı yayın linki yakalandı!")
                return link
                
        # 2. Sayfa içinde gömülü başka iframe varsa onları da tara
        iframe_pattern = r'<iframe[^>]+src=["\']([^"\']+)["\']'
        iframes = re.findall(iframe_pattern, html, re.IGNORECASE)
        
        for iframe_src in iframes:
            iframe_url = urljoin(embed_url, iframe_src)
            try:
                resp_iframe = session.get(iframe_url, timeout=30, headers={**HEADERS, "Referer": embed_url})
                iframe_matches = re.findall(token_pattern, resp_iframe.text)
                if iframe_matches:
                    log(f"  ✓ İframe içerisinden token'lı yayın linki yakalandı!")
                    return iframe_matches[0]
            except Exception:
                pass
                
        log(f"  ⚠️ Bu sayfada token'lı link bulunamadı.")
        
    except Exception as e:
        log(f"  Bağlantı hatası: {e}")
        
    return None


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
    log("TV247 M3U Generator - Embed-R4 Token Tarayıcı")
    log("=" * 50)
    
    channels = load_channels()
    log(f"\n{len(channels)} kanal işlenecek\n")
    
    results = []
    
    for i, ch in enumerate(channels):
        log(f"\n[{i+1}/{len(channels)}] {ch['name']}")
        log("-" * 40)
        
        stream_url = find_token_stream_for_channel(ch['slug'])
        
        results.append({
            'slug': ch['slug'],
            'name': ch['name'],
            'url': stream_url
        })
        
        if stream_url:
            log(f"✓ {stream_url[:90]}...")
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
