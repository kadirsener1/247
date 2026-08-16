#!/usr/bin/env python3
"""
CDNLiveTV M3U Playlist Generator v3.0
API → Player Page → Stream URL → M3U
"""

import requests
import json
import os
import re
import sys
import time
import concurrent.futures
from datetime import datetime, timezone
from urllib.parse import quote, unquote

# ─── Ayarlar ───
API_URL = "https://api.cdnlivetv.is/api/v1/channels/?user=cdnlivetv&plan=free"
OUTPUT_FILE = "cdnlive.m3u"
CONFIG_FILE = "config.json"
MAX_WORKERS = 10  # Paralel istek sayısı
REQUEST_TIMEOUT = 20

# Ülke kodu → Ülke adı eşlemesi
COUNTRY_MAP = {
    "us": "🇺🇸 United States",
    "gb": "🇬🇧 United Kingdom",
    "de": "🇩🇪 Germany",
    "fr": "🇫🇷 France",
    "es": "🇪🇸 Spain",
    "it": "🇮🇹 Italy",
    "pt": "🇵🇹 Portugal",
    "nl": "🇳🇱 Netherlands",
    "be": "🇧🇪 Belgium",
    "tr": "🇹🇷 Turkey",
    "br": "🇧🇷 Brazil",
    "ar": "🇦🇷 Argentina",
    "mx": "🇲🇽 Mexico",
    "ca": "🇨🇦 Canada",
    "au": "🇦🇺 Australia",
    "nz": "🇳🇿 New Zealand",
    "se": "🇸🇪 Sweden",
    "dk": "🇩🇰 Denmark",
    "pl": "🇵🇱 Poland",
    "ro": "🇷🇴 Romania",
    "bg": "🇧🇬 Bulgaria",
    "gr": "🇬🇷 Greece",
    "il": "🇮🇱 Israel",
    "ae": "🇦🇪 UAE",
    "sa": "🇸🇦 Saudi Arabia",
    "ru": "🇷🇺 Russia",
    "cy": "🇨🇾 Cyprus",
    "cz": "🇨🇿 Czech Republic",
    "at": "🇦🇹 Austria",
    "cl": "🇨🇱 Chile",
    "uy": "🇺🇾 Uruguay",
}


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    symbol = {"INFO": "ℹ️", "OK": "✅", "WARN": "⚠️", "ERROR": "❌", "WORK": "🔄"}.get(level, "")
    print(f"[{ts}] {symbol} {msg}")


