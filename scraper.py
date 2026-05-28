import re
import os
import sys
import json
import time
import base64
import asyncio
import aiohttp
from urllib.parse import urljoin
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

# ─────────────────────────────────────────────
# YAPILANDIRMA
# ─────────────────────────────────────────────
BASE_URL = "https://tv247.biz/watch/"
OUTPUT_FILE = "tv247.m3u"
CHANNELS_FILE = "channels.txt"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://tv247.us/",
}

# Bilinen kanal ID'leri (yeni kanallar otomatik eklenir)
CHANNEL_IDS = {
    "abc-usa": "51",
    "ahc-american-heroes-channel": "206",
    "antenna-tv-usa": "283",
    "a-e-usa": "302",
    "amc-usa": "303",
    "animal-planet": "304",
    "astro-supersport-1": "123",
    "astro-supersport-2": "124",
    "astro-supersport-3": "125",
    "astro-supersport-4": "126",
    "arena-sport-1-premium": "134",
    "arena-sport-2-premium": "135",
    "arena-sport-3-premium": "139",
    "arena-sport-1-serbia": "429",
    "arena-sport-2-serbia": "430",
    "arena-sport-3-serbia": "431",
    "arena-sport-4-serbia": "581",
    "arena-sport-1-croatia": "432",
    "arena-sport-2-croatia": "433",
    "arena-sport-3-croatia": "434",
    "arena-sport-4-croatia": "580",
    "alkass-one": "781",
    "alkass-two": "782",
    "alkass-three": "783",
    "alkass-four": "784",
    "arena-sport-1-bih": "579",
    "abu-dhabi-sports-1-uae": "600",
    "abu-dhabi-sports-2-uae": "601",
    "abu-dhabi-sports-1-premium": "609",
    "abu-dhabi-sports-2-premium": "610",
    "astro-cricket": "370",
    "antena-3-spain": "531",
    "arena-sports-tenis-serbia": "612",
    "acc-network-usa": "664",
    "adult-swim": "295",
    "a-sport-pk": "269",
    "axn-movies-portugal": "717",
    "arte-de": "725",
    "axs-tv-usa": "742",
    "abc-ny-usa": "766",
    "azteca-7-mx": "844",
    "altitude-sports": "923",
    "azteca-uno-mx": "934",
    "arena-sport-5-serbia": "940",
    "arena-sport-6-serbia": "941",
    "arena-sport-7-serbia": "942",
    "arena-sport-8-serbia": "943",
    "arena-sport-9-serbia": "944",
    "arena-sport-10-serbia": "945",
    "arte-france": "958",
    "automoto-la-chaine": "961",
    "atv-turkey": "1000",
    "a-spor-turkey": "1011",
    "bein-sports-mena-english-1": "61",
    "bein-sports-mena-english-2": "90",
    "bein-sports-1-arabic": "91",
    "bein-sports-2-arabic": "92",
    "bein-sports-3-arabic": "93",
    "bein-sports-4-arabic": "94",
    "bein-sports-5-arabic": "95",
    "bein-sports-6-arabic": "96",
    "bein-sports-7-arabic": "97",
    "bein-sports-8-arabic": "98",
    "bein-sports-9-arabic": "99",
    "bein-sports-xtra-1": "100",
    "bein-sports-max-4-france": "494",
    "bein-sports-max-5-france": "495",
    "bein-sports-max-6-france": "496",
    "bein-sports-max-7-france": "497",
    "bein-sports-max-8-france": "498",
    "bein-sports-max-9-france": "499",
    "bein-sports-max-10-france": "500",
    "bein-sports-1-france": "116",
    "bein-sports-2-france": "117",
    "bein-sports-3-france": "118",
    "bein-sports-1-turkey": "62",
    "bein-sports-2-turkey": "63",
    "bein-sports-3-turkey": "64",
    "bein-sports-4-turkey": "67",
    "bein-sports-hd-qatar": "578",
    "bein-sports-usa": "425",
    "bein-sports-en-espanol": "372",
    "bein-sports-1-australia": "491",
    "bein-sports-2-australia": "492",
    "bein-sports-3-australia": "493",
    "barca-tv-spain": "522",
    "benfica-tv-pt": "380",
    "boomerang": "648",
    "bnt-1-bulgaria": "476",
    "bnt-2-bulgaria": "477",
    "bnt-3-bulgaria": "478",
    "br-fernsehen-de": "737",
    "btv-bulgaria": "479",
    "btv-action-bulgaria": "481",
    "btv-lady-bulgaria": "484",
    "bbc-america": "305",
    "bet-usa": "306",
    "bravo-usa": "307",
    "bbc-news-channel-hd": "349",
    "bbc-one-uk": "356",
    "bbc-two-uk": "357",
    "bbc-three-uk": "358",
    "bbc-four-uk": "359",
    "big-ten-network-btn-usa": "397",
    "bein-sports-1-malaysia": "712",
    "bein-sports-2-malaysia": "713",
    "bein-sports-3-malaysia": "714",
    "bfm-tv-france": "957",
    "bein-sports-5-turkey": "1010",
    "bandsports-brasil": "275",
    "canal-plus-motogp-france": "271",
    "canal-plus-formula-1": "273",
    "cw-pix-11-usa": "280",
    "court-tv-usa": "281",
    "cw-usa": "300",
    "cnbc-usa": "309",
    "comedy-central": "310",
    "cartoon-network": "339",
    "cnn-usa": "345",
    "cinemax-usa": "374",
    "cuatro-spain": "535",
    "channel-4-uk": "354",
    "channel-5-uk": "355",
    "cbs-sports-network": "308",
    "canal-plus-france": "121",
    "canal-plus-sport-france": "122",
    "canal-plus-foot-france": "463",
    "canal-plus-sport360": "464",
    "canal-11-portugal": "540",
    "canal-plus-sport-poland": "48",
    "canal-plus-sport-2-poland": "73",
    "canal-plus-sport-3-poland": "259",
    "canal-plus-sport-5-poland": "75",
    "canal-plus-premium-poland": "566",
    "canal-plus-family-poland": "567",
    "canal-plus-seriale-poland": "570",
    "canal-plus-sport-1-afrique": "486",
    "canal-plus-sport-2-afrique": "487",
    "canal-plus-sport-3-afrique": "488",
    "canal-plus-sport-4-afrique": "489",
    "canal-plus-sport-5-afrique": "490",
    "canal-9-denmark": "805",
    "combate-brasil": "89",
    "cosmote-sport-1-hd": "622",
    "cosmote-sport-2-hd": "623",
    "cosmote-sport-3-hd": "624",
    "cosmote-sport-4-hd": "625",
    "cosmote-sport-5-hd": "626",
    "cosmote-sport-6-hd": "627",
    "cosmote-sport-7-hd": "628",
    "cosmote-sport-8-hd": "629",
    "cosmote-sport-9-hd": "630",
    "channel-9-israel": "546",
    "channel-10-israel": "547",
    "channel-11-israel": "548",
    "channel-12-israel": "549",
    "channel-13-israel": "551",
    "channel-14-israel": "552",
    "c-more-first-sweden": "812",
    "c-more-hits-sweden": "813",
    "c-more-series-sweden": "814",
    "cozi-tv-usa": "748",
    "cmt-usa": "647",
    "ctv-canada": "602",
    "ctv-2-canada": "838",
    "crime-plus-investigation-usa": "669",
    "comet-usa": "696",
    "cooking-channel-usa": "697",
    "cleo-tv": "715",
    "c-span-1": "750",
    "cbsny-usa": "767",
    "chicago-sports-network": "776",
    "citytv": "831",
    "cbc-ca": "832",
    "claro-sports-mx": "933",
    "canal5-mx": "936",
    "c8-france": "956",
    "cnews-france": "964",
    "canal-plus-sport-cz": "1020",
    "ct-sport-cz": "1033",
    "cbs-sports-golazo": "910",
    "cmtv-portugal": "790",
    "cytavision-sports-1-cyprus": "911",
    "cytavision-sports-2-cyprus": "912",
    "cytavision-sports-3-cyprus": "913",
    "cytavision-sports-4-cyprus": "914",
    "cytavision-sports-5-cyprus": "915",
    "cytavision-sports-6-cyprus": "916",
    "cytavision-sports-7-cyprus": "917",
}

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# ─────────────────────────────────────────────
# TOKEN OLUŞTUR
# ─────────────────────────────────────────────
def generate_playlist_url(channel_id: str) -> str:
    """Channel ID'den playlist URL'si oluştur"""
    ts = int(time.time() * 1000)
    
    token_data = {
        "channelId": str(channel_id),
        "ts": ts
    }
    
    token_json = json.dumps(token_data, separators=(',', ':'))
    token_b64 = base64.b64encode(token_json.encode()).decode()
    
    return f"https://chat.cfbu247.sbs/api/proxy/playlist?token={token_b64}"

