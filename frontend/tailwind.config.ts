import type { Config } from "tailwindcss";

/**
 * Palette adapted from healf.com's live design tokens (not copied):
 *  - signature gradient  #32755F → #5377BB → #CB8F51  (their `bg-chat-gradient`)
 *  - accent green #32755F, blue #5377BB, bronze #CB8F51
 *  - Avenir geometric type with tight tracking, clean near-white surfaces, 8px radius.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        cream: "#FBFAF7", // near-white warm surface (Healf leans white/minimal)
        card: "#FFFFFF",
        ink: "#141414", // Healf uses near-black text
        muted: "#6E6E6E",
        line: "#E7E5E0",
        healf: {
          DEFAULT: "#32755F", // signature green
          dark: "#255949",
          soft: "#EBF1EE",
          ring: "#9CBBAF",
          blue: "#5377BB",
          bronze: "#CB8F51",
          gold: "#F9D685",
        },
      },
      fontFamily: {
        sans: [
          "Avenir Next",
          "Avenir",
          "Nunito Sans",
          "Segoe UI",
          "system-ui",
          "-apple-system",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
      letterSpacing: { tight2: "-0.02em", tight3: "-0.03em" },
      borderRadius: { xl2: "0.85rem", xl3: "1.1rem" },
      boxShadow: {
        soft: "0 1px 2px rgba(20,20,20,0.04), 0 8px 24px rgba(20,20,20,0.05)",
        lift: "0 2px 6px rgba(20,20,20,0.06), 0 14px 40px rgba(20,20,20,0.08)",
      },
      backgroundImage: {
        // Healf's signature chat/brand gradient.
        "healf-gradient": "linear-gradient(130.85deg,#32755F 2.89%,#5377BB 43.91%,#CB8F51 77.91%)",
        "healf-gradient-h": "linear-gradient(90deg,#32755F,#5377BB,#CB8F51,#5377BB,#32755F)",
      },
      keyframes: {
        "fade-up": { "0%": { opacity: "0", transform: "translateY(6px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
        pulseDot: { "0%,100%": { opacity: "0.35" }, "50%": { opacity: "1" } },
        "gradient-pan": { "0%,100%": { backgroundPosition: "0% 50%" }, "50%": { backgroundPosition: "100% 50%" } },
      },
      animation: {
        "fade-up": "fade-up 0.28s ease-out",
        "pulse-dot": "pulseDot 1.2s ease-in-out infinite",
        "gradient-pan": "gradient-pan 6s ease infinite",
      },
    },
  },
  plugins: [],
};
export default config;
