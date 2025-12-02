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
  TFBSHitsResponse
} from './types'

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

  constructor(options: JSONFileProviderOptions = {}) {
    super()
    this.records = options.records || []
    this.pfamColorMap = options.pfamColorMap || {}
  }

  /**
   * Load data from a JSON file
   * @param file - File object or URL to JSON file
   */
  async loadFromFile(file: File | string): Promise<void> {
    let data: any
    
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
   */
  private parseAntiSMASHData(data: any): void {
    // antiSMASH JSON has records array
    if (data.records) {
      this.records = data.records
    } else {
      // Assume single record
      this.records = [data]
    }
  }

  /**
   * Load an entry (no-op for JSON file provider as data is already in memory)
   */
  async loadEntry(entryId: string): Promise<RecordInfo> {
    // For JSON file provider, extract recordId from entryId (format: "filename:record_id")
    const recordId = entryId.includes(':') ? entryId.split(':', 2)[1] : entryId
    
    const record = this.records.find(r => r.id === recordId)
    if (!record) {
      throw new Error(`Record ${recordId} not found`)
    }
    
    return {
      recordId: record.id,
      filename: entryId.includes(':') ? entryId.split(':', 2)[0] : 'unknown',
      recordInfo: {
        description: record.description || ''
      }
    }
  }

  /**
   * Get a list of available records
   */
  async getRecords(): Promise<RecordInfo[]> {
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
      throw new Error(`No MiBIG entries available for region ${region}`)
    }
    
    const locusEntries = mibigEntries[region][locusTag] || []
    
    if (locusEntries.length === 0) {
      throw new Error(`No MiBIG entries found for locus_tag '${locusTag}' in region ${region}`)
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
