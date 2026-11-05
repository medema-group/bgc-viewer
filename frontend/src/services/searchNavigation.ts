import type {
  ProtoclusterSearchHit,
  RecordSearchHit,
  RegionSearchHit,
  SearchLevel
} from './dataProviders/types'

export type SearchHit = ProtoclusterSearchHit | RegionSearchHit | RecordSearchHit

export interface SearchHitRecord {
  entryId: string
  recordId: string
  filename: string
}

export function regionIdFromHit(level: SearchLevel, hit: SearchHit): string {
  if (level === 'record') return ''

  const region = level === 'protocluster'
    ? (hit as ProtoclusterSearchHit).fields.region
    : (hit as RegionSearchHit).region

  return `region_${region}`
}

export function protoclusterNumberFromHit(level: SearchLevel, hit: SearchHit): number | null {
  return level === 'protocluster'
    ? (hit as ProtoclusterSearchHit).fields.protocluster
    : null
}

export function recordSelectionFromHit(level: SearchLevel, hit: SearchHit): SearchHitRecord {
  const identity = level === 'protocluster'
    ? (hit as ProtoclusterSearchHit).fields
    : (hit as RegionSearchHit | RecordSearchHit)

  return {
    entryId: `${identity.output_file}:${identity.record}`,
    recordId: identity.record,
    filename: identity.output_file
  }
}