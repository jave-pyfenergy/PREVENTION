import { useEffect } from 'react'
import { supabase } from '../lib/supabase'
import { useAuthStore } from '../stores/authStore'

/**
 * Hook de autenticación — gestiona la sesión de Supabase Auth.
 * Escucha cambios de sesión y sincroniza el store.
 */
export function useAuth() {
  const { user, session, isLoading, setSession, signOut, isAuthenticated } =
    useAuthStore()

  useEffect(() => {
    // Cargar sesión existente al montar
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
    })

    // Suscribirse a cambios de autenticación
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
    })

    return () => subscription.unsubscribe()
  }, [setSession])

  const signIn = async (email, password) => {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    })
    if (error) throw error
    return data
  }

  const signUp = async (email, password) => {
    const { data, error } = await supabase.auth.signUp({ email, password })
    if (error) throw error
    return data
  }

  return {
    user,
    session,
    isLoading,
    isAuthenticated: isAuthenticated(),
    signIn,
    signUp,
    signOut,
  }
}
