# Özet

Türkiye'de yatırım fonları, TEFAS üzerinden bireysel yatırımcıya açık olmasına rağmen, binden fazla fon arasında karşılaştırma yapmak ve kişinin risk durumuna uygun fonu bulmak uzmanlık gerektirmektedir. Bu projede, TEFAS'taki yatırım fonlarını analiz eden, karşılaştıran ve risk profiline göre eğitim amaçlı öneriler sunan bir web uygulaması geliştirdik.

Uygulama; TEFAS'ın 2026'da değişen JSON arayüzünden 1.071 fonun beş yıllık (13.10.2021 – 14.10.2026) 866.841 günlük fiyatını toplamakta, her gece getiri, volatilite, Sharpe oranı ve maksimum düşüş metriklerini hesaplamakta, fon listesi, fon detayı, karşılaştırma ve sıralama sayfalarında sunmaktadır. Veri kalitesi çalışmasında, 17.09.2026 tarihli SPK kararıyla işleme kapatılan yedi portföy şirketinin 117 fonunu işaretledik; düşük volatiliteli fonlarda Sharpe oranının hafta sonu faizinin pazartesiye yansımasıyla anlamsız büyüdüğünü göstererek %5 volatilite eşiği getirdik.

Sekiz soruluk bir risk anketiyle kullanıcıyı temkinli, dengeli ya da agresif profile yerleştiren; fonları dört bileşenin (fazla getiri, riske göre getiri, düşüş direnci, tutarlılık) yüzdelik puanlarıyla sıralayan ve gerekçeli öneriler üreten bir öneri sistemi kurduk. Son üç yılda her ay yapılan kayan pencereli geriye dönük testte örnek portföyler, yüksek faiz döneminde para piyasası fonlarının medyanını çoğunlukla geçemedi (temkinli 24 dönemin 12'sinde, dengeli 5'inde, agresif 9'unda).

Bir aylık getiri tahmini için LightGBM ve ARIMA modellerini, gelecekten bilgi sızdırmayan walk-forward bir düzenekte basit referans yöntemlerle karşılaştırdık. LightGBM, önceden tanımlanan başarı ölçütünü hiçbir risk grubunda karşılayamadı; en isabetli yöntem fonun geçmiş ortalama getirisinin sürmesi (drift) oldu. Bu nedenle uygulamada makine öğrenmesi tahmini yerine, açık bir etiketle drift tahmini ve ölçülmüş kapsama oranına sahip konformal %80 aralık gösterilmektedir.

**Anahtar kelimeler:** yatırım fonları, TEFAS, risk profili, öneri sistemi, Sharpe oranı, geriye dönük test, walk-forward değerlendirme, LightGBM

# Abstract

[DOLDUR: İngilizce özet — yukarıdaki Türkçe özetin çevirisi; bölüm 07 ve 08 tamamlandıktan sonra son hâli yazılacak.]

**Keywords:** mutual funds, TEFAS, risk profiling, recommender system, Sharpe ratio, backtesting, walk-forward evaluation, LightGBM
