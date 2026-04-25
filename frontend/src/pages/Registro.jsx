import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useVincularEvaluacion } from '../hooks/useEvaluacion'

export default function Registro() {
  const navigate = useNavigate()
  const { signUp } = useAuth()
  const { vincular, hasPendingEvaluacion } = useVincularEvaluacion()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    if (password !== confirm) { setError('Las contraseñas no coinciden'); return }
    if (password.length < 8) { setError('La contraseña debe tener mínimo 8 caracteres'); return }

    setLoading(true)
    try {
      await signUp(email, password)
      // Vincular evaluación si hay pendiente
      if (hasPendingEvaluacion) {
        try { await vincular() } catch {} // No bloquear el registro si falla
      }
      setSuccess(true)
    } catch (err) {
      setError(err.message || 'Error al crear la cuenta')
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center px-4">
        <div className="card max-w-md w-full text-center">
          <div className="text-5xl mb-4">✅</div>
          <h2 className="text-2xl font-bold text-slate-800 mb-2">¡Cuenta creada!</h2>
          <p className="text-slate-500 mb-6">
            Revisa tu correo para confirmar tu cuenta y luego inicia sesión.
          </p>
          <button onClick={() => navigate('/login')} className="btn-primary w-full">
            Ir a iniciar sesión
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-blue-900">Crear cuenta</h1>
          <p className="text-slate-500 mt-2">Guarda tu historial de evaluaciones</p>
          {hasPendingEvaluacion && (
            <div className="mt-3 bg-green-100 text-green-800 text-sm px-4 py-2 rounded-xl">
              ✅ Tu evaluación reciente se vinculará a tu nueva cuenta.
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} className="card space-y-4">
          <div>
            <label className="label">Correo electrónico</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              className="input-field" placeholder="tu@email.com" required />
          </div>
          <div>
            <label className="label">Contraseña (mínimo 8 caracteres)</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              className="input-field" placeholder="••••••••" required />
          </div>
          <div>
            <label className="label">Confirmar contraseña</label>
            <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)}
              className="input-field" placeholder="••••••••" required />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-100 rounded-xl p-3 text-red-700 text-sm">{error}</div>
          )}

          <button type="submit" disabled={loading} className="btn-primary w-full">
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Creando cuenta...
              </span>
            ) : 'Crear cuenta →'}
          </button>

          <p className="text-center text-sm text-slate-500">
            ¿Ya tienes cuenta?{' '}
            <Link to="/login" className="text-blue-700 font-medium hover:underline">Iniciar sesión</Link>
          </p>
        </form>
      </div>
    </div>
  )
}
