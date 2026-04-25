import axios from 'axios'
import { supabase } from './supabase'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080'

/**
 * Instancia Axios con interceptor JWT automático.
 * Adjunta el token de Supabase Auth en cada request autenticado.
 */
export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ── Interceptor de request: adjuntar JWT ─────────────────────────────────────
api.interceptors.request.use(
  async (config) => {
    const { data: { session } } = await supabase.auth.getSession()
    if (session?.access_token) {
      config.headers['Authorization'] = `Bearer ${session.access_token}`
    }
    // Trazabilidad
    config.headers['X-Request-ID'] = crypto.randomUUID()
    return config
  },
  (error) => Promise.reject(error)
)

// ── Interceptor de response: manejo global de errores ────────────────────────
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Token expirado: intentar refresh
      const { error: refreshError } = await supabase.auth.refreshSession()
      if (refreshError) {
        // Sesión inválida: redirigir a login
        window.location.href = '/login'
        return Promise.reject(error)
      }
      // Reintentar la request original
      return api(error.config)
    }
    return Promise.reject(error)
  }
)

// ── Helpers tipados ──────────────────────────────────────────────────────────
export const apiClient = {
  post: (url, data) => api.post(url, data).then((r) => r.data),
  get: (url, params) => api.get(url, { params }).then((r) => r.data),
  put: (url, data) => api.put(url, data).then((r) => r.data),
}
