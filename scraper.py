#!/usr/bin/env python3
"""
SportsBite.org Channel Scraper
Kanal sayfalarındaki iframe içindeki stream URL'lerini bulur
ve tv247.m3u dosyasına yazar.
"""

import re
import json
import time
import logging
import cloudscraper
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_URL = "https://sportsbite.org"
CHANNELS_PAGE = f"{BASE_URL}/watch/channel/"
OUTPUT_FILE = "tv247.m3u"

# Bilinen iframe domain'leri
IFRAME_DOMAINS = [
    "channels.forestgump.space",
    "embedstream",
    "cricfree",
    "streameast",
    "weakstream",
    "methstream",
]


def create_scraper():
    """CloudScraper ile Cloudflare bypass eden session oluştur."""
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
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


def get_channel_list(scraper):
    """
    Ana kanal listesi sayfasından tüm kanal linklerini çek.
    """
    channels = []
    logger.info(f"Kanal listesi çekiliyor: {CHANNELS_PAGE}")

    try:
        resp = scraper.get(CHANNELS_PAGE, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Kanal linklerini bul - /watch/channel/XXX formatında
        links = soup.find_all('a', href=True)
        for link in links:
            href = link.get('href', '')
            full_url = urljoin(BASE_URL, href)

            # /watch/channel/XXXXX formatındaki linkleri yakala
            if re.search(r'/watch/channel/[\w\-]+', full_url):
                # Ana sayfa linkini atla
                if full_url.rstrip('/') == CHANNELS_PAGE.rstrip('/'):
                    continue

                channel_name = extract_channel_name(link, href)
                if channel_name and full_url not in [c['url'] for c in channels]:
                    channels.append({
                        'url': full_url,
                        'name': channel_name,
                    })

        logger.info(f"Toplam {len(channels)} kanal bulundu")

    except Exception as e:
        logger.error(f"Kanal listesi alınamadı: {e}")

    # Eğer otomatik bulamazsa, bilinen kanalları dene
    if not channels:
        channels = generate_known_channels()

    return channels


def extract_channel_name(link_element, href):
    """Link elementinden kanal adını çıkar."""
    # Önce link metnine bak
    text = link_element.get_text(strip=True)
    if text and len(text) > 1:
        return clean_channel_name(text)

    # img alt attribute'una bak
    img = link_element.find('img')
    if img and img.get('alt'):
        return clean_channel_name(img['alt'])

    # URL'den çıkar
    slug = href.rstrip('/').split('/')[-1]
    return clean_channel_name(slug)


def clean_channel_name(name):
    """Kanal adını temizle."""
    name = re.sub(r'[-_]+', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    name = name.title()
    return name if name else None


def generate_known_channels():
    """Bilinen kanal slug'larından liste oluştur."""
    known_slugs = [
        "1-usa", "2-usa", "3-usa", "4-usa", "5-usa",
        "6-usa", "7-usa", "8-usa", "9-usa", "10-usa",
        "1-uk", "2-uk", "3-uk", "4-uk", "5-uk",
        "6-uk", "7-uk", "8-uk", "9-uk", "10-uk",
        "bein-sports-1", "bein-sports-2", "bein-sports-3",
        "bein-sports-4", "bein-sports-5",
        "sky-sports-main-event", "sky-sports-premier-league",
        "sky-sports-football", "sky-sports-f1", "sky-sports-cricket",
        "sky-sports-golf", "sky-sports-tennis", "sky-sports-nfl",
        "bt-sport-1", "bt-sport-2", "bt-sport-3",
        "espn", "espn2", "espn-plus", "espn-news",
        "fox-sports-1", "fox-sports-2",
        "nbc-sports", "cbs-sports",
        "tnt-sports", "usa-network",
        "dazn-1", "dazn-2",
        "eurosport-1", "eurosport-2",
        "supersport",
        "willow-cricket", "willow-extra",
        "star-sports-1", "star-sports-2",
        "ten-sports", "ptv-sports",
        "sony-ten-1", "sony-ten-2", "sony-ten-3",
        "s-sport", "s-sport-2",
        "trt-spor", "bein-sports-turkey",
    ]

    channels = []
    for slug in known_slugs:
        channels.append({
            'url': f"{BASE_URL}/watch/channel/{slug}",
            'name': clean_channel_name(slug),
        })
    return channels


def find_iframe_src(scraper, channel_url):
    """
    Kanal sayfasındaki iframe src'sini bul.
    Birden fazla katmanlı iframe'leri de takip eder.
    """
    logger.info(f"Kanal sayfası taranıyor: {channel_url}")

    try:
        resp = scraper.get(channel_url, timeout=30)
        if resp.status_code == 404:
            logger.warning(f"Sayfa bulunamadı: {channel_url}")
            return None
        resp.raise_for_status()

        html = resp.text
        iframe_urls = extract_iframe_urls(html, channel_url)

        # İlk seviye iframe'leri kontrol et
        for iframe_url in iframe_urls:
            logger.info(f"  iframe bulundu: {iframe_url}")
            stream_url = extract_stream_from_iframe(scraper, iframe_url, channel_url)
            if stream_url:
                return stream_url

        # JavaScript içinde gizli iframe URL'lerini ara
        js_iframes = find_js_embedded_urls(html)
        for iframe_url in js_iframes:
            logger.info(f"  JS iframe bulundu: {iframe_url}")
            stream_url = extract_stream_from_iframe(scraper, iframe_url, channel_url)
            if stream_url:
                return stream_url

    except Exception as e:
        logger.error(f"Hata ({channel_url}): {e}")

    return None


def extract_iframe_urls(html, base_url):
    """HTML içindeki tüm iframe src URL'lerini çıkar."""
    urls = []
    soup = BeautifulSoup(html, 'html.parser')

    # Standart iframe'ler
    iframes = soup.find_all('iframe')
    for iframe in iframes:
        src = iframe.get('src') or iframe.get('data-src') or iframe.get('data-lazy-src')
        if src:
            full_url = urljoin(base_url, src)
            if is_valid_stream_iframe(full_url):
                urls.append(full_url)

    # Regex ile de ara (JS ile eklenen iframe'ler için)
    iframe_pattern = re.compile(
        r'<iframe[^>]+(?:src|data-src)\s*=\s*["\']([^"\']+)["\']',
        re.IGNORECASE
    )
    for match in iframe_pattern.finditer(html):
        url = urljoin(base_url, match.group(1))
        if url not in urls and is_valid_stream_iframe(url):
            urls.append(url)

    return urls


def is_valid_stream_iframe(url):
    """Stream iframe'i olup olmadığını kontrol et."""
    # Reklam / analytics iframe'lerini filtrele
    skip_domains = [
        'google', 'facebook', 'twitter', 'doubleclick',
        'analytics', 'adsense', 'adservice', 'youtube.com/subscribe'
    ]
    url_lower = url.lower()
    for skip in skip_domains:
        if skip in url_lower:
            return False
    return True


def find_js_embedded_urls(html):
    """JavaScript kodunda gizli stream URL'lerini bul."""
    urls = []

    # forestgump.space pattern
    patterns = [
        r'["\']?(https?://channels\.forestgump\.space/[^"\'\s]+)["\']?',
        r'["\']?(https?://[^"\'\s]*embed[^"\'\s]*)["\']?',
        r'["\']?(https?://[^"\'\s]*/ch\d+/[^"\'\s]*)["\']?',
        r'["\']?(https?://[^"\'\s]*stream[^"\'\s]*embed[^"\'\s]*)["\']?',
        r'src\s*:\s*["\']([^"\']+)["\']',
        r'source\s*:\s*["\']([^"\']+)["\']',
        r'file\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        r'url\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, html, re.IGNORECASE):
            url = match.group(1)
            if url.startswith('http') and is_valid_stream_iframe(url):
                urls.append(url)

    return list(set(urls))


def extract_stream_from_iframe(scraper, iframe_url, referer):
    """
    iframe URL'sinden gerçek stream URL'sini çıkar.
    Birden fazla seviye iframe'i takip eder.
    """
    try:
        headers = {
            'Referer': referer,
            'Origin': get_origin(referer),
        }

        resp = scraper.get(iframe_url, timeout=30, headers=headers)
        if resp.status_code != 200:
            return None

        html = resp.text

        # 1. Doğrudan m3u8 URL'si ara
        m3u8_url = find_m3u8_url(html)
        if m3u8_url:
            logger.info(f"  ✓ m3u8 bulundu: {m3u8_url}")
            return m3u8_url

        # 2. mpd (DASH) URL'si ara
        mpd_url = find_mpd_url(html)
        if mpd_url:
            logger.info(f"  ✓ mpd bulundu: {mpd_url}")
            return mpd_url

        # 3. İç içe iframe'leri takip et
        inner_iframes = extract_iframe_urls(html, iframe_url)
        for inner_url in inner_iframes:
            logger.info(f"    İç iframe: {inner_url}")
            result = extract_stream_from_iframe(scraper, inner_url, iframe_url)
            if result:
                return result

        # 4. JS'de gizli URL'leri ara
        js_urls = find_js_embedded_urls(html)
        for js_url in js_urls:
            if '.m3u8' in js_url or '.mpd' in js_url:
                logger.info(f"  ✓ JS'de stream bulundu: {js_url}")
                return js_url

        # 5. forestgump.space embed URL'sini iframe URL olarak döndür
        if 'forestgump.space' in iframe_url or 'embed' in iframe_url:
            logger.info(f"  ✓ Embed URL kullanılıyor: {iframe_url}")
            return iframe_url

        # 6. JSON veri bloklarını kontrol et
        json_stream = find_stream_in_json(html)
        if json_stream:
            return json_stream

    except Exception as e:
        logger.error(f"iframe çözümleme hatası ({iframe_url}): {e}")

    return None


def find_m3u8_url(html):
    """HTML/JS içinde m3u8 URL'si bul."""
    patterns = [
        r'["\']?(https?://[^"\'<>\s]+\.m3u8(?:\?[^"\'<>\s]*)?)["\']?',
        r'source\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        r'file\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        r'src\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        r'url\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        r'video_url\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        r'hls\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        r'hlsUrl\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        r'playbackUrl\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        r'Clappr\.Player\s*\(\s*\{[^}]*source\s*:\s*["\']([^"\']+)["\']',
        r'Hls\.loadSource\s*\(\s*["\']([^"\']+)["\']',
        r'videojs[^{]*\{[^}]*sources\s*:\s*\[\s*\{[^}]*src\s*:\s*["\']([^"\']+)["\']',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            url = match.group(1)
            if url.startswith('http'):
                return url
    return None


def find_mpd_url(html):
    """HTML/JS içinde DASH mpd URL'si bul."""
    patterns = [
        r'["\']?(https?://[^"\'<>\s]+\.mpd(?:\?[^"\'<>\s]*)?)["\']?',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def find_stream_in_json(html):
    """Sayfadaki JSON bloklarında stream URL'si ara."""
    json_patterns = [
        r'JSON\.parse\s*\(\s*["\']({[^"\']+})["\']',
        r'var\s+\w+\s*=\s*({[^;]+});',
    ]

    for pattern in json_patterns:
        for match in re.finditer(pattern, html):
            try:
                text = match.group(1).replace("\\'", "'").replace('\\"', '"')
                data = json.loads(text)
                url = search_dict_for_stream(data)
                if url:
                    return url
            except (json.JSONDecodeError, Exception):
                continue
    return None


def search_dict_for_stream(obj, depth=0):
    """Dict/list içinde m3u8/mpd URL'si ara."""
    if depth > 5:
        return None

    if isinstance(obj, str):
        if '.m3u8' in obj or '.mpd' in obj:
            return obj
    elif isinstance(obj, dict):
        for v in obj.values():
            result = search_dict_for_stream(v, depth + 1)
            if result:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = search_dict_for_stream(item, depth + 1)
            if result:
                return result
    return None


def get_origin(url):
    """URL'den origin çıkar."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def generate_m3u(channels_with_streams):
    """M3U playlist dosyası oluştur."""
    lines = ['#EXTM3U']
    lines.append('#EXTM3U url-tvg="https://iptv-org.github.io/epg/guides/auto.xml"')
    lines.append('')

    for channel in channels_with_streams:
        name = channel['name']
        stream_url = channel['stream_url']
        logo = channel.get('logo', '')
        group = channel.get('group', 'Sports')

        extinf = f'#EXTINF:-1 group-title="{group}"'
        if logo:
            extinf += f' tvg-logo="{logo}"'
        extinf += f' tvg-name="{name}",{name}'

        lines.append(extinf)

        # Eğer stream URL bir embed sayfasıysa (m3u8 değilse), header ekle
        if stream_url and '.m3u8' not in stream_url and '.mpd' not in stream_url:
            # Embed URL'leri için pipe formatı ile referer ekle
            referer = channel.get('url', BASE_URL)
            lines.append(f'#EXTVLCOPT:http-referrer={referer}')
            lines.append(f'#EXTVLCOPT:http-user-agent=Mozilla/5.0')

        lines.append(stream_url)
        lines.append('')

    return '\n'.join(lines)


def try_channel_variations(scraper, base_slug):
    """Farklı URL varyasyonlarını dene."""
    variations = [
        f"{BASE_URL}/watch/channel/{base_slug}",
        f"{BASE_URL}/watch/channel/{base_slug}/",
    ]

    for url in variations:
        result = find_iframe_src(scraper, url)
        if result:
            return result, url

    return None, None


def main():
    logger.info("=" * 60)
    logger.info("SportsBite Channel Scraper başlatılıyor...")
    logger.info("=" * 60)

    scraper = create_scraper()

    # 1. Kanal listesini al
    channels = get_channel_list(scraper)
    if not channels:
        logger.error("Hiç kanal bulunamadı!")
        return

    logger.info(f"\n{'='*60}")
    logger.info(f"Toplam {len(channels)} kanal işlenecek")
    logger.info(f"{'='*60}\n")

    # 2. Her kanal için stream URL'sini bul
    channels_with_streams = []
    failed_channels = []

    for i, channel in enumerate(channels, 1):
        logger.info(f"\n[{i}/{len(channels)}] {channel['name']}")
        logger.info(f"  URL: {channel['url']}")

        stream_url = find_iframe_src(scraper, channel['url'])

        if stream_url:
            channel['stream_url'] = stream_url
            channels_with_streams.append(channel)
            logger.info(f"  ✅ Stream bulundu: {stream_url[:80]}...")
        else:
            failed_channels.append(channel)
            logger.warning(f"  ❌ Stream bulunamadı")

        # Rate limiting - sunucuyu yormamak için
        time.sleep(2)

    # 3. M3U dosyasını oluştur
    logger.info(f"\n{'='*60}")
    logger.info(f"Sonuçlar:")
    logger.info(f"  ✅ Başarılı: {len(channels_with_streams)}")
    logger.info(f"  ❌ Başarısız: {len(failed_channels)}")
    logger.info(f"{'='*60}\n")

    if channels_with_streams:
        m3u_content = generate_m3u(channels_with_streams)

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(m3u_content)

        logger.info(f"✅ {OUTPUT_FILE} dosyası oluşturuldu!")
        logger.info(f"   {len(channels_with_streams)} kanal yazıldı.")
    else:
        logger.warning("Hiç stream bulunamadı, M3U dosyası oluşturulmadı.")

    # Başarısız kanalları logla
    if failed_channels:
        logger.info("\nBaşarısız kanallar:")
        for ch in failed_channels:
            logger.info(f"  - {ch['name']}: {ch['url']}")


if __name__ == '__main__':
    main()
