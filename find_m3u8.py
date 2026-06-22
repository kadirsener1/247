import requests
from bs4 import BeautifulSoup
import re
import sys

URL = "https://dlhd.pk/watch.php?id=51"
M3U_FILE = "playlist.m3u"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def find_m3u8_in_page():
    try:
        resp = requests.get(URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"Sayfa alınamadı: {e}")
        sys.exit(1)

    soup = BeautifulSoup(resp.text, "html.parser")
    content = resp.text

    # Önce video/source etiketlerinde ara
    for tag in soup.find_all(["video", "source"]):
        src = tag.get("src")
        if src and ".m3u8" in src:
            return src

    # script içeriklerinde m3u8 URL'si ara (regex)
    pattern = r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)'
    matches = re.findall(pattern, content)
    if matches:
        return matches[0]

    # iframe içinde olabilir
    iframe = soup.find("iframe")
    if iframe and iframe.get("src"):
        iframe_url = iframe["src"]
        print(f"iframe bulundu: {iframe_url} (manuel kontrol gerekebilir)")
        # Eğer iframe içinde m3u8 varsa burada ek bir istek yapılabilir
        # Şimdilik boş dönüyoruz

    return None

def verify_m3u8(url):
    try:
        r = requests.head(url, headers=HEADERS, timeout=10, allow_redirects=True)
        if r.status_code == 200:
            content_type = r.headers.get("Content-Type", "")
            if "mpegurl" in content_type or "vnd.apple.mpegurl" in content_type:
                return True
            # Bazen text/plain dönebilir, body kontrolü yapalım
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
    print("m3u8 bağlantısı aranıyor...")
    m3u8_url = find_m3u8_in_page()
    if not m3u8_url:
        print("m3u8 bağlantısı bulunamadı!")
        sys.exit(1)

    print(f"Bulunan URL: {m3u8_url}")
    if verify_m3u8(m3u8_url):
        print("Bağlantı geçerli.")
    else:
        print("Uyarı: Bağlantı doğrulanamadı, yine de yazılıyor.")
    write_m3u(m3u8_url)

if __name__ == "__main__":
    main()
