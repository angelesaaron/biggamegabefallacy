import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        sr: {
          bg:             "#0a0a0a",
          surface:        "#111827",
          "surface-raised":"#1a2332",
          primary:        "#a855f7",
          "primary-muted":"#7c3aed",
          success:        "#10b981",
          danger:         "#f43f5e",
          ev:             "#d97706",
          border:         "#1f2937",
          text:           "#ffffff",
          "text-primary": "#f9fafb",
          "text-muted":   "#9ca3af",
          "text-dim":     "#6b7280",
          "text-disabled":"#374151",
        },
      },
      borderRadius: {
        card:  "1rem",
        badge: "9999px",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
