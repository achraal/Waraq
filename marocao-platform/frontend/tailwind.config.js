/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: "#7e0001",
        "on-primary": "#ffffff",
        "primary-container": "#aa0003",
        "on-primary-container": "#ffb4a9",
        "primary-fixed": "#ffdad5",
        "primary-fixed-dim": "#ffb4a9",
        "on-primary-fixed": "#410000",
        "on-primary-fixed-variant": "#930002",
        "inverse-primary": "#ffb4a9",

        secondary: "#ae2f34",
        "on-secondary": "#ffffff",
        "secondary-container": "#ff6b6b",
        "on-secondary-container": "#6d0010",
        "secondary-fixed": "#ffdad8",
        "secondary-fixed-dim": "#ffb3b0",
        "on-secondary-fixed": "#410006",
        "on-secondary-fixed-variant": "#8c1520",

        tertiary: "#453a2a",
        "on-tertiary": "#ffffff",
        "tertiary-container": "#5d513f",
        "on-tertiary-container": "#d5c4ae",
        "tertiary-fixed": "#f2e0c8",
        "tertiary-fixed-dim": "#d5c4ad",
        "on-tertiary-fixed": "#231a0c",
        "on-tertiary-fixed-variant": "#504534",

        surface: "#fcf9f8",
        "on-surface": "#1c1b1b",
        "surface-bright": "#fcf9f8",
        "surface-dim": "#dcd9d9",
        "surface-variant": "#e5e2e1",
        "on-surface-variant": "#5c403c",
        "surface-tint": "#bc160f",

        "surface-container-lowest": "#ffffff",
        "surface-container-low": "#f6f3f2",
        "surface-container": "#f0eded",
        "surface-container-high": "#eae7e7",
        "surface-container-highest": "#e5e2e1",

        "inverse-surface": "#313030",
        "inverse-on-surface": "#f3f0ef",

        background: "#fcf9f8",
        "on-background": "#1c1b1b",

        outline: "#906f6a",
        "outline-variant": "#e5bdb7",

        error: "#ba1a1a",
        "on-error": "#ffffff",
        "error-container": "#ffdad6",
        "on-error-container": "#93000a",
      },
      borderRadius: {
        DEFAULT: "0.125rem",
        lg: "0.25rem",
        xl: "0.5rem",
        full: "0.75rem",
      },
      spacing: {
        gutter: "12px",
        "dense-gap": "4px",
        "container-padding": "16px",
        margin: "24px",
        "base-unit": "4px",
        "element-gap": "8px",
      },
      fontFamily: {
        sans: ["'Geist Sans'", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
    },
  },
  plugins: [],
};