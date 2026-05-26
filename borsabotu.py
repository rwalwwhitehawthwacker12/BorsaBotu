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
TELEGRAM_BOT_TOKEN = None
TELEGRAM_CHAT_ID = None
aktif_alarmlar = {}  
son_update_id = 0  

# Hazır varlık listesi (Eksiksiz 35 Varlık)
varliklar_global = {
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
                if res.status_code != 200: return pd.DataFrame()
            data = res.json()
            result = data['chart']['result'][0]
            df = pd.DataFrame({
                'Close': result['indicators']['quote'][0]['close'],
                'High': result['indicators']['quote'][0]['high'],
                'Low': result['indicators']['quote'][0]['low']
            }, index=pd.to_datetime(result['timestamp'], unit='s'))
            df.index = df.index.date
            df = df.dropna(subset=['Close'])
            return df
        except Exception:
            return pd.DataFrame()


def telegram_mesaj_gonder(mesaj):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, json=payload, timeout=8)
        return res.status_code == 200
    except Exception:
        return False


def fiyat_hesapla_tl(yahoo_kod, engine):
    gercek_sorgu = "GC=F" if yahoo_kod == "GRAM_ALTIN" else yahoo_kod
    df = engine.veri_indir(gercek_sorgu, gun_sayisi=5)
    if df.empty: return None
    usd_df = engine.veri_indir("USDTRY=X", gun_sayisi=5)
    usd_guncel = float(usd_df['Close'].iloc[-1]) if not usd_df.empty else 34.35
    yabanci_varliklar = ["GC=F", "SI=F", "BZ=F", "BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD", "XRP-USD", "AAPL", "TSLA", "NVDA", "MSFT", "AMZN"]
    ham_fiyat = float(df['Close'].iloc[-1])
    if yahoo_kod == "GRAM_ALTIN": return (ham_fiyat / 31.1034768) * usd_guncel
    elif yahoo_kod in yabanci_varliklar: return ham_fiyat * usd_guncel
    else: return ham_fiyat


