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
OUTPUT_FILE = "tv247tr.m3u"
CHANNELS_FILE = "channelstr.txt"

# Başlangıç Base URL (Sayfadan dinamik olarak güncellenecektir)
STREAM_BASE_URL = "https://live.tvnow247.today/live/"
TARGET_SRC_PARAM = "src=r4"  # Kesin olarak Server 4 kaynağını seçmek için

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://tvnow247.top/",
}


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def update_stream_base_url(full_url):
    """Bulunan .m3u8 linkinden base URL kısmını dinamik olarak günceller"""
    global STREAM_BASE_URL
    if full_url:
        try:
            # Örn: https://live.tvnow247.today/live/62/index.m3u8 -> https://live.tvnow247.today/live/
            if '/live/' in full_url:
                base = full_url.split('/live/')[0] + '/live/'
                if base and base != STREAM_BASE_URL:
                    STREAM_BASE_URL = base
                    log(f"  [!!!] GÜNCEL BASE URL TESPİT EDİLDİ: {STREAM_BASE_URL}")
        except Exception:
            pass


def force_server_4(link):
    """Linkteki src parametresini kesin olarak r4 (Server 4) yapar"""
    if not link:
        return link
    try:
        parsed = urlparse(link)
        qs = parse_qs(parsed.query, keep_blank_values=True)
        qs['src'] = ['r4']  # Server 4 zorlaması
        new_query = urlencode(qs, doseq=True)
        parsed_list = list(parsed)
        parsed_list[4] = new_query
        return urlunparse(parsed_list)
    except Exception:
        # Eğer url parse edilemezse string değişimi dene
        if 'src=' in link:
            link = re.sub(r'src=[^&]+', 'src=r4', link)
        else:
            sep = '&' if '?' in link else '?'
            link += f"{sep}src=r4"
        return link


# ─────────────────────────────────────────────
# KANAL VE STREAM VERİSİNİ BULMA (BASE URL + SERVER 4)
# ─────────────────────────────────────────────
def find_stream_data_for_channel(channel_slug):
    """
    Sayfayı ve iframe'leri tarar, bulunan .m3u8 linklerinden base URL'yi günceller 
    ve bağlantıyı Server 4 (src=r4) olacak şekilde uyarlar.
    """
    url = f"{BASE_URL}{channel_slug}/"
    session = requests.Session()
    session.headers.update(HEADERS)
    
    try:
        resp = session.get(url, timeout=30)
        html = resp.text
        
        m3u8_pattern = r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*?)'
        iframe_pattern = r'<iframe[^>]+src=["\']([^"\']+)["\']'
        
        all_m3u8_links = []
        
        # 1. Ana sayfadaki .m3u8 linklerini bul
        page_matches = re.findall(m3u8_pattern, html)
        for m in page_matches:
            if m not in all_m3u8_links:
                all_m3u8_links.append(m)

        # 2. İframeleri tara
        iframes = re.findall(iframe_pattern, html, re.IGNORECASE)
        for iframe_src in iframes:
            iframe_url = urljoin(url, iframe_src)
            try:
                resp_iframe = session.get(iframe_url, timeout=30, headers={**HEADERS, "Referer": url})
                iframe_matches = re.findall(m3u8_pattern, resp_iframe.text)
                for m in iframe_matches:
                    if m not in all_m3u8_links:
                        all_m3u8_links.append(m)
            except Exception:
                pass

        log(f"  Toplam {len(all_m3u8_links)} adet .m3u8 yayın linki bulundu.")
        
        # Öncelik: Zaten src=r4 içeren varsa doğrudan al
        for link in all_m3u8_links:
            if TARGET_SRC_PARAM in link:
                update_stream_base_url(link)
                log(f"  ✓ Doğrudan Server 4 yayın linki yakalandı!")
                return link

        # Yoksa herhangi bir .m3u8 linkini alıp base URL'yi güncelleyelim ve src=r4 zorlayalım
        if all_m3u8_links:
            selected_link = all_m3u8_links[0]
            update_stream_base_url(selected_link)
            forced_link = force_server_4(selected_link)
            log(f"  ✓ Base URL güncellendi ve Server 4 (src=r4) zorlandı.")
            return forced_link
            
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
    log("TV247 M3U Generator - Base URL Destekli Server 4 Sürüm")
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
