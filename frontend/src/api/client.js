import axios from 'axios'

// Oturum HttpOnly çerezde (JavaScript okuyamaz). X-Requested-With: backend, çerezli ve durum değiştiren
// isteklerde bu başlığı ister (CSRF koruması; backend/app/deps.py).
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  withCredentials: true,
  headers: { 'X-Requested-With': 'XMLHttpRequest' },
})

export const getHealth = () => api.get('/health').then((r) => r.data)
export const getFunds = (params) => api.get('/funds', { params }).then((r) => r.data)
export const getCategories = () => api.get('/funds/categories').then((r) => r.data)
export const getFund = (code) => api.get(`/funds/${code}`).then((r) => r.data)
// params: { months } ya da { start, end } (YYYY-MM-DD)
export const getFundPrices = (code, params = { months: 12 }) => api.get(`/funds/${code}/prices`, { params }).then((r) => r.data)
// codes: ['TTE', 'AFA'], params: { months } ya da { start }
export const getCompare = (codes, params) => api.get('/compare', { params: { funds: codes.join(','), ...params } }).then((r) => r.data)
export const getRankings = (params) => api.get('/rankings', { params }).then((r) => r.data)
export const getSurvey = () => api.get('/risk-survey').then((r) => r.data)
// answers: { soruId: puan }, qualified: nitelikli yatırımcı
export const postRiskProfile = (answers, qualified) => api.post('/risk-profile', { answers, qualified }).then((r) => r.data)
export const getRecommendations = (profile, qualified) => api.get('/recommendations', { params: { profile, qualified } }).then((r) => r.data)
export const getBacktest = (profile, qualified) => api.get('/recommendations/backtest', { params: { profile, qualified } }).then((r) => r.data)
// 50/200 günlük ortalama serisi (params prices ile aynı) ve trend / 52 haftalık aralık özeti
export const getTechnical = (code, params = { months: 12 }) => api.get(`/funds/${code}/technical`, { params }).then((r) => r.data)
export const getForecast = (code) => api.get(`/funds/${code}/forecast`).then((r) => r.data)
export const getFundReal = (code) => api.get(`/funds/${code}/real`).then((r) => r.data)
export const getInflation = () => api.get('/inflation').then((r) => r.data)
export const getScorecard = (code, params) => api.get(`/funds/${code}/forecast-scorecard`, { params }).then((r) => r.data)
export const getMlPerformance = () => api.get('/ml/performance').then((r) => r.data)
export const getFx = (source = 'canli') => api.get('/fx', { params: { source } }).then((r) => r.data)
export const getStatus = () => api.get('/status').then((r) => r.data)
// Sanal portföy (hayali para). order: { code, side: 'alis' | 'satis', amount?, units? }
export const getSanal = () => api.get('/sanal-portfoy').then((r) => r.data)
export const postSanalOrder = (order) => api.post('/sanal-portfoy/emir', order).then((r) => r.data)
export const cancelSanalOrder = (id) => api.delete(`/sanal-portfoy/emir/${id}`).then((r) => r.data)
export const resetSanal = (initialBalance) => api.post('/sanal-portfoy/sifirla', { initial_balance: initialBalance }).then((r) => r.data)
export const getWhatIf = (codes, date, amount) => api.get('/sanal-portfoy/geriye', { params: { funds: codes.join(','), tarih: date, tutar: amount } }).then((r) => r.data)

// Kullanıcı hesabı
export const getMe = () => api.get('/auth/ben').then((r) => r.data.user)
export const postRegister = (body) => api.post('/auth/kayit', body).then((r) => r.data)
export const postLogin = (body) => api.post('/auth/giris', body).then((r) => r.data)
export const postLogout = () => api.post('/auth/cikis')
export const postPassword = (body) => api.post('/auth/sifre', body).then((r) => r.data)
export const deleteAccount = (password) => api.delete('/auth/hesap', { data: { password } })
export const getMyProfile = () => api.get('/profilim').then((r) => r.data)
export const postMyProfile = (answers, qualified) => api.post('/profilim', { answers, qualified }).then((r) => r.data)
export const getFavorites = () => api.get('/favoriler').then((r) => r.data)
export const addFavorite = (code) => api.post(`/favoriler/${code}`)
export const removeFavorite = (code) => api.delete(`/favoriler/${code}`)

// API hata mesajı (FastAPI "detail": metin ya da doğrulama listesi)
export function errorMessage(e, fallback = 'Bir hata oluştu.') {
  const d = e?.response?.data?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d) && d.length) {
    const field = d[0].loc?.[d[0].loc.length - 1]
    if (field === 'email') return 'Geçerli bir e-posta adresi girin.'
    return d[0].msg || fallback
  }
  if (!e?.response) return 'Sunucuya ulaşılamadı. Backend çalışıyor mu?'
  return fallback
}

export default api
