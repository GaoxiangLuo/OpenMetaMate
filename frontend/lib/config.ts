// API Configuration
const isDevelopment = process.env.NODE_ENV === "development"

export const config = {
  // API endpoint from environment or local development fallback
  apiUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",

  // File upload limits (must match backend/app/core/config.py)
  MAX_FILE_SIZE_MB: 10,
  MAX_FILES_PER_BATCH: 100,
  ALLOWED_FILE_TYPES: ["application/pdf"],

  // Rate limiting (must match backend EXTRACTION_RATE_LIMIT_PER_MINUTE)
  EXTRACTION_RATE_LIMIT_PER_MINUTE: 20,

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
