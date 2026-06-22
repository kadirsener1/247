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
}


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ─────────────────────────────────────────────
# 1. ADIM: TÜM KANALLARI ÇEK
# ─────────────────────────────────────────────
def fetch_all_channels():
    """
    24-7-channels.php sayfasından tüm kanal ID ve isimlerini tek seferde çek.
    """
    log(f"Kanal listesi çekiliyor: {CHANNELS_PAGE}")

    try:
        resp = requests.get(CHANNELS_PAGE, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        html = resp.text

        # Olası tüm pattern'ler
        patterns = [
            r'href=["\']watch\.php\?id=(\d+)["\'][^>]*>\s*([^<]+?)\s*</a>',
            r'href=["\'](?:https?://dlhd\.pk/)?watch\.php\?id=(\d+)["\'][^>]*>\s*([^<]+?)\s*<',
            r'watch\.php\?id=(\d+)[^>]*>\s*([^<]{2,50}?)\s*</',
        ]

        channels = []
        seen_ids = set()

        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for channel_id, name in matches:
                name = name.strip()
                channel_id = channel_id.strip()
                if channel_id not in seen_ids and name:
                    seen_ids.add(channel_id)
                    channels.append({
                        'id': channel_id,
                        'name': name,
                        'group': 'DLHD'
                    })
            if channels:
                break

        log(f"✓ {len(channels)} kanal bulundu")
        return channels

    except Exception as e:
        log(f"✗ Kanal listesi hatası: {e}")
        return []


# ─────────────────────────────────────────────
# 2. ADIM: HER KANAL İÇİN M3U8 ÇEKME
# ─────────────────────────────────────────────
def search_m3u8_in_html(html):
    """HTML içinde m3u8 URL'si ara"""
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
    """watch.php sayfasından m3u8 URL'sini çıkar (iframe dahil)"""
    watch_url = f"{WATCH_URL}{channel_id}"

    try:
        # Ana sayfa
        resp = session.get(watch_url, timeout=20)
        if resp.status_code != 200:
            return None

        html = resp.text
        m3u8 = search_m3u8_in_html(html)
        if m3u8:
            return m3u8

        # 1. seviye iframe'ler
        iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
        for src in iframes:
            url = urljoin(watch_url, src)
            try:
                r2 = session.get(url, timeout=15, headers={**HEADERS, "Referer": watch_url})
                m3u8 = search_m3u8_in_html(r2.text)
                if m3u8:
                    return m3u8

                # 2. seviye iframe'ler
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
# 3. ADIM: M3U OLUŞTUR
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

    # 1. Tüm kanalları çek
    channels = fetch_all_channels()
    if not channels:
        log("✗ Hiç kanal bulunamadı!")
        return 1

    log(f"\n{len(channels)} kanal işlenecek...\n")

    # 2. Her kanal için m3u8 çek
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

    # 3. M3U oluştur
    log("\n" + "=" * 60)
    content = generate_m3u(results)

    log(f"✓ {OUTPUT_FILE} oluşturuldu")
    log(f"SONUÇ: {found_count}/{len(results)} kanal bulundu")

    print(f"\n{content}")

    return 0 if found_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
