/**
 * Base interface for BGC data providers
 * 
 * This defines the contract that all data providers must implement,
 * allowing the viewer to work with different data sources (API, files, etc.)
 */

export interface RecordInfo {
  recordId: string
  filename: string
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
}

export interface RegionBoundaries {
  start: number
  end: number
}

export interface FeaturesResponse {
  features: Feature[]
  region_boundaries?: RegionBoundaries
}

export interface RegionsResponse {
  regions: Region[]
}

export type PfamColorMap = Record<string, string>

/**
 * Base class for data providers
 * All data providers should implement these methods
 */
export abstract class DataProvider {
  /**
   * Get a list of available records
   */
  abstract getRecords(): Promise<RecordInfo[]>

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
}
