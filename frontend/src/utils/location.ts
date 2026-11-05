export interface LocationPart {
  start: number
  end: number
}

export interface ParsedLocation extends LocationPart {
  strand: string | null
  parts: LocationPart[]
}

const LOCATION_PART = /\[[<>]?(\d+):[<>]?(\d+)\](?:\(([+-])\))?/g

// Parts are listed in transcription order, so they normally ascend on the forward
// strand and descend on the reverse strand. Out of order parts that include
// position 0 wrap around the origin of a circular record.
const crossesOrigin = (parts: LocationPart[], strand: string | null): boolean => {
  const starts = parts.map(part => part.start)
  const inOrder = [...starts].sort((a, b) => (strand === '-' ? b - a : a - b))
  return starts.includes(0) && starts.some((start, i) => start !== inOrder[i])
}

/**
 * Parse location string like "[164:2414](+)" or
 * "join{[9388:10393](+), [10457:21546](+)}".
 * A compound location covers its entire span, including introns. A location that
 * crosses the origin has no single span, so only its first part is used.
 */
export function parseLocation(location?: string | null): ParsedLocation | null {
  if (!location) return null
  const matches = [...location.matchAll(LOCATION_PART)]
  if (matches.length === 0) return null

  const strand = matches[0][3] || null
  const parts = matches.map(match => ({ start: parseInt(match[1]), end: parseInt(match[2]) }))
  if (crossesOrigin(parts, strand)) {
    return { ...parts[0], strand, parts: [parts[0]] }
  }

  return {
    start: Math.min(...parts.map(part => part.start)),
    end: Math.max(...parts.map(part => part.end)),
    strand,
    parts
  }
}

/**
 * Format location string for display, like "165 - 2,414, + (total: 2,250 nt)"
 * or "9,389 - 21,912, + (total: 12129 nt, excluding introns)"
 * Locations are 0-based with an exclusive end, whereas the display is 1-based with
 * an inclusive end, so only the start changes.
 */
export function formatLocation(location?: string | null): string {
  if (!location) return ''

  const parsed = parseLocation(location)
  if (!parsed) return location

  const { start, end, strand, parts } = parsed
  const range = `${(start + 1).toLocaleString()} - ${end.toLocaleString()}${strand ? ', ' + strand : ''}`

  if (parts.length > 1) {
    const total = parts.reduce((sum, part) => sum + part.end - part.start, 0)
    return `${range} (total: ${total} nt, excluding introns)`
  }

  const length = end - start
  return `${range} (total: ${length.toLocaleString()} nt)`
}
