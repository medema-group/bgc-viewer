import { 
  DataProvider, 
  RecordInfo, 
  Region,
  RegionsResponse, 
  FeaturesResponse, 
  PfamColorMap,
  Feature,
  MiBIGEntriesResponse,
  TFBSHitsResponse,
  TTACodonsResponse,
  ResistanceFeaturesResponse
} from './types'
import { fetchPfamColorMap } from './colorMapUtils'

/**
 * Data provider that loads data from GenBank files
 * Converts GenBank format to antiSMASH-compatible structure for rendering
 */
export class GenbankFileProvider extends DataProvider {
  private records: any[]
  private pfamColorMap: PfamColorMap
  private recordCounter: number

  constructor() {
    super()
    this.records = []
    this.pfamColorMap = {}
    this.recordCounter = 0
  }

  /**
   * Load and parse GenBank file
   * @param file - File object containing GenBank data
   */
  async loadFromFile(file: File): Promise<void> {
    const text = await file.text()
    
    // Dynamically import bio-parsers (code-splitting)
    const { genbankToJson } = await import('@teselagen/bio-parsers')
    
    // Parse GenBank file
    const result = genbankToJson(text)
    
    if (!result || result.length === 0) {
      throw new Error('Failed to parse GenBank file')
    }
    
    // Extract the actual records from the parsedSequence wrapper
    const gbRecords = result
      .filter((item: any) => item.success && item.parsedSequence)
      .map((item: any) => item.parsedSequence)
    
    if (gbRecords.length === 0) {
      throw new Error('No valid records found in GenBank file')
    }
    
    // Convert to antiSMASH-compatible format
    const convertedRecords = gbRecords.map((gbRecord: any) => {
      return this.convertGenbankToAntiSMASH(gbRecord, file.name)
    })
    
    this.records = [...this.records, ...convertedRecords]
  }

  /**
   * Convert GenBank record to antiSMASH-compatible structure
   */
  private convertGenbankToAntiSMASH(gbRecord: any, filename: string): any {
    // Create unique record ID using counter and filename
    this.recordCounter++
    const recordName = gbRecord.name || `record-${this.recordCounter}`
    const uniqueRecordId = `${filename}:${recordName}`
    
    // Extract sequence information
    const description = Array.isArray(gbRecord.description) 
      ? gbRecord.description.join(' ') 
      : (gbRecord.description || gbRecord.definition || gbRecord.comments || '')
    const sequence = gbRecord.sequence || ''
    const versionInfo = gbRecord.version || gbRecord.accession || 'unknown'
    
    // Get features array
    const gbFeatures = gbRecord.features || []
    
    // Convert GenBank features to antiSMASH-like features
    const features = gbFeatures.map((gbFeature: any) => {
      const feature: any = {
        type: gbFeature.type || 'unknown',
        location: this.formatLocation(gbFeature.start, gbFeature.end, gbFeature.strand),
        qualifiers: {}
      }
      
      // Copy qualifiers from notes (bio-parsers stores them in 'notes', not 'qualifiers')
      if (gbFeature.notes) {
        Object.entries(gbFeature.notes).forEach(([key, value]) => {
          feature.qualifiers[key] = Array.isArray(value) ? value : [String(value)]
        })
      }
      
      // Add gene qualifier from name property if it exists
      if (gbFeature.name && !feature.qualifiers.gene) {
        feature.qualifiers.gene = [gbFeature.name]
      }
      
      // Add locus_tag if name exists and locus_tag wasn't in notes
      if (gbFeature.name && !feature.qualifiers.locus_tag) {
        feature.qualifiers.locus_tag = [gbFeature.name]
      }
      
      return feature
    })
    
    // Create antiSMASH-compatible record
    return {
      id: uniqueRecordId,
      description: description,
      seq: {
        data: sequence,
        length: sequence.length
      },
      features: features,
      _sourceFilename: filename,
      _inputFile: filename,
      _recordName: recordName,
      modules: {},  // GenBank doesn't have antiSMASH modules
      version: versionInfo
    }
  }

