#!/usr/bin/env python3
"""
cdnlivetv API'den kanalları çekip M3U dosyasına yazar.
"""

import json
import sys
import os
import requests
from datetime import datetime, timezone, timedelta


# ─── AYARLAR ───────────────────────────────────────────────
API_URL = "https://api.cdnlivetv.is/api/v1/channels/?user=cdnlivetv&plan=free"
OUTPUT_FILE = "cdnlive.m3u"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Referer": "https://cdnlivetv.is/",
    "Origin": "https://cdnlivetv.is",
}
# ───────────────────────────────────────────────────────────


def load_channels_from_api() -> list:
    """API'den kanal listesini çeker ve yapıyı debug eder."""
    
    print(f"🌐 API'den veri çekiliyor...")
    print(f"   URL: {API_URL}\n")
    
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        
        response = session.get(API_URL, timeout=30)
        
        print(f"📡 HTTP Status: {response.status_code}")
        print(f"📡 Content-Type: {response.headers.get('Content-Type', 'bilinmiyor')}")
        print(f"📡 Response boyutu: {len(response.content)} byte\n")
        
        # Raw response'u göster (ilk 500 karakter)
        raw_text = response.text[:500]
        print(f"📄 Raw Response (ilk 500 karakter):\n{raw_text}\n")
        
        if response.status_code != 200:
            print(f"❌ HTTP {response.status_code} hatası!")
            return []
        
        # JSON parse
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            print(f"❌ JSON parse hatası: {e}")
            print(f"Response text: {response.text[:1000]}")
            return []
        
        # JSON yapısını analiz et
        print(f"📊 JSON Yapısı:")
        if isinstance(data, dict):
            print(f"   Tip: dict")
            print(f"   Anahtarlar: {list(data.keys())}")
            for key, val in data.items():
                if isinstance(val, list):
                    print(f"   '{key}' listesi: {len(val)} öğe")
                    if val:
                        print(f"   İlk öğe örneği: {json.dumps(val[0], ensure_ascii=False, indent=4)}")
                elif isinstance(val, dict):
                    print(f"   '{key}' dict: {list(val.keys())}")
                else:
                    print(f"   '{key}': {val}")
        elif isinstance(data, list):
            print(f"   Tip: list")
            print(f"   Öğe sayısı: {len(data)}")
            if data:
                print(f"   İlk öğe örneği: {json.dumps(data[0], ensure_ascii=False, indent=4)}")
        
        print()
        
        # Kanalları çıkar
        channels = extract_channels(data)
        print(f"✅ {len(channels)} kanal bulundu.\n")
        return channels
        
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Bağlantı hatası: {e}")
        return []
    except requests.exceptions.Timeout:
        print(f"❌ Timeout hatası!")
        return []
    except Exception as e:
        print(f"❌ Beklenmeyen hata: {type(e).__name__}: {e}")
        return []


def extract_channels(data) -> list:
    """JSON verisinden kanal listesini çıkarır."""
    
    # Direkt liste
    if isinstance(data, list):
        return data
    
    # Dict içinde liste ara
    if isinstance(data, dict):
        # Olası tüm anahtarları dene
        for key in [
            "channels", "data", "items", "results", 
            "streams", "list", "playlist", "channel_list",
            "response", "content"
        ]:
            if key in data and isinstance(data[key], list):
                print(f"✅ Kanallar '{key}' anahtarında bulundu.")
                return data[key]
        
        # İç içe dict kontrolü
        for key, val in data.items():
            if isinstance(val, list) and len(val) > 0:
                if isinstance(val[0], dict) and (
                    "url" in val[0] or "stream_url" in val[0] or 
                    "link" in val[0] or "name" in val[0]
                ):
                    print(f"✅ Kanallar '{key}' anahtarında bulundu (otomatik tespit).")
                    return val
    
    print("⚠️  Kanal listesi otomatik tespit edilemedi!")
    return []


def extract_url(channel: dict) -> str:
    """Kanaldan URL çıkarır."""
    for key in [
        "stream_url", "url", "link", "src", 
        "source", "stream", "hls_url", "m3u8_url",
        "play_url", "video_url"
    ]:
        if key in channel and channel[key]:
            return str(channel[key]).strip()
    return ""


def extract_name(channel: dict) -> str:
    """Kanaldan isim çıkarır."""
    for key in ["name", "title", "channel_name", "display_name", "label"]:
        if key in channel and channel[key]:
            return str(channel[key]).strip()
    return "Bilinmeyen Kanal"


def extract_logo(channel: dict) -> str:
    """Kanaldan logo URL'si çıkarır."""
    for key in ["logo", "image", "icon", "thumbnail", "logo_url", "img"]:
        if key in channel and channel[key]:
            return str(channel[key]).strip()
    return ""


