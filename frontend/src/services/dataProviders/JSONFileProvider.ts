import { 
  DataProvider, 
  RecordInfo, 
  Region,
  RegionsResponse, 
  FeaturesResponse, 
  PfamColorMap,
  Feature,
  MiBIGEntriesResponse,
  MiBIGEntry,
  TFBSHitsResponse,
  TTACodonsResponse,
  ResistanceFeaturesResponse
} from './types'
import { fetchPfamColorMap } from './colorMapUtils'

export interface JSONFileProviderOptions {
  records?: any[]
  pfamColorMap?: PfamColorMap
}

interface ParsedLocation {
  start: number
  end: number
  strand: string | null
}

/**
 * Data provider that loads data from JSON files
 * This can be used for offline viewing or when data is stored locally
 */
export class JSONFileProvider extends DataProvider {
  private records: any[]
  private pfamColorMap: PfamColorMap
  private fileMetadata: Record<string, string>

  constructor(options: JSONFileProviderOptions = {}) {
    super()
    this.records = options.records || []
    this.pfamColorMap = options.pfamColorMap || {}
    this.fileMetadata = {}
  }

  /**
   * Load data from a JSON file
   * @param file - File object or URL to JSON file
   */
  async loadFromFile(file: File | string): Promise<void> {
    let data: any
    let filename: string
    
    if (file instanceof File) {
      // Read from File object (browser file input)
      const text = await file.text()
      data = JSON.parse(text)
      filename = file.name
    } else if (typeof file === 'string') {
      // Fetch from URL
      const response = await fetch(file)
      data = await response.json()
      filename = file.split('/').pop() || 'unknown'
    } else {
      throw new Error('Invalid file parameter')
    }
    
    // Parse the antiSMASH JSON structure
    this.parseAntiSMASHData(data, filename)
  }

  /**
   * Parse antiSMASH JSON data structure
   */
  private parseAntiSMASHData(data: any, filename: string): void {
    // antiSMASH JSON has records array
    const newRecords = data.records ? data.records : [data]
    
    // Store the source filename and input_file with each record
    // Also create unique record IDs using filename:recordId format
    const inputFile = data.input_file || filename
    newRecords.forEach((record: any) => {
      const originalId = record.id
      record._originalId = originalId
      record._sourceFilename = filename
      record._inputFile = inputFile
      // Create unique ID: filename:recordId
      record.id = `${filename}:${originalId}`
    })
    
    // Append new records to existing ones (for multiple file support)
    this.records = [...this.records, ...newRecords]
    
    // Extract file-level metadata (version, input_file, etc.)
    if (data.version && !this.fileMetadata.version) {
      this.fileMetadata.version = data.version
    }
    if (data.input_file) {
      // Store multiple input files if loading multiple files
      if (!this.fileMetadata.input_files) {
        this.fileMetadata.input_files = []
      }
      if (Array.isArray(this.fileMetadata.input_files)) {
        this.fileMetadata.input_files.push(data.input_file)
      }
    }
  }

  /**
   * Load an entry (no-op for JSON file provider as data is already in memory)
   */
  async loadEntry(entryId: string): Promise<RecordInfo> {
    // entryId can be in format "filename:record_id" or just "record_id"
    // Try exact match first
    let record = this.records.find(r => r.id === entryId)
    
    // If not found and entryId has colon, try matching just the record ID part
    if (!record && entryId.includes(':')) {
      const recordIdPart = entryId.split(':')[1]
      record = this.records.find(r => r.id === recordIdPart || r._originalId === recordIdPart)
    }
    
    // If still not found, try matching against _originalId
    if (!record) {
      record = this.records.find(r => r._originalId === entryId)
    }
    
    if (!record) {
      throw new Error(`Record ${entryId} not found`)
    }
    
    // Extract filename from entryId if not stored in record
    let filename = record._sourceFilename
    if (!filename && entryId.includes(':')) {
      filename = entryId.split(':')[0]
    }
    
    return {
      entryId: record.id,  // Full unique ID for internal use
      recordId: record._originalId || record.id,  // Display name
      filename: filename || 'unknown',
      fileMetadata: {
        ...this.fileMetadata,
        input_file: record._inputFile || 'unknown'
      },
      recordInfo: {
        description: record.description || ''
      }
    }
  }

  /**
   * Get a list of available records
   */
  async getRecords(): Promise<RecordInfo[]> {
    return this.records.map((record) => ({
      recordId: record.id,  // Already unique with filename:originalId format
      filename: record._sourceFilename || 'unknown.json',
      recordInfo: {
        description: record.description || record.definition || ''
      }
    }))
  }

