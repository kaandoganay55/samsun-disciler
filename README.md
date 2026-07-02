# Samsun Diş Klinikleri - Web Altyapı Taraması

Samsun'daki diş klinikleri/diş hekimlerini Google Places API ile bulur, web
sitelerini tarar ve hangi altyapıyı (WordPress, özel kod, vb.) kullandıklarını
tespit eder.

## Kurulum (her bilgisayarda tek seferlik)

1. Python 3 kurulu olmalı.
2. Bu klasördeki bağımlılığı kur:
   ```
   pip3 install -r requirements.txt
   ```
3. Bir Google Places API key al (console.cloud.google.com → proje oluştur →
   "Places API"yi etkinleştir → Credentials → Create API key). Key'i sadece
   "Places API" ile kısıtlamayı unutma.

## Çalıştırma

```
export GOOGLE_PLACES_API_KEY="senin-keyin"
python3 api_versiyon.py
```

## Çıktılar

- `samsun_disciler_altyapi.csv` — ham veri (Excel/Sheets ile açılabilir)
- `index.html` — tarayıcıda çift tıklayarak açılan görsel panel (özet
  sayılar, genel + ilçe bazlı dağılım grafiği, filtrelenebilir/aranabilir
  liste). Script her çalıştığında bu dosya güncel veriyle yeniden üretilir.

## Dosyalar

- `api_versiyon.py` — ana script
- `dashboard_template.html` — panelin HTML şablonu (script tarafından
  otomatik dolduruluyor, elle düzenlemene gerek yok, script ile aynı
  klasörde kalmalı)
- `requirements.txt` — Python bağımlılıkları
- `.github/workflows/scan.yml` — GitHub Actions ile otomatik/periyodik
  tarama ve yayın ayarı (aşağıya bak)

## Deploy — otomatik tarama + canlı yayın (GitHub Pages + Actions)

Bu kurulum, script'i haftada bir (istersen daha sık) otomatik çalıştırır ve
sonucu ücretsiz bir GitHub Pages linkinde günceller. API key hiçbir zaman
repoya yazılmaz, GitHub'ın şifreli "secret" deposunda tutulur.

1. **GitHub'da yeni bir repo oluştur** (github.com → New repository).
   Public ya da private fark etmez, Pages her ikisinde de çalışır.

2. **Bu klasörü push et:**
   ```
   git remote add origin https://github.com/KULLANICI_ADIN/REPO_ADIN.git
   git branch -M main
   git push -u origin main
   ```

3. **API key'i secret olarak ekle:** Repo → Settings → Secrets and
   variables → Actions → New repository secret
   - Name: `GOOGLE_PLACES_API_KEY`
   - Value: senin key'in

4. **GitHub Pages'i aç:** Repo → Settings → Pages → Source: "Deploy from a
   branch" → Branch: `main`, klasör: `/ (root)` → Save.

5. **İlk taramayı manuel tetikle:** Repo → Actions → "Samsun Diş Klinikleri
   Taraması" → Run workflow. (Yoksa bir sonraki Pazartesi 08:00'de kendiliğinden
   çalışır — sıklığı `.github/workflows/scan.yml` içindeki `cron` satırından
   değiştirebilirsin.)

6. Birkaç dakika sonra panel şurada yayında olur:
   `https://KULLANICI_ADIN.github.io/REPO_ADIN/`

**Not:** Her çalıştırma ~54 arama sorgusu + ~150-250 site taraması yapıyor,
bu Google'ın aylık 200$'lık ücretsiz kotasının küçük bir kısmını tüketiyor.
Diş klinikleri sık site değiştirmediği için haftalık tarama fazlasıyla yeterli
— günlük çalıştırmaya çevirmeden önce kotayı takip et (console.cloud.google.com
→ APIs & Services → Quotas).
