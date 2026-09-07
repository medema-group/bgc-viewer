import { describe, test, expect } from 'vitest'
import { genbankToJson } from '@teselagen/bio-parsers'

/**
 * Tests for GenBank file parsing using @teselagen/bio-parsers
 * 
 * These tests verify that the bio-parsers library returns the expected
 * structure when parsing GenBank format files.
 */
describe('GenBank Parser', () => {
  // Sample GenBank file content (minimal valid GenBank format)
  const sampleGenbank = `LOCUS       TEST_BGC                1000 bp    DNA     linear   BCT 01-JAN-2024
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
     gene            600..900
                     /gene="testB"
                     /locus_tag="TEST_002"
     CDS             600..900
                     /gene="testB"
                     /locus_tag="TEST_002"
                     /product="Test enzyme B"
                     /protein_id="TEST001.2"
                     /translation="MATEIKLMKLQQQHHQQQQQQQQQQPPPPPPPPPGGGGGGGGGG"
ORIGIN      
        1 atgaaagttc tgtgggtggc cgcattgctg gtcaccttcc tggcgggttg ccaggcgaaa
       61 gtggaacagg ccgttgaaac cgaaccagaa ccagagctga gacaacagta ccaacaacag
      121 tacggacaac aatacggatg atcgaagaag tcatcttacc gccacaaacg cctgacgttg
      181 tcggtacttc cggtacggta cggtacggta cggtacggta cgatcgatcg atcgatcgat
      241 cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat
      301 cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat
      361 cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat
      421 cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat
      481 cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat
      541 cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat
      601 cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat
      661 cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat
      721 cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat
      781 cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat
      841 cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat
      901 cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat
      961 cgatcgatcg atcgatcgat cgatcgatcg atcgatcgat
//
`

  test('should parse GenBank file and return array', () => {
    const result = genbankToJson(sampleGenbank)
    
    // Should return an array (even for single record)
    expect(Array.isArray(result)).toBe(true)
    expect(result.length).toBeGreaterThan(0)
  })

  test('should extract basic record information', () => {
    const result = genbankToJson(sampleGenbank)
    const record = result[0]
    
    // Check for essential fields
    expect(record).toBeDefined()
    
    // Log the actual structure to understand what we get
    console.log('Parsed GenBank record structure:')
    console.log('Keys:', Object.keys(record))
    console.log('Type:', typeof record)
    
    // The record should have some identifiable properties
    // Note: We're not asserting specific keys yet because we need to discover them
    expect(typeof record).toBe('object')
  })

  test('should parse features array', () => {
    const result = genbankToJson(sampleGenbank)
    const record = result[0]
    
    // Log features structure
    console.log('\nFeatures structure:')
    if (record.features) {
      console.log('  Direct features:', record.features.length)
      console.log('  First feature:', JSON.stringify(record.features[0], null, 2))
    }
    if (record.parsedSequence?.features) {
      console.log('  Parsed sequence features:', record.parsedSequence.features.length)
      console.log('  First feature:', JSON.stringify(record.parsedSequence.features[0], null, 2))
    }
    
    // Features might be in record.features or record.parsedSequence.features
    const features = record.features || record.parsedSequence?.features || []
    
    expect(Array.isArray(features)).toBe(true)
    expect(features.length).toBeGreaterThan(0)
  })

  test('should extract feature details', () => {
    const result = genbankToJson(sampleGenbank)
    const record = result[0]
    const features = record.features || record.parsedSequence?.features || []
    
    // Find a CDS feature
    const cdsFeature = features.find((f: any) => f.type === 'CDS' || f.type === 'cds')
    
    console.log('\nCDS Feature structure:')
    console.log(JSON.stringify(cdsFeature, null, 2))
    
    expect(cdsFeature).toBeDefined()
    
    // Check for location information
    expect(cdsFeature.start).toBeDefined()
    expect(cdsFeature.end).toBeDefined()
    
    // Log what we found
    console.log('CDS start:', cdsFeature.start)
    console.log('CDS end:', cdsFeature.end)
    console.log('CDS strand:', cdsFeature.strand)
  })

  test('should extract sequence information', () => {
    const result = genbankToJson(sampleGenbank)
    const record = result[0]
    
    console.log('\nSequence information:')
    console.log('  record.sequence:', record.sequence ? `${record.sequence.substring(0, 50)}... (${record.sequence.length} bp)` : 'undefined')
    console.log('  record.seq:', record.seq ? `${record.seq.substring(0, 50)}... (${record.seq.length} bp)` : 'undefined')
    console.log('  record.parsedSequence?.sequence:', record.parsedSequence?.sequence ? `${record.parsedSequence.sequence.substring(0, 50)}... (${record.parsedSequence.sequence.length} bp)` : 'undefined')
    
    // Sequence might be in different locations
    const sequence = record.sequence || record.seq || record.parsedSequence?.sequence
    
    expect(sequence).toBeDefined()
    expect(typeof sequence).toBe('string')
    expect(sequence.length).toBeGreaterThan(0)
  })

  test('should extract record name and version', () => {
    const result = genbankToJson(sampleGenbank)
    const record = result[0]
    
    console.log('\nRecord metadata:')
    console.log('  record.name:', record.name)
    console.log('  record.version:', record.version)
    console.log('  record.accession:', record.accession)
    console.log('  record.parsedSequence?.name:', record.parsedSequence?.name)
    console.log('  record.parsedSequence?.version:', record.parsedSequence?.version)
    console.log('  record.parsedSequence?.accession:', record.parsedSequence?.accession)
    
    // Name/version might be in different locations
    const name = record.name || record.parsedSequence?.name
    const version = record.version || record.parsedSequence?.version || record.parsedSequence?.accession
    
    expect(name || version).toBeDefined()
  })

  test('should extract feature qualifiers/notes', () => {
    const result = genbankToJson(sampleGenbank)
    const record = result[0]
    const features = record.features || record.parsedSequence?.features || []
    
    // Find a CDS feature with qualifiers
    const cdsFeature = features.find((f: any) => 
      (f.type === 'CDS' || f.type === 'cds') && (f.notes || f.qualifiers)
    )
    
    console.log('\nFeature qualifiers/notes:')
    console.log('  notes:', JSON.stringify(cdsFeature?.notes, null, 2))
    console.log('  qualifiers:', JSON.stringify(cdsFeature?.qualifiers, null, 2))
    console.log('  gene:', cdsFeature?.gene)
    console.log('  product:', cdsFeature?.product)
    console.log('  locus_tag:', cdsFeature?.locus_tag)
    
    // Feature should have some annotation data
    const hasAnnotation = cdsFeature?.notes || cdsFeature?.qualifiers || cdsFeature?.gene || cdsFeature?.product
    expect(hasAnnotation).toBeTruthy()
  })

  test('should provide complete structure summary', () => {
    const result = genbankToJson(sampleGenbank)
    const record = result[0]
    
    console.log('\n=== COMPLETE RECORD STRUCTURE ===')
    console.log('Top-level keys:', Object.keys(record).join(', '))
    
    if (record.parsedSequence) {
      console.log('\nparsedSequence keys:', Object.keys(record.parsedSequence).join(', '))
    }
    
    console.log('\n=== EXPECTED MAPPING ===')
    console.log('For GenbankFileProvider.convertGenbankToAntiSMASH:')
    console.log('  Record name:', record.name || record.parsedSequence?.name || 'NOT FOUND')
    console.log('  Version:', record.version || record.parsedSequence?.version || record.parsedSequence?.accession || 'NOT FOUND')
    console.log('  Description:', record.comments || record.parsedSequence?.comments || record.definition || record.parsedSequence?.description || 'NOT FOUND')
    console.log('  Sequence:', (record.sequence || record.parsedSequence?.sequence) ? 'FOUND' : 'NOT FOUND')
    console.log('  Features count:', (record.features || record.parsedSequence?.features || []).length)
    
    // This test always passes - it's just for logging
    expect(true).toBe(true)
  })
})
