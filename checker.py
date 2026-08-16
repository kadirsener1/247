#!/usr/bin/env python3
"""
cdnlivetv API'den kanalları çekip çalışanları cdnlive.m3u dosyasına yazar.
"""

import json
import sys
import os
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta


# ─── AYARLAR ───────────────────────────────────────────────
API_URL = "https://api.cdnlivetv.is/api/v1/channels/?user=cdnlivetv&plan=free"
OUTPUT_FILE = "cdnlive.m3u"
TIMEOUT = 20
MAX_WORKERS = 15
MAX_RETRIES = 2

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://cdnlivetv.is/",
    "Origin": "https://cdnlivetv.is",
}
# ───────────────────────────────────────────────────────────


def load_channels_from_api() -> list:
    """API'den kanal listesini çeker."""
    print(f"🌐 API'den veri çekiliyor: {API_URL}")
    
    try:
        response = requests.get(API_URL, headers=HEADERS, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        channels = data.get("channels", [])
        print(f"✅ {len(channels)} kanal bulundu.")
        return channels
        
    except requests.exceptions.RequestException as e:
        print(f"❌ API hatası: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse hatası: {e}")
        return []


def resolve_stream_url(api_url: str) -> str:
    """
    API'deki stream URL'sini takip edip gerçek m3u8 linkini bulur.
    cdnlivetv redirect kullanıyor, bu fonksiyon son URL'yi alır.
    """
    try:
        response = requests.head(
            api_url,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True
        )
        # Redirect sonrası final URL
        return response.url
    except:
        return api_url  # Hata olursa orijinal URL'yi döndür


def check_stream(channel: dict) -> dict:
    """
    Bir kanalın stream'inin çalışıp çalışmadığını kontrol eder.
    """
    stream_url = channel.get("stream_url", "")
    
    if not stream_url:
        return {
            "alive": False,
            "channel": channel,
            "final_url": "",
            "response_time": 0,
            "status_code": 0
        }
    
    for attempt in range(MAX_RETRIES + 1):
        try:
            start = time.time()
            
            # İlk olarak HEAD request ile kontrol et
            response = requests.head(
                stream_url,
                headers=HEADERS,
                timeout=TIMEOUT,
                allow_redirects=True
            )
            
            final_url = response.url
            elapsed = time.time() - start
            
            # HEAD başarısız ise GET dene
            if response.status_code >= 400:
                start = time.time()
                response = requests.get(
                    stream_url,
                    headers=HEADERS,
                    timeout=TIMEOUT,
                    allow_redirects=True,
                    stream=True
                )
                final_url = response.url
                elapsed = time.time() - start
                
                # İlk chunk'ı oku
                content_check = False
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        content_check = True
                        break
                response.close()
                
                if not content_check:
                    continue
            
            # M3U8 içeriğini doğrula (opsiyonel)
            if response.status_code < 400:
                # Final URL'nin m3u8 olduğunu kontrol et
                if ".m3u8" in final_url or response.status_code == 200:
                    return {
                        "alive": True,
                        "channel": channel,
                        "final_url": final_url,
                        "response_time": round(elapsed, 2),
                        "status_code": response.status_code
                    }
                    
        except requests.exceptions.Timeout:
            if attempt < MAX_RETRIES:
                time.sleep(1)
                continue
        except requests.exceptions.RequestException:
            if attempt < MAX_RETRIES:
                time.sleep(1)
                continue
    
    return {
        "alive": False,
        "channel": channel,
        "final_url": "",
        "response_time": 0,
        "status_code": 0
    }


def generate_m3u(channels: list, output_path: str) -> int:
    """Çalışan kanalları M3U formatında dosyaya yazar."""
    
    # Türkiye saati
    turkey_tz = timezone(timedelta(hours=3))
    now = datetime.now(turkey_tz).strftime("%d.%m.%Y %H:%M:%S")
    
    total = len(channels)
    alive_channels = []
    dead_channels = []
    
    print(f"\n{'='*65}")
    print(f"🔍 Toplam {total} kanal kontrol edilecek...")
    print(f"⚡ Eşzamanlı kontrol: {MAX_WORKERS} thread")
    print(f"⏱️  Timeout: {TIMEOUT} saniye")
    print(f"{'='*65}\n")
    
    # Paralel kontrol
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_stream, ch): ch for ch in channels}
        
        done_count = 0
        for future in as_completed(futures):
            done_count += 1
            result = future.result()
            ch = result["channel"]
            
            progress = f"[{done_count:3d}/{total}]"
            
            if result["alive"]:
                alive_channels.append(result)
                print(
                    f"  ✅ {progress} {ch['name'][:35]:<35} — "
                    f"{result['response_time']}s (HTTP {result['status_code']})"
                )
            else:
                dead_channels.append(ch)
                print(f"  ❌ {progress} {ch['name'][:35]:<35} — ÇALIŞMIYOR")
    
    # Kanallari isme göre sırala
    alive_channels.sort(key=lambda x: x["channel"]["name"].lower())
    
    # M3U dosyası oluştur
    with open(output_path, "w", encoding="utf-8") as f:
        f.write('#EXTM3U x-tvg-url=""\n')
        f.write(f'# 📺 CDN Live TV - M3U Playlist\n')
        f.write(f'# 🕐 Son güncelleme: {now} (TR)\n')
        f.write(f'# ✅ Çalışan kanal: {len(alive_channels)} / {total}\n')
        f.write(f'# 🔗 Kaynak: cdnlivetv.is\n\n')
        
        for item in alive_channels:
            ch = item["channel"]
            final_url = item["final_url"]
            
            # Kanal bilgileri
            name = ch.get("name", "Bilinmeyen Kanal")
            logo = ch.get("logo", "")
            group = ch.get("group", "GENEL")
            tvg_id = ch.get("id", "")
            
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
            
            # Gerçek stream URL'sini yaz (redirect sonrası)
            # Veya orijinal API URL'sini kullanmak isterseniz: ch.get("stream_url")
            f.write(final_url + "\n\n")
    
    # Sonuç raporu
    print(f"\n{'='*65}")
    print(f"📊 SONUÇ RAPORU")
    print(f"{'='*65}")
    print(f"  📺 Toplam kanal    : {total}")
    print(f"  ✅ Çalışan         : {len(alive_channels)}")
    print(f"  ❌ Çalışmayan      : {len(dead_channels)}")
    print(f"  📁 Dosya           : {output_path}")
    print(f"  🕐 Güncelleme      : {now}")
    print(f"{'='*65}\n")
    
    # Grup bazında istatistik
    groups = {}
    for item in alive_channels:
        g = item["channel"].get("group", "GENEL")
        groups[g] = groups.get(g, 0) + 1
    
    if groups:
        print("📂 Grup bazında çalışan kanallar:")
        for g, count in sorted(groups.items(), key=lambda x: -x[1]):
            print(f"   • {g}: {count} kanal")
        print()
    
    # Çalışmayan kanalları göster
    if dead_channels and len(dead_channels) <= 30:
        print("❌ Çalışmayan kanallar:")
        for ch in sorted(dead_channels, key=lambda x: x["name"].lower()):
            print(f"   • {ch['name']}")
        print()
    elif dead_channels:
        print(f"❌ {len(dead_channels)} kanal çalışmıyor (liste çok uzun, gösterilmiyor)\n")
    
    return len(alive_channels)


def main():
    print("\n" + "="*65)
    print("   📺 CDN LIVE TV - M3U PLAYLIST OLUŞTURUCU")
    print("="*65)
    
    # API'den kanalları yükle
    channels = load_channels_from_api()
    
    if not channels:
        print("❌ Hiç kanal bulunamadı!")
        sys.exit(1)
    
    # M3U oluştur
    output = os.environ.get("OUTPUT_FILE", OUTPUT_FILE)
    alive_count = generate_m3u(channels, output)
    
    if alive_count == 0:
        print("⚠️  Hiçbir kanal çalışmıyor!")
        sys.exit(1)
    
    print(f"✅ {output} dosyası başarıyla oluşturuldu!\n")


if __name__ == "__main__":
    main()
