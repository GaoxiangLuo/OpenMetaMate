import type React from "react"

// Updated CodingSchemeItem
export interface CodingSchemeItem {
  id: string
  name: string
  dataType: "Text" | "Numeric" | "Boolean" // Simplified data types
  description: string
  includeInExtraction: boolean // New property
}

export interface ExtractionResultItem {
  value: string | number | boolean // Value can be string, number, or boolean
  confidence: number // A value between 0 and 1
}

export type ExtractionResult = Record<string, ExtractionResultItem>

export interface ChatMessage {
  id: string
  type: "user-upload" | "system" | "error" | "file-info" | "extraction-result"
  content?: string | React.ReactNode
  fileName?: string
  fileSpecificMessage?: string
  data?: ExtractionResult
  timestamp: Date
  isProcessing?: boolean
}

export interface ExtractionHistoryItem {
  id: string
  fileName: string
  data: ExtractionResult
  timestamp: Date
  codingSchemeUsed: CodingSchemeItem[] // Store the exact scheme used for this extraction
}

export interface ProcessedFileResult {
  fileName: string
  status: "success" | "error"
  data?: ExtractionResult
  errorMessage?: string
}
