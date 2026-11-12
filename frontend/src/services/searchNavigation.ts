import type {
  RecordSearchHit,
  RegionSearchHit,
  SearchLevel
} from './dataProviders/types'

export type SearchHit = RegionSearchHit | RecordSearchHit

export interface SearchHitRecord {
  entryId: string
  recordId: string
  filename: string
}

export function regionIdFromHit(level: SearchLevel, hit: SearchHit): string {
  if (level === 'record') return ''

  return `region_${(hit as RegionSearchHit).fields.region}`
}

export function recordSelectionFromHit(level: SearchLevel, hit: SearchHit): SearchHitRecord {
  const identity = level === 'region'
    ? (hit as RegionSearchHit).fields
    : (hit as RecordSearchHit)

  return {
    entryId: `${identity.output_file}:${identity.record}`,
    recordId: identity.record,
    filename: identity.output_file
  }
}