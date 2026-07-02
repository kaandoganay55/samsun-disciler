"""
Samsun'daki dis klinigi/dis hekimi web sitelerinin altyapisini (CMS/framework)
tespit eden script - Google Places API versiyonu.

Kullanim:
    pip install -r requirements.txt
    export GOOGLE_PLACES_API_KEY="senin-api-keyin"
    python3 api_versiyon.py

Cikti:
    samsun_disciler_altyapi.csv  - ham veri
    index.html                   - tarayicida acilan gorsel panel (GitHub Pages icin de kullanilir)
    (panel, dashboard_template.html dosyasindan her calistirmada yeniden uretilir)
"""

import csv
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime

import requests

API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY")
OUTPUT_CSV = "samsun_disciler_altyapi.csv"
TEMPLATE_FILE = "dashboard_template.html"
OUTPUT_DASHBOARD = "index.html"  # GitHub Pages varsayilan olarak bu dosyayi acar
REQUEST_TIMEOUT = 10
DELAY_BETWEEN_SITE_REQUESTS = 1.0  # siteleri yormamak icin

TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

# Samsun'un tum ilceleri - tek sorguya sigmayan (60 sonuc siniri olan)
# isletmeleri yakalamak icin ilce ilce ariyoruz.
SAMSUN_ILCELERI = [
    "Atakum", "İlkadım", "Canik", "Tekkeköy", "Ondokuzmayıs", "Bafra",
    "Çarşamba", "Terme", "Salıpazarı", "Ayvacık", "Vezirköprü", "Havza",
    "Ladik", "Kavak", "Yakakent", "Alaçam", "Asarcık",
]

# Her ilcede birden fazla anahtar kelimeyle aramak, tek kelimeyle kacan
# isletmeleri de yakalamamizi sagliyor (bircok klinik sadece "dis hekimi"
# ya da sadece "poliklinik" olarak kayitli).
KEYWORDS = ["diş kliniği", "diş hekimi", "ağız ve diş sağlığı polikliniği"]

SEARCH_QUERIES = [f"{kw} Samsun" for kw in KEYWORDS] + [
    f"{kw} {ilce} Samsun" for ilce in SAMSUN_ILCELERI for kw in KEYWORDS
]

# Adres icinde "... , <ilce>/Samsun" seklinde gecen ilce adini yakalar
# (Google'in formatted_address ciktisinin standart bicimi). Ilce adinin
# basindaki posta kodunu ("55200 Atakum" -> "Atakum") ayiklar; "19 Mayıs"
# gibi rakamla baslayan ilce isimlerini bozmadan birakir.
def extract_district(address):
    parts = [p.strip() for p in (address or "").split(",")]
    # Sondan basa ariyoruz: dogru ilce parcasi genelde adresin sonuna,
    # "Turkiye"den hemen once gelir. Bastaki serbest metin alanlari
    # yanlislikla "/samsun" icerebiliyor (ornek: "... Pk:55600 Terme/samsun").
    for part in reversed(parts):
        if "/samsun" in part.lower():
            district = part.split("/")[0].strip()
            district = re.sub(r"^\d{4,6}\s+", "", district)  # posta kodunu sil
            return district or "Diğer"
    return "Diğer"

# Teknoloji imzalari: HTML govdesi + header'lar icinde aranan regex kaliplari.
FINGERPRINTS = {
    "WordPress": [r"wp-content", r"wp-includes", r"wp-json"],
    "Wix": [r"static\.wixstatic\.com", r"_wixCssMd5", r"wix\.com"],
    "Shopify": [r"cdn\.shopify\.com", r"Shopify\.theme"],
    "Squarespace": [r"squarespace\.com", r"static1\.squarespace\.com"],
    "Webflow": [r"webflow\.com", r"data-wf-site"],
    "Joomla": [r"/media/jui/", r"Joomla!"],
    "Drupal": [r"Drupal\.settings", r"/sites/default/files"],
    "Next.js": [r"__NEXT_DATA__", r"_next/static"],
    "React": [r"data-reactroot", r"react-dom"],
    "Angular": [r"ng-version"],
    "Vue.js": [r"data-v-", r"__vue__"],
    "Laravel": [r"laravel_session", r"XSRF-TOKEN"],
    "ASP.NET": [r"__VIEWSTATE", r"asp\.net"],
}


def get_places(query, api_key):
    """Text Search API ile isletmeleri (ad, adres, place_id) toplar, sayfalar."""
    places = []
    params = {"query": query, "key": api_key, "language": "tr"}
    page = 0

    while True:
        resp = requests.get(TEXT_SEARCH_URL, params=params, timeout=REQUEST_TIMEOUT).json()
        status = resp.get("status")

        # next_page_token birkac saniye aktif olmayabilir; birkac kez tekrar dene.
        retries = 0
        while status == "INVALID_REQUEST" and "pagetoken" in params and retries < 3:
            time.sleep(2)
            resp = requests.get(TEXT_SEARCH_URL, params=params, timeout=REQUEST_TIMEOUT).json()
            status = resp.get("status")
            retries += 1

        if status not in ("OK", "ZERO_RESULTS"):
            print(f"  Places API hatasi ({query}): {json.dumps(resp, ensure_ascii=False)}", file=sys.stderr)
            break

        places.extend(resp.get("results", []))

        token = resp.get("next_page_token")
        page += 1
        if not token or page >= 3:
            break

        time.sleep(2)
        params = {"pagetoken": token, "key": api_key}

    return places


