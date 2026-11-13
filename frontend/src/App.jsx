import { lazy, Suspense } from 'react'
import { Routes, Route, NavLink, Link } from 'react-router-dom'
import Home from './pages/Home.jsx'
import Funds from './pages/Funds.jsx'
import Doviz from './pages/Doviz.jsx'
import Rankings from './pages/Rankings.jsx'
import RiskSurvey from './pages/RiskSurvey.jsx'
import Giris from './pages/Giris.jsx'
import Kayit from './pages/Kayit.jsx'
import UserMenu from './components/UserMenu.jsx'
import { useAuth } from './auth.jsx'

// Grafik kütüphanesi (Recharts) büyük; sadece grafikli sayfalar açılınca indirilsin
const FundDetail = lazy(() => import('./pages/FundDetail.jsx'))
const Compare = lazy(() => import('./pages/Compare.jsx'))
const Recommendations = lazy(() => import('./pages/Recommendations.jsx'))
const ModelPerformance = lazy(() => import('./pages/ModelPerformance.jsx'))
const SanalPortfoy = lazy(() => import('./pages/SanalPortfoy.jsx'))
const Hesabim = lazy(() => import('./pages/Hesabim.jsx'))
const Favoriler = lazy(() => import('./pages/Favoriler.jsx'))

export default function App() {
  const { ready, notice, setNotice } = useAuth()
  return (
    <div className="app">
      <a href="#icerik" className="skip-link">İçeriğe geç</a>
      <header className="header">
        <Link to="/" className="logo">Fon<span className="logo-mark">Analiz</span></Link>
        <nav aria-label="Ana menü">
          <NavLink to="/" end>Ana Sayfa</NavLink>
          <NavLink to="/fonlar">Fonlar</NavLink>
          <NavLink to="/siralamalar">Sıralamalar</NavLink>
          <NavLink to="/karsilastir">Karşılaştır</NavLink>
          <NavLink to="/risk-anketi">Risk Anketi</NavLink>
          <NavLink to="/oneriler">Öneriler</NavLink>
          <NavLink to="/sanal-portfoy">Sanal Portföy</NavLink>
          <NavLink to="/favoriler">Favorilerim</NavLink>
          <NavLink to="/model-performansi">Model</NavLink>
          <NavLink to="/doviz">Döviz ve Altın</NavLink>
        </nav>
        {ready && <UserMenu />}
      </header>
      <main className="main" id="icerik" tabIndex={-1}>
        {notice && (
          <p className="notice notice-info" role="status">
            {notice} <button type="button" className="btn-link" onClick={() => setNotice(null)}>Kapat</button>
          </p>
        )}
        {/* oturum bilgisi gelmeden sayfa çizilmez: girişli/girişsiz görünüm arasında gidip gelmesin */}
        {!ready ? <p className="muted">Yükleniyor...</p> : (
        <Suspense fallback={<p className="muted">Yükleniyor...</p>}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/fonlar" element={<Funds />} />
            <Route path="/fonlar/:code" element={<FundDetail />} />
            <Route path="/siralamalar" element={<Rankings />} />
            <Route path="/karsilastir" element={<Compare />} />
            <Route path="/risk-anketi" element={<RiskSurvey />} />
            <Route path="/oneriler" element={<Recommendations />} />
            <Route path="/model-performansi" element={<ModelPerformance />} />
            <Route path="/sanal-portfoy" element={<SanalPortfoy />} />
            <Route path="/doviz" element={<Doviz />} />
            <Route path="/giris" element={<Giris />} />
            <Route path="/kayit" element={<Kayit />} />
            <Route path="/hesabim" element={<Hesabim />} />
            <Route path="/favoriler" element={<Favoriler />} />
          </Routes>
        </Suspense>
        )}
      </main>
      <footer className="footer">
        <p>
          <strong>Yatırım tavsiyesi değildir.</strong> Bu site bir bitirme projesidir; gösterilen veriler, sıralamalar ve
          öneriler bilgilendirme ve eğitim amaçlıdır, SPK lisanslı yatırım danışmanlığı yerine geçmez. Geçmiş performans
          gelecekteki sonuçların göstergesi değildir. Fon verileri TEFAS'tan alınır.
        </p>
      </footer>
    </div>
  )
}
