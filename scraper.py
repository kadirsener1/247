import re
import os
import sys
import time
import requests
from datetime import datetime
from urllib.parse import urljoin

# ─────────────────────────────────────────────
# YAPILANDIRMA
# ─────────────────────────────────────────────
CHANNELS_PAGE = "https://dlhd.pk/24-7-channels.php"
WATCH_URL = "https://dlhd.pk/watch.php?id="
OUTPUT_FILE = "tv247.m3u"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://dlhd.pk/",
    "Connection": "keep-alive",
}


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ─────────────────────────────────────────────
# DEBUG: SAYFA YAPISINI GÖR
# ─────────────────────────────────────────────
def debug_page():
    """Sayfanın ham HTML'ini göster - pattern bulmak için"""
    log(f"Sayfa çekiliyor: {CHANNELS_PAGE}")

    session = requests.Session()

    # Farklı header kombinasyonları dene
    header_sets = [
        # 1. Tam tarayıcı headers
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://dlhd.pk/",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Cache-Control": "max-age=0",
        },
        # 2. Basit headers
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Referer": "https://dlhd.pk/",
        },
        # 3. Mobile user agent
        {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                          "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://dlhd.pk/",
        },
        # 4. Curl benzeri
        {
            "User-Agent": "curl/7.68.0",
            "Accept": "*/*",
        },
    ]

    for i, headers in enumerate(header_sets):
        log(f"\n--- Header Seti {i+1} deneniyor ---")
        try:
            resp = session.get(
                CHANNELS_PAGE,
                headers=headers,
                timeout=30,
                allow_redirects=True
            )

            log(f"Status: {resp.status_code}")
            log(f"Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
            log(f"Content-Length: {len(resp.content)} bytes")
            log(f"Final URL: {resp.url}")

            html = resp.text

            # İlk 500 karakter
            log(f"\nİlk 500 karakter:")
            print(html[:500])
            print("...")

            # watch.php içeriyor mu?
            if 'watch.php' in html:
                log(f"\n✓ 'watch.php' bulundu!")

                # Tüm watch.php linklerini göster
                all_links = re.findall(r'watch\.php[^"\'<>\s]{0,50}', html)
                log(f"watch.php linkleri ({len(all_links)} adet):")
                for link in all_links[:10]:
                    print(f"  {link}")

                # id= içerenleri göster
                id_links = re.findall(r'watch\.php\?id=\d+', html)
                log(f"\nwatch.php?id= linkleri ({len(id_links)} adet):")
                for link in id_links[:10]:
                    print(f"  {link}")

            elif 'id=' in html:
                log(f"\n'id=' bulundu ama 'watch.php' yok")
                id_matches = re.findall(r'id=\d+', html)
                for m in id_matches[:10]:
                    print(f"  {m}")

            else:
                log(f"\n✗ Ne 'watch.php' ne de 'id=' bulundu")

            # Tüm href'leri göster
            hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)
            log(f"\nTüm href'ler ({len(hrefs)} adet, ilk 20):")
            for href in hrefs[:20]:
                print(f"  {href}")

            # Sayfa başarıyla çekildiyse dur
            if resp.status_code == 200 and len(html) > 100:
                log(f"\n--- Başarılı header seti: {i+1} ---")

                # Orta kısım (kanal listesi genelde burada)
                mid = len(html) // 2
                log(f"\nOrta kısım (500 karakter):")
                print(html[mid-250:mid+250])

                break

        except Exception as e:
            log(f"Hata: {e}")

        time.sleep(1)


# ─────────────────────────────────────────────
# KANAL ÇEKME (debug sonrası güncellenir)
# ─────────────────────────────────────────────
def fetch_all_channels():
    """
    24-7-channels.php sayfasından tüm kanal ID ve isimlerini çek.
    """
    log(f"Kanal listesi çekiliyor: {CHANNELS_PAGE}")

    session = requests.Session()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://dlhd.pk/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
    }

    try:
        # Önce ana sayfayı ziyaret et (cookie almak için)
        log("Ana sayfa ziyaret ediliyor (cookie için)...")
        session.get("https://dlhd.pk/", headers=headers, timeout=30)
        time.sleep(1)

        # Şimdi kanal sayfasını çek
        resp = session.get(CHANNELS_PAGE, headers=headers, timeout=30)
        log(f"Status: {resp.status_code}, Size: {len(resp.content)} bytes")

        html = resp.text

        # Ham HTML'i kaydet (debug için)
        with open("debug_channels.html", "w", encoding="utf-8") as f:
            f.write(html)
        log("HTML 'debug_channels.html' dosyasına kaydedildi")

        # Tüm olası pattern'leri dene
        channels = []
        seen_ids = set()

        # Pattern listesi - geniş tutuldu
        patterns = [
            # Standart format
            r'href=["\']watch\.php\?id=(\d+)["\'][^>]*>\s*([^<]+?)\s*</a>',
            r"href=[\"']watch\.php\?id=(\d+)[\"'][^>]*>([^<]+)<",
            # Tam URL
            r'href=["\']https?://dlhd\.pk/watch\.php\?id=(\d+)["\'][^>]*>\s*([^<]+?)\s*</a>',
            # data-id formatı
            r'data-id=["\'](\d+)["\'][^>]*>\s*([^<]+?)\s*</',
            # Genel id formatı
            r'\?id=(\d+)[^>]*>\s*([A-Za-z0-9][^<]{2,50}?)\s*</',
            # JavaScript içinde
            r'id["\']?\s*:\s*["\']?(\d+)["\']?,\s*["\']?(?:name|title|channel)["\']?\s*:\s*["\']([^"\']+)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
            if matches:
                log(f"✓ Pattern çalıştı: {len(matches)} eşleşme")
                for channel_id, name in matches:
                    channel_id = channel_id.strip()
                    name = re.sub(r'\s+', ' ', name).strip()
                    if channel_id not in seen_ids and name and len(name) > 1:
                        seen_ids.add(channel_id)
                        channels.append({
                            'id': channel_id,
                            'name': name,
                            'group': 'DLHD'
                        })
                break
            else:
                log(f"  Pattern eşleşmedi: {pattern[:60]}...")

        # Hiç bulunamadıysa tüm linkleri göster
        if not channels:
            log("\n✗ Hiç kanal bulunamadı!")
            log("Tüm href'ler:")
            all_hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)
            for href in all_hrefs[:30]:
                print(f"  {href}")

            log("\nHam HTML (ilk 2000 karakter):")
            print(html[:2000])

        log(f"Toplam: {len(channels)} kanal bulundu")
        return channels

    except Exception as e:
        log(f"✗ Hata: {e}")
        import traceback
        traceback.print_exc()
        return []