  /**
   * Search records by query string
   * Searches through all leaf values in the record structure
   * @param query - Space-separated search terms (AND logic)
   * @param page - Page number (ignored for file provider, returns all results)
   * @param perPage - Records per page (ignored for file provider, returns all results)
   * @returns Filtered list of records with pagination info
   */
  async searchRecords(query: string, page: number = 1, perPage: number = 20): Promise<{
    records: RecordInfo[]
    total: number
    totalPages: number
    currentPage: number
  }> {
    let filteredRecords = this.records

    if (query.trim()) {
      const searchTerms = query.toLowerCase().split(/\s+/).filter(t => t.length > 0)
      
      // Filter records by searching through all leaf values
      filteredRecords = this.records.filter((record) => {
        const leafValues = this.extractLeafValues(record)
        const searchableText = leafValues.join(' ')
        
        // All search terms must match (AND logic)
        return searchTerms.every(term => searchableText.includes(term))
      })
    }
    
    // Map to RecordInfo format
    const records = filteredRecords.map((record) => {
      // Count regions
      let regionCount = 0
      if (record.regions && Array.isArray(record.regions)) {
        regionCount = record.regions.length
      } else if (record.features && Array.isArray(record.features)) {
        // Count region-type features
        regionCount = record.features.filter((f: any) => f.type === 'region').length
      }
      
      return {
        entryId: record.id,  // Full unique ID in format "filename:originalId"
        recordId: record._originalId || record.id.split(':')[1],  // Just the record ID part
        filename: record._sourceFilename || 'unknown.json',
        recordInfo: {
          description: record.description || record.definition || ''
        },
        featureCount: (record.features || []).length,
        regionCount
      }
    })
    
    // Return all results (client-side provider doesn't need server-side pagination)
    return {
      records,
      total: records.length,
      totalPages: Math.ceil(records.length / perPage),
      currentPage: 1
    }
  }

  /**
   * Recursively extract all leaf values from an object
   * @param obj - Object to traverse
   * @param values - Accumulated values array
   * @returns Array of stringified leaf values
   */
  private extractLeafValues(obj: any, values: string[] = []): string[] {
    if (obj === null || obj === undefined) {
      return values
    }
    
    // Handle primitive types (leaf nodes)
    if (typeof obj === 'string' || typeof obj === 'number' || typeof obj === 'boolean') {
      values.push(String(obj).toLowerCase())
      return values
    }
    
    // Handle arrays
    if (Array.isArray(obj)) {
      for (const item of obj) {
        this.extractLeafValues(item, values)
      }
      return values
    }
    
    // Handle objects
    if (typeof obj === 'object') {
      for (const value of Object.values(obj)) {
        this.extractLeafValues(value, values)
      }
      return values
    }
    
    return values
  }

  /**
   * Get regions for a specific record
   */
  async getRegions(recordId: string): Promise<RegionsResponse> {
    const record = this.findRecord(recordId)
    if (!record) {
      throw new Error(`Record not found: ${recordId}`)
    }

    const regions: Region[] = []
    const features: Feature[] = record.features || []

    // Filter and map region features
    const regionFeatures = features.filter(f => f.type === 'region')
    regionFeatures.forEach((feature, idx) => {
      const location = this.parseLocation(feature.location)
      const regionNumber = parseInt(feature.qualifiers?.region_number?.[0]) || (idx + 1)
      regions.push({
        id: `region_${regionNumber}`,
        region_number: regionNumber,
        product: feature.qualifiers?.product || [],
        start: location?.start,
        end: location?.end
      })
    })

    return { regions }
  }

