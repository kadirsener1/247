import re
import os
import sys
import json
import time
import requests
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
from datetime import datetime

# ─────────────────────────────────────────────
# YAPILANDIRMA
# ─────────────────────────────────────────────
BASE_URL = "https://tvnow247.top/watch/"
EMBED_SERVER4_BASE = "https://tvnow247.top/embed-r4/"
OUTPUT_FILE = "tv247tr.m3u"
CHANNELS_FILE = "channelstr.txt"

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


def extract_m3u8_from_html(html):
    """HTML veya JavaScript metni içerisinden .m3u8 linklerini yakalar"""
    m3u8_pattern = r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*?)'
    return re.findall(m3u8_pattern, html)


def find_stream_data_for_channel(channel_slug):
    """
    Doğrudan Server 4 embed adresine (/embed-r4/{slug}) giderek 
    Server 4 yayın kaynağını çeker.
    """
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # 1. Aşama: Doğrudan Server 4 Embed Sayfasını tara
    embed_r4_url = f"{EMBED_SERVER4_BASE}{channel_slug}"
    log(f"  Server 4 embed adresi taranıyor: {embed_r4_url}")
    
    try:
        resp_r4 = session.get(embed_r4_url, timeout=20, headers={**HEADERS, "Referer": f"{BASE_URL}{channel_slug}/"})
        html_r4 = resp_r4.text
        
        # Embed sayfasında doğrudan .m3u8 ara
        links = extract_m3u8_from_html(html_r4)
        if links:
            log(f"  ✓ Server 4 embed sayfasından doğrudan .m3u8 bulundu!")
            return links[0]
            
        # Embed sayfasında alt iframe var mı kontrol et
        iframe_pattern = r'<iframe[^>]+src=["\']([^"\']+)["\']'
        iframes = re.findall(iframe_pattern, html_r4, re.IGNORECASE)
        for iframe_src in iframes:
            iframe_url = urljoin(embed_r4_url, iframe_src)
            try:
                resp_inner = session.get(iframe_url, timeout=20, headers={**HEADERS, "Referer": embed_r4_url})
                inner_links = extract_m3u8_from_html(resp_inner.text)
                if inner_links:
                    log(f"  ✓ Server 4 alt iframe'inden .m3u8 bulundu!")
                    return inner_links[0]
            except Exception:
                pass
                
    except Exception as e:
        log(f"  Server 4 embed tarama hatası: {e}")

    # 2. Aşama: Ana sayfayı tara (Eğer embed-r4 açılmazsa)
    watch_url = f"{BASE_URL}{channel_slug}/"
    try:
        resp_watch = session.get(watch_url, timeout=20)
        html_watch = resp_watch.text
        links = extract_m3u8_from_html(html_watch)
        for link in links:
            if "src=r4" in link:
                log(f"  ✓ Ana sayfadan Server 4 (src=r4) linki bulundu!")
                return link
    except Exception:
        pass

    # 3. Aşama: Fallback ID Bağlantısı
    log(f"  ⚠️ Canlı link ayıklanamadı, ID üzerinden Server 4 linki üretiliyor...")
    channel_id = CHANNEL_IDS.get(channel_slug)
    if channel_id:
        fallback_url = f"https://live.tvnow247.today/live/{channel_id}/index.m3u8?src=r4"
        log(f"  ✓ ID tabanlı Server 4 URL: {channel_id}")
        return fallback_url

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
    log("TV247 M3U Generator - Embed-R4 Özel Sürüm")
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
