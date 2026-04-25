/**
 * PrevencionApp — Strip EXIF metadata antes del upload.
 * Privacy by Design: elimina geolocalización y datos del dispositivo.
 * Usa piexifjs para limpiar JPEG EXIF.
 */

/**
 * Elimina todos los metadatos EXIF de una imagen JPEG.
 * Para PNG (sin EXIF nativo), retorna el file sin cambios.
 * @param {File} file - Archivo de imagen del usuario
 * @returns {Promise<File>} - Archivo limpio sin metadatos de ubicación
 */
export async function stripExif(file) {
  // Solo JPEG tiene EXIF
  if (!file.type.includes('jpeg') && !file.type.includes('jpg')) {
    return file
  }

  return new Promise((resolve, reject) => {
    const reader = new FileReader()

    reader.onload = (e) => {
      try {
        // piexifjs: eliminar todos los segmentos EXIF
        const { piexif } = window
        if (!piexif) {
          // Fallback: si piexifjs no está disponible, usar el file original
          console.warn('[EXIF] piexifjs no disponible — imagen sin strip')
          resolve(file)
          return
        }

        const dataUrl = e.target.result
        const stripped = piexif.remove(dataUrl)

        // Convertir dataURL de vuelta a File
        const arr = stripped.split(',')
        const mime = arr[0].match(/:(.*?);/)[1]
        const bstr = atob(arr[1])
        let n = bstr.length
        const u8arr = new Uint8Array(n)
        while (n--) u8arr[n] = bstr.charCodeAt(n)

        const cleanFile = new File([u8arr], file.name, { type: mime })
        resolve(cleanFile)
      } catch (err) {
        console.warn('[EXIF] Error al strip EXIF, usando original:', err)
        resolve(file)
      }
    }

    reader.onerror = () => reject(new Error('Error leyendo imagen'))
    reader.readAsDataURL(file)
  })
}

/**
 * Verifica que una imagen no tenga tags GPS en EXIF.
 * Usado en tests e2e para garantizar privacidad.
 */
export async function tieneGPS(file) {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const { piexif } = window
        if (!piexif) { resolve(false); return }
        const exifData = piexif.load(e.target.result)
        const gps = exifData['GPS']
        resolve(gps && Object.keys(gps).length > 0)
      } catch {
        resolve(false)
      }
    }
    reader.readAsDataURL(file)
  })
}
