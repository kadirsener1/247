#!/usr/bin/env python3

import requests
import json
import os
import re
import sys
import time
import concurrent.futures
from datetime import datetime, timezone
from urllib.parse import urljoin

API_URL = "https://api.cdnlivetv.is/api/v1/channels/?user=cdnlivetv&plan=free"
OUTPUT_FILE = "cdnlive.m3u"
CONFIG_FILE = "config.json"

MAX_WORKERS = 10
REQUEST_TIMEOUT = 25
CACHE_TTL = 21600  # 6 saat

COUNTRY_MAP = {
    "us": "USA",
    "gb": "UK",
    "de": "Germany",
    "fr": "France",
    "es": "Spain",
    "it": "Italy",
    "pt": "Portugal",
    "nl": "Netherlands",
    "tr": "Turkey",
    "br": "Brazil",
    "ar": "Argentina",
    "mx": "Mexico",
    "ca": "Canada",
    "au": "Australia",
    "nz": "New Zealand",
    "se": "Sweden",
    "dk": "Denmark",
    "pl": "Poland",
    "ro": "Romania",
    "bg": "Bulgaria",
    "gr": "Greece",
    "il": "Israel",
    "ae": "UAE",
    "sa": "Saudi Arabia",
    "ru": "Russia",
    "cy": "Cyprus",
    "cz": "Czech Republic",
    "at": "Austria",
    "cl": "Chile",
    "uy": "Uruguay",
    "be": "Belgium"
}


def log(msg, level="INFO"):
    now = datetime.now().strftime("%H:%M:%S")
    print("[" + now + "] [" + level + "] " + str(msg))


def get_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://cdnlivetv.tv/",
        "Origin": "https://cdnlivetv.tv"
    })
    return s


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
        except Exception:
            return default

    return default


def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log("Config kaydedilemedi: " + str(e), "WARN")


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


def is_stream_url(url, content_type=""):
    u = (url or "").lower()
    ct = (content_type or "").lower()

    if ".m3u8" in u:
        return True
    if ".mpd" in u:
        return True
    if "/secure/api/" in u:
        return True
    if "playlist.m3u8" in u:
        return True

    if "application/vnd.apple.mpegurl" in ct:
        return True
    if "application/x-mpegurl" in ct:
        return True
    if "application/dash+xml" in ct:
        return True
    if ct.startswith("video/"):
        return True

    return False


def clean_candidate_url(raw, base_url):
    if not raw:
        return ""

    raw = raw.strip()
    raw = raw.replace("\\/", "/")
    raw = raw.replace("&amp;", "&")
    raw = raw.strip("'\"")
    raw = raw.rstrip("\\);,}")

    if raw.startswith("//"):
        return "https:" + raw

    if raw.startswith("/"):
        return urljoin(base_url, raw)

    if raw.startswith("http://") or raw.startswith("https://"):
        return raw

    return urljoin(base_url, raw)


def extract_candidates_from_text(text, base_url):
    candidates = []
    seen = set()

    patterns = [
        r'(https?://[^\s"\'<>]+(?:\.m3u8|\.mpd)[^\s"\'<>]*)',
        r'(https?://[^\s"\'<>]*(?:secure/api|playlist|stream|live)[^\s"\'<>]*)',
        r'(/secure/api/v\d+/[^\s"\'<>]+(?:\.m3u8|\.mpd)[^\s"\'<>]*)',
        r'(?:src|source|file|url|stream|videoUrl|video_url|hls|hlsUrl|hls_url)\s*[:=]\s*["\']([^"\']+)["\']',
        r'<iframe[^>]+src=["\']([^"\']+)["\']'
    ]

    for pattern in patterns:
        try:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                candidate = clean_candidate_url(m, base_url)
                if not candidate:
                    continue
                if candidate in seen:
                    continue
                seen.add(candidate)
                candidates.append(candidate)
        except Exception:
            pass

    return candidates