def arka_plan_siber_motor():
    global son_update_id, aktif_alarmlar
    engine_thread = YahooBypassEngine()
    
    while True:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            time.sleep(5)
            continue
            
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset={son_update_id}&timeout=5"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                updates = resp.json().get("result", [])
                for update in updates:
                    son_update_id = update["update_id"] + 1
                    message = update.get("message", {})
                    text = message.get("text", "").strip()
                    chat_id = str(message.get("chat", {}).get("id", ""))
                    
                    if chat_id != str(TELEGRAM_CHAT_ID): continue
                        
                    if text.startswith("/"):
                        parcalar = text.split()
                        komut = parcalar[0].lower()
                        
                        if komut in ["/help", "/yardim"]:
                            yardim_metni = (
                                "🛰️ *BorsaBotu C2 Komuta Kılavuzu*\n\n"
                                "Botu uzaktan yönetmek için aşağıdaki formatta komutlar gönderebilirsiniz:\n\n"
                                "1️⃣ `/durum` \n➔ Sistem ve aktif alarm sayılarını raporlar.\n\n"
                                "2️⃣ `/analiz <sembol>` \n➔ Varlığın anlık TL fiyatını sorgular.\n"
                                "💻 _Örnek:_ `/analiz btc` veya `/analiz thyao`\n\n"
                                "3️⃣ `/alarm <sembol> <alt_limit> <ust_limit>` \n➔ Uzaktan yeni alarm hattı kurar.\n"
                                "💻 _Örnek:_ `/alarm sol 4500 6500`\n"
                                "ℹ️ _Not:_ Limit istemediğiniz yere 0 yazın. (Örn sadece üst limit: `/alarm thyao 0 360`)\n\n"
                                "🚀 _Sistem realwhitehathacker12 için tetiktedir._"
                            )
                            telegram_mesaj_gonder(yardim_metni)
                        
                        elif komut == "/durum":
                            telegram_mesaj_gonder(f"🤖 *BorsaBotu C2 Sistemi Aktif*\n\n📡 Arka Plan İzleme Hattı: Çevrimiçi\n🔔 Aktif Alarm Sayısı: {len(aktif_alarmlar)}")
                        
                        elif komut == "/analiz" and len(parcalar) > 1:
                            hedef = parcalar[1].upper()
                            if hedef in varliklar_global: y_kod, m_isim = varliklar_global[hedef]
                            else: y_kod, m_isim = (f"{hedef}.IS", f"BIST: {hedef}") if not hedef.endswith(".IS") and "-" not in hedef else (hedef, f"Özel ({hedef})")
                            
                            fiyat = fiyat_hesapla_tl(y_kod, engine_thread)
                            if fiyat is None: telegram_mesaj_gonder(f"❌ `{hedef}` için veri akışı sağlanamadı.")
                            else: telegram_mesaj_gonder(f"📊 *Siber Analiz Raporu: {m_isim}*\n\n💵 Güncel Fiyat: {fiyat:,.2f} TL\n📈 Kaynak: Yahoo Finans")
                        
                        elif komut == "/alarm" and len(parcalar) > 3:
                            hedef = parcalar[1].upper()
                            try:
                                alt_l = float(parcalar[2]) if parcalar[2] != "0" else None
                                ust_l = float(parcalar[3]) if parcalar[3] != "0" else None
                                if hedef in varliklar_global: y_kod, m_isim = varliklar_global[hedef]
                                else: y_kod, m_isim = (f"{hedef}.IS", f"BIST: {hedef}") if not hedef.endswith(".IS") and "-" not in hedef else (hedef, f"Özel ({hedef})")
                                    
                                aktif_alarmlar[y_kod] = {"yahoo_kod": y_kod, "isim": m_isim, "alt_limit": alt_l, "ust_limit": ust_l}
                                telegram_mesaj_gonder(f"📌 *Uzaktan Alarm Kuruldu!*\nVarlık: {m_isim}\n📉 Alt: {alt_l if alt_l else 'Yok'} TL\n📈 Üst: {ust_l if ust_l else 'Yok'} TL")
                            except Exception:
                                telegram_mesaj_gonder("⚠️ Hata: Geçersiz alarm formatı. Kılavuz için `/help` yazın.")
        except Exception: pass

        if aktif_alarmlar:
            silinecekler = []
            for anahtar, alarm in list(aktif_alarmlar.items()):
                guncel_fiyat = fiyat_hesapla_tl(alarm["yahoo_kod"], engine_thread)
                if guncel_fiyat is None: continue
                if alarm["ust_limit"] and guncel_fiyat >= alarm["ust_limit"]:
                    if telegram_mesaj_gonder(f"🔔 *[ALARM TETİKLENDİ - YÜKSELİŞ]*\n\n📈 *Varlık:* {alarm['isim']}\n💵 *Güncel Fiyat:* {guncel_fiyat:,.2f} TL\n🎯 *Hedef Üst Limit:* {alarm['ust_limit']:,.2f} TL"): silinecekler.append(anahtar)
                elif alarm["alt_limit"] and guncel_fiyat <= alarm["alt_limit"]:
                    if telegram_mesaj_gonder(f"🚨 *[ALARM TETİKLENDİ - DÜŞÜŞ]*\n\n📉 *Varlık:* {alarm['isim']}\n💵 *Güncel Fiyat:* {guncel_fiyat:,.2f} TL\n🎯 *Hedef Alt Limit:* {alarm['alt_limit']:,.2f} TL"): silinecekler.append(anahtar)
            for k in silinecekler:
                if k in aktif_alarmlar: del aktif_alarmlar[k]
        time.sleep(10)


