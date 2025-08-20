// API Configuration
const isDevelopment = process.env.NODE_ENV === "development"

export const config = {
  // API endpoint from Lightsail container or local development
  apiUrl:
    process.env.NEXT_PUBLIC_API_URL ||
    (isDevelopment
      ? "http://localhost:8000"
      : "https://metamate-backend.abbcgm4kk31mw.us-east-1.cs.amazonlightsail.com"),

  // File upload limits
  MAX_FILE_SIZE_MB: 10,
  MAX_FILES_PER_BATCH: 100,
  ALLOWED_FILE_TYPES: ["application/pdf"],

  // UI Configuration
  CONFIDENCE_THRESHOLDS: {
    HIGH: 0.8,
    MEDIUM: 0.6,
    LOW: 0.4,
  },

  // Development flags
  isDevelopment,
  isProduction: process.env.NODE_ENV === "production",
}

export default config
