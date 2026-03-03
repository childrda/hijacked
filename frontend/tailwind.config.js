/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        teal: {
          600: '#0d9488',
          700: '#0f766e',
        },
      },
    },
  },
  plugins: [],
}
