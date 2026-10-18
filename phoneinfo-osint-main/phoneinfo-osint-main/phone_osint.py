import requests
from bs4 import BeautifulSoup
import re
import time

def google_search(phone_number, num_results=5):
    query = f'"{phone_number}"'
    url = f"https://www.google.com/search?q={query}&num={num_results}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    print(f"[+] Google araması yapılıyor: {query}")
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print("[!] Google aramasında sorun oluştu.")
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for g in soup.find_all('div', class_='g'):
        a = g.find('a', href=True)
        if a and a['href']:
            results.append(a['href'])
    return results

def scrape_page_for_names(url):
    print(f"[+] Sayfa taranıyor: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return []
        text = resp.text.lower()
        possible_names = re.findall(r'(?:isim|ad|soyad|kullanıcı adı|owner|contact):?\s*([a-zçğıöşü]+(?:\s[a-zçğıöşü]+){0,2})', text, re.I)
        possible_emails = re.findall(r'[\w\.-]+@[\w\.-]+', text)
        results = []
        for name in possible_names:
            results.append(f"Bulunan isim: {name}")
        for email in possible_emails:
            results.append(f"Bulunan e-posta: {email}")
        return results
    except Exception as e:
        print(f"[!] Hata: {e}")
        return []

def run_osint(number):
    links = google_search(number, num_results=10)

    if not links:
        print("[!] Google’dan sonuç bulunamadı.")
        return

    all_found = []
    for link in links:
        time.sleep(2)
        found = scrape_page_for_names(link)
        if found:
            print(f"[+] {link} adresinden bilgiler bulundu:")
            for f in found:
                print(f"    - {f}")
            all_found.extend(found)

    if not all_found:
        print("[!] İsim ya da e-posta gibi bilgi bulunamadı.")
    else:
        print("\n=== Tüm Bulunan Bilgiler ===")
        for info in all_found:
            print(f" - {info}")
