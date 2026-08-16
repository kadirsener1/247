#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import html
import os
import re
import threading
from pathlib import Path
from urllib.parse import urljoin
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


API_URL = "https://api.cdnlivetv.is/api/v1/channels/?user=cdnlivetv&plan=free"
OUTPUT_FILE = "cdnlive.m3u"
DEBUG_FILE = "debug_failed.json"
DEBUG_DIR = "debug_samples"

TIMEOUT = 20
MAX_WORKERS = 10
ONLY_ONLINE = True
SAVE_DEBUG_SAMPLES = 5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://cdnlivetv.tv/",
    "Origin": "https://cdnlivetv.tv",
    "Connection": "keep-alive",
}

thread_local = threading.local()


def make_session():
    session = requests.Session()

    retry = Retry(
        total=2,
        connect=2,
        read=2,
        backoff_factor=0.7,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "HEAD"]),
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=100, pool_maxsize=100)

    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(HEADERS)
    return session


def get_session():
    if not hasattr(thread_local, "session"):
        thread_local.session = make_session()
    return thread_local.session


def load_channels():
    print(f"🌐 API'den veri çekiliyor...")
    print(f"   URL: {API_URL}\n")

    session = make_session()
    r = session.get(API_URL, timeout=30)
    r.raise_for_status()

    data = r.json()
    channels = data.get("channels", [])
    total_channels = data.get("total_channels", len(channels))

    print(f"📡 HTTP Status: {r.status_code}")
    print(f"📡 API toplam kanal: {total_channels}")
    print(f"📡 Gelen kanal sayısı: {len(channels)}")

    if ONLY_ONLINE:
        channels = [c for c in channels if str(c.get("status", "")).lower() == "online"]
        print(f"✅ Online filtre sonrası: {len(channels)} kanal\n")
    else:
        print()

    return channels, total_channels


def clean_candidate(value, base_url=""):
    if not value:
        return ""

    value = str(value).strip()
    value = html.unescape(value)
    value = value.replace("\\/", "/")
    value = value.replace("\\u0026", "&")
    value = value.replace("&amp;", "&")
    value = value.strip(" '\"\t\r\n")

    if value.startswith("//"):
        value = "https:" + value
    elif value.startswith("/"):
        value = urljoin(base_url, value)

    return value


def looks_like_stream_url(url):
    if not url:
        return False

    u = url.lower()
    return any(x in u for x in [
        ".m3u8",
        ".mpd",
        "/manifest",
        "/playlist",
        "mpegurl",
        "master.m3u8",
        "index.m3u8",
    ])


def find_stream_in_obj(obj, base_url=""):
    streamish_keys = {
        "file", "src", "source", "hls", "dash", "manifest",
        "playlist", "stream", "stream_url", "play_url"
    }

    if isinstance(obj, dict):
        for k, v in obj.items():
            key = str(k).lower()

            if isinstance(v, str):
                cand = clean_candidate(v, base_url)
                if cand and (looks_like_stream_url(cand) or key in streamish_keys):
                    return cand

            found = find_stream_in_obj(v, base_url)
            if found:
                return found

    elif isinstance(obj, list):
        for item in obj:
            found = find_stream_in_obj(item, base_url)
            if found:
                return found

    return ""


def extract_stream_from_text(text, base_url=""):
    if not text:
        return ""

    text = html.unescape(text)
    text = text.replace("\\/", "/").replace("\\u0026", "&")

    patterns = [
        r'https?://[^"\'<>\s]+\.m3u8[^"\'<>\s]*',
        r'https?://[^"\'<>\s]+\.mpd[^"\'<>\s]*',
        r'["\'](//[^"\']+\.m3u8[^"\']*)["\']',
        r'["\'](/[^"\']+\.m3u8[^"\']*)["\']',
        r'(?:file|src|source|hls|dash|manifest|playlist)\s*[:=]\s*["\']([^"\']+)["\']',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if not matches:
            continue

        if isinstance(matches, str):
            matches = [matches]

        for m in matches:
            cand = clean_candidate(m, base_url)
            if looks_like_stream_url(cand):
                return cand

    return ""


def probe_player(url, depth=0, max_depth=2):
    if depth > max_depth or not url:
        return ""

    session = get_session()

    try:
        r = session.get(url, timeout=TIMEOUT, allow_redirects=True)
        final_url = r.url
        content_type = r.headers.get("Content-Type", "").lower()

        # Direkt stream URL'ye geldiyse
        if looks_like_stream_url(final_url):
            return final_url

        # M3U içeriği geldiyse
        sample_text = r.text[:5000] if r.text else ""
        if "#EXTM3U" in sample_text or "application/vnd.apple.mpegurl" in content_type:
            return final_url

        # JSON ise içinden stream ara
        if "application/json" in content_type or sample_text.lstrip().startswith(("{", "[")):
            try:
                data = r.json()
                found = find_stream_in_obj(data, final_url)
                if found:
                    return found
            except Exception:
                pass

        # HTML/JS içinden stream ara
        found = extract_stream_from_text(r.text, final_url)
        if found:
            return found

        # iframe varsa onun içine gir
        iframe_matches = re.findall(
            r'<iframe[^>]+src=["\']([^"\']+)["\']',
            r.text,
            flags=re.IGNORECASE
        )
        for iframe_src in iframe_matches:
            iframe_url = clean_candidate(iframe_src, final_url)
            iframe_url = urljoin(final_url, iframe_url)
            found = probe_player(iframe_url, depth + 1, max_depth)
            if found:
                return found

    except requests.RequestException:
        return ""
    except Exception:
        return ""

    return ""


def process_channel(ch):
    name = str(ch.get("name", "Bilinmeyen Kanal")).strip()
    player_url = str(ch.get("url", "")).strip()
    image = str(ch.get("image", "")).strip()
    code = str(ch.get("code", "GENEL")).strip().upper()
    status = str(ch.get("status", "")).strip().lower()

    if not player_url:
        return {
            "ok": False,
            "name": name,
            "reason": "url yok",
            "player_url": "",
            "stream_url": "",
            "image": image,
            "group": code,
        }

    stream_url = probe_player(player_url)

    if stream_url:
        return {
            "ok": True,
            "name": name,
            "player_url": player_url,
            "stream_url": stream_url,
            "image": image,
            "group": code,
            "status": status,
        }

    return {
        "ok": False,
        "name": name,
        "reason": "stream bulunamadı",
        "player_url": player_url,
        "stream_url": "",
        "image": image,
        "group": code,
        "status": status,
    }


def write_m3u(items, output_path):
    turkey_tz = timezone(timedelta(hours=3))
    now = datetime.now(turkey_tz).strftime("%d.%m.%Y %H:%M:%S")

    items = sorted(items, key=lambda x: x["name"].lower())

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f"# Son guncelleme: {now} (TR)\n")
        f.write(f"# Kanal sayisi: {len(items)}\n\n")

        for item in items:
            name = item["name"]
            logo = item["image"]
            group = item["group"]
            stream_url = item["stream_url"]

            extinf = f'#EXTINF:-1 tvg-name="{name}"'
            if logo:
                extinf += f' tvg-logo="{logo}"'
            if group:
                extinf += f' group-title="{group}"'
            extinf += f',{name}'

            f.write(extinf + "\n")
            f.write(stream_url + "\n\n")


