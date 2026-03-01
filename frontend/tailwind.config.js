/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        blueprint: "#1a3a6d",
        "blueprint-dark": "#0f2955",
        "blueprint-light": "#2c5392",
        accent: "#ff8c00",
        "accent-hover": "#e67e00",
        cream: "#f5f5dc",
        "cream-dark": "#e3e3c1",
      },
      fontFamily: {
        game: ['"Outfit"', "ui-sans-serif", "system-ui", "sans-serif"],
      },
      animation: {
        swoosh: "swoosh 0.6s cubic-bezier(0.22, 1, 0.36, 1) forwards",
        toast: "slideIn 0.4s cubic-bezier(0.22, 1, 0.36, 1) forwards",
        "pulse-border": "pulseBorder 2s infinite",
      },
      keyframes: {
        swoosh: {
          "0%": { transform: "translateX(-40px) scale(0.95)", opacity: "0" },
          "100%": { transform: "translateX(0) scale(1)", opacity: "1" },
        },
        slideIn: {
          "0%": { transform: "translateY(-20px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        pulseBorder: {
          "0%, 100%": { borderColor: "rgba(255, 140, 0, 0.3)" },
          "50%": { borderColor: "rgba(255, 140, 0, 1)" },
        },
      },
    },
  },
  plugins: [],
};
