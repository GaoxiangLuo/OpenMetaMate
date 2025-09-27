import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Roman numeral utilities
const ROMAN_PATTERN = /^[ivxlcdm]+$/i
const ROMAN_VALUES: Record<string, number> = {
  I: 1,
  V: 5,
  X: 10,
  L: 50,
  C: 100,
  D: 500,
  M: 1000,
}

export function romanToInt(value: string): number | null {
  if (!value) return null

  let total = 0
  let previous = 0

  for (let i = value.length - 1; i >= 0; i -= 1) {
    const current = ROMAN_VALUES[value[i]]
    if (!current) {
      return null
    }

    if (current < previous) {
      total -= current
    } else {
      total += current
      previous = current
    }
  }

  return total
}

export function extractLabelCandidates(label: string | null | undefined): number[] {
  if (!label) return []

  const candidates = new Set<number>()
  const digitMatches = label.match(/\d+/g)

  if (digitMatches) {
    digitMatches.forEach((match) => {
      const parsed = Number.parseInt(match, 10)
      if (!Number.isNaN(parsed) && parsed > 0) {
        candidates.add(parsed)
      }
    })
  }

  const romanMatches = label.match(/\b[ivxlcdm]+\b/gi)
  if (romanMatches) {
    romanMatches.forEach((match) => {
      if (ROMAN_PATTERN.test(match)) {
        const parsed = romanToInt(match.toUpperCase())
        if (parsed && parsed > 0) {
          candidates.add(parsed)
        }
      }
    })
  }

  return Array.from(candidates)
}