def telegram_alt_panel(varliklar, engine):
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        print(f"{C_MAGENTA}╔════════════════════════════════════════════════════════════════════════╗{C_RESET}")
        print(f"{C_MAGENTA}║               🛰️  TELEGRAM ÇİFT YÖNLÜ C2 KOMUTA MERKEZİ [v7.2]        ║{C_RESET}")
        print(f"{C_MAGENTA}╚════════════════════════════════════════════════════════════════════════╝{C_RESET}")
        print(f"    ➔ Token  : {C_GREEN if TELEGRAM_BOT_TOKEN else C_RED}{TELEGRAM_BOT_TOKEN if TELEGRAM_BOT_TOKEN else 'GİRİLMEDİ'}{C_RESET}")
        print(f"    ➔ Chat ID: {C_GREEN if TELEGRAM_CHAT_ID else C_RED}{TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else 'GİRİLMEDİ'}{C_RESET}")
        print(f"    ➔ Alarmlar: {C_YELLOW}{len(aktif_alarmlar)} aktif takip{C_RESET} | C2 Dinleyici: {C_GREEN}AKTİF{C_RESET}\n")
        print(f" {C_BLUE}[ SEÇENEKLER ]{C_RESET}")
        print(f"   {C_GREEN}[1]{C_RESET} Bot Token Gir / Güncelle")
        print(f"   {C_GREEN}[2]{C_RESET} Chat ID Gir / Güncelle")
        print(f"   {C_GREEN}[3]{C_RESET} Terminalden Manuel Alarm Kur")
        print(f"   {C_GREEN}[4]{C_RESET} Aktif Alarmları Listele / Temizle")
        print(f"   {C_RED}[G]{C_RESET} Ana Menüye Geri Dön")
        print(f"{C_MAGENTA}──────────────────────────────────────────────────────────────────────────{C_RESET}")
        
        secim = input(f"{C_MAGENTA}{C_BOLD}telegram_subsystem# {C_RESET}").strip().upper()
        if secim == "G": break
        elif secim == "1":
            token_girdi = input(f"\n{C_WHITE}👉 Telegram Bot Tokeninizi Girin: {C_RESET}").strip()
            if token_girdi: TELEGRAM_BOT_TOKEN = token_girdi
        elif secim == "2":
            id_girdi = input(f"\n{C_WHITE}👉 Telegram Chat ID'nizi Girin: {C_RESET}").strip()
            if id_girdi:
                TELEGRAM_CHAT_ID = id_girdi
                telegram_mesaj_gonder("🚀 *BorsaBotu Çift Yönlü Komuta Hattı Başarıyla İnşa Edildi!*\n\n📱 Komut Listesi İçin Bota Yazın:\n👉 `/help` veya `/yardim`")
        elif secim == "3":
            if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
                print(f"{C_RED}[-] Önce bağlantı bilgilerini tanımlayın!{C_RESET}"); time.sleep(1.5); continue
            girdi = input(f"\n {C_WHITE}👉 Alarm kodu (Örn: BTC, GRAM_ALTIN, THYAO): {C_RESET}").strip().upper()
            if not girdi: continue
            y_kod, m_isim = varliklar[girdi] if girdi in varliklar else ((f"{girdi}.IS", f"BIST: {girdi}") if not girdi.endswith(".IS") and "-" not in girdi else (girdi, f"Özel ({girdi})"))
            mevcut_fiyat = fiyat_hesapla_tl(y_kod, engine)
            if mevcut_fiyat is None: print(f"{C_RED}[-] Veri çekilemedi.{C_RESET}"); time.sleep(1.5); continue
            print(f"{C_GREEN}[+] Anlık Fiyat: {mevcut_fiyat:,.2f} TL{C_RESET}")
            try:
                alt_girdi = input(f" 📉 Alt Limit [Yoksa Enter]: {C_RESET}").strip()
                alt_limit = float(alt_girdi) if alt_girdi else None
                ust_girdi = input(f" 📈 Üst Limit [Yoksa Enter]: {C_RESET}").strip()
                ust_limit = float(ust_girdi) if ust_girdi else None
            except ValueError: continue
            if alt_limit is None and ust_limit is None: continue
            aktif_alarmlar[y_kod] = {"yahoo_kod": y_kod, "isim": m_isim, "alt_limit": alt_limit, "ust_limit": ust_limit}
            telegram_mesaj_gonder(f"📌 *Takip Başlatıldı: {m_isim}*\n📉 Alt: {alt_limit}\n📈 Üst: {ust_limit}")
        elif secim == "4":
            print(f"\n{C_CYAN}── AKTİF ALARMLAR LİSTESİ ──{C_RESET}")
            if not aktif_alarmlar: print(" Aktif alarm bulunmuyor.")
            else:
                for k, v in aktif_alarmlar.items(): print(f" ➔ {v['isim']} ({k}) -> Alt: {v['alt_limit']} TL | Üst: {v['ust_limit']} TL")
                if input(f"\n{C_RED} Tüm alarmları sıfırlamak ister misiniz? (E/H): {C_RESET}").strip().upper() == "E": aktif_alarmlar.clear()
            input(f"\nDevam etmek için [Enter]...")


