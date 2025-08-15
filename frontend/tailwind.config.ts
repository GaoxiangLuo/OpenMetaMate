import type { Config } from "tailwindcss"

const config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./app/**/*.{ts,tsx}",
    "./src/**/*.{ts,tsx}",
    "*.{js,ts,jsx,tsx,mdx}",
  ],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))", // Maintained for shadcn compatibility
        input: "hsl(var(--input))", // Maintained
        ring: "var(--jhu-light-blue)", // JHU Accent for focus rings
        background: "hsl(var(--background))", // Maintained
        foreground: "hsl(var(--foreground))", // Maintained
        primary: {
          DEFAULT: "var(--jhu-blue)", // JHU Blue
          foreground: "hsl(var(--primary-foreground))", // Typically white or light gray
          jhuBlue: "#002D72",
          jhuLightBlue: "#68ACE5",
        },
        secondary: {
          DEFAULT: "var(--jhu-accent-1)", // JHU Accent Blue
          foreground: "hsl(var(--secondary-foreground))", // Typically white or dark gray
          jhuAccent1: "#0077D8", // Accent Blue
          jhuAccent2: "#4E97E0", // Lighter Accent Blue
          jhuAccent3: "#86C8BC", // Tealish
          jhuAccent4: "#008767", // Green
          jhuAccent5: "#275E3D", // Dark Green
          jhuAccent6: "#76A04C", // Olive Green
          jhuAccent7: "#9E8FB0", // Lavender
          jhuAccent8: "#51284F", // Purple
          jhuAccent9: "#A45C98", // Magenta
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))", // Standard red
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))", // Light gray
          foreground: "hsl(var(--muted-foreground))", // Darker gray
        },
        accent: {
          DEFAULT: "var(--jhu-accent-3)", // JHU Tealish for general accents
          foreground: "hsl(var(--accent-foreground))", // Dark text for tealish bg
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // Define JHU colors as CSS variables for easier use
        "jhu-blue": "var(--jhu-blue)",
        "jhu-light-blue": "var(--jhu-light-blue)",
        "jhu-accent-1": "var(--jhu-accent-1)",
        "jhu-accent-2": "var(--jhu-accent-2)",
        "jhu-accent-3": "var(--jhu-accent-3)",
        "jhu-accent-4": "var(--jhu-accent-4)",
        "jhu-accent-5": "var(--jhu-accent-5)",
        "jhu-accent-6": "var(--jhu-accent-6)",
        "jhu-accent-7": "var(--jhu-accent-7)",
        "jhu-accent-8": "var(--jhu-accent-8)",
        "jhu-accent-9": "var(--jhu-accent-9)",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
      boxShadow: {
        subtle: "0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px 0 rgba(0, 0, 0, 0.03)",
        medium: "0 4px 6px -1px rgba(0, 0, 0, 0.07), 0 2px 4px -1px rgba(0, 0, 0, 0.04)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
} satisfies Config

export default config
