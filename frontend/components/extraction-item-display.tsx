"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { ChevronDown, ChevronUp } from "lucide-react"
import type { ExtractionResultItem } from "@/lib/types"

const ConfidenceIndicator = ({ score }: { score: number }) => {
  const getColor = () => {
    if (score >= 0.9) return "bg-green-500" // Adjusted threshold
    if (score >= 0.75) return "bg-yellow-400" // Adjusted threshold
    return "bg-red-500"
  }
  return (
    <div className="flex items-center gap-1.5 flex-shrink-0">
      <div className={`w-2 h-2 rounded-full ${getColor()}`} />
      <span className="text-xs font-mono text-slate-500 dark:text-slate-400">{(score * 100).toFixed(0)}%</span>
    </div>
  )
}

interface ExtractionItemDisplayProps {
  label: string
  item: ExtractionResultItem
  truncateLength?: number
}

export default function ExtractionItemDisplay({ label, item, truncateLength = 100 }: ExtractionItemDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  const valueAsString = Array.isArray(item.value) ? item.value.join("; ") : String(item.value)
  const isLongText = typeof item.value === "string" && item.value.length > truncateLength

  const displayedValue = isLongText && !isExpanded ? `${valueAsString.substring(0, truncateLength)}...` : valueAsString

  // Don't show confidence indicator for "Not Found" items
  const shouldShowConfidence = item.confidence !== null && item.value !== "Not Found"

  return (
    <div className="p-2.5 bg-slate-50 dark:bg-slate-800/70 rounded-md border border-slate-200 dark:border-slate-700/50 shadow-sm">
      <div className="flex justify-between items-start gap-2">
        <strong className="font-medium text-slate-700 dark:text-slate-200 break-all" title={label}>
          {label}:
        </strong>
        {shouldShowConfidence && <ConfidenceIndicator score={item.confidence} />}
      </div>
      <div className="mt-1 text-slate-800 dark:text-slate-100 break-words whitespace-pre-wrap">{displayedValue}</div>
      {isLongText && (
        <Button
          variant="link"
          size="sm"
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-xs h-auto p-0 mt-1 text-primary-jhuBlue dark:text-primary-jhuLightBlue hover:text-primary-jhuBlue/80 dark:hover:text-primary-jhuLightBlue/80"
        >
          {isExpanded ? "Show less" : "Show more"}
          {isExpanded ? <ChevronUp className="ml-1 h-3 w-3" /> : <ChevronDown className="ml-1 h-3 w-3" />}
        </Button>
      )}
    </div>
  )
}