def save_debug(failed_items):
    with open(DEBUG_FILE, "w", encoding="utf-8") as f:
        json.dump(failed_items, f, ensure_ascii=False, indent=2)

    Path(DEBUG_DIR).mkdir(parents=True, exist_ok=True)

    for i, item in enumerate(failed_items[:SAVE_DEBUG_SAMPLES], start=1):
        try:
            session = make_session()
            r = session.get(item["player_url"], timeout=TIMEOUT)
            sample_path = Path(DEBUG_DIR) / f"{i:02d}_{safe_filename(item['name'])}.html"
            sample_path.write_text(r.text, encoding="utf-8", errors="ignore")
        except Exception:
            pass


def safe_filename(name):
    return re.sub(r'[^a-zA-Z0-9._-]+', "_", name)[:80]


def main():
    print("═════════════════════════════════════════════════════════════════")
    print("   📺 CDN LIVE TV - M3U PLAYLIST OLUŞTURUCU")
    print("═════════════════════════════════════════════════════════════════\n")

    try:
        channels, total_channels = load_channels()
    except Exception as e:
        print(f"❌ API okunamadı: {e}")
        print("⚠️ Workflow kırılmasın diye çıkış kodu 0 dönülüyor.")
        return

    if not channels:
        print("⚠️ Kanal bulunamadı.")
        Path(OUTPUT_FILE).write_text("#EXTM3U\n", encoding="utf-8")
        return

    print("=================================================================")
    print("🔍 Player sayfalarından gerçek stream linkleri çıkarılıyor...")
    print(f"⚡ Worker: {MAX_WORKERS}")
    print("=================================================================\n")

    success = []
    failed = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_channel, ch): ch for ch in channels}

        total = len(futures)
        done = 0

        for future in as_completed(futures):
            done += 1
            try:
                result = future.result()
            except Exception as e:
                ch = futures[future]
                result = {
                    "ok": False,
                    "name": ch.get("name", "Bilinmeyen Kanal"),
                    "reason": f"hata: {e}",
                    "player_url": ch.get("url", ""),
                    "stream_url": "",
                    "image": ch.get("image", ""),
                    "group": str(ch.get("code", "GENEL")).upper(),
                }

            if result["ok"]:
                success.append(result)
                print(f"✅ [{done:03}/{total}] {result['name']}")
            else:
                failed.append(result)
                print(f"❌ [{done:03}/{total}] {result['name']} — {result.get('reason', 'hata')}")

    write_m3u(success, OUTPUT_FILE)
    save_debug(failed)

    print("\n=================================================================")
    print("📊 SONUÇ")
    print("=================================================================")
    print(f"API toplam kanal      : {total_channels}")
    print(f"İşlenen kanal         : {len(channels)}")
    print(f"M3U'ya eklenen        : {len(success)}")
    print(f"Bulunamayan           : {len(failed)}")
    print(f"M3U dosyası           : {OUTPUT_FILE}")
    print(f"Debug dosyası         : {DEBUG_FILE}")
    print(f"Debug örnek klasörü   : {DEBUG_DIR}")
    print("=================================================================\n")

    if len(success) == 0:
        print("⚠️ Hiç stream çıkarılamadı.")
        print("⚠️ Ama workflow artık exit code 1 vermeyecek.")
        print("⚠️ debug_failed.json ve debug_samples artifact olarak yüklenecek.")
        return

    print(f"✅ {OUTPUT_FILE} oluşturuldu. ({len(success)} kanal)")


if __name__ == "__main__":
    main()
