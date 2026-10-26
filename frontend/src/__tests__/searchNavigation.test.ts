import { describe, expect, it } from 'vitest'

import {
  protoclusterNumberFromHit,
  recordSelectionFromHit,
  regionIdFromHit
} from '@/services/searchNavigation'

describe('recordSelectionFromHit', () => {
  it.each([
    [
      'protocluster',
      {
        score: 4,
        fields: {
          record: 'record-1',
          region: 2,
          protocluster: 3,
          start: 100,
          end: 250,
          product: 'NRPS',
          category: 'Peptide',
          organism: 'Example organism',
          output_file: 'nested/example.json',
          input_file: 'example.gbk'
        }
      }
    ],
    [
      'region',
      {
        score: 3,
        record: 'record-1',
        region: 2,
        output_file: 'nested/example.json',
        input_file: 'example.gbk'
      }
    ],
    [
      'record',
      {
        score: 2,
        record: 'record-1',
        output_file: 'nested/example.json',
        input_file: 'example.gbk'
      }
    ]
  ] as const)('composes the existing entry id for a %s hit', (level, hit) => {
    expect(recordSelectionFromHit(level, hit)).toEqual({
      entryId: 'nested/example.json:record-1',
      recordId: 'record-1',
      filename: 'nested/example.json'
    })
  })
})

describe('regionIdFromHit', () => {
  it('returns the region target from a protocluster hit', () => {
    expect(regionIdFromHit('protocluster', {
      score: 4,
      fields: {
        record: 'record-1',
        region: 2,
        protocluster: 3,
        start: 100,
        end: 250,
        product: 'NRPS',
        category: 'Peptide',
        organism: 'Example organism',
        output_file: 'nested/example.json',
        input_file: 'example.gbk'
      }
    })).toBe('region_2')
  })

  it('returns the region target from a region hit', () => {
    expect(regionIdFromHit('region', {
      score: 3,
      record: 'record-1',
      region: 2,
      output_file: 'nested/example.json',
      input_file: 'example.gbk'
    })).toBe('region_2')
  })

  it('clears the region target for a record hit', () => {
    expect(regionIdFromHit('record', {
      score: 2,
      record: 'record-1',
      output_file: 'nested/example.json',
      input_file: 'example.gbk'
    })).toBe('')
  })
})

describe('protoclusterNumberFromHit', () => {
  const protoclusterHit = {
    score: 4,
    fields: {
      record: 'record-1',
      region: 2,
      protocluster: 3,
      start: 100,
      end: 250,
      product: 'NRPS',
      category: 'Peptide',
      organism: 'Example organism',
      output_file: 'nested/example.json',
      input_file: 'example.gbk'
    }
  }

  it('returns the target from a protocluster hit', () => {
    expect(protoclusterNumberFromHit('protocluster', protoclusterHit)).toBe(3)
  })

  it('clears the target for other hit levels', () => {
    expect(protoclusterNumberFromHit('region', {
      score: 3,
      record: 'record-1',
      region: 2,
      output_file: 'nested/example.json',
      input_file: 'example.gbk'
    })).toBeNull()
  })
})