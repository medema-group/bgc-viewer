import axios, { AxiosInstance } from 'axios'
import { 
  DataProvider, 
  RecordInfo, 
  RegionsResponse, 
  FeaturesResponse, 
  PfamColorMap,
  MiBIGEntriesResponse,
  TFBSHitsResponse,
  TTACodonsResponse,
  ResistanceFeaturesResponse
} from './types'
import { fetchPfamColorMap } from './colorMapUtils'

export interface BGCViewerAPIProviderOptions {
  baseURL?: string
}

/**
 * Data provider that fetches data from the BGC Viewer API
 * This is the current backend API implementation
 */
export class BGCViewerAPIProvider extends DataProvider {
  private axiosInstance: AxiosInstance

  constructor(options: BGCViewerAPIProviderOptions = {}) {
    super()
    const baseURL = options.baseURL || ''
    this.axiosInstance = axios.create({ baseURL })
  }

  /**
   * Load an entry into the backend session and get its metadata
   */
  async loadEntry(entryId: string): Promise<RecordInfo> {
    const response = await this.axiosInstance.post<{
      filename: string
      record_id: string
      file_metadata?: Record<string, string>
      record_info: {
        id: string
        description: string
        feature_count: number
      }
    }>('/api/load-entry', {
      id: entryId
    })
    
    return {
      entryId: entryId,
      recordId: response.data.record_id,
      filename: response.data.filename,
      fileMetadata: response.data.file_metadata,
      recordInfo: {
        description: response.data.record_info.description
      }
    }
  }

  /**
   * Get a list of available records
   */
  async getRecords(): Promise<RecordInfo[]> {
    // This is currently handled by RecordListSelector component
    // We might want to add an endpoint for this in the future
    throw new Error('getRecords() is not yet implemented in the API')
  }

  /**
   * Search records by query string
   * For API provider, this delegates to the backend search endpoint
   * @param query - Search query string
   * @param page - Page number (default: 1)
   * @param perPage - Records per page (default: 20)
   */
  async searchRecords(query: string, page: number = 1, perPage: number = 20): Promise<{
    records: RecordInfo[]
    total: number
    totalPages: number
    currentPage: number
  }> {
    const params: any = {
      page,
      per_page: perPage
    }
    
    if (query.trim()) {
      params.search = query.trim()
    }
    
    const response = await this.axiosInstance.get<{
      entries: any[]
      total: number
      total_pages: number
      page: number
    }>('/api/database-entries', { params })
    
    // Map to RecordInfo format
    const records = response.data.entries.map(entry => ({
      recordId: entry.record_id,
      filename: entry.filename,
      recordInfo: {
        description: entry.description
      },
      // Include additional fields for display
      entryId: entry.id,  // Full entry ID in format "filename:recordId"
      organism: entry.organism,
      products: entry.products,
      clusterTypes: entry.cluster_types,
      featureCount: entry.feature_count,
      regionCount: entry.region_count
    } as any))
    
    return {
      records,
      total: response.data.total,
      totalPages: response.data.total_pages,
      currentPage: response.data.page
    }
  }

  /**
   * Get regions for a specific record
   */
  async getRegions(recordId: string): Promise<RegionsResponse> {
    // Extract actual record ID from entryId format (filename:recordId)
    const actualRecordId = recordId.includes(':') ? recordId.split(':')[1] : recordId
    const response = await this.axiosInstance.get<RegionsResponse>(
      `/api/records/${actualRecordId}/regions`
    )
    return response.data
  }

  /**
   * Get all features for a record (no region filtering)
   */
  async getRecordFeatures(recordId: string): Promise<FeaturesResponse> {
    // Extract actual record ID from entryId format (filename:recordId)
    const actualRecordId = recordId.includes(':') ? recordId.split(':')[1] : recordId
    const response = await this.axiosInstance.get<FeaturesResponse>(
      `/api/records/${actualRecordId}/features`
    )
    return response.data
  }

  /**
   * Get features for a specific region within a record
   */
  async getRegionFeatures(recordId: string, regionId: string): Promise<FeaturesResponse> {
    // Extract actual record ID from entryId format (filename:recordId)
    const actualRecordId = recordId.includes(':') ? recordId.split(':')[1] : recordId
    const response = await this.axiosInstance.get<FeaturesResponse>(
      `/api/records/${actualRecordId}/regions/${regionId}/features`
    )
    return response.data
  }

  /**
   * Get features within a coordinate range (viewport-based)
   */
  async getFeaturesByRange(recordId: string, start: number, end: number): Promise<FeaturesResponse> {
    // Extract actual record ID from entryId format (filename:recordId)
    const actualRecordId = recordId.includes(':') ? recordId.split(':')[1] : recordId
    const response = await this.axiosInstance.get<FeaturesResponse>(
      `/api/records/${actualRecordId}/features/range`,
      {
        params: { start, end }
      }
    )
    return response.data
  }

  /**
   * Get PFAM domain color mapping
   */
  async getPfamColorMap(): Promise<PfamColorMap> {
    return fetchPfamColorMap()
  }

  /**
   * Get MiBIG entries for a specific locus_tag
   */
  async getMiBIGEntries(recordId: string, locusTag: string, region: string = '1'): Promise<MiBIGEntriesResponse> {
    const actualRecordId = recordId.includes(':') ? recordId.split(':')[1] : recordId
    const response = await this.axiosInstance.get<MiBIGEntriesResponse>(
      `/api/records/${actualRecordId}/mibig-entries/${locusTag}`,
      { params: { region } }
    )
    return response.data
  }

  /**
   * Get TFBS finder binding site hits for a specific region
   */
  async getTFBSHits(recordId: string, region: string = '1'): Promise<TFBSHitsResponse> {
    const actualRecordId = recordId.includes(':') ? recordId.split(':')[1] : recordId
    const response = await this.axiosInstance.get<TFBSHitsResponse>(
      `/api/records/${actualRecordId}/tfbs-hits`,
      { params: { region } }
    )
    return response.data
  }

  /**
   * Get TTA codon positions for a record
   */
  async getTTACodons(recordId: string): Promise<TTACodonsResponse> {
    const actualRecordId = recordId.includes(':') ? recordId.split(':')[1] : recordId
    const response = await this.axiosInstance.get<TTACodonsResponse>(
      `/api/records/${actualRecordId}/tta-codons`
    )
    return response.data
  }

  /**
   * Get resistance features for a record
   */
  async getResistanceFeatures(recordId: string): Promise<ResistanceFeaturesResponse> {
    const actualRecordId = recordId.includes(':') ? recordId.split(':')[1] : recordId
    const response = await this.axiosInstance.get<ResistanceFeaturesResponse>(
      `/api/records/${actualRecordId}/resistance`
    )
    return response.data
  }
}
