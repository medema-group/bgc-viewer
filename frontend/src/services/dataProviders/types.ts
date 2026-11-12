/**
 * Base interface for BGC data providers
 * 
 * This defines the contract that all data providers must implement,
 * allowing the viewer to work with different data sources (API, files, etc.)
 */

export interface RecordInfo {
  entryId?: string  // Full unique ID (e.g., "filename:recordId") for API calls
  recordId: string  // Display name / short ID
  filename: string
  fileMetadata?: Record<string, string>  // version, input_file, etc.
  recordInfo: {
    description?: string
  }
}

export interface Region {
  id: string
  region_number: number
  product: string[]
  start?: number
  end?: number
}

export interface Feature {
  type: string
  location: string
  qualifiers?: Record<string, any>
  [key: string]: any
}

export interface RegionBoundaries {
  start: number
  end: number
}

export interface MiBIGEntry {
  mibig_protein: string
  description: string
  mibig_cluster: string
  rank: number
  mibig_product: string
  percent_identity: number
  blast_score: number
  percent_coverage: number
  evalue: number
}

export interface MiBIGEntriesResponse {
  record_id: string
  locus_tag: string
  count: number
  entries: MiBIGEntry[]
}

export interface TFBSHit {
  name: string
  start: number
  species: string
  link: string
  description: string
  consensus: string
  confidence: string
  strand: number
  score: number
  max_score: number
}

export interface TFBSHitsResponse {
  record_id: string
  region: string
  count: number
  hits: TFBSHit[]
}

export interface TTACodon {
  start: number
  strand: number
}

export interface TTACodonsResponse {
  record_id: string
  count: number
  codons: TTACodon[]
}

export interface ResistanceFeature {
  locus_tag: string
  query_id: string
  reference_id: string
  subfunctions: string[]
  description: string
  bitscore: number
  evalue: number
  query_start: number
  query_end: number
}

export interface ResistanceFeaturesResponse {
  record_id: string
  count: number
  features: ResistanceFeature[]
}

export interface FeaturesResponse {
  features: Feature[]
  region_boundaries?: RegionBoundaries
}

export interface RegionsResponse {
  regions: Region[]
}

export type PfamColorMap = Record<string, string>

export type SearchLevel = 'region' | 'record'

export interface SearchFieldInfo {
  name: string
  kind: 'exact' | 'full_text' | 'numeric' | 'path' | 'boolean'
  label: string
  group: string
  multi: boolean
  default_search: boolean
  description: string
  /** Structured-filter operators the field supports. */
  operators: FilterOperator[]
  /** Whether the field's values can be counted and suggested. */
  facet: boolean
  /** Whether hits can be sorted by the field. */
  sortable: boolean
}

export interface SearchSchema {
  fields: SearchFieldInfo[]
  examples: string[]
  query_syntax_url: string
  /** Pseudo-field of a filter condition that runs a query string. */
  raw_query_field: string
}

export type FilterOperator =
  | 'in' | 'not_in' | 'equals' | 'not_equals'
  | 'contains' | 'not_contains' | 'starts_with' | 'ends_with'
  | 'gt' | 'gte' | 'lt' | 'lte' | 'between'
  | 'exists' | 'not_exists'
  | 'matches'

export type FilterValue = string | number | null | (string | number | null)[]

/** One field/operator/value comparison of a structured filter (BGC Atlas model). */
export interface FilterCondition {
  id?: string
  field: string
  operator: FilterOperator
  value?: FilterValue
}

/** Conditions and nested groups joined by one operator. */
export interface FilterGroup {
  id?: string
  operator: 'AND' | 'OR'
  conditions: FilterCondition[]
  groups: FilterGroup[]
}

export interface FacetBucket {
  value: string
  count: number
}

/** What a search asks: a query string, or a structured filter. */
export type SearchCriteria = { query: string } | { filter: FilterGroup }

export interface SearchSort {
  field: string
  order: 'asc' | 'desc'
}

export interface StructuredSearchOptions {
  page?: number
  perPage?: number
  sort?: SearchSort | null
  facets?: string[]
  facetSize?: number
}

export interface FieldValuesResponse {
  field: string
  values: FacetBucket[]
}

export interface RegionSearchHit {
  /** Relevance score, or null when hits are sorted by a field. */
  score: number | null
  fields: {
    record: string
    region: number
    start: number | null
    end: number | null
    product: string[]
    product_category: string[]
    organism?: string
    output_file: string
    input_file?: string
  }
}

export interface RecordSearchHit {
  score: number | null
  record: string
  output_file: string
  input_file: string | null
}

export interface SearchResponse<T> {
  hits: T[]
  has_more: boolean
  /** Every matching region, at the record level too. */
  total_regions: number
  /** Most common values of each requested facet field over all matches. */
  facets: Record<string, FacetBucket[]>
}

/**
 * Base class for data providers
 * All data providers should implement these methods
 */
export abstract class DataProvider {
  /**
   * Load an entry into the backend session and get its metadata
   * This should be called before accessing regions/features for a record.
   * For file-based providers, this may be a no-op that just returns metadata.
   * For the API provider, the entryId refers to a record within a file and includes the file path.
   */
  abstract loadEntry(entryId: string): Promise<RecordInfo>

  /**
   * Get a list of available records
   */
  abstract getRecords(): Promise<RecordInfo[]>

  /**
   * Search records by query string
   * Implementations should search through record content and return matching records
   * @param query - Search query string (space-separated terms use AND logic)
   * @param page - Page number (optional, default: 1)
   * @param perPage - Records per page (optional, default: 20)
   * @returns Object containing records array and pagination info
   */
  abstract searchRecords(query: string, page?: number, perPage?: number): Promise<{
    records: RecordInfo[]
    total: number
    totalPages: number
    currentPage: number
  }>

  /**
   * Get regions for a specific record
   */
  abstract getRegions(recordId: string): Promise<RegionsResponse>

  /**
   * Get all features for a record (no region filtering)
   */
  abstract getRecordFeatures(recordId: string): Promise<FeaturesResponse>

  /**
   * Get features for a specific region within a record
   */
  abstract getRegionFeatures(recordId: string, regionId: string): Promise<FeaturesResponse>

  /**
   * Get PFAM domain color mapping
   */
  abstract getPfamColorMap(): Promise<PfamColorMap>

  /**
   * Get MiBIG entries for a specific locus tag
   */
  getMiBIGEntries(recordId: string, locusTag: string, region?: string): Promise<MiBIGEntriesResponse>

  /**
   * Get TFBS finder binding site hits for a specific region
   */
  getTFBSHits(recordId: string, region?: string): Promise<TFBSHitsResponse>

  /**
   * Get TTA codon positions for a record (not region-specific)
   */
  getTTACodons(recordId: string): Promise<TTACodonsResponse>

  /**
   * Get resistance features for a record (not region-specific)
   */
  getResistanceFeatures(recordId: string): Promise<ResistanceFeaturesResponse>
}
