import re
import sys
import time
import html as html_lib
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
# HTML TEMİZLE
# ─────────────────────────────────────────────
def clean_html_text(fragment):
    if not fragment:
        return ""

    fragment = re.sub(r'<!--.*?-->', ' ', fragment, flags=re.S)
    fragment = re.sub(r'<script\b.*?</script>', ' ', fragment, flags=re.I | re.S)
    fragment = re.sub(r'<style\b.*?</style>', ' ', fragment, flags=re.I | re.S)
    fragment = re.sub(r'<br\s*/?>', ' ', fragment, flags=re.I)
    fragment = re.sub(r'<[^>]+>', ' ', fragment)
    fragment = html_lib.unescape(fragment)
    fragment = re.sub(r'\s+', ' ', fragment).strip()
    return fragment


# ─────────────────────────────────────────────
# KANALLARI DİREKT 24-7-CHANNELS.PHP'DEN ÇEK
# ─────────────────────────────────────────────
def fetch_all_channels():
    log(f"Kanal listesi çekiliyor: {CHANNELS_PAGE}")

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        # Cookie / warm-up
        session.get("https://dlhd.pk/", timeout=20)

        resp = session.get(CHANNELS_PAGE, timeout=30)
        resp.raise_for_status()
        html = resp.text

        # Debug için istersen bakarsın
        with open("debug_channels.html", "w", encoding="utf-8") as f:
            f.write(html)

        channels = []
        seen_ids = set()

        # Anchor içeriği nested olabilir, o yüzden tüm <a ...>...</a> bloğunu yakala
        anchor_pattern = re.compile(
            r'<a\b[^>]*href=["\']([^"\']*?/watch\.php\?id=(\d+)[^"\']*)["\'][^>]*>(.*?)</a>',
            re.I | re.S
        )

        matches = list(anchor_pattern.finditer(html))
        log(f"watch.php anchor sayısı: {len(matches)}")

        for m in matches:
            full_anchor = m.group(0)
            href = m.group(1)
            channel_id = m.group(2)
            inner_html = m.group(3)

            if channel_id in seen_ids:
                continue

            # Önce anchor iç metninden isim çıkar
            name = clean_html_text(inner_html)

            # İsim boşsa attribute'lardan dene
            if not name:
                for attr in ["title", "aria-label", "data-title", "data-name", "alt"]:
                    attr_match = re.search(
                        rf'{attr}=["\']([^"\']+)["\']',
                        full_anchor,
                        re.I
                    )
                    if attr_match:
                        name = clean_html_text(attr_match.group(1))
                        if name:
                            break

            # Hâlâ boşsa fallback
            if not name:
                name = f"Channel {channel_id}"

            seen_ids.add(channel_id)
            channels.append({
                "id": channel_id,
                "name": name,
                "group": "DLHD",
                "href": href
            })

        # Eğer üstteki yöntem isim bulamazsa, en azından ID'leri kurtar
        if not channels:
            log("Anchor parse boş geldi, href fallback deneniyor...")
            href_ids = re.findall(r'/watch\.php\?id=(\d+)', html, re.I)
            for cid in href_ids:
                if cid not in seen_ids:
                    seen_ids.add(cid)
                    channels.append({
                        "id": cid,
                        "name": f"Channel {cid}",
                        "group": "DLHD",
                        "href": f"/watch.php?id={cid}"
                    })

        log(f"✓ {len(channels)} kanal bulundu")
        return channels

    except Exception as e:
        log(f"✗ Kanal listesi hatası: {e}")
        return []


# ─────────────────────────────────────────────
# M3U8 ARA
# ─────────────────────────────────────────────
def search_m3u8_in_html(html):
    patterns = [
        r'(https?://[^\s"\'<>\\]+/premium\d+/index\.m3u8[^\s"\'<>\\]*)',
        r'(https?://[^\s"\'<>\\]+\.m3u8[^\s"\'<>\\]*)',
        r'(?:source|file|src|url)\s*[:=]\s*["\']?(https?://[^\s"\'<>\\]+\.m3u8[^\s"\'<>\\]*)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, html, re.I)
        for match in matches:
            url = match.strip().rstrip('"\'\\')
            url = re.sub(r'\\+', '', url)
            if ".m3u8" in url:
                return url

    # Escaped JS string fallback
    js_match = re.search(r'https?:\\\\/\\\\/[^\s"\']+?\.m3u8[^\s"\']*', html, re.I)
    if js_match:
        return js_match.group(0).replace("\\/", "/")

    return None


# ─────────────────────────────────────────────
# WATCH.PHP İÇİNDEN STREAM ÇEK
# ─────────────────────────────────────────────
def extract_m3u8(channel_id, session):
    watch_url = f"{WATCH_URL}{channel_id}"

    try:
        resp = session.get(watch_url, timeout=20)
        if resp.status_code != 200:
            return None

        html = resp.text

        # Ana sayfada var mı?
        m3u8 = search_m3u8_in_html(html)
        if m3u8:
            return m3u8

        # iframe 1
        iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I)
        for src in iframes:
            iframe_url = urljoin(watch_url, src)
            try:
                r2 = session.get(
                    iframe_url,
                    timeout=15,
                    headers={**HEADERS, "Referer": watch_url}
                )
                if r2.status_code != 200:
                    continue

                m3u8 = search_m3u8_in_html(r2.text)
                if m3u8:
                    return m3u8

                # iframe 2
                iframes2 = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', r2.text, re.I)
                for src2 in iframes2:
                    iframe_url2 = urljoin(iframe_url, src2)
                    try:
                        r3 = session.get(
                            iframe_url2,
                            timeout=15,
                            headers={**HEADERS, "Referer": iframe_url}
                        )
                        if r3.status_code != 200:
                            continue

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
        "#EXTM3U",
        f'# Updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}',
        "# Source: dlhd.pk",
        f'# Total: {len([r for r in results if r.get("url")])}',
        ""
    ]

    for ch in results:
        if not ch.get("url"):
            continue

        lines.append(
            f'#EXTINF:-1 tvg-id="{ch["id"]}" '
            f'tvg-name="{ch["name"]}" '
            f'group-title="{ch["group"]}",{ch["name"]}'
        )
        lines.append('#EXTVLCOPT:http-referrer=https://dlhd.pk/')
        lines.append(f'#EXTVLCOPT:http-user-agent={HEADERS["User-Agent"]}')
        lines.append(ch["url"])
        lines.append("")

    content = "\n".join(lines)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    return content


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    log("=" * 60)
    log("DLHD 24/7 M3U Generator")
    log("=" * 60)

    channels = fetch_all_channels()
    if not channels:
        log("✗ Hiç kanal bulunamadı!")
        return 1

    log(f"\n{len(channels)} kanal işlenecek...\n")

    session = requests.Session()
    session.headers.update(HEADERS)

    results = []
    found_count = 0

    for i, ch in enumerate(channels, 1):
        log(f"[{i}/{len(channels)}] {ch['name']} (ID: {ch['id']})")

        m3u8_url = extract_m3u8(ch["id"], session)

        if m3u8_url:
            found_count += 1
            log(f"  ✓ {m3u8_url[:90]}...")
        else:
            log("  ✗ Bulunamadı")

        results.append({
            "id": ch["id"],
            "name": ch["name"],
            "group": ch["group"],
            "url": m3u8_url
        })

        time.sleep(0.3)

    log("\n" + "=" * 60)
    generate_m3u(results)
    log(f"✓ {OUTPUT_FILE} oluşturuldu")
    log(f"SONUÇ: {found_count}/{len(results)} kanal bulundu")

    return 0 if found_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