# ─────────────────────────────────────────────
# ASYNC HTML ÇEKME VE ID BULMA
# ─────────────────────────────────────────────
async def fetch_html(session: aiohttp.ClientSession, url: str, referer: str = None) -> Optional[str]:
    """Async HTML içeriği çek"""
    try:
        headers = HEADERS.copy()
        if referer:
            headers["Referer"] = referer
        
        timeout = aiohttp.ClientTimeout(total=15, connect=5)
        async with session.get(url, headers=headers, timeout=timeout, ssl=False) as response:
            if response.status == 200:
                return await response.text()
    except Exception as e:
        pass
    return None

async def find_channel_id_from_page_async(session: aiohttp.ClientSession, channel_slug: str) -> Optional[str]:
    """Sayfa HTML'inden channel ID'yi async çıkar"""
    url = f"{BASE_URL}{channel_slug}/"
    
    html = await fetch_html(session, url)
    if not html:
        return None
    
    # 1. Doğrudan sayfada ID ara
    id_patterns = [
        r'data-id=["\'](\d+)["\']',
        r'channel[_-]?id["\']?\s*[:=]\s*["\']?(\d+)',
        r'stream[_-]?id["\']?\s*[:=]\s*["\']?(\d+)',
        r'/embed/(\d+)',
        r'\?id=(\d+)',
        r'&id=(\d+)',
    ]
    
    for pattern in id_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        if matches:
            return matches[0]
    
    # 2. iframe src'lerini kontrol et
    iframe_pattern = r'<iframe[^>]+src=["\']([^"\']+)["\']'
    iframes = re.findall(iframe_pattern, html, re.IGNORECASE)
    
    for iframe_src in iframes:
        iframe_url = urljoin(url, iframe_src)
        
        # iframe URL'sinde ID var mı?
        id_match = re.search(r'[?&]id=(\d+)', iframe_url)
        if id_match:
            return id_match.group(1)
        
        # iframe içeriğini çek
        iframe_html = await fetch_html(session, iframe_url, url)
        if iframe_html:
            for pattern in id_patterns:
                matches = re.findall(pattern, iframe_html, re.IGNORECASE)
                if matches:
                    return matches[0]
            
            # iç iframe var mı?
            inner_iframes = re.findall(iframe_pattern, iframe_html, re.IGNORECASE)
            for inner_src in inner_iframes:
                inner_url = urljoin(iframe_url, inner_src)
                id_match = re.search(r'[?&]id=(\d+)', inner_url)
                if id_match:
                    return id_match.group(1)
                
                inner_html = await fetch_html(session, inner_url, iframe_url)
                if inner_html:
                    for pattern in id_patterns:
                        matches = re.findall(pattern, inner_html, re.IGNORECASE)
                        if matches:
                            return matches[0]
    
    # 3. Script tag'larında ara
    script_pattern = r'<script[^>]*>(.*?)</script>'
    scripts = re.findall(script_pattern, html, re.DOTALL | re.IGNORECASE)
    
    for script in scripts:
        for pattern in id_patterns:
            matches = re.findall(pattern, script, re.IGNORECASE)
            if matches:
                return matches[0]
    
    return None

