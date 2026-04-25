import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { supabase } from '../lib/supabase'

/**
 * Store global de autenticación y sesión.
 * Persiste el temp_evaluacion_id en sessionStorage para el flujo anónimo → registro.
 */
export const useAuthStore = create(
  persist(
    (set, get) => ({
      // ── Estado ────────────────────────────────────────────────────────────
      user: null,
      session: null,
      perfil: null,
      isLoading: true,
      // Evaluación temporal del flujo anónimo (para vincular al registrarse)
      tempEvaluacionId: null,
      tempSessionId: null,

      // ── Acciones ─────────────────────────────────────────────────────────
      setSession: (session) =>
        set({ session, user: session?.user ?? null, isLoading: false }),

      setPerfil: (perfil) => set({ perfil }),

      setTempEvaluacion: (evaluacionId, sessionId) =>
        set({ tempEvaluacionId: evaluacionId, tempSessionId: sessionId }),

      clearTempEvaluacion: () =>
        set({ tempEvaluacionId: null, tempSessionId: null }),

      signOut: async () => {
        await supabase.auth.signOut()
        set({
          user: null,
          session: null,
          perfil: null,
          tempEvaluacionId: null,
          tempSessionId: null,
        })
      },

      // ── Helpers ───────────────────────────────────────────────────────────
      isAuthenticated: () => Boolean(get().session?.access_token),
      getUserId: () => get().user?.id,
    }),
    {
      name: 'prevencion-auth',
      partialize: (state) => ({
        // Solo persiste el id temporal (no el JWT — Supabase lo gestiona)
        tempEvaluacionId: state.tempEvaluacionId,
        tempSessionId: state.tempSessionId,
      }),
    }
  )
)
