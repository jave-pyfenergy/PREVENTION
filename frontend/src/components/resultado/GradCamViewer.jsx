/**
 * PrevencionApp — Componente: GradCamViewer
 * Visualiza el mapa de calor Grad-CAM con overlay y zoom.
 */
import { useState } from 'react'

export function GradCamViewer({ gradcamUrl, originalUrl }) {
  const [showOverlay, setShowOverlay] = useState(true)
  const [zoomed, setZoomed] = useState(false)

  if (!gradcamUrl) return null

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-bold text-slate-800 flex items-center gap-2">
          <span>🔬</span> Análisis Visual Grad-CAM
        </h3>
        <button
          onClick={() => setShowOverlay(!showOverlay)}
          className="text-xs text-blue-700 border border-blue-200 rounded-lg px-3 py-1 hover:bg-blue-50"
        >
          {showOverlay ? 'Ver original' : 'Ver Grad-CAM'}
        </button>
      </div>

      <p className="text-slate-500 text-sm leading-relaxed">
        Las zonas en <span className="text-red-500 font-medium">rojo/naranja</span> indican
        las áreas que el modelo identificó como relevantes para la detección de inflamación.
        Las zonas <span className="text-blue-500 font-medium">azules</span> tienen menor relevancia.
      </p>

      <div
        className={`relative rounded-2xl overflow-hidden cursor-zoom-in border border-slate-200 transition-all ${
          zoomed ? 'fixed inset-4 z-50 cursor-zoom-out' : ''
        }`}
        onClick={() => setZoomed(!zoomed)}
      >
        <img
          src={showOverlay ? gradcamUrl : (originalUrl || gradcamUrl)}
          alt={showOverlay ? 'Mapa de calor Grad-CAM' : 'Imagen original'}
          className="w-full object-contain max-h-96"
          loading="lazy"
        />
        {zoomed && (
          <div className="absolute inset-0 bg-black/5 flex items-end justify-center pb-4">
            <span className="bg-black/60 text-white text-xs px-3 py-1 rounded-full">
              Click para cerrar
            </span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3 text-xs text-slate-400">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-full bg-red-500" />
          Alta activación
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-full bg-yellow-400" />
          Activación media
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-full bg-blue-500" />
          Baja activación
        </div>
      </div>
    </div>
  )
}