def extract_group(channel: dict) -> str:
    """Kanaldan grup/kategori çıkarır."""
    for key in ["group", "category", "group_title", "genre", "type", "group-title"]:
        if key in channel and channel[key]:
            return str(channel[key]).strip()
    return "GENEL"


def extract_id(channel: dict) -> str:
    """Kanaldan ID çıkarır."""
    for key in ["id", "tvg_id", "tvg-id", "channel_id", "epg_id"]:
        if key in channel and channel[key]:
            return str(channel[key]).strip()
    return ""


def generate_m3u(channels: list, output_path: str) -> int:
    """Tüm kanalları (URL'si olanları) M3U dosyasına yazar."""
    
    # Türkiye saati
    turkey_tz = timezone(timedelta(hours=3))
    now = datetime.now(turkey_tz).strftime("%d.%m.%Y %H:%M:%S")
    
    valid_channels = []
    skipped = 0
    
    print(f"{'='*65}")
    print(f"📝 M3U dosyası oluşturuluyor...")
    print(f"{'='*65}\n")
    
    for ch in channels:
        url = extract_url(ch)
        name = extract_name(ch)
        
        if not url:
            print(f"  ⏭️  Atlandı (URL yok): {name}")
            skipped += 1
            continue
        
        valid_channels.append({
            "name": name,
            "url": url,
            "logo": extract_logo(ch),
            "group": extract_group(ch),
            "id": extract_id(ch),
        })
        print(f"  ➕ Eklendi: {name}")
    
    # İsme göre sırala
    valid_channels.sort(key=lambda x: x["name"].lower())
    
    # M3U yaz
    with open(output_path, "w", encoding="utf-8") as f:
        f.write('#EXTM3U x-tvg-url=""\n')
        f.write(f'# 📺 CDN Live TV - M3U Playlist\n')
        f.write(f'# 🕐 Son güncelleme: {now} (TR)\n')
        f.write(f'# 📊 Toplam kanal: {len(valid_channels)}\n')
        f.write(f'# 🔗 Kaynak: cdnlivetv.is\n\n')
        
        for ch in valid_channels:
            extinf = '#EXTINF:-1'
            
            if ch["id"]:
                extinf += f' tvg-id="{ch["id"]}"'
            
            extinf += f' tvg-name="{ch["name"]}"'
            
            if ch["logo"]:
                extinf += f' tvg-logo="{ch["logo"]}"'
            
            extinf += f' group-title="{ch["group"]}"'
            extinf += f',{ch["name"]}'
            
            f.write(extinf + "\n")
            f.write(ch["url"] + "\n")
    
    # Sonuç
    print(f"\n{'='*65}")
    print(f"📊 SONUÇ")
    print(f"{'='*65}")
    print(f"  📺 API'deki toplam  : {len(channels)}")
    print(f"  ✅ M3U'ya eklenen   : {len(valid_channels)}")
    print(f"  ⏭️  Atlanılan        : {skipped}")
    print(f"  📁 Dosya            : {output_path}")
    print(f"  🕐 Güncelleme       : {now}")
    print(f"{'='*65}\n")
    
    # Grup istatistiği
    groups = {}
    for ch in valid_channels:
        g = ch["group"]
        groups[g] = groups.get(g, 0) + 1
    
    if groups:
        print("📂 Kategoriler:")
        for g, count in sorted(groups.items(), key=lambda x: -x[1]):
            print(f"   • {g}: {count} kanal")
        print()
    
    return len(valid_channels)


def main():
    print("\n" + "═"*65)
    print("   📺 CDN LIVE TV - M3U PLAYLIST OLUŞTURUCU")
    print("═"*65 + "\n")
    
    # API'den kanalları yükle
    channels = load_channels_from_api()
    
    if not channels:
        print("\n⚠️  API'den kanal çekilemedi!")
        print("💡 GitHub Actions loglarındaki 'Raw Response' satırına bakın.")
        print("   API'nin döndürdüğü veriyi görelim.\n")
        sys.exit(1)
    
    # M3U oluştur (kontrol YOK, direkt ekle)
    output = os.environ.get("OUTPUT_FILE", OUTPUT_FILE)
    count = generate_m3u(channels, output)
    
    if count == 0:
        print("⚠️  URL'si olan kanal bulunamadı!")
        print("💡 Loglardaki 'İlk öğe örneği' kısmına bakın,")
        print("   URL hangi anahtarda tutuluyor kontrol edin.\n")
        sys.exit(1)
    
    print(f"✅ {output} başarıyla oluşturuldu! ({count} kanal)\n")


if __name__ == "__main__":
    main()
