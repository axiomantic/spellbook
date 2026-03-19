/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'bg-primary': '#050505',
        'bg-surface': '#0e0e0e',
        'bg-elevated': '#161616',
        'bg-border': '#2a2a2a',
        'text-primary': '#f0ebe4',
        'text-secondary': '#a09a90',
        'text-dim': '#787068',
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
