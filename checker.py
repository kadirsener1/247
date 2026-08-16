#!/usr/bin/env python3
"""
cdnlivetv API'den kanalları çekip M3U dosyasına yazar.
Gelişmiş stream kontrol mekanizması ile.
"""

import json
import sys
import os
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse


# ─── AYARLAR ───────────────────────────────────────────────
API_URL = "https://api.cdnlivetv.is/api/v1/channels/?user=cdnlivetv&plan=free"
OUTPUT_FILE = "cdnlive.m3u"
TIMEOUT = 25
MAX_WORKERS = 10
MAX_RETRIES = 3

# Kontrol modları:
# "strict"  = Sadece gerçekten çalışanları al (yavaş, bazen false-negative)
# "lenient" = API'den 200 dönerse çalışıyor say (hızlı, güvenilir)
# "all"     = Tüm kanalları al, kontrol yapma (en hızlı)
CHECK_MODE = "lenient"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://cdnlivetv.is/",
    "Origin": "https://cdnlivetv.is",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-site",
}
# ───────────────────────────────────────────────────────────


def load_channels_from_api() -> list:
    """API'den kanal listesini çeker."""
    print(f"🌐 API'den veri çekiliyor...")
    print(f"   URL: {API_URL}")
    
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        
        response = session.get(API_URL, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        channels = data.get("channels", [])
        print(f"✅ {len(channels)} kanal bulundu.\n")
        return channels
        
    except requests.exceptions.RequestException as e:
        print(f"❌ API hatası: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse hatası: {e}")
        return []


def check_stream_strict(stream_url: str, session: requests.Session) -> dict:
    """Katı kontrol - gerçek stream erişimini test eder."""
    
    for attempt in range(MAX_RETRIES):
        try:
            # GET request ile dene (HEAD bazen çalışmıyor)
            response = session.get(
                stream_url,
                timeout=TIMEOUT,
                allow_redirects=True,
                stream=True
            )
            
            final_url = response.url
            status = response.status_code
            
            # İçerik kontrolü
            content_type = response.headers.get("Content-Type", "")
            
            # Başarılı durumlar
            if status == 200:
                # M3U8 içeriği mi kontrol et
                try:
                    first_chunk = next(response.iter_content(chunk_size=512), b"")
                    response.close()
                    
                    # M3U8 işaretçileri
                    if (b"#EXTM3U" in first_chunk or 
                        b"#EXT-X-" in first_chunk or
                        b".ts" in first_chunk or
                        "mpegurl" in content_type.lower() or
                        "application/vnd.apple" in content_type.lower()):
                        return {"alive": True, "final_url": final_url, "status": status}
                    
                    # Video içeriği
                    if ("video" in content_type.lower() or 
                        "octet-stream" in content_type.lower()):
                        return {"alive": True, "final_url": final_url, "status": status}
                        
                except:
                    pass
            
            # 3xx yönlendirme - final URL'yi kullan
            if 300 <= status < 400:
                return {"alive": True, "final_url": final_url, "status": status}
            
            # 302 ile m3u8'e yönlendirme
            if final_url != stream_url and ".m3u8" in final_url:
                return {"alive": True, "final_url": final_url, "status": status}
                
            response.close()
            
        except requests.exceptions.Timeout:
            time.sleep(1)
            continue
        except requests.exceptions.RequestException:
            time.sleep(0.5)
            continue
        except Exception:
            continue
    
    return {"alive": False, "final_url": "", "status": 0}


def check_stream_lenient(stream_url: str, session: requests.Session) -> dict:
    """Esnek kontrol - API erişilebilirliğini kontrol eder."""
    
    try:
        # Sadece bağlantı kontrolü
        response = session.head(
            stream_url,
            timeout=15,
            allow_redirects=True
        )
        
        final_url = response.url
        status = response.status_code
        
        # 200, 206, 302, 301 başarılı say
        if status in [200, 206, 301, 302, 303, 307, 308]:
            return {"alive": True, "final_url": final_url, "status": status}
        
        # HEAD çalışmazsa GET dene
        response = session.get(
            stream_url,
            timeout=15,
            allow_redirects=True,
            stream=True
        )
        response.close()
        
        if response.status_code in [200, 206, 301, 302, 303, 307, 308]:
            return {"alive": True, "final_url": response.url, "status": response.status_code}
            
    except:
        pass
    
    return {"alive": False, "final_url": "", "status": 0}


def check_channel(channel: dict, session: requests.Session) -> dict:
    """Tek bir kanalı kontrol eder."""
    
    stream_url = channel.get("stream_url", "")
    
    if not stream_url:
        return {
            "alive": False,
            "channel": channel,
            "final_url": "",
            "status": 0,
            "use_api_url": True
        }
    
    # Kontrol moduna göre
    if CHECK_MODE == "all":
        # Kontrol yapma, direkt ekle
        return {
            "alive": True,
            "channel": channel,
            "final_url": stream_url,
            "status": 200,
            "use_api_url": True
        }
    elif CHECK_MODE == "lenient":
        result = check_stream_lenient(stream_url, session)
    else:  # strict
        result = check_stream_strict(stream_url, session)
    
    return {
        "alive": result["alive"],
        "channel": channel,
        "final_url": result.get("final_url", stream_url),
        "status": result.get("status", 0),
        "use_api_url": True  # API URL'sini kullan
    }


def generate_m3u(channels: list, output_path: str) -> int:
    """Kanalları M3U formatında dosyaya yazar."""
    
    # Türkiye saati
    turkey_tz = timezone(timedelta(hours=3))
    now = datetime.now(turkey_tz).strftime("%d.%m.%Y %H:%M:%S")
    
    total = len(channels)
    alive_channels = []
    dead_channels = []
    
    print(f"{'='*65}")
    print(f"🔍 Kontrol Modu: {CHECK_MODE.upper()}")
    print(f"📺 Toplam {total} kanal kontrol edilecek...")
    print(f"⚡ Eşzamanlı: {MAX_WORKERS} thread | ⏱️ Timeout: {TIMEOUT}s")
    print(f"{'='*65}\n")
    
    # Session oluştur
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # Paralel kontrol
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(check_channel, ch, session): ch 
            for ch in channels
        }
        
        done_count = 0
        for future in as_completed(futures):
            done_count += 1
            
            try:
                result = future.result()
            except Exception as e:
                ch = futures[future]
                result = {
                    "alive": False,
                    "channel": ch,
                    "final_url": "",
                    "status": 0
                }
            
            ch = result["channel"]
            progress = f"[{done_count:3d}/{total}]"
            name = ch.get("name", "?")[:40]
            
            if result["alive"]:
                alive_channels.append(result)
                status_info = f"HTTP {result['status']}" if result['status'] else "OK"
                print(f"  ✅ {progress} {name:<40} — {status_info}")
            else:
                dead_channels.append(ch)
                print(f"  ❌ {progress} {name:<40} — BAŞARISIZ")
    
    session.close()
    
    # Eğer hiç kanal çalışmıyorsa ve strict modundaysak, lenient dene
    if len(alive_channels) == 0 and CHECK_MODE == "strict":
        print("\n⚠️  Strict modda kanal bulunamadı, tüm kanallar ekleniyor...")
        for ch in channels:
            if ch.get("stream_url"):
                alive_channels.append({
                    "channel": ch,
                    "final_url": ch.get("stream_url"),
                    "status": 0,
                    "use_api_url": True
                })
    
    # Kanallari isme göre sırala
    alive_channels.sort(key=lambda x: x["channel"].get("name", "").lower())
    
    # M3U dosyası oluştur
    with open(output_path, "w", encoding="utf-8") as f:
        f.write('#EXTM3U x-tvg-url=""\n')
        f.write(f'# ════════════════════════════════════════════════════════════\n')
        f.write(f'# 📺 CDN Live TV - M3U Playlist\n')
        f.write(f'# 🕐 Son güncelleme: {now} (TR)\n')
        f.write(f'# ✅ Toplam kanal: {len(alive_channels)}\n')
        f.write(f'# 🔗 Kaynak: cdnlivetv.is\n')
        f.write(f'# ════════════════════════════════════════════════════════════\n\n')
        
        for item in alive_channels:
            ch = item["channel"]
            
            # Kanal bilgileri
            name = ch.get("name", "Bilinmeyen Kanal")
            logo = ch.get("logo", "")
            group = ch.get("group", "GENEL")
            tvg_id = ch.get("id", "")
            
            # Stream URL - API URL'sini kullan (daha güvenilir)
            stream_url = ch.get("stream_url", item.get("final_url", ""))
            
            if not stream_url:
                continue
            
            # EXTINF satırı
            extinf = f'#EXTINF:-1'
            
            if tvg_id:
                extinf += f' tvg-id="{tvg_id}"'
            
            extinf += f' tvg-name="{name}"'
            
            if logo:
                extinf += f' tvg-logo="{logo}"'
            
            extinf += f' group-title="{group}"'
            extinf += f',{name}'
            
            f.write(extinf + "\n")
            f.write(stream_url + "\n")
    
    # Sonuç raporu
    print(f"\n{'='*65}")
    print(f"📊 SONUÇ RAPORU")
    print(f"{'='*65}")
    print(f"  📺 API'deki toplam : {total}")
    print(f"  ✅ M3U'ya eklenen  : {len(alive_channels)}")
    print(f"  ❌ Başarısız       : {len(dead_channels)}")
    print(f"  📁 Dosya           : {output_path}")
    print(f"  🕐 Güncelleme      : {now}")
    print(f"{'='*65}\n")
    
    # Grup bazında istatistik
    groups = {}
    for item in alive_channels:
        g = item["channel"].get("group", "GENEL")
        groups[g] = groups.get(g, 0) + 1
    
    if groups:
        print("📂 Kategoriler:")
        for g, count in sorted(groups.items(), key=lambda x: -x[1]):
            print(f"   • {g}: {count} kanal")
        print()
    
    return len(alive_channels)


def main():
    print("\n" + "═"*65)
    print("   📺 CDN LIVE TV - M3U PLAYLIST OLUŞTURUCU")
    print("═"*65 + "\n")
    
    # API'den kanalları yükle
    channels = load_channels_from_api()
    
    if not channels:
        print("❌ API'den kanal çekilemedi!")
        sys.exit(1)
    
    # M3U oluştur
    output = os.environ.get("OUTPUT_FILE", OUTPUT_FILE)
    alive_count = generate_m3u(channels, output)
    
    if alive_count == 0:
        print("❌ Hiç kanal eklenemedi!")
        sys.exit(1)
    
    print(f"✅ {OUTPUT_FILE} başarıyla oluşturuldu! ({alive_count} kanal)\n")


if __name__ == "__main__":
    main()
