/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        unilog: {
          bg: '#0f1115',
          bgElevated: '#161a1f',
          border: '#2a2f3a',
          borderHover: '#3a4150',
          text: '#e8eaed',
          textMuted: '#8b919a',
          accent: '#00b4d8',
          accentHover: '#0090b0',
          accentSoft: '#00b4d81a',
          success: '#10b981',
          successSoft: '#10b9811a',
          warning: '#f59e0b',
          warningSoft: '#f59e0b1a',
          error: '#ef4444',
          errorSoft: '#ef44441a',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      fontSize: {
        'display': ['44px', { lineHeight: '1.1', letterSpacing: '-0.02em', fontWeight: '600' }],
        'h1': ['32px', { lineHeight: '1.2', letterSpacing: '-0.01em', fontWeight: '600' }],
        'h2': ['24px', { lineHeight: '1.3', letterSpacing: '-0.01em', fontWeight: '600' }],
        'h3': ['20px', { lineHeight: '1.4', fontWeight: '500' }],
        'body': ['15px', { lineHeight: '1.6' }],
        'body-sm': ['13px', { lineHeight: '1.5' }],
        'caption': ['12px', { lineHeight: '1.4' }],
      },
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
      },
      boxShadow: {
        'subtle': '0 1px 3px rgba(0,0,0,0.3), 0 1px 2px rgba(0,0,0,0.2)',
        'card': '0 4px 12px rgba(0,0,0,0.25), 0 2px 4px rgba(0,0,0,0.15)',
        'elevated': '0 8px 24px rgba(0,0,0,0.3), 0 4px 8px rgba(0,0,0,0.2)',
      },
      borderRadius: {
        'lg': '8px',
        'xl': '12px',
      },
      transitionDuration: {
        'fast': '120ms',
        'normal': '200ms',
      },
      transitionTimingFunction: {
        'ease-out-quart': 'cubic-bezier(0.25, 1, 0.5, 1)',
      },
    },
  },
  plugins: [],
}