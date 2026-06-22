import requests
from bs4 import BeautifulSoup
import re
import sys
from urllib.parse import urljoin

MAIN_URL = "https://dlhd.pk/watch.php?id=51"
M3U_FILE = "playlist.m3u"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def find_m3u8_in_text(text, base_url=None):
    """Bir HTML metni veya string içinde m3u8 adresi arar."""
    # Önce <video> ve <source> etiketleri
    soup = BeautifulSoup(text, "html.parser")
    for tag in soup.find_all(["video", "source"]):
        src = tag.get("src")
        if src and ".m3u8" in src:
            if base_url:
                return urljoin(base_url, src)
            return src

    # Regex ile tüm string içinde m3u8 yakalama
    pattern = r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)'
    matches = re.findall(pattern, text)
    if matches:
        return matches[0]

    # Yaygın oynatıcı ayarları (JW Player, Clappr, VideoJS)
    player_patterns = [
        r'["\']file["\']\s*:\s*["\']([^"\']+\.m3u8)["\']',
        r'["\']source["\']\s*:\s*["\']([^"\']+\.m3u8)["\']',
        r'["\']src["\']\s*:\s*["\']([^"\']+\.m3u8)["\']',
        r'["\']url["\']\s*:\s*["\']([^"\']+\.m3u8)["\']',
    ]
    for pat in player_patterns:
        match = re.search(pat, text)
        if match:
            return match.group(1)

    return None

def fetch_and_search(url, base=None):
    """Verilen URL’yi getirip içinde m3u8 arar."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"Sayfa alınamadı ({url}): {e}")
        return None

    content = resp.text
    m3u8 = find_m3u8_in_text(content, base or url)
    if m3u8:
        return m3u8

    # iframe var mı? (iç içe durumlar için)
    soup = BeautifulSoup(content, "html.parser")
    iframe = soup.find("iframe")
    if iframe and iframe.get("src"):
        iframe_url = urljoin(base or url, iframe["src"])
        print(f"İç içe iframe bulundu: {iframe_url}")
        return fetch_and_search(iframe_url, base=iframe_url)

    return None

def verify_m3u8(url):
    """m3u8 bağlantısının geçerli olup olmadığını kontrol eder."""
    try:
        r = requests.head(url, headers=HEADERS, timeout=10, allow_redirects=True)
        if r.status_code == 200:
            content_type = r.headers.get("Content-Type", "")
            if "mpegurl" in content_type or "vnd.apple.mpegurl" in content_type:
                return True
            # Bazen text/plain döner, ilk baytları kontrol et
            r2 = requests.get(url, headers=HEADERS, timeout=10, stream=True)
            first_bytes = r2.raw.read(200)
            if first_bytes.startswith(b"#EXTM3U"):
                return True
    except Exception as e:
        print(f"Doğrulama hatası: {e}")
    return False

def write_m3u(url):
    content = f"#EXTM3U\n#EXTINF:-1,DLHD Stream\n{url}\n"
    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"{M3U_FILE} dosyası güncellendi.")

def main():
    print("Ana sayfa taranıyor...")
    try:
        resp = requests.get(MAIN_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"Ana sayfa alınamadı: {e}")
        sys.exit(1)

    main_text = resp.text

    # Önce ana sayfada doğrudan ara
    m3u8_url = find_m3u8_in_text(main_text, MAIN_URL)

    # Bulunamazsa iframe’i takip et
    if not m3u8_url:
        print("Ana sayfada m3u8 bulunamadı, iframe aranıyor...")
        soup = BeautifulSoup(main_text, "html.parser")
        iframe = soup.find("iframe")
        if iframe and iframe.get("src"):
            iframe_src = urljoin(MAIN_URL, iframe["src"])
            print(f"Bulunan iframe: {iframe_src}")
            m3u8_url = fetch_and_search(iframe_src, base=iframe_src)
        else:
            print("Sayfada hiç iframe bulunamadı.")
            sys.exit(1)

    if not m3u8_url:
        print("m3u8 bağlantısı hiçbir yerde bulunamadı!")
        sys.exit(1)

    print(f"Bulunan m3u8: {m3u8_url}")
    if verify_m3u8(m3u8_url):
        print("Bağlantı geçerli.")
    else:
        print("Uyarı: Bağlantı doğrulanamadı, yine de yazılıyor.")
    write_m3u(m3u8_url)

if __name__ == "__main__":
    main()
