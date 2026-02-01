/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: 'rgb(var(--bg) / <alpha-value>)',
        bg2: 'rgb(var(--bg2) / <alpha-value>)',
        card: 'rgb(var(--card) / <alpha-value>)',
        surface: 'rgb(var(--surface) / <alpha-value>)',
        border: 'rgb(var(--border) / <alpha-value>)',
        primary: 'rgb(var(--primary) / <alpha-value>)',
        'primary-hover': 'rgb(var(--primary-hover) / <alpha-value>)',
        text: 'rgb(var(--text) / <alpha-value>)',
        muted: 'rgb(var(--muted) / <alpha-value>)',
        placeholder: 'rgb(var(--placeholder) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['Heebo', 'ui-sans-serif', 'system-ui', 'Segoe UI', 'Arial', 'sans-serif'],
      },
      borderRadius: {
        xl: '16px',
        '2xl': '20px',
        '3xl': '28px',
      },
      boxShadow: {
        card: '0 18px 60px rgba(0,0,0,0.55)',
      },
    },
  },
  plugins: [],
}

