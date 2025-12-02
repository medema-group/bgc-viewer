import axios, { AxiosInstance } from 'axios'
import { 
  DataProvider, 
  RecordInfo, 
  RegionsResponse, 
  FeaturesResponse, 
  PfamColorMap,
  MiBIGEntriesResponse,
  TFBSHitsResponse
} from './types'

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
      record_info: {
        id: string
        description: string
        feature_count: number
      }
    }>('/api/load-entry', {
      id: entryId
    })
    
    return {
      recordId: response.data.record_id,
      filename: response.data.filename,
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
   * Get regions for a specific record
   */
  async getRegions(recordId: string): Promise<RegionsResponse> {
    const response = await this.axiosInstance.get<RegionsResponse>(
      `/api/records/${recordId}/regions`
    )
    return response.data
  }

  /**
   * Get all features for a record (no region filtering)
   */
  async getRecordFeatures(recordId: string): Promise<FeaturesResponse> {
    const response = await this.axiosInstance.get<FeaturesResponse>(
      `/api/records/${recordId}/features`
    )
    return response.data
  }

  /**
   * Get features for a specific region within a record
   */
  async getRegionFeatures(recordId: string, regionId: string): Promise<FeaturesResponse> {
    const response = await this.axiosInstance.get<FeaturesResponse>(
      `/api/records/${recordId}/regions/${regionId}/features`
    )
    return response.data
  }

  /**
   * Get PFAM domain color mapping
   */
  async getPfamColorMap(): Promise<PfamColorMap> {
    const response = await this.axiosInstance.get<string>('/domain-colors.csv')
    const csvText = response.data
    const lines = csvText.split('\n')
    
    const colorMap: PfamColorMap = {}
    // Skip header line and process each color mapping
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim()
      if (line) {
        const [id, color] = line.split(',')
        if (id && color) {
          colorMap[id] = color
        }
      }
    }
    
    return colorMap
  }

  /**
   * Get MiBIG entries for a specific locus_tag
   */
  async getMiBIGEntries(recordId: string, locusTag: string, region: string = '1'): Promise<MiBIGEntriesResponse> {
    const response = await this.axiosInstance.get<MiBIGEntriesResponse>(
      `/api/records/${recordId}/mibig-entries/${locusTag}`,
      { params: { region } }
    )
    return response.data
  }

  /**
   * Get TFBS finder binding site hits for a specific region
   */
  async getTFBSHits(recordId: string, region: string = '1'): Promise<TFBSHitsResponse> {
    const response = await this.axiosInstance.get<TFBSHitsResponse>(
      `/api/records/${recordId}/tfbs-hits`,
      { params: { region } }
    )
    return response.data
  }
}
