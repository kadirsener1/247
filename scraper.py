#!/usr/bin/env python3
import re
import time
import cloudscraper
import base64
from bs4 import BeautifulSoup
from urllib.parse import unquote

def extract_from_base64(text):
    """Metin içindeki base64 olabilecek kısımları çözer."""
    pattern = r'(?:[A-Za-z0-9+/]{40,})'
    found = []
    for match in re.findall(pattern, text):
        try:
            decoded = base64.b64decode(match).decode('utf-8', errors='ignore')
            if 'forestgump' in decoded or 'http' in decoded:
                found.append(decoded)
        except:
            continue
    return found

def get_stream():
    url = "https://sportsbite.org/watch/channel/5-usa"
    print(f"[*] Hedef: {url}")

    # Cloudflare bypass session
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome','platform': 'windows','desktop': True}
    )
    
    try:
        response = scraper.get(url, timeout=20)
        html = response.text
        
        # 1. Klasik iframe tarama
        soup = BeautifulSoup(html, 'html.parser')
        iframes = soup.find_all('iframe')
        for ifr in iframes:
            src = ifr.get('src') or ifr.get('data-src') or ifr.get('data-lazy-src')
            if src:
                print(f"[FOUND iframe]: {src}")

        # 2. forestgump / track kelimelerini içeren her şeyi yakala (en geniş kapsam)
        # track/360, embed/360, ch1/track gibi varyasyonları arar
        patterns = [
            r'(https?://channels\.forestgump\.space/[^\s"\'<>]+)',
            r'(channels\.forestgump\.space/[^\s"\'<>]+)',
            r'(/ch\d+/(?:track|embed)/\d+)',
            r'["\']([^"\']*forestgump\.space[^"\']*)["\']',
            r'["\']([^"\']*/ch\d+/(?:track|embed)/[^"\']*)["\']'
        ]

        found_links = []
        for pat in patterns:
            matches = re.findall(pat, html)
            for m in matches:
                # URL'yi temizle ve tamamla
                clean_url = m.replace('\\', '')
                if clean_url.startswith('//'): clean_url = 'https:' + clean_url
                if clean_url.startswith('/ch'): clean_url = 'https://channels.forestgump.space' + clean_url
                
                if 'forestgump' in clean_url and clean_url not in found_links:
                    found_links.append(clean_url)

        # 3. Base64 tarama (bazen linkler script içinde encode edilmiştir)
        b64_links = extract_from_base64(html)
        found_links.extend(b64_links)

        if not found_links:
            print("[!] Hâlâ bulunamadı. Sayfada 'forestgump' kelimesi geçiyor mu?")
            print(f"    Cevap: {'forestgump' in html.lower()}")
            
            # Eğer forestgump geçmiyorsa, site büyük ihtimalle farklı bir domain kullanıyor olabilir
            # 'track/' veya '360' içeren tüm linkleri bulalım
            print("[*] 'track' veya '/360' içeren tüm URL'ler listeleniyor:")
            others = re.findall(r'(https?://[^\s"\'<>]+(?:track|360)[^\s"\'<>]*)', html)
            for o in others:
                print(f"    Şüpheli: {o}")

        return list(set(found_links))

    except Exception as e:
        print(f"[!] HATA: {e}")
        return []

def save_to_m3u(links):
    if not links: return
    with open("tv247.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for i, link in enumerate(links):
            f.write(f"#EXTINF:-1, Kanal 5 USA - Stream {i+1}\n")
            f.write(f"{link}\n")
    print(f"\n[OK] tv247.m3u dosyası oluşturuldu. {len(links)} link eklendi.")

if __name__ == "__main__":
    links = get_stream()
    if links:
        print("\n--- BULUNAN LİNKLER ---")
        for l in links: print(f"-> {l}")
        save_to_m3u(links)
    else:
        print("\n[X] Maalesef link bulunamadı.")
