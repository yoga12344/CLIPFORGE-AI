/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#09090b",
        foreground: "#f4f4f5",
        card: "#121217",
        border: "#27272a",
        primary: {
          DEFAULT: "#8b5cf6",
          hover: "#7c3aed",
        },
        accent: {
          yellow: "#facc15",
          green: "#22c55e",
        }
      },
    },
  },
  plugins: [],
};
