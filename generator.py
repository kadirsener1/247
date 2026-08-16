#!/usr/bin/env python3
"""
CDNLiveTV M3U Playlist Generator v3.2
"""

import requests
import json
import os
import re
import sys
import time
import concurrent.futures
from datetime import datetime, timezone

API_URL = "https://api.cdnlivetv.is/api/v1/channels/?user=cdnlivetv&plan=free"
OUTPUT_FILE = "cdnlive.m3u"
CONFIG_FILE = "config.json"
MAX_WORKERS = 12
REQUEST_TIMEOUT = 20

COUNTRY_MAP = {
    "us": "USA", "gb": "UK", "de": "Germany", "fr": "France",
    "es": "Spain", "it": "Italy", "pt": "Portugal", "nl": "Netherlands",
    "tr": "Turkey", "br": "Brazil", "ar": "Argentina", "mx": "Mexico",
    "ca": "Canada", "au": "Australia", "nz": "New Zealand", "se": "Sweden",
    "dk": "Denmark", "pl": "Poland", "ro": "Romania", "bg": "Bulgaria",
    "gr": "Greece", "il": "Israel", "ae": "UAE", "sa": "Saudi Arabia",
    "ru": "Russia", "cy": "Cyprus", "cz": "Czech Republic", "at": "Austria",
    "cl": "Chile", "uy": "Uruguay", "be": "Belgium",
}


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    symbols = {
        "INFO": "i",
        "OK": "OK",
        "WARN": "!!",
        "ERROR": "ERR",
        "WORK": ".."
    }
    print("[" + ts + "] [" + symbols.get(level, level) + "] " + str(msg))


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
                cfg.setdefault(k, v)
            return cfg
        except Exception:
            pass
    return default


def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log("Config kaydetme hatasi: " + str(e), "WARN")