def resolve_playable_url(url, depth=0, seen=None):
    if not url:
        return None

    if seen is None:
        seen = set()

    if depth > 2:
        return None

    if url in seen:
        return None

    seen.add(url)
    s = get_session()

    try:
        r = s.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
    except Exception:
        return None

    final_url = r.url
    content_type = r.headers.get("Content-Type", "")

    if is_stream_url(final_url, content_type):
        return final_url

    # Redirect zincirinden kontrol
    try:
        if r.history:
            for h in r.history:
                loc = h.headers.get("Location", "")
                if loc:
                    loc = clean_candidate_url(loc, h.url)
                    if is_stream_url(loc, ""):
                        return loc
    except Exception:
        pass

    # HTML değilse ama final URL geldiyse
    if "text/html" not in content_type.lower():
        if final_url and final_url != url:
            return final_url
        return None

    text = r.text or ""
    if not text:
        return None

    candidates = extract_candidates_from_text(text, final_url)

    # Önce direkt stream adaylarını dön
    for candidate in candidates:
        if is_stream_url(candidate, ""):
            return candidate

    # Sonra adayları recursive çöz
    for candidate in candidates:
        resolved = resolve_playable_url(candidate, depth + 1, seen)
        if resolved:
            return resolved

    # Son bir deneme: redirects kapalı istek
    try:
        r2 = s.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=False)
        loc = r2.headers.get("Location", "")
        if loc:
            loc = clean_candidate_url(loc, url)
            if is_stream_url(loc, ""):
                return loc
            resolved = resolve_playable_url(loc, depth + 1, seen)
            if resolved:
                return resolved
    except Exception:
        pass

    return None


def process_channel(channel, config):
    name = channel.get("name", "").strip()
    code = channel.get("code", "").strip().lower()
    player_url = channel.get("url", "").strip()
    image = channel.get("image", "").strip()
    status = channel.get("status", "").strip().lower()

    if not name or not player_url:
        return None

    if status != "online":
        return None

    cache_key = name + "_" + code
    cache = config.get("stream_cache", {})
    cached = cache.get(cache_key)

    if cached:
        age = time.time() - cached.get("time", 0)
        if age < CACHE_TTL and cached.get("url"):
            return {
                "name": name,
                "code": code,
                "url": cached.get("url"),
                "image": image,
                "group": COUNTRY_MAP.get(code, code.upper() if code else "Other"),
                "direct": cached.get("direct", False),
                "cache_key": cache_key
            }

    resolved_url = resolve_playable_url(player_url)

    # Kullanıcının istediği mantık:
    # çözülürse çözülen linki, çözülmezse player linkini yaz
    final_url = resolved_url if resolved_url else player_url
    direct = True if resolved_url else False

    return {
        "name": name,
        "code": code,
        "url": final_url,
        "image": image,
        "group": COUNTRY_MAP.get(code, code.upper() if code else "Other"),
        "direct": direct,
        "cache_key": cache_key
    }


def generate_m3u(results, config):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = []
    lines.append('#EXTM3U url-tvg="" refresh="3600"')
    lines.append("# CDNLiveTV M3U Playlist")
    lines.append("# Generated: " + now)
    lines.append("# Total Channels: " + str(len(results)))
    lines.append("")

    results.sort(key=lambda x: (x.get("group", ""), x.get("name", "")))

    groups_count = {}
    direct_count = 0
    fallback_count = 0

    for ch in results:
        group = ch.get("group", "Other")
        groups_count[group] = groups_count.get(group, 0) + 1

        if ch.get("direct"):
            direct_count += 1
        else:
            fallback_count += 1

        code_upper = ch.get("code", "").upper()
        display_name = ch.get("name", "")
        if code_upper:
            display_name = display_name + " (" + code_upper + ")"

        tvg_id = ch.get("name", "") + "." + ch.get("code", "")

        extinf = (
            '#EXTINF:-1'
            + ' tvg-id="' + tvg_id + '"'
            + ' tvg-name="' + display_name + '"'
            + ' tvg-logo="' + ch.get("image", "") + '"'
            + ' group-title="' + group + '"'
            + ',' + display_name
        )

        lines.append(extinf)
        lines.append(ch.get("url", ""))
        lines.append("")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    config["last_update"] = now
    config["channel_count"] = len(results)
    config["groups"] = groups_count
    config["direct_count"] = direct_count
    config["fallback_count"] = fallback_count

    save_config(config)

    log(OUTPUT_FILE + " olusturuldu -> " + str(len(results)) + " kanal", "OK")
    log("Direkt/cozulmus link: " + str(direct_count), "INFO")
    log("Fallback player link: " + str(fallback_count), "INFO")