  /**
   * Format location in antiSMASH style: [start:end](strand)
   * Note: bio-parsers uses 0-based indexing, which matches Python/antiSMASH convention
   */
  private formatLocation(start: number, end: number, strand: number = 1): string {
    const strandSymbol = strand >= 0 ? '+' : '-'
    // bio-parsers already provides 0-based coordinates
    return `[${start}:${end}](${strandSymbol})`
  }

  /**
   * Load an entry
   */
  async loadEntry(entryId: string): Promise<RecordInfo> {
    // entryId is already in format "filename:recordName"
    const record = this.records.find(r => r.id === entryId)
    if (!record) {
      throw new Error(`Record ${entryId} not found`)
    }
    
    return {
      entryId: record.id,  // Full unique ID for internal use
      recordId: record._recordName || record.id,  // Display name
      filename: record._sourceFilename || 'unknown.gb',
      fileMetadata: {
        version: record.version || 'unknown'
      },
      recordInfo: {
        description: record.description || ''
      }
    }
  }

  /**
   * Get list of records
   */
  async getRecords(): Promise<RecordInfo[]> {
    return this.records.map((record) => ({
      recordId: record.id,  // Already unique with filename:recordName format
      filename: record._sourceFilename || 'unknown.gb',
      recordInfo: {
        description: record.description || ''
      }
    }))
  }

  /**
   * Search records
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
      
      filteredRecords = this.records.filter((record) => {
        const searchableText = [
          record.id,
          record._recordName,
          record.description,
          record._sourceFilename,
          JSON.stringify(record.features)
        ].join(' ').toLowerCase()
        
        return searchTerms.every(term => searchableText.includes(term))
      })
    }
    
    const records = filteredRecords.map((record) => ({
      recordId: record.id,  // Already unique with filename:recordName format
      filename: record._sourceFilename || 'unknown.gb',
      recordInfo: {
        description: record.description || ''
      }
    }))
    
    return {
      records,
      total: records.length,
      totalPages: Math.ceil(records.length / perPage),
      currentPage: 1
    }
  }

  /**
   * Get regions (GenBank doesn't have regions like antiSMASH)
   */
  async getRegions(recordId: string): Promise<RegionsResponse> {
    return { regions: [] }
  }

  /**
   * Get all features for a record
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
   * Get features for a region (not applicable for GenBank)
   */
  async getRegionFeatures(recordId: string, regionId: string): Promise<FeaturesResponse> {
    return this.getRecordFeatures(recordId)
  }

  /**
   * Get PFAM color map
   */
  async getPfamColorMap(): Promise<PfamColorMap> {
    if (Object.keys(this.pfamColorMap).length > 0) {
      return this.pfamColorMap
    }
    
    this.pfamColorMap = await fetchPfamColorMap()
    return this.pfamColorMap
  }

  /**
   * GenBank doesn't have MiBIG entries
   */
  async getMiBIGEntries(recordId: string, locusTag: string, region?: string): Promise<MiBIGEntriesResponse> {
    return {
      record_id: recordId,
      locus_tag: locusTag,
      region: region || '1',
      count: 0,
      entries: []
    }
  }

  /**
   * GenBank doesn't have TFBS hits
   */
  async getTFBSHits(recordId: string, region?: string): Promise<TFBSHitsResponse> {
    return {
      record_id: recordId,
      region: region || '1',
      count: 0,
      hits: []
    }
  }

  /**
   * GenBank doesn't have TTA codons
   */
  async getTTACodons(recordId: string): Promise<TTACodonsResponse> {
    return {
      record_id: recordId,
      count: 0,
      codons: []
    }
  }

  /**
   * GenBank doesn't have resistance features
   */
  async getResistanceFeatures(recordId: string): Promise<ResistanceFeaturesResponse> {
    return {
      record_id: recordId,
      count: 0,
      features: []
    }
  }

  /**
   * Find record by ID (expects full entryId with filename:recordName format)
   */
  private findRecord(recordId: string): any | undefined {
    return this.records.find((r) => r.id === recordId)
  }
}
