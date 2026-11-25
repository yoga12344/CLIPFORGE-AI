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
        background: '#0e0e13',
        surface: '#15151c',
        'surface-elevated': '#1c1c26',
        border: '#272736',
        'border-subtle': '#1f1f2b',
        primary: {
          DEFAULT: '#6366f1',
          hover: '#4f46e5',
        },
        accent: '#8b5cf6',
      },
    },
  },
  plugins: [],
}
