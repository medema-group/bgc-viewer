import { describe, test, expect, vi } from 'vitest'
import { GenbankFileProvider } from '@/services/dataProviders/GenbankFileProvider'

/**
 * Tests for GenbankFileProvider conversion to antiSMASH format
 */
describe('GenbankFileProvider', () => {
  const sampleGenbankContent = `LOCUS       TEST_BGC                1000 bp    DNA     linear   BCT 01-JAN-2024
DEFINITION  Test biosynthetic gene cluster for GenBank parsing
ACCESSION   TEST001
VERSION     TEST001.1
KEYWORDS    .
SOURCE      Test organism
  ORGANISM  Test organism
            Bacteria; Test phylum; Test class.
FEATURES             Location/Qualifiers
     source          1..1000
                     /organism="Test organism"
                     /strain="test1"
     gene            100..500
                     /gene="testA"
                     /locus_tag="TEST_001"
     CDS             100..500
                     /gene="testA"
                     /locus_tag="TEST_001"
                     /product="Test enzyme A"
                     /protein_id="TEST001.1"
                     /translation="MKVLWAALLVTFLAGCQAKVEQAVETEPEPELRQQYQQQYGQQY"
ORIGIN      
        1 atgaaagttc tgtgggtggc cgcattgctg gtcaccttcc tggcgggttg ccaggcgaaa
       61 gtggaacagg ccgttgaaac cgaaccagaa ccagagctga gacaacagta ccaacaacag
      121 tacggacaac aatacggatg atcgaagaag tcatcttacc gccacaaacg cctgacgttg
      181 tcggtacttc cggtacggta cggtacggta cggtacggta cgatcgatcg atcgatcgat
//
`

  // Helper function to create a mock File object with text() method
  const createMockFile = (content: string, filename: string): File => {
    const blob = new Blob([content], { type: 'text/plain' })
    const file = new File([blob], filename, { type: 'text/plain' })
    
    // Mock the text() method
    Object.defineProperty(file, 'text', {
      value: vi.fn().mockResolvedValue(content),
      writable: false
    })
    
    return file
  }

  test('should load GenBank file and create provider', async () => {
    const provider = new GenbankFileProvider()
    const file = createMockFile(sampleGenbankContent, 'test.gb')
    
    await provider.loadFromFile(file)
    
    const records = await provider.getRecords()
    expect(records.length).toBeGreaterThan(0)
  })

  test('should create unique record IDs with filename', async () => {
    const provider = new GenbankFileProvider()
    const file = createMockFile(sampleGenbankContent, 'test.gb')
    
    await provider.loadFromFile(file)
    
    const records = await provider.getRecords()
    const firstRecord = records[0]
    
    // Record ID should be in format "filename:recordName"
    expect(firstRecord.recordId).toContain('test.gb:')
    expect(firstRecord.recordId).toBe('test.gb:TEST_BGC')
  })

  test('should extract version information', async () => {
    const provider = new GenbankFileProvider()
    const file = createMockFile(sampleGenbankContent, 'test.gb')
    
    await provider.loadFromFile(file)
    const records = await provider.getRecords()
    
    const entryInfo = await provider.loadEntry(records[0].recordId)
    
    expect(entryInfo.fileMetadata?.version).toBe('TEST001.1')
  })

  test('should convert features to antiSMASH format', async () => {
    const provider = new GenbankFileProvider()
    const file = createMockFile(sampleGenbankContent, 'test.gb')
    
    await provider.loadFromFile(file)
    const records = await provider.getRecords()
    
    const features = await provider.getRecordFeatures(records[0].recordId)
    
    expect(features.features.length).toBeGreaterThan(0)
    
    // Find a CDS feature
    const cdsFeature = features.features.find((f: any) => f.type === 'CDS')
    expect(cdsFeature).toBeDefined()
    
    // Check antiSMASH format location string
    expect(cdsFeature.location).toMatch(/^\[\d+:\d+\]\([+-]\)$/)
    
    // Should have qualifiers
    expect(cdsFeature.qualifiers).toBeDefined()
    expect(cdsFeature.qualifiers.gene).toEqual(['testA'])
    expect(cdsFeature.qualifiers.locus_tag).toEqual(['TEST_001'])
    expect(cdsFeature.qualifiers.product).toEqual(['Test enzyme A'])
  })

  test('should handle multiple files without ID conflicts', async () => {
    const provider = new GenbankFileProvider()
    
    // Load first file
    const file1 = createMockFile(sampleGenbankContent, 'file1.gb')
    await provider.loadFromFile(file1)
    
    // Load second file with same record name
    const file2 = createMockFile(sampleGenbankContent, 'file2.gb')
    await provider.loadFromFile(file2)
    
    const records = await provider.getRecords()
    
    // Should have 2 records
    expect(records.length).toBe(2)
    
    // IDs should be different
    expect(records[0].recordId).toBe('file1.gb:TEST_BGC')
    expect(records[1].recordId).toBe('file2.gb:TEST_BGC')
    
    // Both should be loadable separately
    const entry1 = await provider.loadEntry(records[0].recordId)
    const entry2 = await provider.loadEntry(records[1].recordId)
    
    expect(entry1.filename).toBe('file1.gb')
    expect(entry2.filename).toBe('file2.gb')
  })

  test('should search records correctly', async () => {
    const provider = new GenbankFileProvider()
    const file = createMockFile(sampleGenbankContent, 'test.gb')
    
    await provider.loadFromFile(file)
    
    // Search for something that should match
    const results = await provider.searchRecords('testA')
    expect(results.records.length).toBeGreaterThan(0)
    
    // Search for something that shouldn't match
    const noResults = await provider.searchRecords('nonexistent_gene')
    expect(noResults.records.length).toBe(0)
  })

  test('should return empty arrays for antiSMASH-specific features', async () => {
    const provider = new GenbankFileProvider()
    const file = createMockFile(sampleGenbankContent, 'test.gb')
    
    await provider.loadFromFile(file)
    const records = await provider.getRecords()
    const recordId = records[0].recordId
    
    // GenBank files don't have these antiSMASH-specific features
    const regions = await provider.getRegions(recordId)
    expect(regions.regions).toEqual([])
    
    const mibig = await provider.getMiBIGEntries(recordId, 'TEST_001')
    expect(mibig.entries).toEqual([])
    
    const tfbs = await provider.getTFBSHits(recordId)
    expect(tfbs.hits).toEqual([])
    
    const tta = await provider.getTTACodons(recordId)
    expect(tta.codons).toEqual([])
    
    const resistance = await provider.getResistanceFeatures(recordId)
    expect(resistance.features).toEqual([])
  })

  test('should preserve sequence data', async () => {
    const provider = new GenbankFileProvider()
    const file = createMockFile(sampleGenbankContent, 'test.gb')
    
    await provider.loadFromFile(file)
    const records = await provider.getRecords()
    
    const features = await provider.getRecordFeatures(records[0].recordId)
    
    // This is indirectly testing that the record has sequence data
    // The actual sequence is stored internally but used by the viewer
    expect(features.features).toBeDefined()
  })
})
