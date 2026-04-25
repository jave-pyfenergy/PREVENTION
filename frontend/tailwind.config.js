/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['Outfit', 'system-ui', 'sans-serif'],
        body: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        primary: {
          50:  '#eff6ff',
          100: '#dbeafe',
          800: '#0f4c81',
          900: '#083460',
        },
        riesgo: {
          bajo:     '#22c55e',
          moderado: '#f59e0b',
          alto:     '#ef4444',
          critico:  '#7c3aed',
        },
      },
      borderRadius: {
        xl:  '0.75rem',
        '2xl': '1.25rem',
        '3xl': '2rem',
      },
      boxShadow: {
        card:     '0 4px 24px rgba(15, 76, 129, 0.08)',
        elevated: '0 8px 40px rgba(15, 76, 129, 0.14)',
      },
    },
  },
  plugins: [],
}
