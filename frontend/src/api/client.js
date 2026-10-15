import axios from 'axios'

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '/api' })

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
export const getMlPerformance = () => api.get('/ml/performance').then((r) => r.data)
export const getFx = (source = 'canli') => api.get('/fx', { params: { source } }).then((r) => r.data)
export const getStatus = () => api.get('/status').then((r) => r.data)
// Sanal portföy (hayali para). order: { code, side: 'alis' | 'satis', amount?, units? }
export const getSanal = () => api.get('/sanal-portfoy').then((r) => r.data)
export const postSanalOrder = (order) => api.post('/sanal-portfoy/emir', order).then((r) => r.data)
export const cancelSanalOrder = (id) => api.delete(`/sanal-portfoy/emir/${id}`).then((r) => r.data)
export const resetSanal = (initialBalance) => api.post('/sanal-portfoy/sifirla', { initial_balance: initialBalance }).then((r) => r.data)
export const getWhatIf = (codes, date, amount) => api.get('/sanal-portfoy/geriye', { params: { funds: codes.join(','), tarih: date, tutar: amount } }).then((r) => r.data)

export default api