async def find_direct_token_url_async(session: aiohttp.ClientSession, channel_slug: str) -> Optional[str]:
    """Sayfada hazır token URL'si ara"""
    url = f"{BASE_URL}{channel_slug}/"
    
    html = await fetch_html(session, url)
    if not html:
        return None
    
    # Hazır playlist URL'si
    token_pattern = r'(https?://[^\s"\'<>]+/api/proxy/playlist\?token=[A-Za-z0-9+/=_-]+)'
    
    # Ana sayfada ara
    matches = re.findall(token_pattern, html)
    if matches:
        return matches[0]
    
    # iframe'lerde ara
    iframe_pattern = r'<iframe[^>]+src=["\']([^"\']+)["\']'
    iframes = re.findall(iframe_pattern, html, re.IGNORECASE)
    
    for iframe_src in iframes:
        iframe_url = urljoin(url, iframe_src)
        iframe_html = await fetch_html(session, iframe_url, url)
        if iframe_html:
            matches = re.findall(token_pattern, iframe_html)
            if matches:
                return matches[0]
            
            # Daha derin iframe
            inner_iframes = re.findall(iframe_pattern, iframe_html, re.IGNORECASE)
            for inner_src in inner_iframes:
                inner_url = urljoin(iframe_url, inner_src)
                inner_html = await fetch_html(session, inner_url, iframe_url)
                if inner_html:
                    matches = re.findall(token_pattern, inner_html)
                    if matches:
                        return matches[0]
    
    return None

