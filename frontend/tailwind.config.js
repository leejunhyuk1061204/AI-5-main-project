/** @type {import('tailwindcss').Config} */
module.exports = {
  presets: [require("nativewind/preset")],
  content: ["./App.{js,jsx,ts,tsx}", "./**/*.{js,jsx,ts,tsx}", "!./node_modules/**/*"],
  theme: {
    extend: {
      colors: {
        "primary": "#0d7ff2",
        "primary-dark": "#0b6bc9",
        "primary-glow": "#00f0ff",
        "background-light": "#f5f7f8",
        "background-dark": "#101922",
        "surface-dark": "#16212b",
        "input-dark": "#1e2936",
        "input-border": "#2d3b4e",
        "text-secondary": "#94a3b8",
        "deep-black": "#020202",
        "surface-highlight": "#232d3a",
        "primary-hover": "#0b6bcb",
        "border-dark": "#2A3441",
      },
    },
  },
  plugins: [],
}
