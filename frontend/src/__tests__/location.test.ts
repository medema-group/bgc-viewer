import { describe, test, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import FeatureDetails from '@/components/FeatureDetails.vue'
import { formatLocation, parseLocation } from '@/utils/location'

const INTRON_LOCATION = 'join{[9388:10393](+), [10457:21546](+), [21877:21912](+)}'

describe('parseLocation', () => {
  test('parses a simple location', () => {
    expect(parseLocation('[<164:>2414](-)')).toEqual({
      start: 164,
      end: 2414,
      strand: '-',
      parts: [{ start: 164, end: 2414 }]
    })
  })

  test('covers the entire span of a location with introns', () => {
    expect(parseLocation(INTRON_LOCATION)).toMatchObject({ start: 9388, end: 21912, strand: '+' })
    expect(parseLocation('join{[300:400](-), [100:200](-)}')).toMatchObject({ start: 100, end: 400, strand: '-' })
    expect(parseLocation('join{[0:100](+), [200:300](+)}')).toMatchObject({ start: 0, end: 300 })
  })

  test.each([
    ['join{[900:1000](+), [0:200](+)}', 900, 1000],
    ['join{[0:200](-), [900:1000](-)}', 0, 200],
    ['join{[900:950](+), [10:100](+)}', 900, 950],
    ['join{[10:100](-), [900:950](-)}', 10, 100]
  ])('uses the first part of origin-crossing location %s', (location, start, end) => {
    expect(parseLocation(location)).toMatchObject({ start, end, parts: [{ start, end }] })
  })

  test('returns null for missing or invalid locations', () => {
    expect(parseLocation(undefined)).toBeNull()
    expect(parseLocation('invalid')).toBeNull()
  })
})

describe('formatLocation', () => {
  test('formats a simple location', () => {
    expect(formatLocation('[164:2414](+)')).toBe('165 - 2,414, + (total: 2,250 nt)')
  })

  test('formats a location with introns', () => {
    expect(formatLocation(INTRON_LOCATION)).toBe('9,389 - 21,912, + (total: 12129 nt, excluding introns)')
  })

  test('returns an unparseable location unchanged', () => {
    expect(formatLocation('invalid')).toBe('invalid')
  })
})

describe('FeatureDetails location', () => {
  test('displays a location with introns', () => {
    const wrapper = mount(FeatureDetails, {
      props: { feature: { type: 'CDS', location: INTRON_LOCATION, qualifiers: {} } }
    })

    expect(wrapper.text()).toContain('9,389 - 21,912, + (total: 12129 nt, excluding introns)')
  })
})