def get_website(place_id, api_key):
    """Place Details API ile bir isletmenin web sitesini ceker."""
    params = {
        "place_id": place_id,
        "fields": "name,website,formatted_address",
        "key": api_key,
    }
    resp = requests.get(DETAILS_URL, params=params, timeout=REQUEST_TIMEOUT).json()
    return resp.get("result", {})


def detect_stack(url):
    """Bir web sitesine istek atip header + HTML uzerinden altyapi tespiti yapar."""
    try:
        resp = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; TechDetectBot/1.0)"},
        )
    except requests.RequestException as exc:
        return {"detected": "", "server_header": "", "x_powered_by": "", "status_code": "", "error": str(exc)}

    haystack = resp.text + str(resp.headers)
    found = set()
    for tech, patterns in FINGERPRINTS.items():
        for pattern in patterns:
            if re.search(pattern, haystack, re.IGNORECASE):
                found.add(tech)
                break

    return {
        "detected": ", ".join(sorted(found)) or "Bilinmiyor / özel kod",
        "server_header": resp.headers.get("Server", ""),
        "x_powered_by": resp.headers.get("X-Powered-By", ""),
        "status_code": resp.status_code,
        "error": "",
    }


def collect_places(api_key):
    """Tum sorgulari calistirir, place_id'ye gore tekillestirir."""
    unique = {}
    for i, query in enumerate(SEARCH_QUERIES, start=1):
        print(f"[{i}/{len(SEARCH_QUERIES)}] Aranıyor: {query}")
        for place in get_places(query, api_key):
            # Samsun disinda yanlislikla eslesen sonuclari eleyelim.
            if "samsun" not in place.get("formatted_address", "").lower():
                continue
            unique.setdefault(place["place_id"], place)
        time.sleep(0.3)
    return list(unique.values())


def build_rows(places, api_key):
    rows = []
    for place in places:
        details = get_website(place["place_id"], api_key)
        website = details.get("website", "")
        address = details.get("formatted_address") or place.get("formatted_address", "")

        row = {
            "name": details.get("name") or place.get("name", ""),
            "address": address,
            "district": extract_district(address),
            "website": website,
            "detected": "",
            "server_header": "",
            "x_powered_by": "",
            "status_code": "",
            "error": "",
        }

        if website:
            print(f"Taranıyor: {website}")
            row.update(detect_stack(website))
            time.sleep(DELAY_BETWEEN_SITE_REQUESTS)
        else:
            row["detected"] = "Website yok"

        rows.append(row)
    return rows


def write_csv(rows, path):
    fieldnames = ["name", "address", "district", "website", "detected", "server_header", "x_powered_by", "status_code", "error"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_dashboard(rows, path, template_path, query_count):
    """dashboard_template.html icindeki yer tutucularini gercek veriyle doldurup yazar."""
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    dashboard_rows = [
        {
            "name": r["name"],
            "address": r["address"],
            "district": r["district"],
            "website": r["website"],
            "detected": r["detected"],
            "error": r["error"],
        }
        for r in rows
    ]

    meta = {
        "generatedAt": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "queryCount": query_count,
    }

    html = template.replace(
        "/*__DATA__*/[]", json.dumps(dashboard_rows, ensure_ascii=False)
    ).replace(
        "/*__META__*/{\"generatedAt\": \"\", \"queryCount\": 0}", json.dumps(meta, ensure_ascii=False)
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    if not API_KEY:
        sys.exit("Hata: GOOGLE_PLACES_API_KEY ortam değişkeni tanımlı değil.")

    # Key'in kendisini hic yazdirmadan, calisan key ile karsilastirmak icin
    # sadece uzunluk + hash "parmak izi" basiyoruz (debug amacli).
    key_fingerprint = hashlib.sha256(API_KEY.encode()).hexdigest()[:12]
    print(f"[debug] API_KEY uzunluk: {len(API_KEY)}, sha256 (ilk 12): {key_fingerprint}")

    if not os.path.exists(TEMPLATE_FILE):
        sys.exit(f"Hata: {TEMPLATE_FILE} bulunamadı. Script ile aynı klasörde olmalı.")

    places = collect_places(API_KEY)
    print(f"\nToplam {len(places)} benzersiz işletme bulundu (tüm sorgular birleştirildi).")

    rows = build_rows(places, API_KEY)

    write_csv(rows, OUTPUT_CSV)
    print(f"CSV yazıldı: {OUTPUT_CSV}")

    write_dashboard(rows, OUTPUT_DASHBOARD, TEMPLATE_FILE, len(SEARCH_QUERIES))
    print(f"Panel oluşturuldu: {OUTPUT_DASHBOARD} (tarayıcıda çift tıklayarak açabilirsin)")


if __name__ == "__main__":
    main()