def get_session():
    """Reusable session with headers"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://cdnlivetv.tv/",
        "Origin": "https://cdnlivetv.tv"
    })
    return session


def load_config():
    default = {
        "last_update": "",
        "channel_count": 0,
        "groups": {},
        "stream_cache": {}
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                for k, v in default.items():
                    if k not in cfg:
                        cfg[k] = v
                return cfg
        except:
            pass
    return default


def save_config(config):
    # stream_cache çok büyük olmasın
    cache = config.get("stream_cache", {})
    if len(cache) > 500:
        config["stream_cache"] = {}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def fetch_channels():
    """API'den kanal listesini çek"""
    log("Kanal listesi API'den çekiliyor...", "WORK")
    
    session = get_session()
    session.headers["Accept"] = "application/json"
    
    try:
        resp = session.get(API_URL, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        
        channels = data.get("channels", [])
        total = data.get("total_channels", len(channels))
        
        log(f"API'den {total} kanal bilgisi alındı", "OK")
        return channels
    
    except Exception as e:
        log(f"API hatası: {e}", "ERROR")
        return []


def extract_stream_from_player(player_url, session):
    """
    Player sayfasından gerçek m3u8 stream URL'sini çıkar.
    Player sayfası bir HTML/JS wrapper, içinde gerçek stream URL gömülü.
    """
    try:
        resp = session.get(player_url, timeout=REQUEST_TIMEOUT)
        
        if resp.status_code != 200:
            return None
        
        text = resp.text
        
        # ─── Yöntem 1: Direkt m3u8 URL ara ───
        m3u8_patterns = [
            r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)',
            r'source\s*[:=]\s*["\']?(https?://[^\s"\'<>]+)["\']?',
            r'file\s*[:=]\s*["\']?(https?://[^\s"\'<>]+)["\']?',
            r'src\s*[:=]\s*["\']?(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)["\']?',
            r'video_url\s*[:=]\s*["\']?(https?://[^\s"\'<>]+)["\']?',
            r'stream_url\s*[:=]\s*["\']?(https?://[^\s"\'<>]+)["\']?',
            r'hls\.loadSource\(["\']?(https?://[^\s"\'<>]+)["\']?\)',
            r'Hls\.loadSource\(["\']?(https?://[^\s"\'<>]+)["\']?\)',
            r'player\.src\(\{.*?src\s*:\s*["\']?(https?://[^\s"\'<>]+)["\']?',
        ]
        
        for pattern in m3u8_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                url = match.strip().rstrip("'\"\\);}")
                if ".m3u8" in url or "playlist" in url or "/live/" in url or "/stream/" in url:
                    return url
        
        # ─── Yöntem 2: iframe src ara ───
        iframe_pattern = r'<iframe[^>]+src=["\']?(https?://[^\s"\'<>]+)["\']?'
        iframe_matches = re.findall(iframe_pattern, text, re.IGNORECASE)
        
        for iframe_url in iframe_matches:
            try:
                iframe_resp = session.get(iframe_url, timeout=15)
                for pattern in m3u8_patterns:
                    matches = re.findall(pattern, iframe_resp.text, re.IGNORECASE)
                    for match in matches:
                        url = match.strip().rstrip("'\"\\);}")
                        if ".m3u8" in url or "playlist" in url:
                            return url
            except:
                pass
        
        # ─── Yöntem 3: JSON veri bloğu ara ───
        json_patterns = [
            r'\{[^{}]*"(?:url|source|src|file|stream)":\s*"(https?://[^"]+)"[^{}]*\}',
            r'atob\(["\']([A-Za-z0-9+/=]+)["\']\)',
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                # Base64 decode dene
                try:
                    import base64
                    decoded = base64.b64decode(match).decode("utf-8")
                    if "http" in decoded:
                        url_match = re.search(r'(https?://[^\s"\']+)', decoded)
                        if url_match:
                            return url_match.group(1)
                except:
                    if "http" in match:
                        return match
        
        # ─── Yöntem 4: API endpoint çağrısı ara ───
        api_patterns = [
            r'fetch\(["\']?(https?://[^\s"\'<>]+/api/[^\s"\'<>]+)["\']?',
            r'axios\.[a-z]+\(["\']?(https?://[^\s"\'<>]+)["\']?',
            r'\.get\(["\']?(https?://[^\s"\'<>]+/stream[^\s"\'<>]*)["\']?',
            r'\.get\(["\']?(https?://[^\s"\'<>]+/play[^\s"\'<>]*)["\']?',
        ]
        
        for pattern in api_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for api_url in matches:
                try:
                    api_resp = session.get(api_url, timeout=10)
                    # JSON response'dan URL çıkar
                    try:
                        api_data = api_resp.json()
                        for key in ["url", "source", "src", "file", "stream", "link", "m3u8"]:
                            if key in api_data and api_data[key]:
                                return str(api_data[key])
                            # Nested
                            if isinstance(api_data, dict):
                                for v in api_data.values():
                                    if isinstance(v, dict) and key in v:
                                        return str(v[key])
                    except:
                        # Text response'dan URL çıkar
                        for p in m3u8_patterns[:3]:
                            m = re.findall(p, api_resp.text)
                            if m:
                                return m[0].strip()
                except:
                    pass
        
        return None
    
    except Exception as e:
        return None


def process_channel(channel, session, config):
    """Tek bir kanalı işle: player page → stream URL"""
    name = channel.get("name", "")
    code = channel.get("code", "")
    player_url = channel.get("url", "")
    image = channel.get("image", "")
    status = channel.get("status", "")
    
    if not name or not player_url:
        return None
    
    if status != "online":
        return None
    
    # Cache kontrolü
    cache_key = f"{name}_{code}"
    cache = config.get("stream_cache", {})
    
    cached = cache.get(cache_key)
    if cached:
        cached_time = cached.get("time", 0)
        # 6 saatten eski değilse cache'den kullan
        if time.time() - cached_time < 21600:
            return {
                "name": name,
                "code": code,
                "url": cached["url"],
                "image": image,
                "group": COUNTRY_MAP.get(code, code.upper())
            }
    
    # Player sayfasından stream URL çıkar
    stream_url = extract_stream_from_player(player_url, session)
    
    if stream_url:
        # Cache'e kaydet
        cache[cache_key] = {
            "url": stream_url,
            "time": time.time()
        }
        config["stream_cache"] = cache
        
        return {
            "name": name,
            "code": code,
            "url": stream_url,
            "image": image,
            "group": COUNTRY_MAP.get(code, code.upper())
        }
    
    # Stream bulunamadıysa player URL'yi direkt kullan
    return {
        "name": name,
        "code": code,
        "url": player_url,
        "image": image,
        "group": COUNTRY_MAP.get(code, code.upper())
    }


def generate_m3u(results, config):
    """M3U dosyası oluştur"""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    lines = [
        '#EXTM3U url-tvg="" refresh="3600"',
        f'# CDNLiveTV M3U Playlist',
        f'# Generated: {now}',
        f'# Source: https://cdnlivetv.is',
        f'# Channels: {len(results)}',
        ''
    ]
    
    # Grupla sırala
    results.sort(key=lambda x: (x["group"], x["name"]))
    
    groups_count = {}
    
    for ch in results:
        name = ch["name"]
        code = ch["code"]
        group = ch["group"]
        logo = ch["image"]
        url = ch["url"]
        
        # Aynı isimli kanallar için ülke kodu ekle
        display_name = f'{name} ({code.upper()})' if code else name
        
        groups_count[group] = groups_count.get(group, 0) + 1
        
        extinf = (
            f'#EXTINF:-1 '
            f'tvg-id="{name}.{code}" '
            f'tvg-name="{display_name}" '
            f'tvg-logo="{logo}" '
            f'group-title="{group}"'
            f',{display_name}'
        )
        
        lines.append(extinf)
        lines.append(url)
        lines.append('')
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    config["last_update"] = now
    config["channel_count"] = len(results)
    config["groups"] = groups_count
    save_config(config)
    
    log(f"{OUTPUT_FILE} oluşturuldu: {len(results)} kanal", "OK")
    return len(results)


def create_readme(config):
    now = config.get("last_update", "")
    count = config.get("channel_count", 0)
    groups = config.get("groups", {})
    
    groups_md = ""
    for g, c in sorted(groups.items(), key=lambda x: -x[1]):
        groups_md += f"| {g} | {c} |\n"
    
    readme = f"""# 📺 CDNLiveTV M3U Playlist

![Update](https://img.shields.io/badge/Updated-Automatic-brightgreen)
![Channels](https://img.shields.io/badge/Channels-{count}-blue)

## 📥 Playlist URL
