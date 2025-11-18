/**
 * Base interface for BGC data providers
 * 
 * This defines the contract that all data providers must implement,
 * allowing the viewer to work with different data sources (API, files, etc.)
 */

/**
 * @typedef {Object} RecordInfo
 * @property {string} recordId - Unique identifier for the record
 * @property {string} filename - Name of the file containing the record
 * @property {Object} recordInfo - Additional record metadata
 * @property {string} [recordInfo.description] - Description of the record
 */

/**
 * @typedef {Object} Region
 * @property {string} id - Unique identifier for the region
 * @property {number} region_number - Display number for the region
 * @property {string[]} product - List of products in the region
 * @property {number} [start] - Start position of the region
 * @property {number} [end] - End position of the region
 */

/**
 * @typedef {Object} Feature
 * @property {string} type - Type of feature (CDS, PFAM_domain, protocluster, etc.)
 * @property {string} location - Location string in format "[start:end](strand)"
 * @property {Object} [qualifiers] - Feature qualifiers/attributes
 */

/**
 * @typedef {Object} RegionBoundaries
 * @property {number} start - Start position
 * @property {number} end - End position
 */

/**
 * @typedef {Object} FeaturesResponse
 * @property {Feature[]} features - Array of features
 * @property {RegionBoundaries} [region_boundaries] - Optional region boundaries
 */

/**
 * Base class for data providers
 * All data providers should implement these methods
 */
export class DataProvider {
  /**
   * Get a list of available records
   * @returns {Promise<RecordInfo[]>}
   */
  async getRecords() {
    throw new Error('getRecords() must be implemented by subclass')
  }

  /**
   * Get regions for a specific record
   * @param {string} recordId - The record identifier
   * @returns {Promise<{regions: Region[]}>}
   */
  async getRegions(recordId) {
    throw new Error('getRegions() must be implemented by subclass')
  }

  /**
   * Get all features for a record (no region filtering)
   * @param {string} recordId - The record identifier
   * @returns {Promise<FeaturesResponse>}
   */
  async getRecordFeatures(recordId) {
    throw new Error('getRecordFeatures() must be implemented by subclass')
  }

  /**
   * Get features for a specific region within a record
   * @param {string} recordId - The record identifier
   * @param {string} regionId - The region identifier
   * @returns {Promise<FeaturesResponse>}
   */
  async getRegionFeatures(recordId, regionId) {
    throw new Error('getRegionFeatures() must be implemented by subclass')
  }

  /**
   * Get PFAM domain color mapping
   * @returns {Promise<Object<string, string>>} Map of PFAM IDs to colors
   */
  async getPfamColorMap() {
    throw new Error('getPfamColorMap() must be implemented by subclass')
  }
}
