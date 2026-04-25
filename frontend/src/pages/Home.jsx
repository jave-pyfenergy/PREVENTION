import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export default function Home() {
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-teal-50">
      {/* Navbar */}
      <nav className="fixed top-0 w-full bg-white/80 backdrop-blur-sm border-b border-slate-100 z-50">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-blue-800 rounded-lg flex items-center justify-center">
              <span className="text-white text-xs font-bold">PA</span>
            </div>
            <span className="font-display font-bold text-blue-900 text-lg">PrevencionApp</span>
          </div>
          <div className="flex items-center gap-3">
            {isAuthenticated ? (
              <button onClick={() => navigate('/dashboard')} className="btn-primary text-sm py-2">
                Mi Dashboard
              </button>
            ) : (
              <>
                <button onClick={() => navigate('/login')} className="btn-outline text-sm py-2">
                  Iniciar sesión
                </button>
                <button onClick={() => navigate('/formulario')} className="btn-primary text-sm py-2">
                  Comenzar evaluación
                </button>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-4xl mx-auto text-center animate-fade-in">
          <div className="inline-flex items-center gap-2 bg-blue-100 text-blue-800 text-sm font-medium px-4 py-2 rounded-full mb-6">
            <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse-soft" />
            Detección temprana · Reumatología preventiva
          </div>

          <h1 className="text-5xl md:text-6xl font-bold text-slate-900 mb-6 leading-tight">
            Detecta inflamación
            <span className="text-blue-800 block">sinovial a tiempo</span>
          </h1>

          <p className="text-xl text-slate-600 mb-10 max-w-2xl mx-auto leading-relaxed">
            Completa un formulario clínico, sube una foto de tus manos y recibe
            un análisis de riesgo impulsado por inteligencia artificial en segundos.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <button
              onClick={() => navigate('/formulario')}
              className="btn-primary text-lg px-8 py-4"
            >
              Iniciar evaluación gratuita →
            </button>
            <button
              onClick={() => navigate('/login')}
              className="btn-outline text-lg px-8 py-4"
            >
              Ver mi historial
            </button>
          </div>

          <p className="text-sm text-slate-400 mt-4">
            Sin registro previo · Resultado en menos de 30 segundos
          </p>
        </div>
      </section>

      {/* Features */}
      <section className="pb-24 px-6">
        <div className="max-w-5xl mx-auto grid md:grid-cols-3 gap-6">
          {[
            {
              icon: '🔬',
              title: 'Análisis con IA',
              desc: 'Modelos de machine learning entrenados con datos clínicos reales de reumatología.',
            },
            {
              icon: '🔒',
              title: 'Privacidad total',
              desc: 'Privacy by Design. Tus datos se hashean y tus imágenes se procesan sin metadatos de ubicación.',
            },
            {
              icon: '📊',
              title: 'Mapa de calor visual',
              desc: 'Visualización Grad-CAM que muestra exactamente qué zonas de la imagen activaron el modelo.',
            },
          ].map((f, i) => (
            <div key={i} className="card text-center hover:shadow-lg transition-shadow">
              <div className="text-4xl mb-4">{f.icon}</div>
              <h3 className="font-bold text-slate-800 text-lg mb-2">{f.title}</h3>
              <p className="text-slate-500 text-sm leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Disclaimer */}
      <footer className="border-t border-slate-200 py-8 px-6">
        <p className="text-center text-xs text-slate-400 max-w-2xl mx-auto">
          PrevencionApp es una herramienta de apoyo diagnóstico. No reemplaza la consulta
          médica profesional. Siempre consulte a un reumatólogo para diagnóstico y tratamiento.
        </p>
      </footer>
    </div>
  )
}