# ─────────────────────────────────────────────
# M3U8 ÇEKME
# ─────────────────────────────────────────────
def search_m3u8_in_html(html):
    patterns = [
        r'(https?://[^\s"\'<>\\]+/premium\d+/index\.m3u8[^\s"\'<>\\]*)',
        r'(https?://[^\s"\'<>\\]+\.m3u8[^\s"\'<>\\]*)',
        r'(?:source|file|src|url)\s*[:=]\s*["\']?(https?://[^\s"\'<>\\]+\.m3u8[^\s"\'<>\\]*)',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for match in matches:
            url = match.strip().rstrip('"\'\\')
            url = re.sub(r'\\+', '', url)
            if '.m3u8' in url:
                return url
    return None


def extract_m3u8(channel_id, session):
    watch_url = f"{WATCH_URL}{channel_id}"
    try:
        resp = session.get(watch_url, timeout=20)
        if resp.status_code != 200:
            return None

        m3u8 = search_m3u8_in_html(resp.text)
        if m3u8:
            return m3u8

        iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)
        for src in iframes:
            url = urljoin(watch_url, src)
            try:
                r2 = session.get(url, timeout=15, headers={**HEADERS, "Referer": watch_url})
                m3u8 = search_m3u8_in_html(r2.text)
                if m3u8:
                    return m3u8

                iframes2 = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', r2.text, re.IGNORECASE)
                for src2 in iframes2:
                    url2 = urljoin(url, src2)
                    try:
                        r3 = session.get(url2, timeout=15, headers={**HEADERS, "Referer": url})
                        m3u8 = search_m3u8_in_html(r3.text)
                        if m3u8:
                            return m3u8
                    except:
                        pass
            except:
                pass
    except:
        pass
    return None


# ─────────────────────────────────────────────
# M3U OLUŞTUR
# ─────────────────────────────────────────────
def generate_m3u(results):
    lines = [
        '#EXTM3U',
        f'# Updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}',
        f'# Source: dlhd.pk',
        f'# Total: {len([r for r in results if r.get("url")])} channels',
        ''
    ]
    for ch in results:
        if ch.get('url'):
            lines.append(
                f'#EXTINF:-1 tvg-id="{ch["id"]}" '
                f'tvg-name="{ch["name"]}" '
                f'group-title="{ch["group"]}",{ch["name"]}'
            )
            lines.append(f'#EXTVLCOPT:http-referrer=https://dlhd.pk/')
            lines.append(f'#EXTVLCOPT:http-user-agent={HEADERS["User-Agent"]}')
            lines.append(ch['url'])
            lines.append('')

    content = '\n'.join(lines)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    return content


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    log("=" * 60)
    log("DLHD 24/7 M3U Generator")
    log("=" * 60)

    # DEBUG MODU: Önce sayfa yapısını kontrol et
    if "--debug" in sys.argv or len(sys.argv) > 1:
        debug_page()
        return 0

    channels = fetch_all_channels()
    if not channels:
        log("✗ Hiç kanal bulunamadı! '--debug' ile çalıştırın")
        return 1

    log(f"\n{len(channels)} kanal işlenecek...\n")

    session = requests.Session()
    session.headers.update(HEADERS)

    results = []
    found_count = 0

    for i, ch in enumerate(channels):
        log(f"[{i+1}/{len(channels)}] {ch['name']} (ID: {ch['id']})")

        m3u8_url = extract_m3u8(ch['id'], session)

        if m3u8_url:
            found_count += 1
            log(f"  ✓ {m3u8_url[:80]}...")
        else:
            log(f"  ✗ Bulunamadı")

        results.append({
            'id': ch['id'],
            'name': ch['name'],
            'group': ch['group'],
            'url': m3u8_url
        })

        time.sleep(0.5)

    log("\n" + "=" * 60)
    content = generate_m3u(results)
    log(f"✓ {OUTPUT_FILE} oluşturuldu")
    log(f"SONUÇ: {found_count}/{len(results)} kanal bulundu")
    print(f"\n{content}")

    return 0 if found_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