def fetch_channels():
    log("API kanallar cekiliyor...", "WORK")
    session = get_session()
    session.headers["Accept"] = "application/json"
    try:
        r = session.get(API_URL, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        channels = data.get("channels", [])
        log(str(len(channels)) + " kanal alindi", "OK")
        return channels
    except Exception as e:
        log("API hatasi: " + str(e), "ERROR")
        return []


def extract_stream_from_player(player_url, session):
    try:
        resp = session.get(player_url, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return None
        text = resp.text

        patterns = [
            r'(https?://[^\s"\'<>]+\.m3u8[^"\'<>\s]*)',
            r'source["\s:=]+["\']?(https?://[^\s"\'<>]+)',
            r'["\']file["\']?\s*[:=]\s*["\']?(https?://[^\s"\'<>]+)',
            r'hls\.loadSource\(["\']?(https?://[^\s"\'<>]+)',
            r'video_url\s*[:=]\s*["\']?(https?://[^\s"\'<>]+)',
            r'stream_url\s*[:=]\s*["\']?(https?://[^\s"\'<>]+)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                url = match.strip().rstrip("'\"\\);,}")
                if ".m3u8" in url or "/live" in url or "/stream" in url:
                    return url

        iframe_matches = re.findall(
            r'<iframe[^>]+src=["\']?(https?://[^\s"\'<>]+)', text, re.IGNORECASE
        )
        for iframe_url in iframe_matches[:3]:
            try:
                ir = session.get(iframe_url, timeout=15)
                for pattern in patterns:
                    ms = re.findall(pattern, ir.text, re.IGNORECASE)
                    for m in ms:
                        u = m.strip().rstrip("'\"\\);,}")
                        if ".m3u8" in u or "/live" in u:
                            return u
            except Exception:
                pass

        return None
    except Exception:
        return None


def process_channel(channel, session, config):
    name = channel.get("name", "").strip()
    code = channel.get("code", "")
    player_url = channel.get("url", "")
    image = channel.get("image", "")
    status = channel.get("status", "")

    if not name or not player_url or status != "online":
        return None

    cache_key = name + "_" + code
    cache = config.setdefault("stream_cache", {})

    if cache_key in cache:
        cached = cache[cache_key]
        if time.time() - cached.get("time", 0) < 21600:
            return {
                "name": name,
                "code": code,
                "url": cached.get("url", player_url),
                "image": image,
                "group": COUNTRY_MAP.get(code, code.upper() if code else "Other")
            }

    stream_url = extract_stream_from_player(player_url, session)

    final_url = stream_url if stream_url else player_url

    result = {
        "name": name,
        "code": code,
        "url": final_url,
        "image": image,
        "group": COUNTRY_MAP.get(code, code.upper() if code else "Other")
    }

    if stream_url:
        cache[cache_key] = {
            "url": stream_url,
            "time": time.time()
        }

    return result


def generate_m3u(results, config):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = []
    lines.append('#EXTM3U url-tvg="" refresh="3600"')
    lines.append("# CDNLiveTV M3U Playlist")
    lines.append("# Generated: " + now)
    lines.append("# Total: " + str(len(results)) + " channels")
    lines.append("")

    results.sort(key=lambda x: (x["group"], x["name"]))

    groups_count = {}
    for ch in results:
        code_upper = ch["code"].upper() if ch["code"] else ""
        display_name = ch["name"] + " (" + code_upper + ")" if code_upper else ch["name"]
        group = ch["group"]
        groups_count[group] = groups_count.get(group, 0) + 1

        extinf = (
            "#EXTINF:-1"
            + ' tvg-id="' + ch["name"] + "." + ch["code"] + '"'
            + ' tvg-name="' + display_name + '"'
            + ' tvg-logo="' + ch["image"] + '"'
            + ' group-title="' + group + '"'
            + "," + display_name
        )
        lines.append(extinf)
        lines.append(ch["url"])
        lines.append("")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    config["last_update"] = now
    config["channel_count"] = len(results)
    config["groups"] = groups_count
    save_config(config)

    log(OUTPUT_FILE + " olusturuldu: " + str(len(results)) + " kanal", "OK")
    return len(results)


def create_readme(config):
    now = config.get("last_update", "")
    count = config.get("channel_count", 0)
    groups = config.get("groups", {})

    lines = []
    lines.append("# CDNLiveTV M3U Playlist")
    lines.append("")
    lines.append("## Playlist URL")
    lines.append("")
    lines.append("```")
    lines.append("https://raw.githubusercontent.com/kadirsener1/247/main/cdnlive.m3u")
    lines.append("```")
    lines.append("")
    lines.append("## Kanal Gruplari")
    lines.append("")
    lines.append("| Ulke / Grup | Kanal Sayisi |")
    lines.append("|-------------|--------------|")

    for g, c in sorted(groups.items(), key=lambda x: -x[1]):
        lines.append("| " + str(g) + " | " + str(c) + " |")

    lines.append("")
    lines.append("**Toplam: " + str(count) + " kanal**")
    lines.append("")
    lines.append("## Son Guncelleme")
    lines.append("")
    lines.append(now)
    lines.append("")
    lines.append("Her 6 saatte bir otomatik guncellenir.")

    with open("README.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    log("README.md guncellendi", "OK")


def main():
    print("=" * 60)
    log("CDNLiveTV M3U Generator v3.2 Baslatildi", "WORK")
    print("=" * 60)

    config = load_config()

    channels = fetch_channels()
    if not channels:
        log("Hic kanal bulunamadi!", "ERROR")
        sys.exit(1)

    online_channels = [ch for ch in channels if ch.get("status") == "online"]
    log(str(len(online_channels)) + " online kanal isleniyor...", "INFO")

    session = get_session()
    results = []

    log("Stream URL cikartiliyor (" + str(MAX_WORKERS) + " paralel)...", "WORK")

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_channel, ch, session, config): ch.get("name", "?")
            for ch in online_channels
        }

        done = 0
        total = len(futures)

        for future in concurrent.futures.as_completed(futures):
            done += 1
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception:
                pass

            if done % 100 == 0 or done == total:
                log(
                    "Ilerleme: " + str(done) + "/" + str(total)
                    + " | Basarili: " + str(len(results)),
                    "INFO"
                )

    log("Toplam " + str(len(results)) + " kanal bulundu", "OK")

    if not results:
        log("Hic stream bulunamadi!", "ERROR")
        sys.exit(1)

    generate_m3u(results, config)
    create_readme(config)

    print("=" * 60)
    log("TAMAMLANDI! " + str(len(results)) + " kanal eklendi", "OK")
    print("=" * 60)


if __name__ == "__main__":
    main()