# ─────────────────────────────────────────────
# ANA STREAM BULMA FONKSİYONU (ASYNC)
# ─────────────────────────────────────────────
async def find_stream_url_async(session: aiohttp.ClientSession, channel_slug: str, semaphore: asyncio.Semaphore) -> Optional[str]:
    """Kanal için stream URL'si bul - async versiyon"""
    async with semaphore:
        # 1. Bilinen ID varsa doğrudan kullan
        if channel_slug in CHANNEL_IDS and CHANNEL_IDS[channel_slug]:
            return generate_playlist_url(CHANNEL_IDS[channel_slug])
        
        # 2. Doğrudan token URL ara
        direct_url = await find_direct_token_url_async(session, channel_slug)
        if direct_url:
            CHANNEL_IDS[channel_slug] = "found_via_token"
            return direct_url
        
        # 3. Sayfadan ID bul
        channel_id = await find_channel_id_from_page_async(session, channel_slug)
        if channel_id:
            CHANNEL_IDS[channel_slug] = channel_id
            return generate_playlist_url(channel_id)
        
        return None

# ─────────────────────────────────────────────
# KANAL LİSTESİ YÜKLE
# ─────────────────────────────────────────────
def load_channels() -> List[Dict]:
    """channels.txt'den kanal listesi yükle (format: slug|isim|grup)"""
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
                group = parts[2].strip() if len(parts) > 2 else "TV247"
                channels.append({'slug': slug, 'name': name, 'group': group})
    else:
        # Varsayılan kanal
        channels = [
            {'slug': 'bein-sports-1-turkey', 'name': 'beIN Sports 1', 'group': 'TV247'},
        ]
    
    return channels

# ─────────────────────────────────────────────
# TOPLU ASYNC İŞLEME
# ─────────────────────────────────────────────
async def process_all_channels(channels: List[Dict]) -> List[Dict]:
    """Tüm kanalları async işle"""
    results = []
    
    # Bağlantı ayarları
    connector = aiohttp.TCPConnector(
        limit=50,
        limit_per_host=20,
        ttl_dns_cache=300,
        ssl=False
    )
    
    # Semaphore ile eşzamanlı istek limiti
    max_concurrent = int(os.getenv('MAX_WORKERS', 20))
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for ch in channels:
            task = find_stream_url_async(session, ch['slug'], semaphore)
            tasks.append(task)
        
        # Tüm görevleri paralel çalıştır
        urls = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Sonuçları birleştir
        for ch, url in zip(channels, urls):
            if isinstance(url, Exception):
                url = None
            
            results.append({
                'slug': ch['slug'],
                'name': ch['name'],
                'group': ch.get('group', 'TV247'),
                'url': url
            })
    
    return results

# ─────────────────────────────────────────────
# M3U DOSYASI OLUŞTUR
# ─────────────────────────────────────────────
def generate_m3u(results: List[Dict]) -> str:
    """M3U dosyası oluştur"""
    lines = ['#EXTM3U']
    lines.append(f'# Updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}')
    lines.append('')
    
    for ch in results:
        if ch.get('url'):
            group_title = ch.get('group', 'TV247')
            lines.append(
                f'#EXTINF:-1 tvg-id="{ch["slug"]}" '
                f'tvg-name="{ch["name"]}" '
                f'group-title="{group_title}",{ch["name"]}'
            )
            lines.append(ch['url'])
            lines.append('')
    
    content = '\n'.join(lines)
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return content

# ─────────────────────────────────────────────
# MAIN (ASYNC)
# ─────────────────────────────────────────────
async def main_async():
    log("=" * 50)
    log("TV247 M3U Generator (ASYNC Optimize)")
    log("=" * 50)
    
    channels = load_channels()
    log(f"\n📺 {len(channels)} kanal işlenecek (Async paralel mod)")
    
    start_time = time.time()
    
    # Tüm kanalları işle
    results = await process_all_channels(channels)
    
    elapsed = time.time() - start_time
    
    # M3U oluştur
    content = generate_m3u(results)
    
    # Özet
    found = sum(1 for r in results if r.get('url'))
    log(f"\n{'=' * 50}")
    log(f"✅ Tamamlandı! {found}/{len(channels)} kanal bulundu")
    log(f"⏱️  Süre: {elapsed:.2f} saniye")
    log(f"📁 {OUTPUT_FILE} oluşturuldu")
    
    # Bulunan ID'leri göster (sadece yeni bulunanlar)
    new_ids = {k: v for k, v in CHANNEL_IDS.items() if v and v not in ["found_via_token"]}
    if new_ids:
        log(f"\n💾 Yeni bulunan kanal ID'leri ({len(new_ids)} adet):")
        for slug, cid in list(new_ids.items())[:10]:  # İlk 10'u göster
            log(f"  {slug}: {cid}")
    
    return 0 if found > 0 else 1

def main():
    """Ana fonksiyon"""
    try:
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        log("\n⚠️ İşlem kullanıcı tarafından durduruldu")
        return 1
    except Exception as e:
        log(f"❌ Beklenmeyen hata: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
