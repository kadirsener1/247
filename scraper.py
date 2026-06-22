import re
import sys
import time
import base64
import html as html_lib
import threading
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests

# ─────────────────────────────────────────────
# YAPILANDIRMA
# ─────────────────────────────────────────────
BASE_URL = "https://dlhd.pk/"
CHANNELS_PAGE = "https://dlhd.pk/24-7-channels.php"
WATCH_URL = "https://dlhd.pk/watch.php?id="
OUTPUT_FILE = "tv247.m3u"

MAX_DEPTH = 3
MAX_CANDIDATES_PER_PAGE = 20
SLEEP_BETWEEN_REQUESTS = 0.15

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
# SESSION
# ─────────────────────────────────────────────
_thread_local = threading.local()


def make_session():
    # cloudscraper varsa onu kullan, yoksa requests
    try:
        import cloudscraper
        s = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True}
        )
    except Exception:
        s = requests.Session()

    s.headers.update(HEADERS)
    return s


def get_session():
    if not hasattr(_thread_local, "session"):
        _thread_local.session = make_session()
    return _thread_local.session


# ─────────────────────────────────────────────
# YARDIMCI
# ─────────────────────────────────────────────
def normalize_url(url, base_url=None):
    if not url:
        return None
    url = url.strip().strip('"\'')
    if url.startswith("//"):
        return "https:" + url
    if base_url:
        return urljoin(base_url, url)
    return url


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


def normalize_channel_name(name, channel_id=None):
    name = clean_html_text(name)
    name = re.sub(r'\s*ID\s*:\s*\d+\s*$', '', name, flags=re.I).strip()
    name = re.sub(r'\s+', ' ', name).strip()
    if not name:
        name = f"Channel {channel_id}" if channel_id else "Unknown Channel"
    return name


def is_probably_base64(s):
    if not s or len(s) < 40:
        return False
    if len(s) % 4 != 0:
        return False
    return re.fullmatch(r'[A-Za-z0-9+/=]+', s) is not None


def decode_variants(text):
    variants = []
    seen = set()

    def add(v):
        if v and v not in seen:
            seen.add(v)
            variants.append(v)

    add(text)

    html_unescaped = html_lib.unescape(text)
    add(html_unescaped)
    add(html_unescaped.replace("\\/", "/"))

    try:
        add(bytes(html_unescaped, "utf-8").decode("unicode_escape"))
    except Exception:
        pass

    # atob("....")
    for b64 in re.findall(r'atob\(\s*[\'"]([A-Za-z0-9+/=]{20,})[\'"]\s*\)', text, re.I):
        try:
            dec = base64.b64decode(b64).decode("utf-8", errors="ignore")
            add(dec)
        except Exception:
            pass

    # generic quoted base64 strings
    b64_tokens = re.findall(r'[\'"]([A-Za-z0-9+/=]{60,})[\'"]', text)
    for token in b64_tokens[:20]:
        if is_probably_base64(token):
            try:
                dec = base64.b64decode(token).decode("utf-8", errors="ignore")
                if any(x in dec.lower() for x in ["m3u8", "premium", "watch.php", "api.php", "iframe", "http"]):
                    add(dec)
            except Exception:
                pass

    return variants


def is_interesting_url(url):
    if not url:
        return False

    low = url.lower()

    # gereksiz static / sosyal / reklam şeyleri ele
    bad_parts = [
        ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
        ".woff", ".woff2", ".ttf", ".eot",
        "googleapis.com", "gstatic.com", "fontawesome", "cdnjs",
        "discord.gg", "t.me/", "telegram", "chatango",
        "histats", "doubleclick", "googlesyndication"
    ]
    if any(x in low for x in bad_parts):
        return False

    good_parts = [
        ".m3u8", "premium", "watch.php", "embed", "player",
        "stream", "source", "api.php", "channel", "play"
    ]
    if any(x in low for x in good_parts):
        return True

    parsed = urlparse(url)
    if parsed.netloc.endswith("dlhd.pk") and parsed.path.endswith(".php"):
        return True

    return False


def candidate_score(url, channel_id=None):
    low = url.lower()
    score = 0

    if ".m3u8" in low:
        score += 100
    if channel_id and f"premium{channel_id}" in low:
        score += 80
    if "premium" in low:
        score += 40
    if "api.php" in low:
        score += 30
    if "embed" in low:
        score += 25
    if "player" in low:
        score += 20
    if "stream" in low:
        score += 20
    if "watch.php" in low:
        score += 10

    parsed = urlparse(url)
    if parsed.netloc.endswith("dlhd.pk"):
        score += 5

    return score


