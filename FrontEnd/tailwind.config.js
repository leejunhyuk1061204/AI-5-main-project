/** @type {import('tailwindcss').Config} */
module.exports = {
  presets: [require("nativewind/preset")],
  content: ["./**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "primary": "#0d7ff2",
        "primary-glow": "#00f0ff",
        "background-light": "#f5f7f8",
        "background-dark": "#0a1016",
        "deep-black": "#020202",
      },
    },
  },
  plugins: [],
}
