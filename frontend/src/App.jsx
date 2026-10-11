import { Routes, Route, NavLink, Link } from 'react-router-dom'
import Home from './pages/Home.jsx'
import Funds from './pages/Funds.jsx'
import Doviz from './pages/Doviz.jsx'

export default function App() {
  return (
    <div className="app">
      <header className="header">
        <Link to="/" className="logo">Fon Analiz</Link>
        <nav>
          <NavLink to="/" end>Ana Sayfa</NavLink>
          <NavLink to="/fonlar">Fonlar</NavLink>
          <NavLink to="/doviz">Döviz ve Altın</NavLink>
        </nav>
      </header>
      <main className="main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/fonlar" element={<Funds />} />
          <Route path="/doviz" element={<Doviz />} />
        </Routes>
      </main>
    </div>
  )
}
