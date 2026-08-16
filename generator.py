#!/usr/bin/env python3
"""
CDNLiveTV M3U Playlist Generator
API'den kanal bilgilerini çeker, token'ları doğrular ve cdnlive.m3u dosyası oluşturur.
"""

import requests
import json
import os
import time
import hashlib
import logging
from datetime import datetime, timezone

# ─── Ayarlar ───
API_URL = "https://api.cdnlivetv.is/api/v1/channels/?user=cdnlivetv&plan=free"
STREAM_BASE = "https://cdnlivetv.is/secure/api/v1"
TOKEN_API = "https://api.cdnlivetv.is/api/v1/token/?user=cdnlivetv&plan=free"
OUTPUT_FILE = "cdnlive.m3u"
CONFIG_FILE = "config.json"
LOG_FILE = "generator.log"

# ─── Logging ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_config():
    """config.json dosyasından ayarları yükle"""
    default_config = {
        "api_url": API_URL,
        "stream_base": STREAM_BASE,
        "token_api": TOKEN_API,
        "output_file": OUTPUT_FILE,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "timeout": 30,
        "check_streams": True,
        "last_update": "",
        "last_token": ""
    }

    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            # Eksik anahtarları default ile doldur
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            return config
    else:
        save_config(default_config)
        return default_config


def save_config(config):
    """config.json dosyasını güncelle"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def get_headers(config):
    """HTTP istekleri için header"""
    return {
        "User-Agent": config["user_agent"],
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://cdnlivetv.is/",
        "Origin": "https://cdnlivetv.is"
    }


def fetch_channels(config):
    """API'den kanal listesini çek"""
    logger.info("📡 Kanal listesi çekiliyor...")

    try:
        response = requests.get(
            config["api_url"],
            headers=get_headers(config),
            timeout=config["timeout"]
        )
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list):
            channels = data
        elif isinstance(data, dict):
            # API farklı yapılarda dönebilir
            channels = data.get("channels", data.get("data", data.get("items", [])))
            if not isinstance(channels, list) and isinstance(data, dict):
                # Tek seviye dict ise direkt listeye çevir
                channels = [data] if "name" in data or "title" in data else []
        else:
            channels = []

        logger.info(f"✅ {len(channels)} kanal bulundu")
        return channels

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ API hatası: {e}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parse hatası: {e}")
        return []


def fetch_token(config):
    """Yeni token al"""
    logger.info("🔑 Token alınıyor...")

    try:
        # Yöntem 1: Token API'den çek
        response = requests.get(
            config["token_api"],
            headers=get_headers(config),
            timeout=config["timeout"]
        )

        if response.status_code == 200:
            data = response.json()
            token = None

            if isinstance(data, dict):
                token = data.get("token", data.get("access_token", data.get("key", "")))
            elif isinstance(data, str):
                token = data

            if token:
                logger.info(f"✅ Token alındı: {token[:30]}...")
                config["last_token"] = token
                save_config(config)
                return token

    except Exception as e:
        logger.warning(f"⚠️ Token API hatası: {e}")

    # Yöntem 2: Kanal sayfasından token çıkar
    try:
        response = requests.get(
            "https://cdnlivetv.is/",
            headers=get_headers(config),
            timeout=config["timeout"]
        )
        text = response.text

        # Token pattern'lerini ara
        import re
        patterns = [
            r'token["\s]*[:=]\s*["\']([A-Za-z0-9+/=]+)["\']',
            r'playlist\.m3u8\?token=([A-Za-z0-9+/=]+)',
            r'["\']([A-Za-z0-9]{100,})["\']'
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                token = match.group(1)
                logger.info(f"✅ Token sayfadan çıkarıldı: {token[:30]}...")
                config["last_token"] = token
                save_config(config)
                return token

    except Exception as e:
        logger.warning(f"⚠️ Sayfa scraping hatası: {e}")

    # Yöntem 3: Kayıtlı token'ı kullan
    if config.get("last_token"):
        logger.info("♻️ Kayıtlı token kullanılıyor")
        return config["last_token"]

    logger.error("❌ Token bulunamadı!")
    return ""


def extract_channel_info(channel):
    """Kanal verisinden bilgileri çıkar (farklı API formatlarını destekle)"""
    info = {
        "name": "",
        "logo": "",
        "group": "Diğer",
        "stream_id": "",
        "url": "",
        "tvg_id": "",
        "quality": ""
    }

    # İsim
    for key in ["name", "title", "channel_name", "channelName", "label"]:
        if key in channel and channel[key]:
            info["name"] = str(channel[key]).strip()
            break

    # Logo
    for key in ["logo", "image", "icon", "thumbnail", "tvg_logo", "tvgLogo", "img"]:
        if key in channel and channel[key]:
            logo = str(channel[key]).strip()
            if not logo.startswith("http"):
                logo = f"https://cdnlivetv.is{logo}" if logo.startswith("/") else f"https://cdnlivetv.is/{logo}"
            info["logo"] = logo
            break

    # Grup
    for key in ["group", "category", "genre", "group_title", "groupTitle", "cat"]:
        if key in channel and channel[key]:
            info["group"] = str(channel[key]).strip()
            break

    # Stream ID
    for key in ["id", "stream_id", "streamId", "channel_id", "channelId", "_id"]:
        if key in channel and channel[key]:
            info["stream_id"] = str(channel[key]).strip()
            break

    # Direkt URL
    for key in ["url", "stream_url", "streamUrl", "link", "source", "src"]:
        if key in channel and channel[key]:
            info["url"] = str(channel[key]).strip()
            break

    # TVG ID
    for key in ["tvg_id", "tvgId", "epg_id", "epgId"]:
        if key in channel and channel[key]:
            info["tvg_id"] = str(channel[key]).strip()
            break

    # Kalite
    for key in ["quality", "resolution", "hd"]:
        if key in channel and channel[key]:
            info["quality"] = str(channel[key]).strip()
            break

    return info


def build_stream_url(info, token, config):
    """Kanal için stream URL oluştur"""
    # Eğer direkt URL varsa onu kullan
    if info["url"]:
        url = info["url"]
        # Token ekle (yoksa)
        if "token=" not in url and token:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}token={token}"
        return url

    # Stream ID'den URL oluştur
    if info["stream_id"]:
        return f'{config["stream_base"]}/{info["stream_id"]}/playlist.m3u8?token={token}'

    return ""