# ─────────────────────────────────────────────
# KANAL LİSTESİ
# ─────────────────────────────────────────────
def fetch_all_channels():
    log(f"Kanal listesi çekiliyor: {CHANNELS_PAGE}")

    session = get_session()

    try:
        # warm-up
        session.get(BASE_URL, timeout=20)

        resp = session.get(CHANNELS_PAGE, timeout=30)
        resp.raise_for_status()
        html = resp.text

        with open("debug_channels.html", "w", encoding="utf-8") as f:
            f.write(html)

        channels = []
        seen_ids = set()

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

            name = normalize_channel_name(inner_html, channel_id)

            if not name or name == f"Channel {channel_id}":
                for attr in ["title", "aria-label", "data-title", "data-name", "alt"]:
                    mm = re.search(rf'{attr}=["\']([^"\']+)["\']', full_anchor, re.I)
                    if mm:
                        name = normalize_channel_name(mm.group(1), channel_id)
                        break

            seen_ids.add(channel_id)
            channels.append({
                "id": channel_id,
                "name": name,
                "group": "DLHD",
                "href": href
            })

        log(f"✓ {len(channels)} kanal bulundu")
        return channels

    except Exception as e:
        log(f"✗ Kanal listesi hatası: {e}")
        return []


# ─────────────────────────────────────────────
# STREAM ARAMA
# ─────────────────────────────────────────────
def search_m3u8_in_text(text, channel_id=None):
    found = []

    patterns = [
        r'(https?:\/\/[^\s"\'<>\\]+?\.m3u8[^\s"\'<>\\]*)',
        r'((?:https?:)?\/\/[^\s"\'<>\\]+?\/premium\d+\/index\.m3u8[^\s"\'<>\\]*)',
        r'((?:https?:)?\/\/[^\s"\'<>\\]+?\/premium\d+[^\s"\'<>\\]*)',
        r'(https?:\\\\/\\\\/[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)',
    ]

    for pattern in patterns:
        for m in re.findall(pattern, text, re.I):
            url = m.replace("\\/", "/").strip().strip('"\'')
            url = normalize_url(url)
            if url and ".m3u8" in url.lower():
                found.append(url)

    if not found:
        return None

    # channel id ile premium eşleşmesini öne al
    if channel_id:
        for u in found:
            if f"premium{channel_id}" in u.lower():
                return u

    return found[0]


def extract_candidate_urls(text, base_url, channel_id=None):
    urls = set()

    patterns = [
        r'<iframe[^>]+src=["\']([^"\']+)["\']',
        r'<source[^>]+src=["\']([^"\']+)["\']',
        r'<video[^>]+src=["\']([^"\']+)["\']',
        r'\b(?:src|href|file|url|source|data-src|data-url|data-file)\b\s*[:=]\s*["\']([^"\']+)["\']',
        r'["\']((?:https?:)?//[^"\']+)["\']',
        r'["\']((?:/|\./|\.\./)[^"\']+)["\']',
    ]

    for pattern in patterns:
        for raw in re.findall(pattern, text, re.I):
            url = normalize_url(raw, base_url)
            if url and is_interesting_url(url):
                urls.add(url)

    # premium{id} path plain text olarak geçtiyse
    if channel_id:
        premium_matches = re.findall(
            rf'((?:https?:)?//[^\s"\'<>]*premium{channel_id}[^\s"\'<>]*)',
            text,
            re.I
        )
        for raw in premium_matches:
            url = normalize_url(raw, base_url)
            if url:
                urls.add(url)

    return sorted(
        urls,
        key=lambda u: candidate_score(u, channel_id),
        reverse=True
    )[:MAX_CANDIDATES_PER_PAGE]


def resolve_stream_url(url, session, referer):
    url = normalize_url(url, referer)
    if not url:
        return None

    if ".m3u8" not in url.lower():
        return url

    try:
        resp = session.get(
            url,
            timeout=15,
            allow_redirects=True,
            headers={
                **HEADERS,
                "Referer": referer or BASE_URL,
                "Origin": BASE_URL.rstrip("/")
            }
        )
        final_url = resp.url

        if ".m3u8" in final_url.lower():
            return final_url

        text = resp.text[:5000]
        if "#EXTM3U" in text:
            return final_url if final_url else url

        nested = search_m3u8_in_text(text)
        if nested:
            return nested

    except Exception:
        pass

    return url


