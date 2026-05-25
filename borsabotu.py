import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import requests
import time

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


def portfoy_simulasyonu(guncel_fiyat, z_skoru, rsi, gunluk_oynaklik, m_egim):
    """
    Kullanıcının girdiği vade ve sermayeye göre risk/getiri simülasyonu yapan yeni motor.
    """
    print(f"\n{C_YELLOW}╔════════════════════════════════════════════════════════════════════════╗{C_RESET}")
    print(f"{C_YELLOW}║               💰 PORTFÖY RİSK & GELECEK TAHMİN SİMÜLATÖRÜ              ║{C_RESET}")
    print(f"{C_YELLOW}╚════════════════════════════════════════════════════════════════════════╝{C_RESET}")
    
    try:
        bakiye = float(input(f" {C_WHITE}👉 Bu varlığa yatıracağınız toplam bütçe (TL): {C_RESET}"))
        vade = int(input(f" {C_WHITE}👉 Elinizde tutacağınız yaklaşık süre (Gün): {C_RESET}"))
        if bakiye <= 0 or vade <= 0:
            print(f"{C_RED}[-] HATA: Geçersiz bütçe veya vade süresi!{C_RESET}")
            return
    except ValueError:
        print(f"{C_RED}[-] HATA: Lütfen sadece sayısal değerler girin!{C_RESET}")
        return

    print(f"\n{C_CYAN}[+] Kuantum olasılık matrisleri ve trend eğimleri hesaplanıyor...{C_RESET}")
    time.sleep(1)

    # Matematiksel Simülasyon Ağırlıkları
    # m_egim logaritmiktir, günlük ortalama logaritmik büyümeyi temsil eder.
    trend_etkisi = m_egim * vade * 100  # Vadeye yayılmış makro yön
    
    # RSI ve Z-Skoru uç noktalarındaysa düzeltme (mean-reversion) çarpanı ekleyelim
    duzeltme_etkisi = 0.0
    if z_skoru > 1.0: duzeltme_etkisi -= (z_skoru * 1.5)  # Aşırı pahalıysa aşağı baskı
    if z_skoru < -1.0: duzeltme_etkisi += (abs(z_skoru) * 2.0) # Aşırı ucuzsa yukarı destek
    if rsi > 75: duzeltme_etkisi -= 2.0
    if rsi < 25: duzeltme_etkisi += 2.5

    # Beklenen baz getiri yüzdesi (Makro + Mikro birleşik eğilim)
    beklenen_baz_degisim = trend_etkisi + duzeltme_etkisi
    
    # Vade uzadıkça oynaklığın (risk marjının) karekök zaman yasasına göre genişlemesi
    toplam_oynaklik_marji = gunluk_oynaklik * np.sqrt(vade) * 1.5

    # İyimser ve Kötümser senaryoların matematiksel tavan/taban sınırları
    tahmini_kar_orani = beklenen_baz_degisim + toplam_oynaklik_marji
    tahmini_zarar_orani = beklenen_baz_degisim - toplam_oynaklik_marji

    # Negatif kâr saçmalığını veya aşırı abartı durumları törpüleme (Siber Sigorta)
    if tahmini_zarar_orani < -90: tahmini_zarar_orani = -90.0

    iyimser_bakiye = bakiye * (1 + (tahmini_kar_orani / 100))
    kotumser_bakiye = bakiye * (1 + (tahmini_zarar_orani / 100))
    
    # Ekran Çıktısı Paneli
    print(f"\n{C_MAGENTA}┌────────────────────────────────────────────────────────────────────────┐{C_RESET}")
    print(f"│ {C_BOLD}{C_WHITE}📊 {vade} GÜNLÜK MATEMATİKSEL PROJEKSİYON SONUÇLARI{C_RESET}                          │")
    print(f"{C_MAGENTA}├────────────────────────────────────────────────────────────────────────┤{C_RESET}")
    print(f"  {C_WHITE}İlk Yatırılan Ana Para : {C_BOLD}{bakiye:,.2f} TL{C_RESET}")
    print(f"  {C_WHITE}Pazar Trend Eğilimi    : {C_CYAN}%{beklenen_baz_degisim:+.2f}{C_RESET}")
    print(f"{C_MAGENTA}├────────────────────────────────────────────────────────────────────────┤{C_RESET}")
    
    # İyimser Senaryo
    print(f"  {C_GREEN}{C_BOLD}🚀 İYİMSER SENARYO (Boğa Piyasası):{C_RESET}")
    print(f"    Olası Maksimum Kâr     : {C_GREEN}{C_BOLD}%{tahmini_kar_orani:+.2f}{C_RESET}")
    print(f"    Vade Sonu Tahmini Para : {C_GREEN}{C_BOLD}{iyimser_bakiye:,.2f} TL{C_RESET}")
    
    # Kötümser Senaryo
    print(f"  {C_RED}{C_BOLD}💥 KÖTÜMSER SENARYO (Ayı Piyasası):{C_RESET}")
    print(f"    Olası Maksimum Zarar   : {C_RED}{C_BOLD}%{tahmini_zarar_orani:+.2f}{C_RESET}")
    print(f"    Vade Sonu Tahmini Para : {C_RED}{C_BOLD}{kotumser_bakiye:,.2f} TL{C_RESET}")
    
    print(f"{C_MAGENTA}└────────────────────────────────────────────────────────────────────────┘{C_RESET}")
    
    # Siber Uyarı Notu
    print(f"{C_RED}{C_BOLD}⚠️  SİBER QUANT NOTU & YASAL UYARI:{C_RESET}")
    print(f" {C_YELLOW}Bu simülasyon; geçmiş 10 yıllık veri sapmaları (Z-skor), RSI momentumu ve")
    print(f" oynaklık (volatilite) algoritmaları kullanılarak olasılıksal hesaplanmıştır.")
    print(f" Finansal piyasalarda %100 kesinlik YOKTUR. Savaşlar, manipülasyonlar ve ani")
    print(f" makroekonomik krizler teknik hesaplamaları bozabilir. Asla tek başına yatırım")
    print(f" tavsiyesi olarak değerlendirilmemelidir! Pozisyon alırken riskinizi bölün.{C_RESET}\n")