def portfoy_simulasyonu(guncel_fiyat, z_skoru, rsi, gunluk_oynaklik, m_egim):
    print(f"\n{C_YELLOW}╔════════════════════════════════════════════════════════════════════════╗{C_RESET}")
    print(f"{C_YELLOW}║               💰 PORTFÖY RİSK & GELECEK TAHMİN SİMÜLATÖRÜ              ║{C_RESET}")
    print(f"{C_YELLOW}╚════════════════════════════════════════════════════════════════════════╝{C_RESET}")
    try:
        bakiye = float(input(f" {C_WHITE}👉 Toplam bütçe (TL): {C_RESET}"))
        vade = int(input(f" {C_WHITE}👉 Süre (Gün): {C_RESET}"))
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
    print(f"  {C_WHITE}İlk Yatırılan Ana Para : {C_BOLD}{bakiye:,.2f} TL{C_RESET}\n  {C_WHITE}Pazar Trend Eğilimi    : {C_CYAN}%{beklenen_baz_degisim:+.2f}{C_RESET}")
    print(f"  {C_GREEN}🚀 İYİMSER (Boğa): %{tahmini_kar_orani:+.2f} -> {iyimser_bakiye:,.2f} TL{C_RESET}")
    print(f"  {C_RED}💥 KÖTÜMSER (Ayı): %{tahmini_zarar_orani:+.2f} -> {kotumser_bakiye:,.2f} TL{C_RESET}")
    print(f"{C_MAGENTA}└────────────────────────────────────────────────────────────────────────┘{C_RESET}")


