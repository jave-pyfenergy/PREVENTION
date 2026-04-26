import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate } from 'react-router-dom'
import { useEvaluacion } from '../hooks/useEvaluacion'
import { useImageUpload } from '../hooks/useImageUpload'

// ── Esquema de validación Zod (espejo del backend Pydantic) ──────────────────
const step1Schema = z.object({
  edad: z.coerce.number().min(0).max(120).optional(),
  sexo: z.string().optional(),
  pais_id: z.coerce.number().optional(),
})

const step2Schema = z.object({
  dolor_articular: z.boolean(),
  rigidez_matutina: z.boolean(),
  duracion_rigidez_minutos: z.coerce.number().min(0).max(1440),
  localizacion: z.array(z.string()).min(1, 'Selecciona al menos una localización'),
  inflamacion_visible: z.boolean(),
  calor_local: z.boolean(),
  limitacion_movimiento: z.boolean(),
})

const STEPS = ['Datos básicos', 'Síntomas', 'Imagen', 'Consentimiento']

const LOCALIZACIONES = [
  { value: 'mano_derecha', label: 'Mano derecha' },
  { value: 'mano_izquierda', label: 'Mano izquierda' },
  { value: 'muneca_derecha', label: 'Muñeca derecha' },
  { value: 'muneca_izquierda', label: 'Muñeca izquierda' },
  { value: 'codo_derecho', label: 'Codo derecho' },
  { value: 'codo_izquierdo', label: 'Codo izquierdo' },
  { value: 'rodilla_derecha', label: 'Rodilla derecha' },
  { value: 'rodilla_izquierda', label: 'Rodilla izquierda' },
]