def create_readme(config):
    now = config.get("last_update", "")
    count = config.get("channel_count", 0)
    groups = config.get("groups", {})
    direct_count = config.get("direct_count", 0)
    fallback_count = config.get("fallback_count", 0)

    lines = []
    lines.append("# CDNLiveTV M3U Playlist")
    lines.append("")
    lines.append("## Playlist URL")
    lines.append("")
    lines.append("```")
    lines.append("https://raw.githubusercontent.com/kadirsener1/247/main/cdnlive.m3u")
    lines.append("```")
    lines.append("")
    lines.append("## Ozet")
    lines.append("")
    lines.append("- Toplam kanal: " + str(count))
    lines.append("- Cozulmus/direkt link: " + str(direct_count))
    lines.append("- Fallback player link: " + str(fallback_count))
    lines.append("")
    lines.append("## Gruplar")
    lines.append("")
    lines.append("| Grup | Kanal Sayisi |")
    lines.append("|------|--------------|")

    for g, c in sorted(groups.items(), key=lambda x: (-x[1], x[0])):
        lines.append("| " + str(g) + " | " + str(c) + " |")

    lines.append("")
    lines.append("## Son Guncelleme")
    lines.append("")
    lines.append(now)
    lines.append("")
    lines.append("Not: Fallback olarak yazilan player URL'leri Tivimate'de her zaman dogrudan oynatmayabilir.")

    with open("README.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    log("README.md guncellendi", "OK")


def main():
    print("=" * 60)
    log("Generator baslatildi", "WORK")
    print("=" * 60)

    config = load_config()
    config.setdefault("stream_cache", {})

    channels = fetch_channels()
    if not channels:
        log("Hic kanal bulunamadi!", "ERROR")
        sys.exit(1)

    online_channels = [ch for ch in channels if ch.get("status", "").lower() == "online"]
    log(str(len(online_channels)) + " online kanal islenecek", "INFO")

    results = []
    failed = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {
            executor.submit(process_channel, ch, config): ch
            for ch in online_channels
        }

        done = 0
        total = len(future_map)

        for future in concurrent.futures.as_completed(future_map):
            done += 1
            ch = future_map[future]

            try:
                result = future.result()
                if result:
                    results.append(result)

                    # main thread'de cache guncelle
                    cache_key = result.get("cache_key")
                    if cache_key:
                        config["stream_cache"][cache_key] = {
                            "url": result.get("url"),
                            "time": time.time(),
                            "direct": result.get("direct", False)
                        }
                else:
                    failed += 1
            except Exception:
                failed += 1

            if done % 50 == 0 or done == total:
                success = len(results)
                log(
                    "Ilerleme: " + str(done) + "/" + str(total)
                    + " | Basarili: " + str(success)
                    + " | Basarisiz: " + str(failed),
                    "INFO"
                )

    if not results:
        log("Hic sonuc yok!", "ERROR")
        sys.exit(1)

    generate_m3u(results, config)
    create_readme(config)

    print("=" * 60)
    log("Tamamlandi", "OK")
    print("=" * 60)


if __name__ == "__main__":
    main()
