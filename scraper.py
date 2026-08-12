#!/usr/bin/env python3
"""
SportsBite.org M3U Scraper
Tüm kanalları tarar, yayın stream linklerini bulur ve tv247.m3u dosyasına yazar.
"""

import re
import json
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import cloudscraper
import logging
from datetime import datetime

# Logging ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Sabitler
BASE_URL = "https://sportsbite.org"
CHANNELS_URL = f"{BASE_URL}/channels"
WATCH_BASE = f"{BASE_URL}/watch/channel/"

# Cloudflare bypass için scraper
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': BASE_URL,
    'Origin': BASE_URL,
}


def get_page(url, retries=3):
    """Sayfayı indir, Cloudflare korumasını aşmaya çalış"""
    for attempt in range(retries):
        try:
            logger.info(f"Sayfa indiriliyor: {url} (Deneme {attempt + 1})")
            response = scraper.get(url, headers=HEADERS, timeout=30)
            if response.status_code == 200:
                return response.text
            else:
                logger.warning(f"HTTP {response.status_code}: {url}")
        except Exception as e:
            logger.error(f"Hata: {e}")
        time.sleep(2)
    return None


def get_all_channels():
    """Ana kanallar sayfasından tüm kanal listesini çek"""
    channels = []

    html = get_page(CHANNELS_URL)
    if not html:
        logger.error("Kanallar sayfası yüklenemedi!")
        return channels

    soup = BeautifulSoup(html, 'html.parser')

    # Kanal linklerini bul - farklı CSS pattern'leri dene
    link_patterns = [
        # /watch/channel/XXXX formatındaki linkler
        re.compile(r'/watch/channel/[\w\-]+'),
        # /channel/ formatındaki linkler
        re.compile(r'/channel/[\w\-]+'),
    ]

    found_links = set()

    # Tüm <a> taglarını tara
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        full_url = urljoin(BASE_URL, href)

        for pattern in link_patterns:
            if pattern.search(href):
                channel_name = a_tag.get_text(strip=True)
                if not channel_name:
                    # Alt elementlerden isim bulmaya çalış
                    img = a_tag.find('img')
                    if img and img.get('alt'):
                        channel_name = img['alt']
                    else:
                        # URL'den isim çıkar
                        channel_name = href.split('/')[-1].replace('-', ' ').title()

                if full_url not in found_links:
                    found_links.add(full_url)
                    channels.append({
                        'name': channel_name,
                        'url': full_url,
                        'slug': href.split('/')[-1]
                    })
                break

    # Eğer linkler bulunamadıysa, sayfadaki tüm olası kanal slug'larını dene
    if not channels:
        logger.info("Link bulunamadı, alternatif yöntem deneniyor...")
        channels = try_alternative_channel_discovery(soup, html)

    # Eğer hala bulunamadıysa, bilinen kanalları dene
    if not channels:
        logger.info("Alternatif yöntem de başarısız, bilinen kanallar deneniyor...")
        channels = get_known_channels()

    logger.info(f"Toplam {len(channels)} kanal bulundu")
    return channels