  /**
   * Get all features for a record (no region filtering)
   */
  async getRecordFeatures(recordId: string): Promise<FeaturesResponse> {
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
   */
  async getRegionFeatures(recordId: string, regionId: string): Promise<FeaturesResponse> {
    const record = this.findRecord(recordId)
    if (!record) {
      throw new Error(`Record not found: ${recordId}`)
    }

    const features: Feature[] = record.features || []
    
    // Extract region number from regionId (format: "region_1", "region_2", etc.)
    const regionNumber = regionId.replace('region_', '')
    
    // Find the region feature by matching region_number qualifier
    const regionFeature = features.find(f => {
      if (f.type !== 'region') return false
      const featureRegionNumber = f.qualifiers?.region_number?.[0]
      // Compare as strings since qualifiers can be strings or numbers
      return String(featureRegionNumber) === regionNumber
    })
    
    if (!regionFeature) {
      throw new Error(`Region not found: ${regionId}`)
    }

    const regionLocation = this.parseLocation(regionFeature.location)
    
    if (!regionLocation) {
      throw new Error(`Invalid region location: ${regionFeature.location}`)
    }

    // Filter features that fall within the region boundaries
    const regionFeatures = features.filter(feature => {
      const location = this.parseLocation(feature.location)
      if (!location) return false
      
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
   * Get features within a coordinate range (viewport-based)
   */
  async getFeaturesByRange(recordId: string, start: number, end: number): Promise<FeaturesResponse> {
    const record = this.findRecord(recordId)
    if (!record) {
      throw new Error(`Record not found: ${recordId}`)
    }

    const features: Feature[] = record.features || []
    
    // Filter features that overlap with the specified range
    const rangeFeatures = features.filter(feature => {
      const location = this.parseLocation(feature.location)
      if (!location) return false
      
      // Check if feature overlaps with the specified range
      return !(location.end < start || location.start > end)
    })

    return {
      features: rangeFeatures,
      region_boundaries: {
        start: start,
        end: end
      }
    }
  }

  /**
   * Get PFAM domain color mapping
   */
  async getPfamColorMap(): Promise<PfamColorMap> {
    // If we already have colors loaded, return them
    if (Object.keys(this.pfamColorMap).length > 0) {
      return this.pfamColorMap
    }
    
    // Otherwise, fetch from public folder
    this.pfamColorMap = await fetchPfamColorMap()
    return this.pfamColorMap
  }

  /**
   * Set PFAM color map (for loading from external source)
   */
  setPfamColorMap(colorMap: PfamColorMap): void {
    this.pfamColorMap = colorMap
  }

  /**
   * Find a record by ID
   */
  private findRecord(recordId: string): any | undefined {
    return this.records.find((r, idx) => 
      (r.id || `record-${idx}`) === recordId
    )
  }

  /**
   * Get MiBIG entries for a specific locus_tag
   */
  async getMiBIGEntries(recordId: string, locusTag: string, region: string = '1'): Promise<MiBIGEntriesResponse> {
    const record = this.findRecord(recordId)
    if (!record) {
      throw new Error(`Record not found: ${recordId}`)
    }

    // Navigate to MiBIG entries: modules -> antismash.modules.clusterblast -> knowncluster -> mibig_entries -> region -> locus_tag
    const modules = record.modules || {}
    const clusterblast = modules['antismash.modules.clusterblast'] || {}
    const knowncluster = clusterblast.knowncluster || {}
    const mibigEntries = knowncluster.mibig_entries || {}
    
    if (!mibigEntries[region]) {
      return {
        record_id: recordId,
        locus_tag: locusTag,
        region: region,
        count: 0,
        entries: []
      }
    }
    
    const locusEntries = mibigEntries[region][locusTag] || []
    
    if (locusEntries.length === 0) {
      return {
        record_id: recordId,
        locus_tag: locusTag,
        region: region,
        count: 0,
        entries: []
      }
    }
    
    // Format the entries
    const formattedEntries: MiBIGEntry[] = locusEntries.map((entry: any[]) => ({
      mibig_protein: entry[0],
      description: entry[1],
      mibig_cluster: entry[2],
      rank: entry[3],
      mibig_product: entry[4],
      percent_identity: entry[5],
      blast_score: entry[6],
      percent_coverage: entry[7],
      evalue: entry[8]
    }))
    
    return {
      record_id: recordId,
      locus_tag: locusTag,
      region: region,
      count: formattedEntries.length,
      entries: formattedEntries
    }
  }

  /**
   * Get TFBS finder binding site hits for a specific region
   */
  async getTFBSHits(recordId: string, region: string = '1'): Promise<TFBSHitsResponse> {
    const record = this.findRecord(recordId)
    if (!record) {
      throw new Error(`Record not found: ${recordId}`)
    }

    // Navigate to TFBS hits: modules -> antismash.modules.tfbs_finder -> hits_by_region -> region
    const modules = record.modules || {}
    const tfbsFinder = modules['antismash.modules.tfbs_finder'] || {}
    const hitsByRegion = tfbsFinder.hits_by_region || {}
    
    if (!hitsByRegion[region]) {
      return {
        record_id: recordId,
        region: region,
        count: 0,
        hits: []
      }
    }
    
    const bindingSites = hitsByRegion[region] || []
    
    return {
      record_id: recordId,
      region: region,
      count: bindingSites.length,
      hits: bindingSites
    }
  }

  /**
   * Get TTA codon positions for a record
   */
  async getTTACodons(recordId: string): Promise<TTACodonsResponse> {
    const record = this.findRecord(recordId)
    if (!record) {
      throw new Error(`Record not found: ${recordId}`)
    }

    // Navigate to TTA codons: modules -> antismash.modules.tta -> TTA codons
    const modules = record.modules || {}
    const ttaModule = modules['antismash.modules.tta'] || {}
    const ttaCodons = ttaModule['TTA codons'] || []
    
    return {
      record_id: recordId,
      count: ttaCodons.length,
      codons: ttaCodons
    }
  }

  /**
   * Get resistance features for a record
   */
  async getResistanceFeatures(recordId: string): Promise<ResistanceFeaturesResponse> {
    const record = this.findRecord(recordId)
    if (!record) {
      throw new Error(`Record not found: ${recordId}`)
    }

    // Navigate to resistance features: modules -> antismash.detection.genefunctions -> tools -> resist -> best_hits
    const modules = record.modules || {}
    const genefunctions = modules['antismash.detection.genefunctions'] || {}
    const tools = genefunctions.tools || {}
    const resist = tools.resist || {}
    const bestHits = resist.best_hits || {}
    
    // Convert dict to list for easier frontend consumption
    const resistanceFeatures = []
    for (const [locusTag, hitData] of Object.entries(bestHits)) {
      resistanceFeatures.push({
        locus_tag: locusTag,
        ...(hitData as any)
      })
    }
    
    return {
      record_id: recordId,
      count: resistanceFeatures.length,
      features: resistanceFeatures
    }
  }

  /**
   * Parse location string like "[164:2414](+)" or "[257:2393](+)"
   */
  private parseLocation(location: string): ParsedLocation | null {
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
