// Öneri sayfalarındaki belirgin uyarı kutusu. Her sayfanın altındaki genel uyarı App.jsx'te.
export default function Disclaimer() {
  return (
    <aside className="disclaimer" role="note">
      <strong>Yatırım tavsiyesi değildir.</strong> Bu öneriler eğitim amaçlı bir algoritmanın çıktısıdır; SPK lisanslı
      yatırım danışmanlığı değildir. Geçmiş performans gelecekteki sonuçların göstergesi değildir. Yatırım kararı
      vermeden önce lisanslı bir yatırım danışmanına başvurun.
    </aside>
  )
}
