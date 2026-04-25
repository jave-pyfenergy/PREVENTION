import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { apiClient } from '../lib/api'
import { useAuthStore } from '../stores/authStore'

/**
 * Hook principal para el flujo de evaluación clínica.
 * Gestiona submit, polling del resultado y vinculación al usuario.
 */
export function useEvaluacion() {
  const navigate = useNavigate()
  const { setTempEvaluacion } = useAuthStore()

  const submitMutation = useMutation({
    mutationFn: async (formData) => {
      const payload = {
        sintomas: {
          dolor_articular: formData.dolor_articular,
          rigidez_matutina: formData.rigidez_matutina,
          duracion_rigidez_minutos: Number(formData.duracion_rigidez_minutos),
          localizacion: formData.localizacion || [],
          inflamacion_visible: formData.inflamacion_visible,
          calor_local: formData.calor_local,
          limitacion_movimiento: formData.limitacion_movimiento,
        },
        imagen_url: formData.imagen_url || null,
        consentimiento: formData.consentimiento,
        version_cuestionario: '1.0',
        edad: formData.edad ? Number(formData.edad) : null,
        sexo: formData.sexo || null,
        pais_id: formData.pais_id ? Number(formData.pais_id) : null,
      }

      return apiClient.post('/api/v1/evaluacion-temporal', payload)
    },
    onSuccess: (data) => {
      // Guardar IDs para vinculación posterior
      setTempEvaluacion(data.evaluacion_id, data.session_id)
      // Navegar al resultado
      navigate(`/resultado/${data.session_id}`)
    },
  })

  return {
    submit: submitMutation.mutate,
    isLoading: submitMutation.isPending,
    error: submitMutation.error,
  }
}

/**
 * Hook para obtener el resultado por session_id.
 */
export function useResultado(sessionId) {
  return useQuery({
    queryKey: ['resultado', sessionId],
    queryFn: () => apiClient.get(`/api/v1/resultado/${sessionId}`),
    enabled: Boolean(sessionId),
    staleTime: 5 * 60 * 1000, // 5 min
    retry: 2,
  })
}

/**
 * Hook para vincular evaluación anónima al usuario autenticado.
 */
export function useVincularEvaluacion() {
  const { tempEvaluacionId, clearTempEvaluacion } = useAuthStore()

  const vincularMutation = useMutation({
    mutationFn: async () => {
      if (!tempEvaluacionId) return
      return apiClient.post(
        `/api/v1/vincular-evaluacion?evaluacion_id=${tempEvaluacionId}`
      )
    },
    onSuccess: () => {
      clearTempEvaluacion()
    },
  })

  return {
    vincular: vincularMutation.mutate,
    isPending: vincularMutation.isPending,
    hasPendingEvaluacion: Boolean(tempEvaluacionId),
  }
}

/**
 * Hook para historial de evaluaciones del usuario.
 */
export function useHistorial({ page = 1, pageSize = 20 } = {}) {
  return useQuery({
    queryKey: ['historial', page, pageSize],
    queryFn: () =>
      apiClient.get('/api/v1/historial', { page, page_size: pageSize }),
    staleTime: 60_000,
    retry: 1,
  })
}