def try_alternative_channel_discovery(soup, html):
    """Alternatif yöntemlerle kanal keşfi"""
    channels = []

    # JavaScript içinden kanal listesi bulmaya çalış
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string:
            # JSON veri yapıları ara
            json_patterns = [
                r'channels\s*[=:]\s*(\[.*?\])',
                r'data\s*[=:]\s*(\[.*?\])',
                r'"channels"\s*:\s*(\[.*?\])',
            ]
            for jp in json_patterns:
                match = re.search(jp, script.string, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        for item in data:
                            if isinstance(item, dict):
                                name = item.get('name', item.get('title', ''))
                                slug = item.get('slug', item.get('id', ''))
                                if slug:
                                    channels.append({
                                        'name': name or slug.replace('-', ' ').title(),
                                        'url': f"{WATCH_BASE}{slug}",
                                        'slug': str(slug)
                                    })
                    except json.JSONDecodeError:
                        pass

    # Sayfa içindeki card/grid elementlerini kontrol et
    card_selectors = [
        'div.channel', 'div.card', 'li.channel',
        'div[class*="channel"]', 'a[class*="channel"]',
        'div.grid > div', 'div.row > div',
        'div[class*="item"]', 'div[class*="stream"]'
    ]

    for selector in card_selectors:
        try:
            elements = soup.select(selector)
            if elements and len(elements) > 3:  # En az birkaç kanal olmalı
                for el in elements:
                    a = el.find('a', href=True) if el.name != 'a' else el
                    if a and a.get('href'):
                        href = a['href']
                        name = el.get_text(strip=True)[:50]
                        full_url = urljoin(BASE_URL, href)
                        if 'channel' in href or 'watch' in href:
                            channels.append({
                                'name': name or href.split('/')[-1],
                                'url': full_url,
                                'slug': href.split('/')[-1]
                            })
        except Exception:
            pass

    return channels


def get_known_channels():
    """Bilinen / yaygın kanal slug'ları"""
    known_slugs = [
        # USA Kanalları
        "5-usa", "espn", "espn2", "fox-sports-1", "fox-sports-2",
        "nbc-sports", "cbs-sports", "abc", "nba-tv", "nfl-network",
        "mlb-network", "nhl-network", "tnt", "tbs",
        "usa-network", "fs1", "fs2", "btn", "sec-network",

        # UK Kanalları
        "sky-sports-main-event", "sky-sports-premier-league",
        "sky-sports-football", "sky-sports-f1", "sky-sports-cricket",
        "sky-sports-action", "sky-sports-arena", "sky-sports-news",
        "bt-sport-1", "bt-sport-2", "bt-sport-3",
        "bbc-one", "bbc-two", "itv1", "itv4",
        "eurosport-1", "eurosport-2",
        "tnt-sports-1", "tnt-sports-2", "tnt-sports-3", "tnt-sports-4",

        # Spor Kanalları
        "bein-sports-1", "bein-sports-2", "bein-sports-3",
        "dazn-1", "dazn-2",
        "star-sports-1", "star-sports-2",
        "sony-ten-1", "sony-ten-2", "sony-ten-3",
        "supersport", "tsn-1", "tsn-2", "tsn-3", "tsn-4", "tsn-5",
        "sportsnet", "willow-cricket",

        # Diğer
        "arena-sport-1", "arena-sport-2",
        "eleven-sports-1", "eleven-sports-2",
        "premier-sports-1", "premier-sports-2",
        "racing-tv", "at-the-races",
    ]

    channels = []
    for slug in known_slugs:
        channels.append({
            'name': slug.replace('-', ' ').title(),
            'url': f"{WATCH_BASE}{slug}",
            'slug': slug
        })
    return channels


def extract_stream_url(channel_url):
    """
    Kanal sayfasından stream URL'sini çıkar.
    Birden fazla yöntem dener.
    """
    html = get_page(channel_url)
    if not html:
        return None

    soup = BeautifulSoup(html, 'html.parser')
    stream_url = None

    # ============================================
    # YÖNTEM 1: iframe src'den stream URL bul
    # ============================================
    iframes = soup.find_all('iframe')
    for iframe in iframes:
        src = iframe.get('src', '')
        if src:
            logger.info(f"  iframe bulundu: {src}")
            # iframe içindeki sayfayı da kontrol et
            stream_url = extract_from_iframe(src)
            if stream_url:
                return stream_url

    # ============================================
    # YÖNTEM 2: Doğrudan .m3u8 linkleri ara
    # ============================================
    m3u8_patterns = [
        r'(https?://[^\s\'"<>]+\.m3u8[^\s\'"<>]*)',
        r'source\s*[=:]\s*["\']?(https?://[^\s\'"<>]+\.m3u8[^\s\'"<>]*)',
        r'file\s*[=:]\s*["\']?(https?://[^\s\'"<>]+\.m3u8[^\s\'"<>]*)',
        r'src\s*[=:]\s*["\']?(https?://[^\s\'"<>]+\.m3u8[^\s\'"<>]*)',
        r'url\s*[=:]\s*["\']?(https?://[^\s\'"<>]+\.m3u8[^\s\'"<>]*)',
        r'["\']?(https?://[^\s\'"<>]*\.m3u8\??[^\s\'"<>]*)["\']?',
    ]

    for pattern in m3u8_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        if matches:
            stream_url = matches[0]
            logger.info(f"  m3u8 bulundu: {stream_url}")
            return clean_url(stream_url)

    # ============================================
    # YÖNTEM 3: .mpd (DASH) linkleri ara
    # ============================================
    mpd_patterns = [
        r'(https?://[^\s\'"<>]+\.mpd[^\s\'"<>]*)',
    ]
    for pattern in mpd_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        if matches:
            stream_url = matches[0]
            logger.info(f"  mpd bulundu: {stream_url}")
            return clean_url(stream_url)

    # ============================================
    # YÖNTEM 4: JavaScript değişkenlerinden stream URL
    # ============================================
    js_patterns = [
        r'var\s+\w*[Ss]ource\w*\s*=\s*["\']([^"\']+)["\']',
        r'var\s+\w*[Ss]tream\w*\s*=\s*["\']([^"\']+)["\']',
        r'var\s+\w*[Uu]rl\w*\s*=\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        r'var\s+\w*[Ll]ink\w*\s*=\s*["\']([^"\']+)["\']',
        r'["\']?file["\']?\s*:\s*["\']([^"\']+)["\']',
        r'["\']?source["\']?\s*:\s*["\']([^"\']+)["\']',
        r'["\']?stream["\']?\s*:\s*["\']([^"\']+)["\']',
        r'["\']?url["\']?\s*:\s*["\']([^"\']+)["\']',
        r'["\']?src["\']?\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        r'atob\(["\']([^"\']+)["\']\)',  # base64 encoded
    ]

    for pattern in js_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for match in matches:
            # Base64 decode dene
            if 'atob' in pattern:
                try:
                    import base64
                    decoded = base64.b64decode(match).decode('utf-8')
                    if '.m3u8' in decoded or 'http' in decoded:
                        logger.info(f"  Base64 decoded stream: {decoded}")
                        return clean_url(decoded)
                except Exception:
                    pass
            elif is_stream_url(match):
                logger.info(f"  JS'den stream bulundu: {match}")
                return clean_url(match)

    # ============================================
    # YÖNTEM 5: video/source elementleri
    # ============================================
    video_tags = soup.find_all('video')
    for video in video_tags:
        src = video.get('src', '')
        if src and is_stream_url(src):
            return clean_url(src)
        sources = video.find_all('source')
        for source in sources:
            src = source.get('src', '')
            if src and is_stream_url(src):
                return clean_url(src)

    # ============================================
    # YÖNTEM 6: API endpoint'leri kontrol et
    # ============================================
    api_patterns = [
        r'(https?://[^\s\'"<>]+/api/[^\s\'"<>]+)',
        r'(https?://[^\s\'"<>]+/embed/[^\s\'"<>]+)',
        r'(https?://[^\s\'"<>]+/live/[^\s\'"<>]+)',
        r'(https?://[^\s\'"<>]+/stream/[^\s\'"<>]+)',
        r'(https?://[^\s\'"<>]+/play/[^\s\'"<>]+)',
        r'fetch\(["\']([^"\']+)["\']',
        r'axios\.\w+\(["\']([^"\']+)["\']',
    ]

    for pattern in api_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for match in matches:
            if any(kw in match.lower() for kw in ['stream', 'live', 'play', 'channel', 'video']):
                api_stream = try_api_endpoint(match, channel_url)
                if api_stream:
                    return api_stream

    # ============================================
    # YÖNTEM 7: Embed sayfalarını kontrol et
    # ============================================
    embed_patterns = [
        r'(https?://[^\s\'"<>]+/embed[^\s\'"<>]*)',
        r'(https?://[^\s\'"<>]+/player[^\s\'"<>]*)',
        r'(https?://[^\s\'"<>]+\.php\?[^\s\'"<>]*)',
    ]

    for pattern in embed_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for match in matches:
            if BASE_URL not in match:  # Kendi sitesi değilse
                embed_stream = extract_from_embed(match, channel_url)
                if embed_stream:
                    return embed_stream

    logger.warning(f"  Stream bulunamadı: {channel_url}")
    return None


def extract_from_iframe(iframe_url):
    """iframe içindeki sayfadan stream URL çıkar"""
    if not iframe_url.startswith('http'):
        iframe_url = 'https:' + iframe_url if iframe_url.startswith('//') else iframe_url

    try:
        html = get_page(iframe_url)
        if not html:
            return None

        # m3u8 ara
        m3u8_matches = re.findall(
            r'(https?://[^\s\'"<>]+\.m3u8[^\s\'"<>]*)',
            html, re.IGNORECASE
        )
        if m3u8_matches:
            return clean_url(m3u8_matches[0])

        # Nested iframe kontrol
        soup = BeautifulSoup(html, 'html.parser')
        for nested_iframe in soup.find_all('iframe'):
            nested_src = nested_iframe.get('src', '')
            if nested_src and nested_src != iframe_url:
                result = extract_from_iframe(urljoin(iframe_url, nested_src))
                if result:
                    return result

        # JS değişkenlerinden ara
        js_stream_patterns = [
            r'["\']?(https?://[^\s\'"<>]+\.m3u8[^\s\'"<>]*)["\']?',
            r'source\s*:\s*["\']([^"\']+)["\']',
            r'file\s*:\s*["\']([^"\']+)["\']',
        ]
        for pattern in js_stream_patterns:
            matches = re.findall(pattern, html)
            for match in matches:
                if is_stream_url(match):
                    return clean_url(match)

    except Exception as e:
        logger.error(f"  iframe hatası: {e}")

    return None


def extract_from_embed(embed_url, referer):
    """Embed sayfasından stream URL çıkar"""
    try:
        custom_headers = HEADERS.copy()
        custom_headers['Referer'] = referer

        response = scraper.get(embed_url, headers=custom_headers, timeout=20)
        if response.status_code == 200:
            html = response.text
            m3u8_matches = re.findall(
                r'(https?://[^\s\'"<>]+\.m3u8[^\s\'"<>]*)',
                html, re.IGNORECASE
            )
            if m3u8_matches:
                return clean_url(m3u8_matches[0])
    except Exception as e:
        logger.error(f"  embed hatası: {e}")

    return None


def try_api_endpoint(api_url, referer):
    """API endpoint'inden stream URL almayı dene"""
    try:
        custom_headers = HEADERS.copy()
        custom_headers['Referer'] = referer
        custom_headers['Accept'] = 'application/json'
        custom_headers['X-Requested-With'] = 'XMLHttpRequest'

        response = scraper.get(api_url, headers=custom_headers, timeout=15)
        if response.status_code == 200:
            # JSON yanıt kontrol
            try:
                data = response.json()
                stream_keys = ['url', 'stream', 'source', 'file', 'link', 'src', 'playback']
                stream_url = find_in_dict(data, stream_keys)
                if stream_url and is_stream_url(stream_url):
                    return clean_url(stream_url)
            except json.JSONDecodeError:
                # Düz metin olarak m3u8 ara
                m3u8 = re.findall(
                    r'(https?://[^\s\'"<>]+\.m3u8[^\s\'"<>]*)',
                    response.text
                )
                if m3u8:
                    return clean_url(m3u8[0])
    except Exception:
        pass
    return None


def find_in_dict(data, keys):
    """Sözlükte belirli anahtarları recursive olarak ara"""
    if isinstance(data, dict):
        for key in keys:
            if key in data and isinstance(data[key], str):
                return data[key]
        for value in data.values():
            result = find_in_dict(value, keys)
            if result:
                return result
    elif isinstance(data, list):
        for item in data:
            result = find_in_dict(item, keys)
            if result:
                return result
    return None


def is_stream_url(url):
    """URL'nin geçerli bir stream URL'si olup olmadığını kontrol et"""
    if not url or not url.startswith('http'):
        return False
    stream_indicators = ['.m3u8', '.mpd', '.ts', '/live/', '/stream/',
                         '/play/', '/hls/', '/dash/', 'playlist']
    return any(ind in url.lower() for ind in stream_indicators)


def clean_url(url):
    """URL'yi temizle"""
    url = url.strip().strip('"').strip("'").strip()
    # Sonundaki gereksiz karakterleri temizle
    for char in ['"', "'", '\\', ';', ',', ')', '}']:
        if url.endswith(char):
            url = url[:-1]
    return url


def generate_m3u(channels_with_streams):
    """M3U dosyası oluştur"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')

    m3u_content = f'#EXTM3U\n'
    m3u_content += f'# SportsBite.org Channel List\n'
    m3u_content += f'# Generated: {timestamp}\n'
    m3u_content += f'# Total Channels: {len(channels_with_streams)}\n\n'

    for ch in channels_with_streams:
        name = ch['name']
        url = ch['stream_url']
        slug = ch.get('slug', '')
        group = categorize_channel(name, slug)

        # Logo URL (varsa)
        logo = ch.get('logo', '')
        logo_attr = f' tvg-logo="{logo}"' if logo else ''

        m3u_content += f'#EXTINF:-1 tvg-id="{slug}" tvg-name="{name}"{logo_attr} group-title="{group}",{name}\n'
        m3u_content += f'{url}\n\n'

    return m3u_content


def categorize_channel(name, slug):
    """Kanalı kategorize et"""
    text = (name + ' ' + slug).lower()

    categories = {
        'USA Sports': ['espn', 'fox sports', 'nbc sports', 'cbs sports', 'nba tv',
                       'nfl network', 'mlb network', 'nhl network', 'tnt', 'tbs',
                       'usa network', 'fs1', 'fs2', 'btn', 'sec network', 'abc',
                       'usa', 'big ten'],
        'UK Sports': ['sky sports', 'bt sport', 'bbc', 'itv', 'tnt sports',
                      'premier sports', 'racing tv'],
        'beIN Sports': ['bein'],
        'Eurosport': ['eurosport'],
        'Cricket': ['cricket', 'willow', 'star sports', 'sony ten'],
        'Canadian Sports': ['tsn', 'sportsnet'],
        'DAZN': ['dazn'],
        'Other Sports': ['arena sport', 'eleven sports', 'supersport'],
    }

    for group, keywords in categories.items():
        for kw in keywords:
            if kw in text:
                return group

    return 'Sports'


def main():
    """Ana fonksiyon"""
    logger.info("=" * 60)
    logger.info("SportsBite.org M3U Scraper Başlatılıyor...")
    logger.info("=" * 60)

    # 1. Kanalları keşfet
    channels = get_all_channels()
    if not channels:
        logger.error("Hiç kanal bulunamadı!")
        # Boş m3u oluştur
        with open('tv247.m3u', 'w', encoding='utf-8') as f:
            f.write('#EXTM3U\n# No channels found\n')
        return

    logger.info(f"\n{'='*60}")
    logger.info(f"Toplam {len(channels)} kanal bulundu. Stream'ler taranıyor...")
    logger.info(f"{'='*60}\n")

    # 2. Her kanal için stream URL'si bul
    channels_with_streams = []
    failed_channels = []

    for i, channel in enumerate(channels, 1):
        logger.info(f"[{i}/{len(channels)}] {channel['name']} taranıyor...")

        stream_url = extract_stream_url(channel['url'])

        if stream_url:
            channel['stream_url'] = stream_url
            channels_with_streams.append(channel)
            logger.info(f"  ✅ Stream bulundu: {stream_url[:80]}...")
        else:
            failed_channels.append(channel)
            logger.warning(f"  ❌ Stream bulunamadı")

        # Rate limiting - siteyi yormamak için
        time.sleep(1.5)

    # 3. M3U dosyası oluştur
    logger.info(f"\n{'='*60}")
    logger.info(f"Sonuç: {len(channels_with_streams)}/{len(channels)} kanal başarılı")
    logger.info(f"{'='*60}\n")

    if channels_with_streams:
        m3u_content = generate_m3u(channels_with_streams)

        with open('tv247.m3u', 'w', encoding='utf-8') as f:
            f.write(m3u_content)
        logger.info(f"✅ tv247.m3u dosyası oluşturuldu ({len(channels_with_streams)} kanal)")
    else:
        # Stream bulunamasa bile, kanal sayfası URL'lerini m3u'ya yaz
        logger.warning("Hiçbir stream URL bulunamadı. Kanal sayfaları URL olarak yazılıyor...")
        m3u_content = '#EXTM3U\n'
        m3u_content += f'# SportsBite.org - Kanal Sayfaları\n'
        m3u_content += f'# Not: Doğrudan stream linkleri bulunamadı\n\n'

        for ch in channels:
            m3u_content += f'#EXTINF:-1 tvg-name="{ch["name"]}",{ch["name"]}\n'
            m3u_content += f'{ch["url"]}\n\n'

        with open('tv247.m3u', 'w', encoding='utf-8') as f:
            f.write(m3u_content)
        logger.info("tv247.m3u dosyası kanal sayfası URL'leri ile oluşturuldu")

    # Başarısız kanalları logla
    if failed_channels:
        logger.info(f"\nBaşarısız kanallar ({len(failed_channels)}):")
        for ch in failed_channels:
            logger.info(f"  - {ch['name']}: {ch['url']}")

    # Özet JSON oluştur
    summary = {
        'generated': datetime.now().isoformat(),
        'total_channels': len(channels),
        'successful': len(channels_with_streams),
        'failed': len(failed_channels),
        'channels': [
            {'name': ch['name'], 'stream': ch.get('stream_url', '')}
            for ch in channels_with_streams
        ]
    }

    with open('scrape_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    logger.info("scrape_summary.json özet dosyası oluşturuldu")


if __name__ == '__main__':
    main()
