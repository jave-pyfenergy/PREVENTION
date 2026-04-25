import { useState } from 'react'
import { apiClient } from '../lib/api'
import { stripExif } from '../lib/exif'

const MAX_SIZE_MB = 10
const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024
const ALLOWED_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']

/**
 * Hook para subida segura de imágenes médicas.
 * Flujo: strip EXIF → obtener Signed URL → PUT directo a Supabase Storage
 * El tráfico de la imagen NO pasa por el servidor FastAPI.
 */
export function useImageUpload() {
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState(null)

  const uploadImage = async (file) => {
    setError(null)
    setProgress(0)

    // Validaciones cliente
    if (!ALLOWED_TYPES.includes(file.type)) {
      throw new Error(`Formato no soportado. Use: ${ALLOWED_TYPES.join(', ')}`)
    }
    if (file.size > MAX_SIZE_BYTES) {
      throw new Error(`La imagen excede ${MAX_SIZE_MB}MB`)
    }

    setUploading(true)
    try {
      // 1. Strip EXIF — Privacy by Design
      setProgress(10)
      const cleanFile = await stripExif(file)

      // 2. Obtener Signed URL del backend
      setProgress(25)
      const { signed_url, path } = await apiClient.post(
        '/api/v1/imagenes/upload-url'
      )

      // 3. PUT directo a Supabase Storage con Signed URL
      setProgress(50)
      const uploadResponse = await fetch(signed_url, {
        method: 'PUT',
        body: cleanFile,
        headers: {
          'Content-Type': cleanFile.type,
          'x-upsert': 'false',
        },
      })

      if (!uploadResponse.ok) {
        throw new Error(`Error subiendo imagen: ${uploadResponse.status}`)
      }

      setProgress(100)
      return path // Se incluye en el payload del formulario
    } finally {
      setUploading(false)
    }
  }

  return { uploadImage, uploading, progress, error }
}
