/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
      },
      colors: {
        energy: {
          hydro: "#0284c7",
          coal: "#d97706",
          oil: "#ea580c",
          nuclear: "#4f46e5",
          gas: "#059669",
          deficit: "#dc2626",
        },
      },
    },
  },
  plugins: [],
};
