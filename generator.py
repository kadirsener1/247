#!/usr/bin/env python3
"""
CDNLiveTV M3U Playlist Generator v3.1
Düzeltilmiş README string + daha stabil parsing
"""

import requests
import json
import os
import re
import sys
import time
import concurrent.futures
from datetime import datetime, timezone
from urllib.parse import quote

# ─── Ayarlar ───
API_URL = "https://api.cdnlivetv.is/api/v1/channels/?user=cdnlivetv&plan=free"
OUTPUT_FILE = "cdnlive.m3u"
CONFIG_FILE = "config.json"
MAX_WORKERS = 12
REQUEST_TIMEOUT = 20

COUNTRY_MAP = {
    "us": "🇺🇸 USA", "gb": "🇬🇧 UK", "de": "🇩🇪 Germany", "fr": "🇫🇷 France",
    "es": "🇪🇸 Spain", "it": "🇮🇹 Italy", "pt": "🇵🇹 Portugal", "nl": "🇳🇱 Netherlands",
    "tr": "🇹🇷 Turkey", "br": "🇧🇷 Brazil", "ar": "🇦🇷 Argentina", "mx": "🇲🇽 Mexico",
    "ca": "🇨🇦 Canada", "au": "🇦🇺 Australia", "nz": "🇳🇿 New Zealand", "se": "🇸🇪 Sweden",
    "dk": "🇩🇰 Denmark", "pl": "🇵🇱 Poland", "ro": "🇷🇴 Romania", "bg": "🇧🇬 Bulgaria",
    "gr": "🇬🇷 Greece", "il": "🇮🇱 Israel", "ae": "🇦🇪 UAE", "sa": "🇸🇦 Saudi Arabia",
    "ru": "🇷🇺 Russia", "cy": "🇨🇾 Cyprus", "cz": "🇨🇿 Czech", "at": "🇦🇹 Austria",
    "cl": "🇨🇱 Chile", "uy": "🇺🇾 Uruguay", "be": "🇧🇪 Belgium",
}


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    symbols = {"INFO": "ℹ️", "OK": "✅", "WARN": "⚠️", "ERROR": "❌", "WORK": "🔄"}
    print(f"[{ts}] {symbols.get(level, '')} {msg}")


def get_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://cdnlivetv.tv/",
        "Origin": "https://cdnlivetv.tv"
    })
    return session


def load_config():
    default = {"last_update": "", "channel_count": 0, "groups": {}, "stream_cache": {}}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                for k, v in default.items():
                    cfg.setdefault(k, v)
                return cfg
        except Exception:
            pass
    return default


def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def fetch_channels():
    log("API’den kanal listesi çekiliyor...", "WORK")
    session = get_session()
    session.headers["Accept"] = "application/json"
    
    try:
        r = session.get(API_URL, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        channels = data.get("channels", [])
        log(f"{len(channels)} kanal alındı", "OK")
        return channels
    except Exception as e:
        log(f"API hatası: {e}", "ERROR")
        return []


def extract_stream_from_player(player_url, session):
    """Player sayfasından gerçek stream URL’sini çıkar"""
    try:
        resp = session.get(player_url, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return None
        text = resp.text

        patterns = [
            r'(https?://[^\s"\'<>]+\.m3u8[^"\']*)',
            r'source["\s:=]+["\']?(https?://[^\s"\'<>]+)',
            r'["\']file["\']?\s*[:=]\s*["\']?(https?://[^\s"\'<>]+)',
            r'hls\.loadSource\(["\']?(https?://[^\s"\'<>]+)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                url = match.strip().rstrip("'\"\\);,}")
                if ".m3u8" in url or "/live" in url or "/stream" in url or "playlist" in url:
                    return url
        return None
    except:
        return None


def process_channel(channel, session, config):
    name = channel.get("name", "").strip()
    code = channel.get("code", "")
    player_url = channel.get("url", "")
    image = channel.get("image", "")
    status = channel.get("status", "")

    if not name or not player_url or status != "online":
        return None

    cache_key = f"{name}_{code}"
    cache = config.setdefault("stream_cache", {})

    if cache_key in cache:
        cached = cache[cache_key]
        if time.time() - cached.get("time", 0) < 21600:   # 6 saat
            return {**cached["data"], "name": name, "code": code, "image": image}

    stream_url = extract_stream_from_player(player_url, session)

    result = {
        "name": name,
        "code": code,
        "url": stream_url or player_url,
        "image": image,
        "group": COUNTRY_MAP.get(code, code.upper() if code else "Other")
    }

    if stream_url:
        cache[cache_key] = {"data": result, "time": time.time()}

    return result


def generate_m3u(results, config):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    lines = [
        '#EXTM3U url-tvg="" refresh="3600"',
        '# CDNLiveTV M3U Playlist',
        f'# Generated: {now}',
        f'# Total Channels: {len(results)}',
        ''
    ]

    results.sort(key=lambda x: (x["group"], x["name"]))

    groups_count = {}
    for ch in results:
        display_name = f'{ch["name"]} ({ch["code"].upper()})' if ch["code"] else ch["name"]
        group = ch["group"]
        groups_count[group] = groups_count.get(group, 0) + 1

        extinf = (
            f'#EXTINF:-1 '
            f'tvg-id="{ch["name"]}.{ch["code"]}" '
            f'tvg-name="{display_name}" '
            f'tvg-logo="{ch["image"]}" '
            f'group-title="{group}"'
            f',{display_name}'
        )
        lines.extend([extinf, ch["url"], ''])

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    config["last_update"] = now
    config["channel_count"] = len(results)
    config["groups"] = groups_count
    save_config(config)
    
    log(f"{OUTPUT_FILE} başarıyla oluşturuldu → {len(results)} kanal", "OK")
    return len(results)


def create_readme(config):
    """Düzeltilmiş ve daha güvenli README oluşturucu"""
    now = config.get("last_update", "Henüz yok")
    count = config.get("channel_count", 0)
    groups = config.get("groups", {})

    groups_table = "\n".join([f"| {g} | {c} |" for g, c in sorted(groups.items(), key=lambda x: -x[1])])

    readme_content = f"""# 📺 CDNLiveTV M3U Playlist

![Update](https://img.shields.io/badge/Last_Update-{now.replace(' ', '_')}-brightgreen)
![Channels](https://img.shields.io/badge/Channels-{count}-blue)

## 📥 Kullanım Linki
