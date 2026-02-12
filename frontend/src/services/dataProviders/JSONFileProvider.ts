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
    // entryId is already in format "filename:record_id" for unique identification
    const record = this.records.find(r => r.id === entryId)
    if (!record) {
      throw new Error(`Record ${entryId} not found`)
    }
    
    return {
      entryId: record.id,  // Full unique ID for internal use
      recordId: record._originalId || record.id,  // Display name
      filename: record._sourceFilename || 'unknown',
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
    const records = filteredRecords.map((record) => ({
      recordId: record.id,  // Already unique with filename:originalId format
      filename: record._sourceFilename || 'unknown.json',
      recordInfo: {
        description: record.description || record.definition || ''
      }
    }))
    
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
    
    // Find the region feature
    const regionIdx = parseInt(regionId.replace('region-', ''))
    const regionFeature = features[regionIdx]
    
    if (!regionFeature || regionFeature.type !== 'region') {
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
