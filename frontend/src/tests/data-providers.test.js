/**
 * Data Provider Tests
 * Tests for JSONFileProvider and BGCViewerAPIProvider
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import axios from 'axios'
import { JSONFileProvider } from '../services/dataProviders/JSONFileProvider'
import { BGCViewerAPIProvider } from '../services/dataProviders/BGCViewerAPIProvider'

vi.mock('axios', () => ({
  default: {
    create: vi.fn()
  }
}))

describe('JSONFileProvider', () => {
  let provider
  const mockData = {
    records: [
      {
        id: 'test-record-1',
        seq_id: 'NC_003888.3',
        description: 'Test record 1',
        features: [
          { 
            type: 'region', 
            id: 'region-feature-1', 
            location: '100..1000',
            qualifiers: {
              region_number: ['1'],
              product: ['NRPS']
            }
          },
          { 
            type: 'CDS', 
            id: 'gene1', 
            location: '200..500' 
          }
        ]
      }
    ]
  }

  beforeEach(() => {
    provider = new JSONFileProvider(mockData)
  })

  describe('initialization', () => {
    it('should initialize with JSON data', () => {
      expect(provider).toBeInstanceOf(JSONFileProvider)
    })

    it('should parse entryId format correctly', async () => {
      const entryInfo = await provider.loadEntry('test.json:test-record-1')
      expect(entryInfo.recordId).toBe('test-record-1')
      expect(entryInfo.filename).toBe('test.json')
    })
  })

  describe('getRecords', () => {
    it('should return list of records', async () => {
      const records = await provider.getRecords()
      expect(records).toHaveLength(1)
      expect(records[0].recordId).toBe('test-record-1')
      expect(records[0].recordInfo.description).toBe('Test record 1')
    })
  })

  describe('getRegions', () => {
    it('should return regions object for a record', async () => {
      const regionsData = await provider.getRegions('test-record-1')
      expect(regionsData).toHaveProperty('regions')
      expect(regionsData.regions).toHaveLength(1)
      expect(regionsData.regions[0].region_number).toBe(1) // Number per Region interface
      expect(regionsData.regions[0].product).toContain('NRPS')
    })

    it('should throw error for non-existent record', async () => {
      await expect(provider.getRegions('non-existent')).rejects.toThrow('Record not found')
    })
  })

  describe('loadEntry', () => {
    it('should load entry with description', async () => {
      const entry = await provider.loadEntry('test.json:test-record-1')
      expect(entry.recordId).toBe('test-record-1')
      expect(entry.recordInfo.description).toBe('Test record 1')
    })

    it('should handle entryId without colon', async () => {
      const entry = await provider.loadEntry('test-record-1')
      expect(entry.recordId).toBe('test-record-1')
    })
  })

  describe('getRecordFeatures', () => {
    it('should return features object for a record', async () => {
      const featuresData = await provider.getRecordFeatures('test-record-1')
      expect(featuresData).toHaveProperty('features')
      expect(featuresData.features).toHaveLength(2) // region + CDS
      // Find the CDS feature (not the region feature)
      const cdsFeature = featuresData.features.find(f => f.type === 'CDS')
      expect(cdsFeature).toBeDefined()
      expect(cdsFeature.id).toBe('gene1')
    })
  })
})

describe('BGCViewerAPIProvider', () => {
  let provider
  let axiosInstance

  beforeEach(() => {
    axiosInstance = {
      get: vi.fn(),
      post: vi.fn()
    }
    axios.create.mockReturnValue(axiosInstance)
    provider = new BGCViewerAPIProvider()
  })

  describe('initialization', () => {
    it('should initialize with default baseURL', () => {
      expect(provider).toBeInstanceOf(BGCViewerAPIProvider)
    })

    it('should accept custom baseURL', () => {
      const customProvider = new BGCViewerAPIProvider('http://custom-api.com')
      expect(customProvider).toBeInstanceOf(BGCViewerAPIProvider)
    })
  })

  describe('advanced search', () => {
    it.each(['protocluster', 'region', 'record'])(
      'posts %s searches to the matching level endpoint',
      async (level) => {
        const searchResponse = { hits: [], total: 0 }
        axiosInstance.post.mockResolvedValue({ data: searchResponse })

        const result = await provider.searchLevel(level, 'pfam:PF00512', 2, 50)

        expect(axiosInstance.post).toHaveBeenCalledWith(`/api/search/${level}`, {
          query: 'pfam:PF00512',
          page: 2,
          per_page: 50
        })
        expect(result).toBe(searchResponse)
      }
    )

    it('gets the shared search schema', async () => {
      const schema = {
        fields: [],
        examples: ['pfam:PF00512'],
        query_syntax_url: 'https://example.test/query-parser'
      }
      axiosInstance.get.mockResolvedValue({ data: schema })

      const result = await provider.getSearchSchema()

      expect(axiosInstance.get).toHaveBeenCalledWith('/api/search/schema')
      expect(result).toBe(schema)
    })
  })
})
