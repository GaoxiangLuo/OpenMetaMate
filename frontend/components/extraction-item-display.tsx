"use client"

import { useEffect, useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ChevronDown, ChevronUp, Pencil, X, Check, Sparkles } from "lucide-react"
import type { Citation, CodingSchemeItem, ExtractionResultItem } from "@/lib/types"

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
  editable?: boolean
  dataType?: CodingSchemeItem["dataType"]
  onSave?: (updatedItem: ExtractionResultItem) => void
}

export default function ExtractionItemDisplay({
  label,
  item,
  truncateLength = 100,
  onCitationSelect,
  editable = false,
  dataType,
  onSave,
}: ExtractionItemDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [draftValue, setDraftValue] = useState("")
  const [draftAnswerType, setDraftAnswerType] = useState<ExtractionResultItem["answerType"]>(item.answerType)
  const [draftReasoning, setDraftReasoning] = useState(item.reasoning ?? "")
  const [error, setError] = useState<string | null>(null)

  const dataKind = dataType ?? "Text"
  const canEdit = editable && typeof onSave === "function"

  const valueAsString = Array.isArray(item.value)
    ? item.value.join("; ")
    : item.value === null || item.value === undefined
      ? ""
      : String(item.value)
  const isLongText = typeof item.value === "string" && item.value && item.value.length > truncateLength

  const displayedValue = isLongText && !isExpanded ? `${valueAsString.substring(0, truncateLength)}...` : valueAsString
  const renderedValue = displayedValue === "" ? "—" : displayedValue

  const parsedBooleanValue = useMemo(() => {
    if (typeof item.value === "boolean") {
      return item.value
    }
    if (typeof item.value === "string") {
      if (item.value.toLowerCase() === "true") return true
      if (item.value.toLowerCase() === "false") return false
    }
    return undefined
  }, [item.value])

  useEffect(() => {
    setDraftAnswerType(item.answerType)
    setDraftReasoning(item.reasoning ?? "")
    setDraftValue(dataKind === "Boolean" ? String(parsedBooleanValue ?? "") : valueAsString)
    setError(null)
    setIsEditing(false)
  }, [valueAsString, item.answerType, item.reasoning, dataKind, parsedBooleanValue])

  const resetEditingState = () => {
    setDraftAnswerType(item.answerType)
    setDraftReasoning(item.reasoning ?? "")
    setDraftValue(dataKind === "Boolean" ? String(parsedBooleanValue ?? "") : valueAsString)
    setError(null)
    setIsEditing(false)
  }

  const handleSave = () => {
    if (!canEdit || !onSave) {
      return
    }

    const nextItem: ExtractionResultItem = {
      ...item,
      manualOverride: true,
    }

    if (draftAnswerType === "Not Found") {
      nextItem.value = "Not Found"
      nextItem.answerType = "Not Found"
      nextItem.reasoning = null
      nextItem.citations = []
      nextItem.confidence = null
      onSave(nextItem)
      resetEditingState()
      return
    }

    if (dataKind === "Numeric") {
      const trimmed = draftValue.trim()
      if (trimmed === "") {
        setError("Please enter a numeric value.")
        return
      }
      const parsed = Number.parseFloat(trimmed)
      if (Number.isNaN(parsed)) {
        setError("Invalid number format.")
        return
      }
      nextItem.value = parsed
    } else if (dataKind === "Boolean") {
      if (draftValue !== "true" && draftValue !== "false") {
        setError("Select true or false.")
        return
      }
      nextItem.value = draftValue === "true"
    } else {
      const normalized = draftValue.trim()
      nextItem.value = normalized
    }

    nextItem.answerType = draftAnswerType
    nextItem.citations = draftAnswerType === "Grounded" ? item.citations : []
    nextItem.confidence = draftAnswerType === "Grounded" ? item.confidence : null
    nextItem.reasoning = draftAnswerType === "Inference" ? draftReasoning.trim() || null : null

    onSave(nextItem)
    resetEditingState()
  }

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
              {item.answerType === "Grounded" ? "Direct Evidence" : item.answerType}
            </span>
            {item.manualOverride && (
              <span className="ml-1 inline-flex items-center gap-1 rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-amber-700">
                <Sparkles className="h-3 w-3" /> Manual Override
              </span>
            )}
          </div>
        </div>
        <div className="flex items-start gap-1">
          {typeof item.confidence === "number" &&
            item.confidence !== null &&
            item.confidence >= 0 &&
            item.value !== "Not Found" && <ConfidenceIndicator score={item.confidence} />}
          {canEdit && !isEditing && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => {
                setIsEditing(true)
                setDraftValue(
                  dataKind === "Boolean"
                    ? String(parsedBooleanValue ?? "")
                    : dataKind === "Numeric"
                      ? valueAsString
                      : valueAsString,
                )
              }}
              className="h-7 w-7 text-primary-jhuBlue dark:text-primary-jhuLightBlue"
              title="Edit value"
            >
              <Pencil className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
      {!(item.answerType === "Not Found" && valueAsString === "Not Found") && (
        <div className="mt-1 text-slate-800 dark:text-slate-100 break-words whitespace-pre-wrap">{renderedValue}</div>
      )}
      {isEditing && canEdit && (
        <div className="mt-3 space-y-2 rounded-md border border-slate-200 bg-white p-3 text-xs shadow-sm dark:border-slate-600 dark:bg-slate-800">
          <div className="grid gap-2">
            <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              Value
            </label>
            {dataKind === "Text" ? (
              <Textarea
                value={draftValue}
                onChange={(event) => setDraftValue(event.target.value)}
                rows={3}
                className="text-xs"
              />
            ) : dataKind === "Numeric" ? (
              <Input
                type="text"
                inputMode="decimal"
                value={draftValue}
                onChange={(event) => setDraftValue(event.target.value)}
                className="text-xs"
              />
            ) : (
              <Select value={draftValue} onValueChange={(value) => setDraftValue(value)}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue placeholder="Select..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="true">True</SelectItem>
                  <SelectItem value="false">False</SelectItem>
                </SelectContent>
              </Select>
            )}
          </div>
          <div className="grid gap-2">
            <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              Answer Type
            </label>
            <Select
              value={draftAnswerType}
              onValueChange={(value: ExtractionResultItem["answerType"]) => setDraftAnswerType(value)}
            >
              <SelectTrigger className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="Grounded">Grounded</SelectItem>
                <SelectItem value="Inference">Inference</SelectItem>
                <SelectItem value="Not Found">Not Found</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {draftAnswerType === "Inference" && (
            <div className="grid gap-2">
              <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Reasoning (optional)
              </label>
              <Textarea
                value={draftReasoning}
                onChange={(event) => setDraftReasoning(event.target.value)}
                rows={2}
                className="text-xs"
              />
            </div>
          )}
          {error && <p className="text-[11px] font-medium text-red-600 dark:text-red-400">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={resetEditingState}
              className="h-7 px-2 text-xs text-slate-600 dark:text-slate-300"
            >
              <X className="mr-1 h-3.5 w-3.5" /> Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleSave}
              className="h-7 bg-primary-jhuBlue px-2 text-xs text-white hover:bg-primary-jhuBlue/90 dark:bg-primary-jhuLightBlue dark:text-primary-jhuBlue"
            >
              <Check className="mr-1 h-3.5 w-3.5" /> Save
            </Button>
          </div>
        </div>
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
