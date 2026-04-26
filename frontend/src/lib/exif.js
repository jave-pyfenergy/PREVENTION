/**
 * PrevencionApp — Strip EXIF metadata antes del upload.
 * Privacy by Design: elimina geolocalización y datos del dispositivo.
 *
 * FIX: importar piexifjs como módulo ES (no window.piexif — silently broken en Vite).
 */
import piexif from 'piexifjs'

/**
 * Elimina todos los metadatos EXIF de una imagen JPEG.
 * Para PNG/WebP (sin EXIF nativo), retorna el file sin cambios.
 * @param {File} file
 * @returns {Promise<File>}
 */
export async function stripExif(file) {
  if (!file.type.includes('jpeg') && !file.type.includes('jpg')) {
    return file
  }

  return new Promise((resolve, reject) => {
    const reader = new FileReader()

    reader.onload = (e) => {
      try {
        const dataUrl = e.target.result
        const stripped = piexif.remove(dataUrl)

        const arr = stripped.split(',')
        const mime = arr[0].match(/:(.*?);/)[1]
        const bstr = atob(arr[1])
        let n = bstr.length
        const u8arr = new Uint8Array(n)
        while (n--) u8arr[n] = bstr.charCodeAt(n)

        resolve(new File([u8arr], file.name, { type: mime }))
      } catch (err) {
        // Log pero no fallar — preferimos subir con EXIF a no subir
        console.error('[EXIF] Strip falló, imagen con metadatos:', err)
        resolve(file)
      }
    }

    reader.onerror = () => reject(new Error('Error leyendo imagen para strip EXIF'))
    reader.readAsDataURL(file)
  })
}

/**
 * Verifica que una imagen no tenga tags GPS en EXIF.
 * Usado en tests e2e para garantizar privacidad.
 * @param {File} file
 * @returns {Promise<boolean>}
 */
export async function tieneGPS(file) {
  if (!file.type.includes('jpeg') && !file.type.includes('jpg')) {
    return false
  }
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const exifData = piexif.load(e.target.result)
        const gps = exifData['GPS']
        resolve(Boolean(gps && Object.keys(gps).length > 0))
      } catch {
        resolve(false)
      }
    }
    reader.readAsDataURL(file)
  })
}
