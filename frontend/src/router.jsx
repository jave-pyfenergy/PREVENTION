import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'

// Pages (lazy-loaded para code splitting)
import { lazy, Suspense } from 'react'
import { Spinner } from './components/common/Spinner'

const Home = lazy(() => import('./pages/Home'))
const Formulario = lazy(() => import('./pages/Formulario'))
const Resultado = lazy(() => import('./pages/Resultado'))
const Registro = lazy(() => import('./pages/Registro'))
const Login = lazy(() => import('./pages/Login'))
const Dashboard = lazy(() => import('./pages/Dashboard'))

/**
 * Ruta protegida — requiere autenticación.
 */
function ProtectedRoute({ children }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated())
  const isLoading = useAuthStore((s) => s.isLoading)

  if (isLoading) return <Spinner />
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return children
}

const router = createBrowserRouter([
  {
    path: '/',
    element: (
      <Suspense fallback={<Spinner />}>
        <Home />
      </Suspense>
    ),
  },
  {
    path: '/formulario',
    element: (
      <Suspense fallback={<Spinner />}>
        <Formulario />
      </Suspense>
    ),
  },
  {
    path: '/resultado/:sessionId',
    element: (
      <Suspense fallback={<Spinner />}>
        <Resultado />
      </Suspense>
    ),
  },
  {
    path: '/registro',
    element: (
      <Suspense fallback={<Spinner />}>
        <Registro />
      </Suspense>
    ),
  },
  {
    path: '/login',
    element: (
      <Suspense fallback={<Spinner />}>
        <Login />
      </Suspense>
    ),
  },
  {
    path: '/dashboard',
    element: (
      <Suspense fallback={<Spinner />}>
        <ProtectedRoute>
          <Dashboard />
        </ProtectedRoute>
      </Suspense>
    ),
  },
  // Catch-all
  { path: '*', element: <Navigate to="/" replace /> },
])

export default function AppRouter() {
  return <RouterProvider router={router} />
}
