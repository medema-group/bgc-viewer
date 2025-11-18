import { DataProvider } from './types.js'

/**
 * Data provider that loads data from JSON files
 * This can be used for offline viewing or when data is stored locally
 */
export class JSONFileProvider extends DataProvider {
  constructor(options = {}) {
    super()
    this.records = options.records || []
    this.pfamColorMap = options.pfamColorMap || {}
  }

  /**
   * Load data from a JSON file
   * @param {File|string} file - File object or URL to JSON file
   * @returns {Promise<void>}
   */
  async loadFromFile(file) {
    let data
    
    if (file instanceof File) {
      // Read from File object (browser file input)
      const text = await file.text()
      data = JSON.parse(text)
    } else if (typeof file === 'string') {
      // Fetch from URL
      const response = await fetch(file)
      data = await response.json()
    } else {
      throw new Error('Invalid file parameter')
    }
    
    // Parse the antiSMASH JSON structure
    this.parseAntiSMASHData(data)
  }

  /**
   * Parse antiSMASH JSON data structure
   * @private
   */
  parseAntiSMASHData(data) {
    // antiSMASH JSON has records array
    if (data.records) {
      this.records = data.records
    } else {
      // Assume single record
      this.records = [data]
    }
  }

  /**
   * Get a list of available records
   * @returns {Promise<RecordInfo[]>}
   */
  async getRecords() {
    return this.records.map((record, idx) => ({
      recordId: record.id || `record-${idx}`,
      filename: record.filename || `record-${idx}.json`,
      recordInfo: {
        description: record.description || record.definition || ''
      }
    }))
  }

  /**
   * Get regions for a specific record
   * @param {string} recordId - The record identifier
   * @returns {Promise<{regions: Region[]}>}
   */
  async getRegions(recordId) {
    const record = this.findRecord(recordId)
    if (!record) {
      throw new Error(`Record not found: ${recordId}`)
    }

    const regions = []
    const features = record.features || []

    // Find region features
    features.forEach((feature, idx) => {
      if (feature.type === 'region') {
        const location = this.parseLocation(feature.location)
        regions.push({
          id: `region-${idx}`,
          region_number: feature.qualifiers?.region_number?.[0] || (idx + 1),
          product: feature.qualifiers?.product || [],
          start: location?.start,
          end: location?.end
        })
      }
    })

    return { regions }
  }

  /**
   * Get all features for a record (no region filtering)
   * @param {string} recordId - The record identifier
   * @returns {Promise<FeaturesResponse>}
   */
  async getRecordFeatures(recordId) {
    const record = this.findRecord(recordId)
    if (!record) {
      throw new Error(`Record not found: ${recordId}`)
    }

    return {
      features: record.features || []
    }
  }

  /**
   * Get features for a specific region within a record
   * @param {string} recordId - The record identifier
   * @param {string} regionId - The region identifier
   * @returns {Promise<FeaturesResponse>}
   */
  async getRegionFeatures(recordId, regionId) {
    const record = this.findRecord(recordId)
    if (!record) {
      throw new Error(`Record not found: ${recordId}`)
    }

    const features = record.features || []
    
    // Find the region feature
    const regionIdx = parseInt(regionId.replace('region-', ''))
    const regionFeature = features[regionIdx]
    
    if (!regionFeature || regionFeature.type !== 'region') {
      throw new Error(`Region not found: ${regionId}`)
    }

    const regionLocation = this.parseLocation(regionFeature.location)
    
    // Filter features that fall within the region boundaries
    const regionFeatures = features.filter(feature => {
      const location = this.parseLocation(feature.location)
      if (!location || !regionLocation) return false
      
      // Check if feature overlaps with region
      return !(location.end < regionLocation.start || location.start > regionLocation.end)
    })

    return {
      features: regionFeatures,
      region_boundaries: {
        start: regionLocation.start,
        end: regionLocation.end
      }
    }
  }

  /**
   * Get PFAM domain color mapping
   * @returns {Promise<Object<string, string>>} Map of PFAM IDs to colors
   */
  async getPfamColorMap() {
    return this.pfamColorMap
  }

  /**
   * Set PFAM color map (for loading from external source)
   * @param {Object<string, string>} colorMap
   */
  setPfamColorMap(colorMap) {
    this.pfamColorMap = colorMap
  }

  /**
   * Find a record by ID
   * @private
   */
  findRecord(recordId) {
    return this.records.find(r => (r.id || `record-${this.records.indexOf(r)}`) === recordId)
  }

  /**
   * Parse location string like "[164:2414](+)" or "[257:2393](+)"
   * @private
   */
  parseLocation(location) {
    if (!location) return null
    const match = location.match(/\[<?(\d+):>?(\d+)\](?:\(([+-])\))?/)
    if (!match) return null

    return {
      start: parseInt(match[1]),
      end: parseInt(match[2]),
      strand: match[3] || null
    }
  }
}