def matematiksel_analiz(secilen_sembol, isim, engine):
    print(f"\n{C_CYAN}[+] {isim} verileri indiriliyor...{C_RESET}")
    gercek_sorgu = "GC=F" if secilen_sembol == "GRAM_ALTIN" else secilen_sembol
    hedef_df = engine.veri_indir(gercek_sorgu)
    if hedef_df.empty: return
    usd_df = engine.veri_indir("USDTRY=X")
    eur_df = engine.veri_indir("EURTRY=X")
    gbp_df = engine.veri_indir("GBPTRY=X")
    usd_guncel = float(usd_df['Close'].iloc[-1]) if not usd_df.empty else 34.35
    close_data = pd.DataFrame(index=hedef_df.index)
    yabanci_varliklar = ["GC=F", "SI=F", "BZ=F", "BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD", "XRP-USD", "AAPL", "TSLA", "NVDA", "MSFT", "AMZN"]
    if secilen_sembol == "GRAM_ALTIN":
        hizalanmis_usd = usd_df['Close'].reindex(hedef_df.index, method='ffill').bfill() if not usd_df.empty else usd_guncel
        close_data['HEDEF'] = (hedef_df['Close'] / 31.1034768) * hizalanmis_usd
        hedef_df['High'] = (hedef_df['High'] / 31.1034768) * hizalanmis_usd
        hedef_df['Low'] = (hedef_df['Low'] / 31.1034768) * hizalanmis_usd
        carpan = 1.0
    elif secilen_sembol in yabanci_varliklar:
        hizalanmis_usd = usd_df['Close'].reindex(hedef_df.index, method='ffill').bfill() if not usd_df.empty else usd_guncel
        close_data['HEDEF'] = hedef_df['Close'] * hizalanmis_usd
        carpan = usd_guncel
    else:
        close_data['HEDEF'] = hedef_df['Close']
        carpan = 1.0
    close_data['USD'] = usd_df['Close'] if not usd_df.empty else usd_guncel
    close_data['EUR'] = eur_df['Close'] if not eur_df.empty else 35.85
    close_data['GBP'] = gbp_df['Close'] if not gbp_df.empty else 43.15
    close_data = close_data.ffill().bfill().dropna()
    if len(close_data) < 15: return
    guncel_tl = float(close_data['HEDEF'].iloc[-1])
    close_data['Kuresel_Sepet_TL'] = (close_data['USD'] * 0.50) + (close_data['EUR'] * 0.35) + (close_data['GBP'] * 0.15)
    close_data['VARLIK_KURESEL'] = close_data['HEDEF'] / close_data['Kuresel_Sepet_TL']
    close_data['Zaman'] = np.arange(len(close_data))
    log_fiyat = np.log(close_data['VARLIK_KURESEL'].values.flatten())
    m, c = np.polyfit(close_data['Zaman'].values, log_fiyat, 1)
    uzun_vade_denge = np.exp(m * close_data['Zaman'].values[-1] + c) * float(close_data['Kuresel_Sepet_TL'].iloc[-1])
    z_skoru = (np.log(float(close_data['VARLIK_KURESEL'].iloc[-1])) - (m * close_data['Zaman'].values[-1] + c)) / np.std(log_fiyat - (m * close_data['Zaman'].values + c))
    kisa_vade_data = close_data.tail(14).copy()
    delta = close_data['HEDEF'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    guncel_rsi = float((100 - (100 / (1 + (gain / loss)))).iloc[-1]) if not (gain/loss).dropna().empty else 50.0
    iki_haftalik_degisim = ((guncel_tl - float(kisa_vade_data['HEDEF'].iloc[0])) / float(kisa_vade_data['HEDEF'].iloc[0])) * 100
    high_target = (hedef_df['High'] * (1.0 if secilen_sembol == "GRAM_ALTIN" else carpan)).tail(14).dropna()
    low_target = (hedef_df['Low'] * (1.0 if secilen_sembol == "GRAM_ALTIN" else carpan)).tail(14).dropna()
    print(f"\n{C_MAGENTA}{'='*60}\n   {C_BOLD}{C_WHITE}{isim.upper()} ANALİZ RAPORU\n{'='*60}{C_RESET}")
    print(f"{C_WHITE}Anlık Fiyat  : {C_BOLD}{guncel_tl:,.2f} TL{C_RESET} | Değişim: {C_CYAN}%{iki_haftalik_degisim:+.2f}{C_RESET}")
    print(f"{C_WHITE}10Y Döngü (Z): {C_YELLOW}{z_skoru:.2f}{C_RESET}     | RSI    : {C_YELLOW}{guncel_rsi:.2f}{C_RESET}")
    print(f"  ⚪ Adil Denge Değeri (Z=0.0):     {uzun_vade_denge:,.2f} TL")
    print(f"  👉 14G Grafik : En Yüksek: {high_target.max():,.2f} / En Düşük: {low_target.min():,.2f} TL\n{C_MAGENTA}{'='*60}{C_RESET}")
    if input(f"{C_YELLOW}[?] Simülasyon yapmak ister misiniz? (E/H): {C_RESET}").strip().upper() == "E":
        portfoy_simulasyonu(guncel_tl, z_skoru, guncel_rsi, float(((high_target - low_target) / kisa_vade_data['HEDEF']).mean()), m)


def menu():
    engine = YahooBypassEngine()
    t = threading.Thread(target=arka_plan_siber_motor, daemon=True)
    t.start()
    
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
        print(f"    [+] CODENAME: {C_RED}realwhitehathacker12{C_GREEN} | C2 SERVER ACTIVE  {C_RESET}")
        print(f"{C_MAGENTA}╔════════════════════════════════════════════════════════════════════════╗{C_RESET}")
        print(f"{C_MAGENTA}║                       {C_WHITE}{C_BOLD}MATRIX QUANT BORSA BOTU v7.2{C_RESET}{C_MAGENTA}                      ║{C_RESET}")
        print(f"{C_MAGENTA}╚════════════════════════════════════════════════════════════════════════╝{C_RESET}")
        
        # --- ARAYÜZE TÜM VARLIKLARIN EKSİKSİZ BASILMASI ---
        print(f" {C_BLUE}[ 🏅 EMTİA VE DEĞERLİ METALLER ]{C_RESET}")
        print(f"   GRAM_ALTIN | GOLD | SILVER | BRENT")
        print(f" ──────────────────────────────────────────────────────────────────────────")
        print(f" {C_BLUE}[ 🌟 KRİPTO PARA BİRİMLERİ ]{C_RESET}")
        print(f"   BTC | ETH | SOL | AVAX | XRP")
        print(f" ──────────────────────────────────────────────────────────────────────────")
        print(f" {C_BLUE}[ 🏭 BIST - SANAYİ, ULAŞIM VE HOLDİNG DEVLERİ ]{C_RESET}")
        print(f"   THYAO | PGSUS | DOAS  | FROTO | TOASO | AKBNK | GARAN | ISCTR | YKBNK")
        print(f"   EREGL | KRDMD | KCHOL | SAHOL | TUPRS | SASA  | HEKTS | ENJSA | ASTOR")
        print(f"   ASELS | TCELL | TTKOM | BIMAS | MGROS | CCOLA")
        print(f" ──────────────────────────────────────────────────────────────────────────")
        print(f" {C_BLUE}[ 🇺🇸 ABD TEKNOLOJİ DEVLERİ ]{C_RESET}")
        print(f"   AAPL | TSLA | NVDA | MSFT | AMZN")
        
        print(f"{C_MAGENTA}──────────────────────────────────────────────────────────────────────────{C_RESET}")
        print(f" {C_YELLOW}💡 TELEGRAM ENTEGRASYONU İÇİN:{C_RESET} Terminale {C_BOLD}'TELEGRAM'{C_RESET} yazıp Enter'a bakın.")
        print(f" {C_RED}❌ ÇIKIŞ YAPMAK İÇİN:{C_RESET} {C_BOLD}'CIKIS'{C_RESET} yazıp Enter'a basın.")
        print(f" {C_CYAN}ℹ️  LİSTEDE OLMAYAN VARLIKLAR İÇİN:{C_RESET} Doğrudan kodunu yazabilirsiniz (Örn: {C_BOLD}KOZAL{C_RESET})")
        print(f"{C_MAGENTA}──────────────────────────────────────────────────────────────────────────{C_RESET}")
        
        girdi = input(f"{C_GREEN}{C_BOLD}realwhitehathacker12@quant_bot:~# {C_RESET}").strip()
        if girdi.upper() == "CIKIS": break
        if not girdi: continue
        if girdi.upper() == "TELEGRAM":
            telegram_alt_panel(varliklar_global, engine)
            continue
            
        girdi_upper = girdi.upper()
        if girdi_upper in varliklar_global: yahoo_kod, meta_isim = varliklar_global[girdi_upper]
        else: yahoo_kod, meta_isim = (f"{girdi_upper}.IS", f"BIST: {girdi_upper}") if not girdi_upper.endswith(".IS") and "-" not in girdi_upper and "=" not in girdi_upper else (girdi_upper, f"Özel ({girdi_upper})")
                
        matematiksel_analiz(yahoo_kod, meta_isim, engine)
        input(f"\n{C_CYAN}🔄 Geri dönmek için [Enter]'a basın...{C_RESET}")

if __name__ == "__main__":
    menu()
