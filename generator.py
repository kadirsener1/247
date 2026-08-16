#!/usr/bin/env python3
"""
CDNLiveTV M3U Generator v4.0
Her kanalın player sayfasindan tokenli m3u8 URL ceker.
Ornek hedef URL:
https://cdnlivetv.is/secure/api/v1/STREAM_ID/playlist.m3u8?token=TOKEN
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
MAX_WORKERS = 10
REQUEST_TIMEOUT = 25

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
    symbols = {"INFO": "i", "OK": "OK", "WARN": "!!", "ERROR": "ERR", "WORK": ".."}
    print("[" + ts + "] [" + symbols.get(level, level) + "] " + str(msg))


def get_session():
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
                cfg.setdefault(k, v)
            return cfg
        except Exception:
            pass
    return default


def save_config(config):
    # Cache cok buyurse sifirla
    if len(config.get("stream_cache", {})) > 1000:
        config["stream_cache"] = {}
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log("Config kayit hatasi: " + str(e), "WARN")


def fetch_channels():
    log("API'den kanal listesi aliniyor...", "WORK")
    s = get_session()
    s.headers["Accept"] = "application/json"
    try:
        r = s.get(API_URL, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        channels = data.get("channels", [])
        log(str(len(channels)) + " kanal bulundu", "OK")
        return channels
    except Exception as e:
        log("API hatasi: " + str(e), "ERROR")
        return []


def extract_m3u8_url(player_url, session):
    """
    Player sayfasindan tokenli m3u8 URL'sini cek.
    Hedef format:
    https://cdnlivetv.is/secure/api/v1/{STREAM_ID}/playlist.m3u8?token={TOKEN}
    """
    try:
        resp = session.get(player_url, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            log("HTTP " + str(resp.status_code) + " -> " + player_url, "WARN")
            return None

        text = resp.text

        # --- 1. YONTEM: Dogrudan cdnlivetv.is/secure m3u8 URL ara ---
        # Ornek: https://cdnlivetv.is/secure/api/v1/XXXX/playlist.m3u8?token=YYYY
        pattern_secure = re.findall(
            r'(https?://[a-zA-Z0-9._-]*cdnlivetv[a-zA-Z0-9._-]*/secure/api/v\d+/[^"\'<>\s]+\.m3u8[^"\'<>\s]*)',
            text, re.IGNORECASE
        )
        if pattern_secure:
            url = pattern_secure[0].strip().rstrip("\\;),")
            log("Secure URL bulundu: " + url[:60] + "...", "OK")
            return url

        # --- 2. YONTEM: Herhangi bir m3u8 URL ara ---
        pattern_m3u8 = re.findall(
            r'(https?://[^\s"\'<>]+\.m3u8[^"\'<>\s]*)',
            text, re.IGNORECASE
        )
        for u in pattern_m3u8:
            url = u.strip().rstrip("\\;),")
            if "token=" in url:
                log("Tokenli m3u8 bulundu: " + url[:60] + "...", "OK")
                return url

        # Token olmasa bile m3u8 varsa al
        for u in pattern_m3u8:
            url = u.strip().rstrip("\\;),")
            log("m3u8 bulundu (token yok): " + url[:60] + "...", "WARN")
            return url

        # --- 3. YONTEM: JS icindeki degiskenleri ara ---
        js_patterns = [
            r'(?:src|url|file|source|stream|video_url|hls_url)\s*[=:]\s*["\']?(https?://[^\s"\'<>]+)',
            r'loadSource\s*\(\s*["\']?(https?://[^\s"\'<>]+)',
            r'\.src\s*\(\s*["\']?(https?://[^\s"\'<>]+)',
        ]
        for pat in js_patterns:
            matches = re.findall(pat, text, re.IGNORECASE)
            for m in matches:
                url = m.strip().rstrip("\\;),\"'")
                if "cdnlivetv" in url or ".m3u8" in url or "token=" in url:
                    log("JS degiskeninden URL: " + url[:60] + "...", "OK")
                    return url

        # --- 4. YONTEM: iframe icine gir ---
        iframes = re.findall(
            r'<iframe[^>]+src=["\']?(https?://[^\s"\'<>]+)',
            text, re.IGNORECASE
        )
        for iframe_url in iframes[:3]:
            log("iframe inceleniyor: " + iframe_url[:60], "WORK")
            try:
                ir = session.get(iframe_url.strip(), timeout=15)
                if ir.status_code == 200:
                    # Secure URL ara
                    sec = re.findall(
                        r'(https?://[a-zA-Z0-9._-]*cdnlivetv[a-zA-Z0-9._-]*/secure/api/v\d+/[^"\'<>\s]+\.m3u8[^"\'<>\s]*)',
                        ir.text, re.IGNORECASE
                    )
                    if sec:
                        url = sec[0].strip().rstrip("\\;),")
                        log("iframe'den secure URL: " + url[:60] + "...", "OK")
                        return url

                    # Genel m3u8 ara
                    m3u8s = re.findall(
                        r'(https?://[^\s"\'<>]+\.m3u8[^"\'<>\s]*)',
                        ir.text, re.IGNORECASE
                    )
                    for u in m3u8s:
                        url = u.strip().rstrip("\\;),")
                        log("iframe'den m3u8: " + url[:60] + "...", "OK")
                        return url
            except Exception:
                pass

        # --- 5. YONTEM: API endpoint dene ---
        # Player URL'sinden stream_id ve code al
        # https://cdnlivetv.tv/api/v1/channels/player/?name=ABC&code=us&user=cdnlivetv&plan=free
        name_match = re.search(r'name=([^&]+)', player_url)
        code_match = re.search(r'code=([^&]+)', player_url)

        if name_match and code_match:
            ch_name = name_match.group(1)
            ch_code = code_match.group(1)

            # Stream endpoint dene
            stream_endpoints = [
                "https://cdnlivetv.tv/api/v1/channels/stream/?name=" + ch_name + "&code=" + ch_code + "&user=cdnlivetv&plan=free",
                "https://api.cdnlivetv.is/api/v1/stream/?name=" + ch_name + "&code=" + ch_code + "&user=cdnlivetv&plan=free",
                "https://cdnlivetv.tv/api/v1/channels/token/?name=" + ch_name + "&code=" + ch_code + "&user=cdnlivetv&plan=free",
            ]

            for endpoint in stream_endpoints:
                try:
                    er = session.get(endpoint, timeout=15)
                    if er.status_code == 200:
                        try:
                            edata = er.json()
                            # JSON icinden URL ara
                            for key in ["url", "stream", "m3u8", "source", "link", "file"]:
                                if key in edata and edata[key]:
                                    val = str(edata[key]).strip()
                                    if val.startswith("http"):
                                        log("API endpoint URL: " + val[:60] + "...", "OK")
                                        return val
                            # Nested dict
                            for v in edata.values():
                                if isinstance(v, str) and v.startswith("http") and (".m3u8" in v or "token=" in v):
                                    log("API nested URL: " + v[:60] + "...", "OK")
                                    return v
                        except Exception:
                            # JSON degilse direkt m3u8 ara
                            ms = re.findall(r'(https?://[^\s"\'<>]+\.m3u8[^"\'<>\s]*)', er.text)
                            if ms:
                                return ms[0].strip()
                except Exception:
                    pass

        log("URL bulunamadi: " + player_url[:60], "WARN")
        return None

    except Exception as e:
        log("Hata: " + str(e), "ERROR")
        return None


def process_channel(args):
    channel, session, config = args
    name = channel.get("name", "").strip()
    code = channel.get("code", "")
    player_url = channel.get("url", "")
    image = channel.get("image", "")
    status = channel.get("status", "")

    if not name or not player_url or status != "online":
        return None

    # Cache kontrol (6 saat gecerli)
    cache_key = name + "_" + code
    cache = config.setdefault("stream_cache", {})

    if cache_key in cache:
        entry = cache[cache_key]
        age = time.time() - entry.get("time", 0)
        if age < 21600 and entry.get("url"):
            return {
                "name": name,
                "code": code,
                "url": entry["url"],
                "image": image,
                "group": COUNTRY_MAP.get(code, code.upper() if code else "Other")
            }

    # Player sayfasindan m3u8 URL cek
    m3u8_url = extract_m3u8_url(player_url, session)

    if not m3u8_url:
        return None

    # Cache guncelle
    cache[cache_key] = {"url": m3u8_url, "time": time.time()}

    return {
        "name": name,
        "code": code,
        "url": m3u8_url,
        "image": image,
        "group": COUNTRY_MAP.get(code, code.upper() if code else "Other")
    }


def generate_m3u(results, config):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = []
    lines.append('#EXTM3U url-tvg="" refresh="3600"')
    lines.append("# CDNLiveTV M3U Playlist")
    lines.append("# Generated: " + now)
    lines.append("# Channels: " + str(len(results)))
    lines.append("")

    results.sort(key=lambda x: (x.get("group", ""), x.get("name", "")))

    groups_count = {}
    for ch in results:
        code_upper = ch.get("code", "").upper()
        display_name = ch["name"] + " (" + code_upper + ")" if code_upper else ch["name"]
        group = ch.get("group", "Other")
        groups_count[group] = groups_count.get(group, 0) + 1

        extinf = (
            "#EXTINF:-1"
            + ' tvg-id="' + ch["name"] + "." + ch.get("code", "") + '"'
            + ' tvg-name="' + display_name + '"'
            + ' tvg-logo="' + ch.get("image", "") + '"'
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

    log(OUTPUT_FILE + " olusturuldu -> " + str(len(results)) + " kanal", "OK")
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
    lines.append("| Ulke | Kanal Sayisi |")
    lines.append("|------|-------------|")

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
    log("CDNLiveTV M3U Generator v4.0", "WORK")
    print("=" * 60)

    config = load_config()

    # Kanalları çek
    channels = fetch_channels()
    if not channels:
        log("Hic kanal bulunamadi!", "ERROR")
        sys.exit(1)

    online_channels = [ch for ch in channels if ch.get("status") == "online"]
    log(str(len(online_channels)) + " online kanal isleniyor...", "INFO")

    session = get_session()
    results = []
    failed = 0

    log("Paralel stream URL cekme basliyor (" + str(MAX_WORKERS) + " is parcacigi)...", "WORK")

    args_list = [(ch, session, config) for ch in online_channels]

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_channel, args): args[0].get("name", "?") for args in args_list}

        done = 0
        total = len(futures)

        for future in concurrent.futures.as_completed(futures):
            done += 1
            try:
                result = future.result()
                if result:
                    results.append(result)
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                log("Future hatasi: " + str(e), "WARN")

            if done % 50 == 0 or done == total:
                log(
                    "Ilerleme: " + str(done) + "/" + str(total)
                    + " | Basarili: " + str(len(results))
                    + " | Basarisiz: " + str(failed),
                    "INFO"
                )

    # Ozet
    log("Tamamlandi: " + str(len(results)) + " basarili, " + str(failed) + " basarisiz", "OK")

    if not results:
        log("Hic tokenli URL bulunamadi!", "ERROR")
        sys.exit(1)

    generate_m3u(results, config)
    create_readme(config)

    print("=" * 60)
    log("BITTI! " + str(len(results)) + " kanal M3U dosyasina yazildi.", "OK")
    print("=" * 60)


if __name__ == "__main__":
    main()
