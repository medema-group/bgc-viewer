import axios from 'axios'
import { DataProvider } from './types.js'

/**
 * Data provider that fetches data from the BGC Viewer API
 * This is the current backend API implementation
 */
export class BGCViewerAPIProvider extends DataProvider {
  constructor(options = {}) {
    super()
    this.baseURL = options.baseURL || ''
    this.axiosInstance = axios.create({
      baseURL: this.baseURL
    })
  }

  /**
   * Get a list of available records
   * @returns {Promise<RecordInfo[]>}
   */
  async getRecords() {
    // This is currently handled by RecordListSelector component
    // We might want to add an endpoint for this in the future
    throw new Error('getRecords() is not yet implemented in the API')
  }

  /**
   * Get regions for a specific record
   * @param {string} recordId - The record identifier
   * @returns {Promise<{regions: Region[]}>}
   */
  async getRegions(recordId) {
    const response = await this.axiosInstance.get(`/api/records/${recordId}/regions`)
    return response.data
  }

  /**
   * Get all features for a record (no region filtering)
   * @param {string} recordId - The record identifier
   * @returns {Promise<FeaturesResponse>}
   */
  async getRecordFeatures(recordId) {
    const response = await this.axiosInstance.get(`/api/records/${recordId}/features`)
    return response.data
  }

  /**
   * Get features for a specific region within a record
   * @param {string} recordId - The record identifier
   * @param {string} regionId - The region identifier
   * @returns {Promise<FeaturesResponse>}
   */
  async getRegionFeatures(recordId, regionId) {
    const response = await this.axiosInstance.get(
      `/api/records/${recordId}/regions/${regionId}/features`
    )
    return response.data
  }

  /**
   * Get PFAM domain color mapping
   * @returns {Promise<Object<string, string>>} Map of PFAM IDs to colors
   */
  async getPfamColorMap() {
    const response = await this.axiosInstance.get('/domain-colors.csv')
    const csvText = response.data
    const lines = csvText.split('\n')
    
    const colorMap = {}
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
}
