import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import requests
import time
import threading

# ANSI Renk Kodları
C_GREEN = "\033[92m"
C_RED = "\033[91m"
C_YELLOW = "\033[93m"
C_BLUE = "\033[94m"
C_CYAN = "\033[96m"
C_MAGENTA = "\033[95m"
C_WHITE = "\033[97m"
C_BOLD = "\033[1m"
C_RESET = "\033[0m"

# ── TELEGRAM KÜRESEL SİBER VERİLERİ ──
# Değerler uygulama çalışırken dinamik olarak doldurulacak
TELEGRAM_BOT_TOKEN = None
TELEGRAM_CHAT_ID = None
aktif_alarmlar = {}  # Yapısı: {"SEMBOL": {"alt_limit": X, "ust_limit": Y, "isim": Z, "yahoo_kod": W}}

class YahooBypassEngine:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,tr;q=0.8"
        }
        self.session.headers.update(self.headers)
        self.crumb = None
        self.init_bypass()

    def init_bypass(self):
        try:
            self.session.get("https://finance.yahoo.com", timeout=10)
            crumb_resp = self.session.get("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=10)
            if crumb_resp.status_code == 200 and crumb_resp.text:
                self.crumb = crumb_resp.text.strip()
        except Exception:
            self.crumb = None

    def veri_indir(self, sembol, gun_sayisi=3650):
        bitis_ts = int(time.time())
        baslangic_ts = bitis_ts - (gun_sayisi * 24 * 60 * 60)
        
        if self.crumb:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sembol}?period1={baslangic_ts}&period2={bitis_ts}&interval=1d&crumb={self.crumb}"
        else:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sembol}?period1={baslangic_ts}&period2={bitis_ts}&interval=1d"
            
        try:
            res = self.session.get(url, timeout=12)
            if res.status_code != 200:
                url_fallback = f"https://query1.finance.yahoo.com/v8/finance/chart/{sembol}?period1={baslangic_ts}&period2={bitis_ts}&interval=1d"
                res = self.session.get(url_fallback, timeout=12)
                if res.status_code != 200:
                    return pd.DataFrame()

            data = res.json()
            result = data['chart']['result'][0]
            timestamps = result['timestamp']
            indicators = result['indicators']['quote'][0]
            
            df = pd.DataFrame({
                'Close': indicators['close'],
                'High': indicators['high'],
                'Low': indicators['low']
            }, index=pd.to_datetime(timestamps, unit='s'))
            
            df.index = df.index.date
            df = df.dropna(subset=['Close'])
            return df
        except Exception:
            return pd.DataFrame()


