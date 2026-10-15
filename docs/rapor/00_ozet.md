# Özet

Türkiye'de bireysel yatırımcıya açık binden fazla yatırım fonu arasında karşılaştırma yapmak ve kişinin risk durumuna uygun fonu bulmak uzmanlık gerektirmektedir. Bu projede, TEFAS'taki yatırım fonlarını analiz eden, karşılaştıran ve risk profiline göre eğitim amaçlı öneriler sunan bir web uygulaması geliştirdik.

Uygulama, TEFAS'ın 2026'da değişen arayüzünden 1.071 fonun beş yıllık 866.841 günlük fiyatını toplar ve her gece getiri, volatilite, Sharpe oranı ve maksimum düşüşü hesaplar. Veri kalitesi çalışmasında SPK kararıyla işleme kapatılan 117 fonu veriden silmeden işaretledik. Düşük volatiliteli fonlarda Sharpe oranının hafta sonu faizinin pazartesiye yansımasıyla anlamsız büyüdüğünü göstererek %5 volatilite eşiği getirdik.

Dokuz soruluk risk anketine dayanan öneri sistemi, fonları dört bileşenle puanlayıp gerekçeli öneriler üretir. Son üç yılda her ay yapılan kayan pencereli geriye dönük testte örnek portföyler, yüksek faiz döneminde para piyasası fonlarının medyanını 24 dönemin yalnızca 5–12'sinde geçti. Bir aylık getiri tahmininde LightGBM, gelecekten bilgi sızdırmayan walk-forward testte fonun geçmiş ortalama getirisinin sürmesini varsayan drift yöntemini hiçbir risk grubunda geçemedi. Bu yüzden sitede makine öğrenmesi tahmini yerine etiketli drift tahmini ve konformal %80 aralık gösterilir.

Uygulamada ayrıca teknik göstergeler, TEFAS valörüne göre işleyen bir sanal portföy ve geriye dönük "Ya o zaman alsaydım?" hesabı bulunur. KAP verisi, kullanım koşulu saklamayı yasakladığı için kullanılmadı. Uygulama sunum bilgisayarında tek tıkla ve internetsiz çalışır; 131 otomatik test ve gerçek tarayıcıda uçtan uca testle doğrulandı.

**Anahtar kelimeler:** yatırım fonları, TEFAS, risk profili, öneri sistemi, Sharpe oranı, geriye dönük test, walk-forward değerlendirme, LightGBM, veri kalitesi

# Abstract

Choosing among more than a thousand Turkish mutual funds requires expertise. We developed a web application that analyses and compares the funds on TEFAS, the Turkish fund trading platform, and gives educational recommendations based on a risk profile.

It collects five years of daily prices (866,841 records) for 1,071 funds from TEFAS's interface, which changed in 2026, and computes return, volatility, Sharpe ratio and maximum drawdown nightly. We flagged, without deleting them, 117 funds closed by a Capital Markets Board decision. We showed that the Sharpe ratio of low-volatility funds is inflated because weekend interest is credited on Mondays, and introduced a 5% volatility threshold.

A recommender based on a nine-question survey scores funds on four components and explains each recommendation. In a monthly rolling backtest over three years, sample portfolios beat the median money market fund in only 5 to 12 of 24 periods during high interest rates. For one-month return forecasts, LightGBM did not beat a simple drift baseline in any risk group in a walk-forward test without look-ahead bias, so the site shows a labelled drift forecast with a conformal 80% interval instead of a machine learning forecast.

The application also offers technical indicators, a virtual portfolio following TEFAS settlement rules and a "what if I had bought" calculator. Public Disclosure Platform (KAP) data was not used because its terms forbid storage. The application runs offline with one click and is verified by 131 automated tests and end-to-end browser tests.

**Keywords:** mutual funds, TEFAS, risk profiling, recommender system, Sharpe ratio, backtesting, walk-forward evaluation, LightGBM, data quality
