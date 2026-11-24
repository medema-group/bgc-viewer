import type {
  ProtoclusterSearchHit,
  RecordSearchHit,
  RegionSearchHit,
  SearchLevel
} from './dataProviders/types'

export type SearchHit = RegionSearchHit | RecordSearchHit | ProtoclusterSearchHit

export interface SearchHitRecord {
  entryId: string
  recordId: string
  filename: string
}

/** The region a hit opens: its own, or a protocluster's parent region; none for a record. */
export function regionIdFromHit(level: SearchLevel, hit: SearchHit): string {
  if (level === 'record') return ''

  return `region_${(hit as RegionSearchHit).fields.region}`
}

/** The protocluster a protocluster hit zooms to; null at the other levels. */
export function protoclusterNumberFromHit(level: SearchLevel, hit: SearchHit): number | null {
  if (level !== 'protocluster') return null

  return (hit as ProtoclusterSearchHit).fields.protocluster_number
}

export function recordSelectionFromHit(level: SearchLevel, hit: SearchHit): SearchHitRecord {
  const identity = level === 'record'
    ? (hit as RecordSearchHit)
    : (hit as RegionSearchHit).fields

  return {
    entryId: `${identity.output_file}:${identity.record}`,
    recordId: identity.record,
    filename: identity.output_file
  }
}