def matematiksel_analiz(secilen_sembol, isim, engine):
    print(f"\n{C_CYAN}[+] {isim} ({secilen_sembol}) siber tünel üzerinden indiriliyor...{C_RESET}")
    
    hedef_df = engine.veri_indir(secilen_sembol)
    if hedef_df.empty:
        print(f"{C_RED}[-] HATA: Veri akışı sağlanamadı! Yahoo BIST blokajı devreye girdi.{C_RESET}")
        return
        
    print(f"{C_CYAN}[+] Küresel Para Sepeti entegre ediliyor...{C_RESET}")
    usd_df = engine.veri_indir("USDTRY=X")
    eur_df = engine.veri_indir("EURTRY=X")
    gbp_df = engine.veri_indir("GBPTRY=X")
    
    close_data = pd.DataFrame(index=hedef_df.index)
    close_data['HEDEF'] = hedef_df['Close']
    
    close_data['USD'] = usd_df['Close'] if not usd_df.empty else 34.35
    close_data['EUR'] = eur_df['Close'] if not eur_df.empty else 35.85
    close_data['GBP'] = gbp_df['Close'] if not gbp_df.empty else 43.15
    
    close_data = close_data.ffill().bfill().dropna()
    
    if len(close_data) < 15:
        print(f"{C_RED}[-] HATA: Teknik matris analizi için yetersiz veri noktası.{C_RESET}")
        return

    guncel_tl = float(close_data['HEDEF'].iloc[-1])
    
    # ── UZUN VADE (10 YILLIK MAKRO DÖNGÜ) ──
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
    uzun_vade_potansiyel = ((uzun_vade_denge - guncel_tl) / guncel_tl) * 100
    
    guclu_al_tl = np.exp(ideal_log_guncel - (1.2 * standart_sapma)) * guncel_sepet
    kademeli_al_tl = np.exp(ideal_log_guncel - (0.5 * standart_sapma)) * guncel_sepet
    kademeli_sat_tl = np.exp(ideal_log_guncel + (0.5 * standart_sapma)) * guncel_sepet
    guclu_sat_tl = np.exp(ideal_log_guncel + (1.2 * standart_sapma)) * guncel_sepet
    
    if z_skoru < -1.0:
        uzun_vade_kod = "AL"
        uzun_vade_sinyal = f"{C_GREEN}{C_BOLD}🔥 GÜÇLÜ AL (TARİHSEL BEDAVA BÖLGE){C_RESET}"
        uzun_vade_detay = "Varlık, küresel döviz sepetine oranla son 10 yılın en dip ve yıpranmış seviyesinde. Makro trend istatistiksel olarak tamamen alıcı lehine dönmüş durumda. Orta-uzun vadeli portföyler için matematiksel açıdan riskin minimum, kâr potansiyelinin maksimum olduğu altın fırsat dönemidir."
    elif -1.0 <= z_skoru < -0.3:
        uzun_vade_kod = "AL"
        uzun_vade_sinyal = f"{C_GREEN}🟢 KADEMELİ ALUM ALANI{C_RESET}"
        uzun_vade_detay = "Fiyat, 10 yıllık küresel büyüme kanalının ve tarihsel ortalamaların altında seyrediyor. Mevcut seviyeler uzun vadeli biriktirme stratejisi (dolar maliyet ortalaması) için gayet ucuz ve makul. Parçalı alımlarla maliyet düşürerek pozisyon büyütülebilir."
    elif -0.3 <= z_skoru <= 0.3:
        uzun_vade_kod = "NOTR"
        uzun_vade_sinyal = f"{C_WHITE}⚪ BEKLE / NÖTR (ADİL DEĞER BANDI){C_RESET}"
        uzun_vade_detay = "Fiyat, makro regresyon kanalının tam merkezinde oturuyor. Varlık ne aşırı primli ne de hak ettiğinden ucuz; tam olarak adil değerinde (Fair Value). Yeni büyük bir temel hikaye veya küresel nakit akışı tetiklenene kadar bu dengenin korunması beklenir."
    elif 0.3 < z_skoru <= 1.0:
        uzun_vade_kod = "SAT"
        uzun_vade_sinyal = f"{C_YELLOW}🟠 KADEMELİ SATIŞ / KÂR REALİZASYONU{C_RESET}"
        uzun_vade_detay = "Fiyat uzun vadeli büyüme trendinin üzerine taşmış durumda. İstatistiksel olarak aşırı coşku bölgesine yaklaşılıyor. Bu seviyelerden yeni alımlar yapmak matematiksel riski artırır; mevcut pozisyonlardan parça parça kâr alarak nakit oranını artırmak mantıklıdır."
    else:
        uzun_vade_kod = "SAT"
        uzun_vade_sinyal = f"{C_RED}{C_BOLD}🔴 GÜÇLÜ SAT (MAKRO BALON BÖLGESİ){C_RESET}"
        uzun_vade_detay = "Varlık, küresel para sepetine karşı son 10 yıllık döngünün en uç tepe noktasına (Z zirvesine) ulaşmış durumda. Matematiksel olarak aşırı şişmiş ve fiyatın tarihsel ortalamasına (regresyona) geri dönme riski çok yüksek. Akıllı para bu bölgede mal boşaltır, sert düzeltmelere karşı azami dikkat!"

    # ── KISA VADE (2 HAFTALIK MİKRO TREND) ──
    kisa_vade_data = close_data.tail(14).copy()
    delta = close_data['HEDEF'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi_serisi = 100 - (100 / (1 + (gain / loss)))
    guncel_rsi = float(rsi_serisi.iloc[-1]) if not rsi_serisi.dropna().empty else 50.0
    
    ilk_gun_fiyat = float(kisa_vade_data['HEDEF'].iloc[0])
    iki_haftalik_degisim = ((guncel_tl - ilk_gun_fiyat) / ilk_gun_fiyat) * 100
    
    high_target = hedef_df['High'].tail(14).dropna()
    low_target = hedef_df['Low'].tail(14).dropna()
    en_yuksek_direnc = float(high_target.max()) if not high_target.empty else guncel_tl
    en_dusuk_destek = float(low_target.min()) if not low_target.empty else guncel_tl
    
    gunluk_dalga = ((high_target - low_target) / kisa_vade_data['HEDEF']) * 100 if not high_target.empty else pd.Series([2.0])
    ortalama_oynaklik = float(gunluk_dalga.mean())
    
    if guncel_rsi < 30:
        kisa_vade_kod = "AL"
        kisa_vade_sinyal = f"{C_GREEN}{C_BOLD}🔥 KISA VADE: AŞIRI SATIMDAN TEPKİ ALIMI{C_RESET}"
        kisa_vade_detay = "Son 14 günlük periyotta çok agresif satılmış, teknik osilatörler (RSI) dipten sinyal veriyor. Kısa vadeli bir yukarı yönlü tepki yükselişi kapıda."
    elif 30 <= guncel_rsi < 45:
        kisa_vade_kod = "AL"
        kisa_vade_sinyal = f"{C_GREEN}🟢 KISA VADE: DESTEKTEN TEPKİ ALIMI{C_RESET}"
        kisa_vade_detay = "Fiyat kısa vadeli teknik destek seviyesine oldukça yakın seyrediyor. Satış baskısı azalmış, risk-ödül oranı kısa vadeli trade edenler için makul alım seviyelerine işaret ediyor."
    elif 45 <= guncel_rsi <= 65:
        kisa_vade_kod = "NOTR"
        kisa_vade_sinyal = f"{C_WHITE}⚪ KISA VADE: BEKLE / DENGELİ{C_RESET}"
        kisa_vade_detay = "2 haftalık grafik yatay ve kararsız bir konsolidasyon bandında. Net bir momentum veya kırılım yok, yönü görmek için izlemek daha güvenli."
    elif 65 < guncel_rsi <= 75:
        kisa_vade_kod = "SAT"
        kisa_vade_sinyal = f"{C_YELLOW}🟠 KISA VADE: DİRENÇTEN KÂR ALUM{C_RESET}"
        kisa_vade_detay = "Fiyat 14 günlük kanalın en üst direnç sınırına çarptı. RSI şişmeye başlıyor, buralardan kâr satışı yiyerek yerel bir geri çekilme yaşayabilir."
    else:
        kisa_vade_kod = "SAT"
        kisa_vade_sinyal = f"{C_RED}{C_BOLD}🔴 KISA VADE: AŞIRI ALUM (YÜKSEK RİSK){C_RESET}"
        kisa_vade_detay = "Kısa vadede çok çılgın bir momentum yakalamış, RSI 75 üzerine fırlamış durumda. Fiyat nefes tazelemek için her an sert bir düzeltme dalgası başlatabilir, korumasız girmek tehlikeli."

    # Sentez Döngüleri
    if uzun_vade_kod == "AL" and kisa_vade_kod == "AL":
        kombinasyon = f"{C_GREEN}{C_BOLD}🌟 KUSURSUZ ALUM DÖNGÜSÜ: Hem 10 yıllık makro kanalda tarihsel olarak ucuz/bedava seviyede, hem de 2 haftalık mikro grafikte dipten kalkıyor! Kaçırılmayacak pazar fırsatı.{C_RESET}"
    elif uzun_vade_kod == "SAT" and kisa_vade_kod == "SAT":
        kombinasyon = f"{C_RED}{C_BOLD}🚨 KUSURSUZ SATUM DÖNGÜSÜ: Hem uzun vadeli grafikte küresel balon bölgesinde hem de kısa vadede aşırı şişmiş! Derhal kar realizasyonu veya nakde geçiş düşünülmeli.{C_RESET}"
    elif uzun_vade_kod == "AL" and kisa_vade_kod == "SAT":
        kombinasyon = f"{C_CYAN}🔄 ÇELİŞKİLİ STRATEJİ (MAKRO UCUZ / MİKRO PAHALI): Varlık uzun vadede hala ucuz ve büyük potansiyel barındırıyor ancak son 2 haftada çok sert yükselmiş. Alım yapmak için kısa vadeli bu şişkinliğin (RSI) sönmesini ve yerel bir düzeltme yapmasını beklemek en akıllıca hamledir.{C_RESET}"
    elif uzun_vade_kod == "SAT" and kisa_vade_kod == "AL":
        kombinasyon = f"{C_YELLOW}⚠️ TEHLİKELİ TEPKİ OYNANIŞI (MAKRO BALON / MİKRO UCUZ): Varlık 10 yıllık döngüde zirvede (aşırı pahalı) ancak son 2 haftada çok sert düştüğü için anlık bir tepki yükselişi vermeye hazırlanıyor. Bu bölgeden alınacak mal sadece çok kısa vadeli 'vur-kaç' amaçlı trade edilebilir, asla uzun süre cüzdanda taşınmamalıdır!{C_RESET}"
    else:
        kombinasyon = f"{C_WHITE}⚪ DENGELİ PAZAR: Varlık şu an makro ve mikro dengede salınıyor. Büyük bir trend başlangıcı yok, yatay bant trade stratejisi uygulanabilir.{C_RESET}"

    # EKRAN ÇIKTISI
    print(f"\n{C_MAGENTA}{'='*60}{C_RESET}")
    print(f"   {C_BOLD}{C_WHITE}{isim.upper()} DERİN DÖNGÜ ANALİZ RAPORU{C_RESET}")
    print(f"{C_MAGENTA}{'='*60}{C_RESET}")
    print(f"{C_WHITE}Anlık Fiyat  : {C_BOLD}{guncel_tl:.2f} TL{C_RESET} | 2 Haftalık Değişim: {C_CYAN}%{iki_haftalik_degisim:+.2f}{C_RESET}")
    print(f"{C_WHITE}10Y Döngü (Z): {C_YELLOW}{z_skoru:.2f}{C_RESET}     | 2 Haftalık RSI    : {C_YELLOW}{guncel_rsi:.2f}{C_RESET}")
    print(f"{C_MAGENTA}{'-'*60}{C_RESET}")
    print(f"{C_BLUE}📊 MATEMATİKSEL KANAL SEVİYELERİ (TL):{C_RESET}")
    print(f"  {C_RED}🔴 Güçlü Satış Bölgesi (Z=+1.2): {guclu_sat_tl:.2f} TL{C_RESET}")
    print(f"  {C_YELLOW}🟠 Kademeli Satış Bölgesi (Z=+0.5): {kademeli_sat_tl:.2f} TL{C_RESET}")
    print(f"  {C_WHITE}⚪ Adil Denge Değeri (Z=0.0):     {uzun_vade_denge:.2f} TL{C_RESET}")
    print(f"  {C_YELLOW}🟡 Kademeli Alım Bölgesi (Z=-0.5):  {kademeli_al_tl:.2f} TL{C_RESET}")
    print(f"  {C_GREEN}🟢 Güçlü Alım Bölgesi (Z=-1.2):    {guclu_al_tl:.2f} TL{C_RESET}")
    print(f"{C_MAGENTA}{'-'*60}{C_RESET}")
    print(f"{C_BLUE}⏳ UZUN VADELİ MAKRO ANALİZ (10 Yıl):{C_RESET}")
    print(f"  👉 Sinyal : {uzun_vade_sinyal}")
    print(f"  👉 Mesafe : Adil Değere Uzaklık Potansiyeli -> {C_CYAN}%{uzun_vade_potansiyel:+.2f}{C_RESET}")
    print(f"  📝 Yorum  : {C_WHITE}{uzun_vade_detay}{C_RESET}")
    print(f"{C_MAGENTA}{'-'*60}{C_RESET}")
    print(f"{C_BLUE}⚡ KISA VADELİ MİKRO ANALİZ (2 Hafta):{C_RESET}")
    print(f"  👉 Sinyal : {kisa_vade_sinyal}")
    print(f"  👉 Grafik : 14 Günlük En Yüksek/Düşük: {C_WHITE}{en_yuksek_direnc:.2f} / {en_dusuk_destek:.2f} TL{C_RESET}")
    print(f"  👉 Tahmin : Olası 2 Günlük Dalgalanma Marjı: {C_CYAN}±%{ortalama_oynaklik:.2f}{C_RESET}")
    print(f"  📝 Yorum  : {C_WHITE}{kisa_vade_detay}{C_RESET}")
    print(f"{C_MAGENTA}{'='*60}{C_RESET}")
    print(f"🎯 {kombinasyon}")
    print(f"{C_MAGENTA}{'='*60}{C_RESET}\n")

    # Yeni Modülün Tetiklenmesi Sorusunu Soruyoruz
    sim_onay = input(f"{C_YELLOW}{C_BOLD}[?] Bu varlık için Kişisel Yatırım ve Risk Simülasyonu yapmak ister misiniz? (E/H): {C_RESET}").strip().upper()
    if sim_onay == "E":
        portfoy_simulasyonu(guncel_tl, z_skoru, guncel_rsi, ortalama_oynaklik, m)


def menu():
    engine = YahooBypassEngine()
    varliklar = {
        "BTC": ("BTC-USD", "Bitcoin"), "ETH": ("ETH-USD", "Ethereum"), "SOL": ("SOL-USD", "Solana"), "AVAX": ("AVAX-USD", "Avalanax"), "XRP": ("XRP-USD", "Ripple"),
        "GOLD": ("GC=F", "Ons Altın"), "SILVER": ("SI=F", "Ons Gümüş"), "BRENT": ("BZ=F", "Brent Petrol"),
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
        print(f"{C_MAGENTA}║                       {C_WHITE}{C_BOLD}MATRIX QUANT BORSA BOTU v5.0{C_RESET}{C_MAGENTA}                      ║{C_RESET}")
        print(f"{C_MAGENTA}╚════════════════════════════════════════════════════════════════════════╝{C_RESET}")
        
        print(f" {C_BLUE}[ KATEGORİLER VE ENTEGRE EDİLMİŞ ONLARCA HAZIR VARLIK ]{C_RESET}")
        print(f" {C_CYAN}⚡ Kripto Paralar : {C_WHITE}BTC, ETH, SOL, AVAX, XRP{C_RESET}")
        print(f" {C_CYAN}💰 Emtia & Metal  : {C_WHITE}GOLD (Altın), SILVER (Gümüş), BRENT (Petrol){C_RESET}")
        print(f" {C_CYAN}✈️ Havacılık/Oto  : {C_WHITE}THYAO, PGSUS, FROTO, TOASO, DOAS{C_RESET}")
        print(f" {C_CYAN}🏦 Bankacılık     : {C_WHITE}AKBNK, GARAN, ISCTR, YKBNK{C_RESET}")
        print(f" {C_CYAN}🏭 Sanayi & Devler: {C_WHITE}EREGL, KRDMD, KCHOL, SAHOL, TUPRS{C_RESET}")
        print(f" {C_CYAN}🔥 Enerji & Kimya : {C_WHITE}SASA, HEKTS, ENJSA, ASTOR, ASELS{C_RESET}")
        print(f" {C_CYAN}📱 Gıda & İletişim: {C_WHITE}TCELL, TTKOM, BIMAS, MGROS, CCOLA{C_RESET}")
        print(f" {C_CYAN}🇺🇸 ABD Teknoloji  : {C_WHITE}AAPL (Apple), TSLA (Tesla), NVDA, MSFT, AMZN{C_RESET}")
        print(f"{C_MAGENTA}──────────────────────────────────────────────────────────────────────────{C_RESET}")
        print(f" {C_YELLOW}💡 İPUCU:{C_RESET} Yukarıdaki listeden bir kelime yazabilir ya da listede olmayan")
        print(f"          farklı bir BIST hissesini direkt yazabilirsiniz (Örn: `EREGL`).")
        print(f" {C_RED}❌ ÇIKIŞ YAPMAK İÇİN:{C_RESET} {C_BOLD}'CIKIS'{C_RESET} yazıp Enter'a basın.")
        print(f"{C_MAGENTA}──────────────────────────────────────────────────────────────────────────{C_RESET}")
        
        girdi = input(f"{C_GREEN}{C_BOLD}realwhitehathacker12@quant_bot:~# {C_RESET}").strip().upper()
        if girdi == "CIKIS":
            print(f"\n{C_RED}[!] Siber Borsa Ajanı Devre Dışı Bırakıldı. Güvenli Çıkış Yapıldı.{C_RESET}")
            break
        if not girdi:
            continue
            
        if girdi in varliklar:
            yahoo_kod, meta_isim = varliklar[girdi]
        else:
            if not girdi.endswith(".IS") and "-" not in girdi and "=" not in girdi:
                yahoo_kod, meta_isim = f"{girdi}.IS", f"BIST: {girdi}"
            else:
                yahoo_kod, meta_isim = girdi, f"Özel Varlık ({girdi})"
                
        matematiksel_analiz(yahoo_kod, meta_isim, engine)
        input(f"\n{C_CYAN}🔄 Yeniden Matrix Paneline dönmek için [Enter]'a basın...{C_RESET}")

if __name__ == "__main__":
    menu()