def check_stream(url, config):
    """Stream'in çalışıp çalışmadığını kontrol et"""
    if not config.get("check_streams", False):
        return True

    try:
        response = requests.head(
            url,
            headers=get_headers(config),
            timeout=10,
            allow_redirects=True
        )
        return response.status_code in [200, 301, 302]
    except:
        return False


def categorize_channel(name, current_group):
    """Kanal isminden otomatik kategori belirle"""
    if current_group and current_group != "Diğer":
        return current_group

    name_lower = name.lower()

    categories = {
        "Spor": ["sport", "spor", "bein", "s sport", "tivibu spor", "eurosport",
                  "nba", "futbol", "match", "arena"],
        "Haber": ["haber", "news", "cnn", "ntv", "habertürk", "tgrt haber",
                   "a haber", "bloomberg", "euronews"],
        "Sinema": ["sinema", "movie", "film", "cinema", "fx", "tcm",
                    "premiere", "filmbox"],
        "Belgesel": ["belgesel", "documentary", "national geo", "discovery",
                     "animal planet", "history", "bbc earth", "dmax"],
        "Çocuk": ["çocuk", "child", "kids", "cartoon", "disney", "nickelodeon",
                   "baby", "minika", "trt çocuk"],
        "Müzik": ["müzik", "music", "kral", "power", "mtv", "vh1"],
        "Ulusal": ["trt", "atv", "star tv", "show tv", "kanal d", "fox tv",
                    "tv8", "tv 8", "now tv", "teve2", "trt 1"],
        "Eğlence": ["eğlence", "entertainment", "comedy", "tlc", "e!",
                     "tv2", "dizi"]
    }

    for group, keywords in categories.items():
        for keyword in keywords:
            if keyword in name_lower:
                return group

    return current_group


def generate_m3u(channels, token, config):
    """M3U dosyası oluştur"""
    logger.info(f"📝 {OUTPUT_FILE} oluşturuluyor...")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        f'#EXTM3U url-tvg="" refresh="3600"',
        f'# CDNLiveTV M3U Playlist',
        f'# Son Güncelleme: {now}',
        f'# Toplam Kanal: {len(channels)}',
        f'# GitHub: cdnlivetv-m3u',
        ''
    ]

    success_count = 0
    failed_count = 0
    groups = {}

    for channel in channels:
        info = extract_channel_info(channel)

        if not info["name"]:
            logger.warning(f"⚠️ İsimsiz kanal atlandı: {channel}")
            continue

        # URL oluştur
        stream_url = build_stream_url(info, token, config)
        if not stream_url:
            logger.warning(f"⚠️ URL bulunamadı: {info['name']}")
            failed_count += 1
            continue

        # Otomatik kategorize et
        info["group"] = categorize_channel(info["name"], info["group"])

        # Grup sayacı
        groups[info["group"]] = groups.get(info["group"], 0) + 1

        # Kalite etiketi
        quality_tag = f' [{info["quality"]}]' if info["quality"] else ""

        # M3U satırları
        extinf = (
            f'#EXTINF:-1 '
            f'tvg-id="{info["tvg_id"]}" '
            f'tvg-name="{info["name"]}" '
            f'tvg-logo="{info["logo"]}" '
            f'group-title="{info["group"]}"'
            f',{info["name"]}{quality_tag}'
        )

        lines.append(extinf)
        lines.append(stream_url)
        lines.append('')
        success_count += 1

    # Dosyaya yaz
    with open(config["output_file"], "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"✅ {config['output_file']} oluşturuldu!")
    logger.info(f"📊 Başarılı: {success_count} | Başarısız: {failed_count}")
    logger.info(f"📂 Gruplar: {json.dumps(groups, ensure_ascii=False)}")

    # Config güncelle
    config["last_update"] = now
    config["channel_count"] = success_count
    config["groups"] = groups
    save_config(config)

    return success_count


def update_readme(config):
    """README.md dosyasını güncelle"""
    now = config.get("last_update", "Bilinmiyor")
    count = config.get("channel_count", 0)
    groups = config.get("groups", {})

    groups_table = ""
    for group, cnt in sorted(groups.items()):
        groups_table += f"| {group} | {cnt} |\n"

    readme = f"""# 📺 CDNLiveTV M3U Playlist

![Güncelleme](https://img.shields.io/badge/Son_Güncelleme-{now.replace(' ', '_')}-brightgreen)
![Kanal](https://img.shields.io/badge/Kanal_Sayısı-{count}-blue)
![Otomatik](https://img.shields.io/badge/Otomatik-GitHub_Actions-yellow)

## 📥 Kullanım

### Tivimate / IPTV Oynatıcı