export default function Formulario() {
  const [currentStep, setCurrentStep] = useState(0)
  const [formData, setFormData] = useState({})
  const [imagePath, setImagePath] = useState(null)
  const [consentimiento, setConsentimiento] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const { submit, isLoading, error } = useEvaluacion()
  const { uploadImage, uploading, progress } = useImageUpload()

  const { register, handleSubmit, watch, setValue, formState: { errors } } = useForm({
    defaultValues: { localizacion: [] },
  })

  const localizacionSeleccionadas = watch('localizacion') || []

  const handleNext = handleSubmit((data) => {
    setFormData((prev) => ({ ...prev, ...data }))
    setCurrentStep((s) => s + 1)
  })

  const handleBack = () => setCurrentStep((s) => s - 1)

  const handleImageChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadError(null)
    try {
      const path = await uploadImage(file)
      setImagePath(path)
    } catch (err) {
      setUploadError(err.message || 'Error al subir la imagen. Intente nuevamente.')
    }
  }

  const toggleLocalizacion = (value) => {
    const current = localizacionSeleccionadas
    const updated = current.includes(value)
      ? current.filter((v) => v !== value)
      : [...current, value]
    setValue('localizacion', updated)
  }

  const handleFinalSubmit = () => {
    submit({ ...formData, imagen_url: imagePath, consentimiento })
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-start justify-center py-12 px-4">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-blue-900">Evaluación Clínica</h1>
          <p className="text-slate-500 mt-2">Responde con honestidad para obtener el mejor resultado</p>
        </div>

        {/* Progress steps */}
        <div className="flex items-center justify-center gap-2 mb-8">
          {STEPS.map((step, i) => (
            <div key={i} className="flex items-center gap-2">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all
                ${i < currentStep ? 'bg-green-500 text-white' :
                  i === currentStep ? 'bg-blue-800 text-white' :
                  'bg-slate-200 text-slate-400'}`}>
                {i < currentStep ? '✓' : i + 1}
              </div>
              {i < STEPS.length - 1 && (
                <div className={`h-0.5 w-12 transition-all ${i < currentStep ? 'bg-green-500' : 'bg-slate-200'}`} />
              )}
            </div>
          ))}
        </div>

        {/* Step content */}
        <div className="card animate-fade-in">
          <h2 className="text-xl font-bold text-slate-800 mb-6">{STEPS[currentStep]}</h2>

          {/* Step 1: Datos básicos */}
          {currentStep === 0 && (
            <form onSubmit={handleNext} className="space-y-4">
              <div>
                <label className="label">Edad (opcional)</label>
                <input type="number" {...register('edad')} className="input-field" placeholder="Ej. 45" />
              </div>
              <div>
                <label className="label">Sexo (opcional)</label>
                <select {...register('sexo')} className="input-field">
                  <option value="">Prefiero no decir</option>
                  <option value="masculino">Masculino</option>
                  <option value="femenino">Femenino</option>
                  <option value="no_binario">No binario</option>
                </select>
              </div>
              <div className="pt-4 flex justify-end">
                <button type="submit" className="btn-primary">Continuar →</button>
              </div>
            </form>
          )}

          {/* Step 2: Síntomas */}
          {currentStep === 1 && (
            <div className="space-y-6">
              {[
                { name: 'dolor_articular', label: '¿Siente dolor en sus articulaciones?' },
                { name: 'rigidez_matutina', label: '¿Tiene rigidez por las mañanas?' },
                { name: 'inflamacion_visible', label: '¿Observa inflamación visible en alguna articulación?' },
                { name: 'calor_local', label: '¿Nota calor local en las articulaciones afectadas?' },
                { name: 'limitacion_movimiento', label: '¿Tiene limitación de movimiento?' },
              ].map(({ name, label }) => (
                <div key={name} className="flex items-center justify-between p-4 bg-slate-50 rounded-xl">
                  <span className="text-slate-700 font-medium text-sm">{label}</span>
                  <div className="flex gap-3">
                    {['Sí', 'No'].map((opt) => (
                      <button
                        key={opt}
                        type="button"
                        onClick={() => setValue(name, opt === 'Sí')}
                        className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all
                          ${watch(name) === (opt === 'Sí') ? 'bg-blue-800 text-white' : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'}`}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                </div>
              ))}

              <div>
                <label className="label">Duración de la rigidez matutina (minutos)</label>
                <input type="number" {...register('duracion_rigidez_minutos')} className="input-field" placeholder="Ej. 30" min="0" max="1440" />
              </div>

              <div>
                <label className="label">Localizaciones afectadas</label>
                <div className="grid grid-cols-2 gap-2 mt-2">
                  {LOCALIZACIONES.map(({ value, label }) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => toggleLocalizacion(value)}
                      className={`p-3 rounded-xl text-sm font-medium text-left transition-all
                        ${localizacionSeleccionadas.includes(value)
                          ? 'bg-blue-800 text-white'
                          : 'bg-slate-50 border border-slate-200 text-slate-600 hover:bg-blue-50'}`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                {errors.localizacion && (
                  <p className="text-red-500 text-sm mt-1">{errors.localizacion.message}</p>
                )}
              </div>

              <div className="flex justify-between pt-4">
                <button type="button" onClick={handleBack} className="btn-outline">← Atrás</button>
                <button type="button" onClick={() => { setFormData(f => ({...f, ...watch()})); setCurrentStep(2) }} className="btn-primary">Continuar →</button>
              </div>
            </div>
          )}

          {/* Step 3: Imagen */}
          {currentStep === 2 && (
            <div className="space-y-6">
              <p className="text-slate-600 text-sm leading-relaxed">
                Opcionalmente, puedes subir una foto de tus manos para análisis visual adicional con IA.
                Los metadatos de ubicación son eliminados automáticamente antes del envío.
              </p>

              <div className="border-2 border-dashed border-slate-200 rounded-2xl p-8 text-center hover:border-blue-300 transition-colors">
                <div className="text-4xl mb-3">📷</div>
                <label className="cursor-pointer">
                  <span className="text-blue-700 font-medium hover:underline">
                    {imagePath ? '✅ Imagen subida correctamente' : 'Seleccionar imagen'}
                  </span>
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    onChange={handleImageChange}
                    className="hidden"
                  />
                </label>
                <p className="text-slate-400 text-xs mt-2">JPEG, PNG o WebP · Máximo 10MB</p>
              </div>

              {uploading && (
                <div>
                  <div className="progress-bar">
                    <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
                  </div>
                  <p className="text-sm text-slate-500 mt-1 text-center">Subiendo imagen... {progress}%</p>
                </div>
              )}

              {uploadError && (
                <div className="bg-red-50 border border-red-100 rounded-xl p-4 text-red-700 text-sm">
                  {uploadError}
                </div>
              )}

              <div className="flex justify-between pt-4">
                <button type="button" onClick={handleBack} className="btn-outline">← Atrás</button>
                <button type="button" onClick={() => setCurrentStep(3)} disabled={uploading} className="btn-primary">
                  {imagePath ? 'Continuar →' : 'Omitir imagen →'}
                </button>
              </div>
            </div>
          )}

          {/* Step 4: Consentimiento */}
          {currentStep === 3 && (
            <div className="space-y-6">
              <div className="bg-blue-50 border border-blue-100 rounded-xl p-5 text-sm text-slate-700 leading-relaxed">
                <p className="font-semibold text-blue-900 mb-2">Consentimiento Informado</p>
                <p>
                  Consiento que PrevencionApp procese mis datos de salud con fines de evaluación
                  preventiva de inflamación sinovial. Entiendo que este análisis es orientativo y
                  no reemplaza diagnóstico médico. Mis datos serán tratados conforme al GDPR,
                  Ley 1581 y las políticas de privacidad.
                </p>
              </div>

              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={consentimiento}
                  onChange={(e) => setConsentimiento(e.target.checked)}
                  className="mt-1 w-5 h-5 rounded accent-blue-800"
                />
                <span className="text-slate-700 text-sm">
                  Acepto el consentimiento informado y el tratamiento de mis datos de salud.
                </span>
              </label>

              {error && (
                <div className="bg-red-50 border border-red-100 rounded-xl p-4 text-red-700 text-sm">
                  {error?.response?.data?.message || 'Error al procesar la evaluación. Intente nuevamente.'}
                </div>
              )}

              <div className="flex justify-between pt-4">
                <button type="button" onClick={handleBack} className="btn-outline">← Atrás</button>
                <button
                  type="button"
                  onClick={handleFinalSubmit}
                  disabled={!consentimiento || isLoading}
                  className="btn-primary min-w-[160px]"
                >
                  {isLoading ? (
                    <span className="flex items-center gap-2">
                      <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Analizando...
                    </span>
                  ) : 'Obtener resultado →'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
