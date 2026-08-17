import type { Config } from "tailwindcss";

// "Factory Floor" design system - a dark control-room aesthetic for
// watching autonomous agents work, deliberately not a generic SaaS
// admin-dashboard palette. See docs/16-frontend.md for the full rationale.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        base: "#0A0D12",
        surface: "#12161D",
        "surface-raised": "#171C25",
        "surface-hover": "#1D2330",
        border: {
          DEFAULT: "#232937",
          subtle: "#1A1F2B",
        },
        text: {
          primary: "#E8EAED",
          secondary: "#8B93A7",
          tertiary: "#5B6478",
        },
        brass: {
          DEFAULT: "#E8A33D",
          dim: "#8A6529",
          glow: "#F5C773",
        },
        signal: {
          DEFAULT: "#3DDBD9",
          dim: "#1F7A79",
        },
        status: {
          success: "#5FBD8A",
          "success-dim": "#2E5C42",
          failure: "#E8615F",
          "failure-dim": "#6B2E2D",
          pending: "#6B7280",
          blocked: "#C77D4F",
          "blocked-dim": "#5C3B24",
        },
      },
      fontFamily: {
        display: ["'Space Grotesk'", "system-ui", "sans-serif"],
        sans: ["'IBM Plex Sans'", "system-ui", "sans-serif"],
        mono: ["'IBM Plex Mono'", "ui-monospace", "monospace"],
      },
      borderRadius: {
        DEFAULT: "4px",
        sm: "3px",
        md: "6px",
        lg: "8px",
      },
      boxShadow: {
        glow: "0 0 12px 1px var(--tw-shadow-color)",
      },
      keyframes: {
        "pulse-signal": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
        "tick-in": {
          "0%": { transform: "translateY(4px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
      },
      animation: {
        "pulse-signal": "pulse-signal 1.6s ease-in-out infinite",
        "tick-in": "tick-in 0.15s ease-out",
      },
    },
  },
  plugins: [],
} satisfies Config;
