import { describe, expect, it } from 'vitest'

import {
  protoclusterNumberFromHit,
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
    length: 151,
    product: ['NRPS', 'T1PKS'],
    product_category: ['NRPS', 'PKS'],
    organism: 'Example organism',
    output_file: 'nested/example.json',
    input_file: 'example.gbk'
  }
}

const protoclusterHit = {
  score: 1,
  fields: { ...regionHit.fields, product: ['NRPS'], product_category: ['NRPS'], protocluster_number: 5 }
}

const recordHit = {
  score: 2,
  record: 'record-1',
  output_file: 'nested/example.json',
  input_file: 'example.gbk',
  description: null,
  organism: null,
  region_count: null,
  feature_count: null
}

describe('recordSelectionFromHit', () => {
  it.each([
    ['region', regionHit],
    ['record', recordHit],
    ['protocluster', protoclusterHit]
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

  it('opens the parent region of a protocluster hit', () => {
    expect(regionIdFromHit('protocluster', protoclusterHit)).toBe('region_2')
  })

  it('clears the region target for a record hit', () => {
    expect(regionIdFromHit('record', recordHit)).toBe('')
  })
})

describe('protoclusterNumberFromHit', () => {
  it('returns the protocluster of a protocluster hit', () => {
    expect(protoclusterNumberFromHit('protocluster', protoclusterHit)).toBe(5)
  })

  it('returns nothing at the region and record levels', () => {
    expect(protoclusterNumberFromHit('region', regionHit)).toBeNull()
    expect(protoclusterNumberFromHit('record', recordHit)).toBeNull()
  })
})