def extract_m3u8(channel_id, session):
    start_url = f"{WATCH_URL}{channel_id}"

    queue = [(start_url, BASE_URL, 0)]
    visited = set()

    while queue:
        current_url, referer, depth = queue.pop(0)

        if not current_url or current_url in visited or depth > MAX_DEPTH:
            continue

        visited.add(current_url)

        try:
            # doğrudan m3u8 candidate ise resolve et
            if ".m3u8" in current_url.lower():
                resolved = resolve_stream_url(current_url, session, referer)
                if resolved and ".m3u8" in resolved.lower():
                    return resolved
                continue

            resp = session.get(
                current_url,
                timeout=20,
                allow_redirects=True,
                headers={
                    **HEADERS,
                    "Referer": referer or BASE_URL
                }
            )

            if resp.status_code != 200:
                continue

            final_url = resp.url
            text = resp.text

            # raw + decode varyantları
            variants = decode_variants(text)

            # 1) direkt m3u8 ara
            for variant in variants:
                m3u8 = search_m3u8_in_text(variant, channel_id)
                if m3u8:
                    resolved = resolve_stream_url(m3u8, session, final_url)
                    if resolved and ".m3u8" in resolved.lower():
                        return resolved

            # 2) candidate URL'leri çıkar
            next_urls = []
            seen_next = set()

            for variant in variants:
                cands = extract_candidate_urls(variant, final_url, channel_id)
                for c in cands:
                    if c not in seen_next and c not in visited:
                        seen_next.add(c)
                        next_urls.append(c)

            # puana göre sırala
            next_urls = sorted(
                next_urls,
                key=lambda u: candidate_score(u, channel_id),
                reverse=True
            )[:MAX_CANDIDATES_PER_PAGE]

            for u in next_urls:
                queue.append((u, final_url, depth + 1))

            time.sleep(SLEEP_BETWEEN_REQUESTS)

        except Exception:
            continue

    return None


# ─────────────────────────────────────────────
# M3U
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
# DEBUG TEK KANAL
# ─────────────────────────────────────────────
def debug_single_channel(channel_id):
    session = get_session()
    watch_url = f"{WATCH_URL}{channel_id}"

    log(f"DEBUG kanal: {channel_id}")
    try:
        resp = session.get(watch_url, timeout=20, allow_redirects=True)
        log(f"watch status: {resp.status_code}")
        log(f"watch final url: {resp.url}")

        with open(f"debug_watch_{channel_id}.html", "w", encoding="utf-8") as f:
            f.write(resp.text)

        variants = decode_variants(resp.text)
        all_candidates = set()

        for i, variant in enumerate(variants[:10], 1):
            m3u8 = search_m3u8_in_text(variant, channel_id)
            if m3u8:
                log(f"variant {i} m3u8: {m3u8}")

            cands = extract_candidate_urls(variant, resp.url, channel_id)
            for c in cands:
                all_candidates.add(c)

        ranked = sorted(all_candidates, key=lambda u: candidate_score(u, channel_id), reverse=True)

        log("Aday URL'ler:")
        for u in ranked[:30]:
            print(" ", u)

        final = extract_m3u8(channel_id, session)
        log(f"FINAL: {final}")

    except Exception as e:
        log(f"DEBUG hata: {e}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    log("=" * 60)
    log("DLHD 24/7 M3U Generator")
    log("=" * 60)

    # python script.py --debug 51
    if len(sys.argv) >= 3 and sys.argv[1] == "--debug":
        debug_single_channel(sys.argv[2])
        return 0

    channels = fetch_all_channels()
    if not channels:
        log("✗ Hiç kanal bulunamadı!")
        return 1

    log(f"\n{len(channels)} kanal işlenecek...\n")

    session = get_session()

    results = []
    found_count = 0

    for i, ch in enumerate(channels, 1):
        log(f"[{i}/{len(channels)}] {ch['name']} (ID: {ch['id']})")

        m3u8_url = extract_m3u8(ch["id"], session)

        if m3u8_url:
            found_count += 1
            log(f"  ✓ {m3u8_url[:100]}...")
        else:
            log("  ✗ Bulunamadı")

        results.append({
            "id": ch["id"],
            "name": ch["name"],
            "group": ch["group"],
            "url": m3u8_url
        })

        time.sleep(0.2)

    log("\n" + "=" * 60)
    generate_m3u(results)
    log(f"✓ {OUTPUT_FILE} oluşturuldu")
    log(f"SONUÇ: {found_count}/{len(results)} kanal bulundu")

    return 0 if found_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
