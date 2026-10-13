import axios from 'axios'

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '/api' })

export const getHealth = () => api.get('/health').then((r) => r.data)
export const getFunds = (params) => api.get('/funds', { params }).then((r) => r.data)
export const getCategories = () => api.get('/funds/categories').then((r) => r.data)
export const getFund = (code) => api.get(`/funds/${code}`).then((r) => r.data)
// params: { months } ya da { start, end } (YYYY-MM-DD)
export const getFundPrices = (code, params = { months: 12 }) => api.get(`/funds/${code}/prices`, { params }).then((r) => r.data)
export const getFx = (source = 'canli') => api.get('/fx', { params: { source } }).then((r) => r.data)
export const getStatus = () => api.get('/status').then((r) => r.data)

export default api
