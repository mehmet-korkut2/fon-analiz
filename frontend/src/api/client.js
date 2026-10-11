import axios from 'axios'

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '/api' })

export const getHealth = () => api.get('/health').then((r) => r.data)
export const getFunds = (params) => api.get('/funds', { params }).then((r) => r.data)
export const getFx = (source = 'canli') => api.get('/fx', { params: { source } }).then((r) => r.data)
export const getStatus = () => api.get('/status').then((r) => r.data)

export default api
