"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { ChevronDown, ChevronUp } from "lucide-react"
import type { Citation, ExtractionResultItem } from "@/lib/types"

const answerTypeStyles: Record<ExtractionResultItem["answerType"], string> = {
  Grounded: "bg-emerald-100 text-emerald-800 border-emerald-300",
  Inference: "bg-amber-100 text-amber-800 border-amber-300",
  "Not Found": "bg-slate-100 text-slate-700 border-slate-300",
}

const ConfidenceIndicator = ({ score }: { score: number }) => {
  const boundedScore = Math.max(0, Math.min(1, score))
  const getColor = () => {
    if (boundedScore >= 0.85) return "bg-green-500"
    if (boundedScore >= 0.65) return "bg-yellow-400"
    return "bg-red-500"
  }
  return (
    <div className="flex items-center gap-1.5 flex-shrink-0 text-slate-600 dark:text-slate-300">
      <div className={`w-2 h-2 rounded-full ${getColor()}`} />
      <span className="text-xs font-mono">{Math.round(boundedScore * 100)}%</span>
    </div>
  )
}

interface ExtractionItemDisplayProps {
  label: string
  item: ExtractionResultItem
  truncateLength?: number
  onCitationSelect?: (citation: Citation, index: number, allCitations: Citation[]) => void
}

export default function ExtractionItemDisplay({
  label,
  item,
  truncateLength = 100,
  onCitationSelect,
}: ExtractionItemDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  const valueAsString = Array.isArray(item.value)
    ? item.value.join("; ")
    : item.value === null || item.value === undefined
      ? ""
      : String(item.value)
  const isLongText = typeof item.value === "string" && item.value && item.value.length > truncateLength

  const displayedValue = isLongText && !isExpanded ? `${valueAsString.substring(0, truncateLength)}...` : valueAsString
  const renderedValue = displayedValue === "" ? "—" : displayedValue

  return (
    <div className="p-2.5 bg-slate-50 dark:bg-slate-800/70 rounded-md border border-slate-200 dark:border-slate-700/50 shadow-sm">
      <div className="flex justify-between items-start gap-2">
        <div>
          <strong className="font-medium text-slate-700 dark:text-slate-200 break-all" title={label}>
            {label}:
          </strong>
          <div className="mt-1">
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full border text-[11px] font-medium uppercase tracking-wide ${answerTypeStyles[item.answerType]}`}
            >
              {item.answerType === "Grounded" ? "Exact Quote" : item.answerType}
            </span>
          </div>
        </div>
        {typeof item.confidence === "number" &&
          item.confidence !== null &&
          item.confidence >= 0 &&
          item.value !== "Not Found" && <ConfidenceIndicator score={item.confidence} />}
      </div>
      {!(item.answerType === "Not Found" && valueAsString === "Not Found") && (
        <div className="mt-1 text-slate-800 dark:text-slate-100 break-words whitespace-pre-wrap">{renderedValue}</div>
      )}
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
      {item.answerType === "Inference" && item.reasoning && (
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 italic">Reasoning: {item.reasoning}</p>
      )}
      {item.citations && item.citations.length > 0 && (
        <div className="mt-2 space-y-1">
          <p className="text-[11px] uppercase tracking-wide text-slate-500 dark:text-slate-400 font-semibold">
            Citations
          </p>
          <div className="space-y-1.5">
            {item.citations.map((citation, index) => (
              <Button
                key={`${citation.pageNumber}-${index}`}
                variant="ghost"
                size="sm"
                className="w-full justify-start items-start text-xs h-auto py-1 px-2 text-primary-jhuBlue dark:text-primary-jhuLightBlue hover:bg-primary-jhuLightBlue/10 dark:hover:bg-primary-jhuBlue/40"
                onClick={() => onCitationSelect?.(citation, index, item.citations)}
              >
                <div className="flex flex-col flex-1 min-w-0 text-left">
                  <span className="font-semibold">Page {citation.pageNumber}</span>
                  {citation.type === "Inference" && citation.reasoning && (
                    <span className="text-left text-[11px] text-slate-500 dark:text-slate-400 italic whitespace-normal break-all">
                      Reasoning: {citation.reasoning}
                    </span>
                  )}
                </div>
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
