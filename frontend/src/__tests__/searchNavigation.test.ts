import { describe, expect, it } from 'vitest'

import {
  recordSelectionFromHit,
  regionIdFromHit
} from '@/services/searchNavigation'

const regionHit = {
  score: 3,
  fields: {
    record: 'record-1',
    region: 2,
    start: 100,
    end: 250,
    product: ['NRPS', 'T1PKS'],
    product_category: ['NRPS', 'PKS'],
    organism: 'Example organism',
    output_file: 'nested/example.json',
    input_file: 'example.gbk'
  }
}

const recordHit = {
  score: 2,
  record: 'record-1',
  output_file: 'nested/example.json',
  input_file: 'example.gbk'
}

describe('recordSelectionFromHit', () => {
  it.each([
    ['region', regionHit],
    ['record', recordHit]
  ] as const)('composes the existing entry id for a %s hit', (level, hit) => {
    expect(recordSelectionFromHit(level, hit)).toEqual({
      entryId: 'nested/example.json:record-1',
      recordId: 'record-1',
      filename: 'nested/example.json'
    })
  })
})

describe('regionIdFromHit', () => {
  it('returns the region target from a region hit', () => {
    expect(regionIdFromHit('region', regionHit)).toBe('region_2')
  })

  it('clears the region target for a record hit', () => {
    expect(regionIdFromHit('record', recordHit)).toBe('')
  })
})
