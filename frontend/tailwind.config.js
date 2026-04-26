/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#0EA5A6',
        secondary: '#F97316',
        background: '#081018',
        surface: '#13202B',
        accent: '#FACC15'
      }
    },
  },
  plugins: [],
}