def telegram_mesaj_gonder(mesaj):
    """Telegram API üzerinden mesaj iletimi sağlar."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mesaj,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, json=payload, timeout=8)
        return res.status_code == 200
    except Exception:
        return False


def fiyat_hesapla_tl(yahoo_kod, engine):
    """Anlık TL fiyatını hesaplayan optimize edilmiş siber fonksiyon."""
    gercek_sorgu = "GC=F" if yahoo_kod == "GRAM_ALTIN" else yahoo_kod
    df = engine.veri_indir(gercek_sorgu, gun_sayisi=5)
    if df.empty:
        return None
        
    usd_df = engine.veri_indir("USDTRY=X", gun_sayisi=5)
    usd_guncel = float(usd_df['Close'].iloc[-1]) if not usd_df.empty else 34.35
    
    yabanci_varliklar = [
        "GC=F", "SI=F", "BZ=F", "BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD", "XRP-USD",
        "AAPL", "TSLA", "NVDA", "MSFT", "AMZN"
    ]
    
    ham_fiyat = float(df['Close'].iloc[-1])
    
    if yahoo_kod == "GRAM_ALTIN":
        return (ham_fiyat / 31.1034768) * usd_guncel
    elif yahoo_kod in yabanci_varliklar:
        return ham_fiyat * usd_guncel
    else:
        return ham_fiyat


def alarm_takip_motoru():
    """Arka planda sessizce çalışan asenkron siber takip motoru."""
    engine_thread = YahooBypassEngine()
    
    while True:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or not aktif_alarmlar:
            time.sleep(15)
            continue
            
        silinecekler = []
        
        for anahtar, alarm in list(aktif_alarmlar.items()):
            guncel_fiyat = fiyat_hesapla_tl(alarm["yahoo_kod"], engine_thread)
            if guncel_fiyat is None:
                continue
                
            # Üst Limit Kontrolü
            if alarm["ust_limit"] and guncel_fiyat >= alarm["ust_limit"]:
                mesaj = (
                    f"🔔 *[ALARM TETİKLENDİ - YÜKSELİŞ]*\n\n"
                    f"📈 *Varlık:* {alarm['isim']}\n"
                    f"💵 *Güncel Fiyat:* {guncel_fiyat:,.2f} TL\n"
                    f"🎯 *Hedef Üst Limit:* {alarm['ust_limit']:,.2f} TL\n\n"
                    f"⚡ _Belirttiğiniz direnç seviyesi yukarı yönlü kırıldı!_"
                )
                if telegram_mesaj_gonder(mesaj):
                    silinecekler.append(anahtar)
                    
            # Alt Limit Kontrolü
            elif alarm["alt_limit"] and guncel_fiyat <= alarm["alt_limit"]:
                mesaj = (
                    f"🚨 *[ALARM TETİKLENDİ - DÜŞÜŞ]*\n\n"
                    f"📉 *Varlık:* {alarm['isim']}\n"
                    f"💵 *Güncel Fiyat:* {guncel_fiyat:,.2f} TL\n"
                    f"🎯 *Hedef Alt Limit:* {alarm['alt_limit']:,.2f} TL\n\n"
                    f"⚠️ _Belirttiğiniz destek seviyesi aşağı yönlü kırıldı!_"
                )
                if telegram_mesaj_gonder(mesaj):
                    silinecekler.append(anahtar)
        
        for k in silinecekler:
            if k in aktif_alarmlar:
                del aktif_alarmlar[k]
                
        time.sleep(60)


def telegram_alt_panel(varliklar, engine):
    """'TELEGRAM' komutu girildiğinde açılan tamamen izole siber katman."""
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    
    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        print(f"{C_MAGENTA}╔════════════════════════════════════════════════════════════════════════╗{C_RESET}")
        print(f"{C_MAGENTA}║                  🛰️  TELEGRAM BİLDİRİM VE ALARM KONTROL MERKEZİ        ║{C_RESET}")
        print(f"{C_MAGENTA}╚════════════════════════════════════════════════════════════════════════╝{C_RESET}")
        
        print(f" 🛠️  *Mevcut Bağlantı Durumu:*")
        print(f"    ➔ Token  : {C_GREEN if TELEGRAM_BOT_TOKEN else C_RED}{TELEGRAM_BOT_TOKEN if TELEGRAM_BOT_TOKEN else 'GİRİLMEDİ (YOK)'}{C_RESET}")
        print(f"    ➔ Chat ID: {C_GREEN if TELEGRAM_CHAT_ID else C_RED}{TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else 'GİRİLMEDİ (YOK)'}{C_RESET}")
        print(f"    ➔ Alarmlar: {C_YELLOW}{len(aktif_alarmlar)} adet aktif takip var.{C_RESET}\n")
        
        print(f" {C_BLUE}[ SEÇENEKLER ]{C_RESET}")
        print(f"   {C_GREEN}[1]{C_RESET} Bot Token Gir / Güncelle")
        print(f"   {C_GREEN}[2]{C_RESET} Chat ID Gir / Güncelle")
        print(f"   {C_GREEN}[3]{C_RESET} Yeni Fiyat Takip Alarmı Kur")
        print(f"   {C_GREEN}[4]{C_RESET} Aktif Alarmları Listele / Temizle")
        print(f"   {C_RED}[G]{C_RESET} Ana Menüye Geri Dön")
        print(f"{C_MAGENTA}──────────────────────────────────────────────────────────────────────────{C_RESET}")
        
        secim = input(f"{C_MAGENTA}{C_BOLD}telegram_subsystem# {C_RESET}").strip().upper()
        
        if secim == "G":
            break
            
        elif secim == "1":
            token_girdi = input(f"\n{C_WHITE}👉 Telegram Bot Tokeninizi Girin: {C_RESET}").strip()
            if token_girdi:
                TELEGRAM_BOT_TOKEN = token_girdi
                print(f"{C_GREEN}[+] Token sisteme kaydedildi.{C_RESET}")
            time.sleep(1)
            
        elif secim == "2":
            id_girdi = input(f"\n{C_WHITE}👉 Telegram Chat ID'nizi Girin: {C_RESET}").strip()
            if id_girdi:
                TELEGRAM_CHAT_ID = id_girdi
                print(f"{C_GREEN}[+] Chat ID sisteme kaydedildi.{C_RESET}")
                if TELEGRAM_BOT_TOKEN:
                    print(f"{C_CYAN}[+] Test mesajı fırlatılıyor...{C_RESET}")
                    telegram_mesaj_gonder("🧪 *BorsaBotu siber entegrasyon testi başarılı!*")
            time.sleep(1.5)
            
        elif secim == "3":
            if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
                print(f"{C_RED}[-] Önce Seçenek 1 ve 2'yi kullanarak bağlantı bilgilerini tanımlayın!{C_RESET}")
                time.sleep(2)
                continue
                
            girdi = input(f"\n {C_WHITE}👉 Alarm kurulacak varlık kodu (Örn: BTC, GRAM_ALTIN, THYAO): {C_RESET}").strip().upper()
            if not girdi: continue
            
            if girdi in varliklar:
                yahoo_kod, meta_isim = varliklar[girdi]
            else:
                if not girdi.endswith(".IS") and "-" not in girdi and "=" not in girdi:
                    yahoo_kod, meta_isim = f"{girdi}.IS", f"BIST: {girdi}"
                else:
                    yahoo_kod, meta_isim = girdi, f"Özel Varlık ({girdi})"
            
            print(f"{C_CYAN}[+] Canlı fiyat kontrol ediliyor...{C_RESET}")
            mevcut_fiyat = fiyat_hesapla_tl(yahoo_kod, engine)
            
            if mevcut_fiyat is None:
                print(f"{C_RED}[-] HATA: Veri çekilemedi, varlık kodunu kontrol edin.{C_RESET}")
                time.sleep(2)
                continue
                
            print(f"{C_GREEN}[+] Bulundu! Anlık Fiyat: {C_BOLD}{mevcut_fiyat:,.2f} TL{C_RESET}")
            try:
                alt_girdi = input(f" 📉 Bu fiyatın ALTINA düşerse (TL) [Boş bırakmak için Enter]: {C_RESET}").strip()
                alt_limit = float(alt_girdi) if alt_girdi else None
                
                ust_girdi = input(f" 📈 Bu fiyatın ÜZERİNE çıkarsa (TL) [Boş bırakmak için Enter]: {C_RESET}").strip()
                ust_limit = float(ust_girdi) if ust_girdi else None
            except ValueError:
                print(f"{C_RED}[-] HATA: Geçersiz sayı girdiniz!{C_RESET}")
                time.sleep(1.5)
                continue
                
            if alt_limit is None and ust_limit is None:
                print(f"{C_RED}[-] Herhangi bir limit girilmedi, iptal edildi.{C_RESET}")
                time.sleep(1.5)
                continue
                
            aktif_alarmlar[yahoo_kod] = {
                "yahoo_kod": yahoo_kod,
                "isim": meta_isim,
                "alt_limit": alt_limit,
                "ust_limit": ust_limit
            }
            telegram_mesaj_gonder(f"📌 *Takip Başlatıldı: {meta_isim}*\n📉 Alt Limit: {alt_limit if alt_limit else 'Yok'}\n📈 Üst Limit: {ust_limit if ust_limit else 'Yok'}")
            print(f"{C_GREEN}[+] Alarm başarıyla arka plan motoruna eklendi!{C_RESET}")
            time.sleep(1.5)
            
        elif secim == "4":
            print(f"\n{C_CYAN}── AKTİF ALARMLAR LİSTESİ ──{C_RESET}")
            if not aktif_alarmlar:
                print(f" {C_WHITE}Şu anda kurulmuş aktif alarm bulunmuyor.{C_RESET}")
            else:
                for k, v in aktif_alarmlar.items():
                    print(f" ➔ {C_BOLD}{v['isim']}{C_RESET} ({k}) -> Alt: {v['alt_limit']} TL | Üst: {v['ust_limit']} TL")
                
                temizle = input(f"\n{C_RED} Tüm alarmları sıfırlamak ister misiniz? (E/H): {C_RESET}").strip().upper()
                if temizle == "E":
                    aktif_alarmlar.clear()
                    print(f"{C_GREEN}[+] Tüm alarmlar temizlendi.{C_RESET}")
            input(f"\nDevam etmek için [Enter]'a basın...")


def portfoy_simulasyonu(guncel_fiyat, z_skoru, rsi, gunluk_oynaklik, m_egim):
    print(f"\n{C_YELLOW}╔════════════════════════════════════════════════════════════════════════╗{C_RESET}")
    print(f"{C_YELLOW}║               💰 PORTFÖY RİSK & GELECEK TAHMİN SİMÜLATÖRÜ              ║{C_RESET}")
    print(f"{C_YELLOW}╚════════════════════════════════════════════════════════════════════════╝{C_RESET}")
    
    try:
        bakiye = float(input(f" {C_WHITE}👉 Bu varlığa yatıracağınız toplam bütçe (TL): {C_RESET}"))
        vade = int(input(f" {C_WHITE}👉 Elinizde tutacağınız yaklaşık süre (Gün): {C_RESET}"))
        if bakiye <= 0 or vade <= 0: return
    except ValueError: return

    trend_etkisi = m_egim * vade * 100  
    duzeltme_etkisi = 0.0
    if z_skoru > 1.0: duzeltme_etkisi -= (z_skoru * 1.5)  
    if z_skoru < -1.0: duzeltme_etkisi += (abs(z_skoru) * 2.0) 
    if rsi > 75: duzeltme_etkisi -= 2.0
    if rsi < 25: duzeltme_etkisi += 2.5

    beklenen_baz_degisim = trend_etkisi + duzeltme_etkisi
    toplam_oynaklik_marji = gunluk_oynaklik * np.sqrt(vade) * 1.5

    tahmini_kar_orani = beklenen_baz_degisim + toplam_oynaklik_marji
    tahmini_zarar_orani = beklenen_baz_degisim - toplam_oynaklik_marji
    if tahmini_zarar_orani < -90: tahmini_zarar_orani = -90.0

    iyimser_bakiye = bakiye * (1 + (tahmini_kar_orani / 100))
    kotumser_bakiye = bakiye * (1 + (tahmini_zarar_orani / 100))
    
    print(f"\n{C_MAGENTA}┌────────────────────────────────────────────────────────────────────────┐{C_RESET}")
    print(f"│ {C_BOLD}{C_WHITE}📊 {vade} GÜNLÜK MATEMATİKSEL PROJEKSİYON SONUÇLARI{C_RESET}                          │")
    print(f"{C_MAGENTA}├────────────────────────────────────────────────────────────────────────┤{C_RESET}")
    print(f"  {C_WHITE}İlk Yatırılan Ana Para : {C_BOLD}{bakiye:,.2f} TL{C_RESET}")
    print(f"  {C_WHITE}Pazar Trend Eğilimi    : {C_CYAN}%{beklenen_baz_degisim:+.2f}{C_RESET}")
    print(f"{C_MAGENTA}├────────────────────────────────────────────────────────────────────────┤{C_RESET}")
    print(f"  {C_GREEN}{C_BOLD}🚀 İYİMSER SENARYO (Boğa Piyasası):{C_RESET}")
    print(f"    Olası Maksimum Kâr     : {C_GREEN}{C_BOLD}%{tahmini_kar_orani:+.2f}{C_RESET}")
    print(f"    Vade Sonu Tahmini Para : {C_GREEN}{C_BOLD}{iyimser_bakiye:,.2f} TL{C_RESET}")
    print(f"  {C_RED}{C_BOLD}💥 KÖTÜMSER SENARYO (Ayı Piyasası):{C_RESET}")
    print(f"    Olası Maksimum Zarar   : {C_RED}{C_BOLD}%{tahmini_zarar_orani:+.2f}{C_RESET}")
    print(f"    Vade Sonu Tahmini Para : {C_RED}{C_BOLD}{kotumser_bakiye:,.2f} TL{C_RESET}")
    print(f"{C_MAGENTA}└────────────────────────────────────────────────────────────────────────┘{C_RESET}")


def matematiksel_analiz(secilen_sembol, isim, engine):
    print(f"\n{C_CYAN}[+] {isim} ({secilen_sembol}) siber tünel üzerinden indiriliyor...{C_RESET}")
    
    gercek_sorgu = "GC=F" if secilen_sembol == "GRAM_ALTIN" else secilen_sembol
    hedef_df = engine.veri_indir(gercek_sorgu)
    if hedef_df.empty:
        print(f"{C_RED}[-] HATA: Veri akışı sağlanamadı!{C_RESET}")
        return
        
    usd_df = engine.veri_indir("USDTRY=X")
    eur_df = engine.veri_indir("EURTRY=X")
    gbp_df = engine.veri_indir("GBPTRY=X")
    
    usd_guncel = float(usd_df['Close'].iloc[-1]) if not usd_df.empty else 34.35
    eur_guncel = float(eur_df['Close'].iloc[-1]) if not eur_df.empty else 35.85
    gbp_guncel = float(gbp_df['Close'].iloc[-1]) if not gbp_df.empty else 43.15
    
    close_data = pd.DataFrame(index=hedef_df.index)
    yabanci_varliklar = ["GC=F", "SI=F", "BZ=F", "BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD", "XRP-USD", "AAPL", "TSLA", "NVDA", "MSFT", "AMZN"]
    ONS_TO_GRAM = 31.1034768
    
    if secilen_sembol == "GRAM_ALTIN":
        if not usd_df.empty:
            hizalanmis_usd = usd_df['Close'].reindex(hedef_df.index, method='ffill').bfill()
            close_data['HEDEF'] = (hedef_df['Close'] / ONS_TO_GRAM) * hizalanmis_usd
            hedef_df['High'] = (hedef_df['High'] / ONS_TO_GRAM) * hizalanmis_usd
            hedef_df['Low'] = (hedef_df['Low'] / ONS_TO_GRAM) * hizalanmis_usd
        else:
            close_data['HEDEF'] = (hedef_df['Close'] / ONS_TO_GRAM) * usd_guncel
            hedef_df['High'] = (hedef_df['High'] / ONS_TO_GRAM) * usd_guncel
            hedef_df['Low'] = (hedef_df['Low'] / ONS_TO_GRAM) * usd_guncel
        carpan = 1.0
    elif secilen_sembol in yabanci_varliklar:
        if not usd_df.empty:
            hizalanmis_usd = usd_df['Close'].reindex(hedef_df.index, method='ffill').bfill()
            close_data['HEDEF'] = hedef_df['Close'] * hizalanmis_usd
        else:
            close_data['HEDEF'] = hedef_df['Close'] * usd_guncel
        carpan = usd_guncel
    else:
        close_data['HEDEF'] = hedef_df['Close']
        carpan = 1.0
    
    close_data['USD'] = usd_df['Close'] if not usd_df.empty else usd_guncel
    close_data['EUR'] = eur_df['Close'] if not eur_df.empty else eur_guncel
    close_data['GBP'] = gbp_df['Close'] if not gbp_df.empty else gbp_guncel
    close_data = close_data.ffill().bfill().dropna()
    
    if len(close_data) < 15: return

    guncel_tl = float(close_data['HEDEF'].iloc[-1])
    
    # 10 Yıllık Makro Döngü
    close_data['Kuresel_Sepet_TL'] = (close_data['USD'] * 0.50) + (close_data['EUR'] * 0.35) + (close_data['GBP'] * 0.15)
    close_data['VARLIK_KURESEL'] = close_data['HEDEF'] / close_data['Kuresel_Sepet_TL']
    close_data['Zaman'] = np.arange(len(close_data))
    
    log_fiyat = np.log(close_data['VARLIK_KURESEL'].values.flatten())
    zaman_serisi = close_data['Zaman'].values
    m, c = np.polyfit(zaman_serisi, log_fiyat, 1)
    
    ideal_log_guncel = m * zaman_serisi[-1] + c
    ideal_kuresel_guncel = np.exp(ideal_log_guncel)
    guncel_sepet = float(close_data['Kuresel_Sepet_TL'].iloc[-1])
    
    hata_serisi = log_fiyat - (m * zaman_serisi + c)
    standart_sapma = np.std(hata_serisi)
    guncel_kuresel = float(close_data['VARLIK_KURESEL'].iloc[-1])
    z_skoru = (np.log(guncel_kuresel) - np.log(ideal_kuresel_guncel)) / standart_sapma
    uzun_vade_denge = ideal_kuresel_guncel * guncel_sepet
    
    # 2 Haftalık Grafik
    kisa_vade_data = close_data.tail(14).copy()
    delta = close_data['HEDEF'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi_serisi = 100 - (100 / (1 + (gain / loss)))
    guncel_rsi = float(rsi_serisi.iloc[-1]) if not rsi_serisi.dropna().empty else 50.0
    iki_haftalik_degisim = ((guncel_tl - float(kisa_vade_data['HEDEF'].iloc[0])) / float(kisa_vade_data['HEDEF'].iloc[0])) * 100
    
    if secilen_sembol != "GRAM_ALTIN":
        high_target = (hedef_df['High'] * carpan).tail(14).dropna()
        low_target = (hedef_df['Low'] * carpan).tail(14).dropna()
    else:
        high_target = hedef_df['High'].tail(14).dropna()
        low_target = hedef_df['Low'].tail(14).dropna()
        
    en_yuksek_direnc = float(high_target.max()) if not high_target.empty else guncel_tl
    en_dusuk_destek = float(low_target.min()) if not low_target.empty else guncel_tl
    gunluk_dalga = ((high_target - low_target) / kisa_vade_data['HEDEF']) * 100 if not high_target.empty else pd.Series([2.0])
    ortalama_oynaklik = float(gunluk_dalga.mean())
    
    print(f"\n{C_MAGENTA}{'='*60}{C_RESET}")
    print(f"   {C_BOLD}{C_WHITE}{isim.upper()} DERİN DÖNGÜ ANALİZ RAPORU (TL BAZLI){C_RESET}")
    print(f"{C_MAGENTA}{'='*60}{C_RESET}")
    print(f"{C_WHITE}Anlık Fiyat  : {C_BOLD}{guncel_tl:,.2f} TL{C_RESET} | 2 Haftalık Değişim: {C_CYAN}%{iki_haftalik_degisim:+.2f}{C_RESET}")
    print(f"{C_WHITE}10Y Döngü (Z): {C_YELLOW}{z_skoru:.2f}{C_RESET}     | 2 Haftalık RSI    : {C_YELLOW}{guncel_rsi:.2f}{C_RESET}")
    print(f"{C_MAGENTA}{'-'*60}{C_RESET}")
    print(f"  ⚪ Adil Denge Değeri (Z=0.0):     {uzun_vade_denge:,.2f} TL{C_RESET}")
    print(f"  👉 14G Grafik : 14 Günlük En Yüksek/Düşük: {C_WHITE}{en_yuksek_direnc:,.2f} / {en_dusuk_destek:,.2f} TL{C_RESET}")
    print(f"{C_MAGENTA}{'='*60}{C_RESET}\n")

    sim_onay = input(f"{C_YELLOW}{C_BOLD}[?] Bu varlık için Kişisel Yatırım ve Risk Simülasyonu yapmak ister misiniz? (E/H): {C_RESET}").strip().upper()
    if sim_onay == "E":
        portfoy_simulasyonu(guncel_tl, z_skoru, guncel_rsi, ortalama_oynaklik, m)


def menu():
    engine = YahooBypassEngine()
    
    # Arka plan motoru daemon thread olarak başlar
    t = threading.Thread(target=alarm_takip_motoru, daemon=True)
    t.start()
    
    varliklar = {
        "GRAM_ALTIN": ("GRAM_ALTIN", "Gram Altın"), "GOLD": ("GC=F", "Ons Altın"), 
        "SILVER": ("SI=F", "Ons Gümüş"), "BRENT": ("BZ=F", "Brent Petrol"),
        "BTC": ("BTC-USD", "Bitcoin"), "ETH": ("ETH-USD", "Ethereum"), "SOL": ("SOL-USD", "Solana"), "AVAX": ("AVAX-USD", "Avalanax"), "XRP": ("XRP-USD", "Ripple"),
        "THYAO": ("THYAO.IS", "Türk Hava Yolları"), "PGSUS": ("PGSUS.IS", "Pegasus"), "DOAS": ("DOAS.IS", "Doğuş Otomotiv"), "FROTO": ("FROTO.IS", "Ford Otosan"), "TOASO": ("TOASO.IS", "Tofaş"),
        "AKBNK": ("AKBNK.IS", "Akbank"), "GARAN": ("GARAN.IS", "Garanti Bankası"), "ISCTR": ("ISCTR.IS", "İş Bankası C"), "YKBNK": ("YKBNK.IS", "Yapı Kredi"),
        "EREGL": ("EREGL.IS", "Ereğli Demir Çelik"), "KRDMD": ("KRDMD.IS", "Kardemir D"), "KCHOL": ("KCHOL.IS", "Koç Holding"), "SAHOL": ("SAHOL.IS", "Sabancı Holding"),
        "TUPRS": ("TUPRS.IS", "Tüpraş"), "SASA": ("SASA.IS", "Sasa Polyester"), "HEKTS": ("HEKTS.IS", "Hektaş"), "ENJSA": ("ENJSA.IS", "Enerjisa"), "ASTOR": ("ASTOR.IS", "Astor Enerji"),
        "ASELS": ("ASELS.IS", "Aselsan"), "TCELL": ("TCELL.IS", "Turkcell"), "TTKOM": ("TTKOM.IS", "Türk Telekom"),
        "BIMAS": ("BIMAS.IS", "BİM Mağazalar"), "MGROS": ("MGROS.IS", "Migros"), "CCOLA": ("CCOLA.IS", "Coca-Cola İçecek"),
        "AAPL": ("AAPL", "Apple Inc."), "TSLA": ("TSLA", "Tesla Inc."), "NVDA": ("NVDA", "NVIDIA Corp."), "MSFT": ("MSFT", "Microsoft"), "AMZN": ("AMZN", "Amazon")
    }

    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        
        print(f"{C_GREEN}{C_BOLD}")
        print("██████╗ ███████╗ █████╗ ██╗     ██╗    ██╗██╗  ██╗██╗████████╗███████╗")
        print("██╔══██╗██╔════╝██╔══██╗██║     ██║    ██║██║  ██║██║╚══██╔══╝██╔════╝")
        print("██████╔╝█████╗  ███████║██║     ██║ █╗ ██║███████║██║   ██║   █████╗  ")
        print("██╔══██╗██╔══╝  ██╔══██║██║     ██║███╗██║██╔══██║██║   ██║   ██╔══╝  ")
        print("██║  ██║███████╗██║  ██║███████╗╚███╔███╔╝██║  ██║██║   ██║   ███████╗")
        print("╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝ ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝   ╚═╝   ╚══════╝")
        print("    [+] SECURITY EXPLOIT & QUANTITATIVE ALGORITHMIC TRADING SYSTEM    ")
        print(f"    [+] CODENAME: {C_RED}realwhitehathacker12{C_GREEN} | SYSTEM ACTIVE    {C_RESET}")
        
        print(f"{C_MAGENTA}╔════════════════════════════════════════════════════════════════════════╗{C_RESET}")
        print(f"{C_MAGENTA}║                       {C_WHITE}{C_BOLD}MATRIX QUANT BORSA BOTU v5.5{C_RESET}{C_MAGENTA}                      ║{C_RESET}")
        print(f"{C_MAGENTA}╚════════════════════════════════════════════════════════════════════════╝{C_RESET}")
        
        print(f" {C_BLUE}[ KATEGORİLER VE ENTEGRE EDİLMİŞ ONLARCA HAZIR VARLIK ]{C_RESET}")
        print(f" {C_CYAN}🌟 Altın Piyasası : {C_WHITE}GRAM_ALTIN, GOLD (Ons Altın){C_RESET}")
        print(f" {C_CYAN}⚡ Kripto Paralar : {C_WHITE}BTC, ETH, SOL, AVAX, XRP{C_RESET}")
        print(f" {C_CYAN}💰 Emtia & Metal  : {C_WHITE}SILVER, BRENT{C_RESET}")
        print(f" {C_CYAN}✈️ Havacılık/Oto  : {C_WHITE}THYAO, PGSUS, FROTO, TOASO, DOAS{C_RESET}")
        print(f" {C_CYAN}🏦 Bankacılık     : {C_WHITE}AKBNK, GARAN, ISCTR, YKBNK{C_RESET}")
        print(f" {C_CYAN}🏭 Sanayi & Devler: {C_WHITE}EREGL, KRDMD, KCHOL, SAHOL, TUPRS{C_RESET}")
        print(f" {C_CYAN}🔥 Enerji & Kimya : {C_WHITE}SASA, HEKTS, ENJSA, ASTOR, ASELS{C_RESET}")
        print(f" {C_CYAN}📱 Gıda & İletişim: {C_WHITE}TCELL, TTKOM, BIMAS, MGROS, CCOLA{C_RESET}")
        print(f" {C_CYAN}🇺🇸 ABD Teknoloji  : {C_WHITE}AAPL, TSLA, NVDA, MSFT, AMZN{C_RESET}")
        print(f"{C_MAGENTA}──────────────────────────────────────────────────────────────────────────{C_RESET}")
        print(f" {C_YELLOW}💡 TELEGRAM ENTEGRASYONU İÇİN:{C_RESET} Terminale {C_BOLD}'TELEGRAM'{C_RESET} yazıp Enter'a basın.")
        print(f" {C_RED}❌ ÇIKIŞ YAPMAK İÇİN:{C_RESET} {C_BOLD}'CIKIS'{C_RESET} yazıp Enter'a basın.")
        print(f"{C_MAGENTA}──────────────────────────────────────────────────────────────────────────{C_RESET}")
        
        girdi = input(f"{C_GREEN}{C_BOLD}realwhitehathacker12@quant_bot:~# {C_RESET}").strip()
        
        if girdi.upper() == "CIKIS":
            print(f"\n{C_RED}[!] Siber Borsa Ajanı Devre Dışı Bırakıldı. Güvenli Çıkış Yapıldı.{C_RESET}")
            break
        if not girdi:
            continue
            
        if girdi.upper() == "TELEGRAM":
            telegram_alt_panel(varliklar, engine)
            continue
            
        girdi_upper = girdi.upper()
        if girdi_upper in varliklar:
            yahoo_kod, meta_isim = varliklar[girdi_upper]
        else:
            if not girdi_upper.endswith(".IS") and "-" not in girdi_upper and "=" not in girdi_upper:
                yahoo_kod, meta_isim = f"{girdi_upper}.IS", f"BIST: {girdi_upper}"
            else:
                yahoo_kod, meta_isim = girdi_upper, f"Özel Varlık ({girdi_upper})"
                
        matematiksel_analiz(yahoo_kod, meta_isim, engine)
        input(f"\n{C_CYAN}🔄 Yeniden Matrix Paneline dönmek için [Enter]'a basın...{C_RESET}")

if __name__ == "__main__":
    menu()
