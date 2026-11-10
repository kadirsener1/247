import re
import os
import sys
import json
import time
import base64
import requests
from urllib.parse import urljoin
from datetime import datetime

# ─────────────────────────────────────────────
# YAPILANDIRMA
# ─────────────────────────────────────────────
BASE_URL = "https://tvnow247.top/watch/"
OUTPUT_FILE = "tv247tr.m3u"
CHANNELS_FILE = "channelstr.txt"

# Kesin olarak Server 4 kaynağını almak için hedef sunucu indexi (0 tabanlı: 0=Server1, 3=Server4)
TARGET_SERVER_INDEX = 3  # Server 4

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://tvnow247.top/",
}

CHANNEL_IDS = {
    "bein-sports-1-turkey": "62",
    "bein-sports-2-turkey": "63",
    "bein-sports-3-turkey": "64",
    "bein-sports-4-turkey": "67",
    "bein-sports-5-turkey": "1010",
}


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def generate_playlist_url(stream_base_url, channel_id):
    """Dinamik olarak bulunan stream base URL'sini token ile birleştirir"""
    ts = int(time.time() * 1000)
    token_data = {
        "channelId": str(channel_id),
        "ts": ts
    }
    token_json = json.dumps(token_data, separators=(',', ':'))
    token_b64 = base64.b64encode(token_json.encode()).decode()
    return f"{stream_base_url}?token={token_b64}"


# ─────────────────────────────────────────────
# DOĞRUDAN TOKEN VE DİNAMİK BASE URL BUL (SERVER 4)
# ─────────────────────────────────────────────
def find_stream_data_for_channel(channel_slug):
    """
    Sayfadaki iframeleri tarayarak Server 4'e ait tam token URL'sini 
    ve oradaki güncel sunucu (stream base url) adresini dinamik olarak çeker.
    """
    url = f"{BASE_URL}{channel_slug}/"
    session = requests.Session()
    session.headers.update(HEADERS)
    
    try:
        resp = session.get(url, timeout=30)
        html = resp.text
        
        token_pattern = r'(https?://[^\s"\'<>]+/api/proxy/playlist\?token=[A-Za-z0-9+/=_-]+)'
        iframe_pattern = r'<iframe[^>]+src=["\']([^"\']+)["\']'
        
        # 1. Sayfadaki tüm iframeleri bul
        iframes = re.findall(iframe_pattern, html, re.IGNORECASE)
        log(f"  Sayfada toplam {len(iframes)} adet iframe bulundu.")
        
        # Hedef Server 4 (Index 3)
        if len(iframes) > TARGET_SERVER_INDEX:
            target_iframe_src = iframes[TARGET_SERVER_INDEX]
            iframe_url = urljoin(url, target_iframe_src)
            log(f"  ✓ Hedef Server 4 iframe adresi yakalandı: {iframe_url[:80]}...")
            
            try:
                resp_iframe = session.get(iframe_url, timeout=30, headers={**HEADERS, "Referer": url})
                matches = re.findall(token_pattern, resp_iframe.text)
                if matches:
                    full_token_url = matches[0]
                    stream_base = full_token_url.split('?')[0]
                    log(f"  ✓ Dinamik Sunucu Adresi: {stream_base}")
                    return full_token_url
            except Exception as e:
                log(f"  Server 4 iframe isteğinde hata: {e}")
        
        # 2. Alternatif: İframe bulunamazsa ana sayfadaki token'lardan seç
        matches = re.findall(token_pattern, html)
        if len(matches) > TARGET_SERVER_INDEX:
            full_token_url = matches[TARGET_SERVER_INDEX]
            log(f"  ✓ Sayfa genelindeki token listesinden Server 4 seçildi.")
            return full_token_url
        elif matches:
            full_token_url = matches[0]
            log(f"  ⚠️ 4. sunucu bulunamadı, mevcut ilk sunucu seçiliyor.")
            return full_token_url
            
    except Exception as e:
        log(f"  Hata: {e}")
    
    return None


# ─────────────────────────────────────────────
# KANAL LİSTESİ
# ─────────────────────────────────────────────
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
    log("TV247 M3U Generator - Dinamik Server 4 Sürüm")
    log("=" * 50)
    
    channels = load_channels()
    log(f"\n{len(channels)} kanal işlenecek\n")
    
    results = []
    
    for i, ch in enumerate(channels):
        log(f"\n[{i+1}/{len(channels)}] {ch['name']}")
        log("-" * 40)
        
        stream_url = find_stream_data_for_channel(ch['slug'])
        
        results.append({
            'slug': ch['slug'],
            'name': ch['name'],
            'url': stream_url
        })
        
        if stream_url:
            log(f"✓ {stream_url[:80]}...")
        else:
            log(f"✗ Bulunamadı")
        
        time.sleep(1)
    
    log("\n" + "=" * 50)
    content = generate_m3u(results)
    print(f"\n{content}")
    
    found = sum(1 for r in results if r.get('url'))
    log(f"\nSONUÇ: {found}/{len(results)} kanal bulundu")
    
    return 0 if found > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
