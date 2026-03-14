/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'bg-primary': '#0a0a0a',
        'bg-surface': '#141414',
        'bg-elevated': '#1a1a1a',
        'bg-border': '#2a2a2a',
        'text-primary': '#e8e0d0',
        'text-secondary': '#8a8478',
        'text-dim': '#5a5650',
        'accent-green': '#b4f461',
        'accent-cyan': '#61f4e8',
        'accent-amber': '#f4c761',
        'accent-red': '#f46161',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
