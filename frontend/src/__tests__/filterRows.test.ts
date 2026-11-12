// Row model tests ported from the BGC Atlas (lib/filters/rows.test.ts), plus
// the operator defaults, value normalization, and condition wording of this port.
import { describe, expect, it } from 'vitest'
import type { FilterCondition, FilterGroup, SearchFieldInfo } from '@/services/dataProviders/types'
import {
  RAW_QUERY_FIELD_INFO, conditionRow, createCondition, defaultCondition, defaultOperator, describeCondition,
  groupRow, groupToRows, isBlankCondition, normalizeValue, pruneRows, rowsHaveRules, rowsToGroup, summarizeRows,
  type FilterRow, type Join,
} from '@/services/filterRows'

const c = (field: string, value: string = 'x'): FilterCondition => createCondition(field, 'in', [value])
const row = (field: string, join: Join = 'AND') => conditionRow(c(field), join)

/** The tree with ids dropped, as nested arrays: ['AND', 'a', ['OR', 'b', 'c']]. */
type Shape = string | Shape[]
const shape = (g: FilterGroup): Shape => [g.operator, ...g.conditions.map((x) => x.field), ...g.groups.map(shape)]
const text = (rows: FilterRow[]): string => rows.map((r, i) => `${i ? `${r.join} ` : ''}${r.kind === 'condition' ? r.condition.field : `(${text(r.rows)})`}`).join(' ')
const describe_ = (x: FilterCondition) => x.field
const line = (rows: FilterRow[]) => summarizeRows(rows, describe_)
  .map((l) => `${l.joiner ? `${l.joiner} ` : ''}${l.parts.map((p) => p.value).join(' ')}`)

describe('rowsToGroup', () => {
  it('keeps an all-AND list as one AND group', () => {
    expect(shape(rowsToGroup([row('a'), row('b'), row('c')]))).toEqual(['AND', 'a', 'b', 'c'])
  })

  it('reads AND before OR: a AND b OR c AND d is (a AND b) OR (c AND d)', () => {
    const g = rowsToGroup([row('a'), row('b'), row('c', 'OR'), row('d')])
    expect(shape(g)).toEqual(['OR', ['AND', 'a', 'b'], ['AND', 'c', 'd']])
  })

  it('leaves a one-row alternative bare', () => {
    expect(shape(rowsToGroup([row('a'), row('b', 'OR')]))).toEqual(['OR', 'a', 'b'])
  })

  it('turns a bracketed group into a nested group', () => {
    const g = rowsToGroup([row('a'), groupRow([row('b'), row('c', 'OR')])])
    expect(shape(g)).toEqual(['AND', 'a', ['OR', 'b', 'c']])
  })

  it('keeps a condition written after a bracket in its place', () => {
    const g = rowsToGroup([row('a'), groupRow([row('b'), row('c', 'OR')]), row('d')])
    expect(shape(g)).toEqual(['AND', ['AND', 'a'], ['OR', 'b', 'c'], ['AND', 'd']])
    expect(text(groupToRows(g))).toBe('a AND (b OR c) AND d')
  })

  it('is empty for no rows', () => {
    expect(shape(rowsToGroup([]))).toEqual(['AND'])
  })
})

describe('groupToRows', () => {
  it('reads the polar example as three rows and one bracket', () => {
    const polar: FilterGroup = {
      id: 'r', operator: 'AND', conditions: [c('category'), c('complete'), c('kind')],
      groups: [{ id: 'g', operator: 'OR', conditions: [c('lat_n'), c('lat_s')], groups: [] }],
    }
    expect(text(groupToRows(polar))).toBe('category AND complete AND kind AND (lat_n OR lat_s)')
  })

  it('flattens an OR of AND groups into one list with per-row joins', () => {
    const g: FilterGroup = {
      id: 'r', operator: 'OR', conditions: [],
      groups: [
        { id: '1', operator: 'AND', conditions: [c('a'), c('b')], groups: [] },
        { id: '2', operator: 'AND', conditions: [c('c'), c('d')], groups: [] },
      ],
    }
    expect(text(groupToRows(g))).toBe('a AND b OR c AND d')
  })

  it('flattens same-operator nesting and the single-child wrapper', () => {
    const g: FilterGroup = {
      id: 'r', operator: 'AND', conditions: [],
      groups: [{ id: '1', operator: 'AND', conditions: [c('a'), c('b')], groups: [] }],
    }
    expect(text(groupToRows(g))).toBe('a AND b')
  })

  it('keeps an OR group inside an AND group in brackets', () => {
    const g: FilterGroup = {
      id: 'r', operator: 'AND', conditions: [c('a')],
      groups: [{ id: '1', operator: 'OR', conditions: [c('b'), c('c')], groups: [] }],
    }
    expect(text(groupToRows(g))).toBe('a AND (b OR c)')
  })

  it('returns nothing for null', () => {
    expect(groupToRows(null)).toEqual([])
  })

  it.each([
    'a AND b AND c',
    'a OR b',
    'a AND b OR c AND d',
    'a AND b OR c',
    'a OR b AND c OR d',
  ])('round-trips %s', (written) => {
    // Build rows from the written text: tokens alternate field, join, field…
    const tokens = written.split(' ')
    const rows = tokens.filter((_, i) => i % 2 === 0)
      .map((field, i) => row(field, i ? tokens[i * 2 - 1] as Join : 'AND'))
    expect(text(groupToRows(rowsToGroup(rows)))).toBe(written)
  })
})

describe('summarizeRows', () => {
  it('is one line per row while everything is ANDed', () => {
    expect(line([row('a'), row('b'), groupRow([row('c'), row('d', 'OR')])]))
      .toEqual(['a', 'AND b', 'AND ( c OR d )'])
  })

  it('is one line per alternative once an OR appears, bracketed', () => {
    expect(line([row('a'), row('b'), row('c', 'OR'), row('d')]))
      .toEqual(['( a AND b )', 'OR ( c AND d )'])
  })

  it('drops blank conditions and empty groups', () => {
    const blank = conditionRow(createCondition('blank', 'in', []))
    expect(line([row('a'), blank, groupRow([conditionRow(createCondition('e', 'in', []))])])).toEqual(['a'])
  })
})

describe('rowsHaveRules / pruneRows', () => {
  it('ignores half-built rows', () => {
    const blank = conditionRow(createCondition('a', 'in', []))
    expect(rowsHaveRules([blank, groupRow([blank])])).toBe(false)
    expect(rowsHaveRules([blank, row('b')])).toBe(true)
    expect(pruneRows([blank, groupRow([blank]), row('b')]).length).toBe(1)
  })
})

const field = (name: string, kind: SearchFieldInfo['kind'], facet = false): SearchFieldInfo => ({
  name, kind, label: name.toUpperCase(), group: 'G', multi: false, default_search: false,
  description: '', operators: [], facet, sortable: false
})

describe('defaultOperator', () => {
  it.each([
    [field('product', 'exact', true), 'in'],
    [field('core_seq', 'exact'), 'equals'],
    [field('length', 'numeric'), 'gte'],
    [field('is_complete', 'boolean'), 'equals'],
    [field('text', 'full_text'), 'contains'],
    [field('output_file', 'path'), 'contains'],
    [RAW_QUERY_FIELD_INFO, 'matches']
  ])('picks a starting operator for %o', (info, operator) => {
    expect(defaultOperator(info)).toBe(operator)
  })

  it('starts a yes/no condition at yes', () => {
    expect(defaultCondition(field('is_complete', 'boolean')).value).toBe('true')
  })
})

describe('normalizeValue', () => {
  it('carries a value into the shape the new operator takes', () => {
    expect(normalizeValue('5', 'between')).toEqual(['5', ''])
    expect(normalizeValue(['5', '9'], 'gte')).toBe('5')
    expect(normalizeValue('NRPS', 'in')).toEqual(['NRPS'])
    expect(normalizeValue('', 'in')).toEqual([])
    expect(normalizeValue(['a', 'b'], 'not_in')).toEqual(['a', 'b'])
    expect(normalizeValue('x', 'exists')).toBe('')
  })
})

describe('isBlankCondition', () => {
  it('treats exists as complete without a value', () => {
    expect(isBlankCondition(createCondition('substrates', 'exists', ''))).toBe(false)
    expect(isBlankCondition(createCondition('substrates', 'equals', '  '))).toBe(true)
    expect(isBlankCondition(createCondition('length', 'between', ['', null]))).toBe(true)
  })
})

describe('describeCondition', () => {
  const fields = new Map([['length', field('length', 'numeric')], ['product', field('product', 'exact')]])

  it.each([
    [createCondition('product', 'in', ['NRPS', 'T1PKS']), 'PRODUCT is any of NRPS, T1PKS'],
    [createCondition('length', 'between', ['10', '20']), 'LENGTH between 10 and 20'],
    [createCondition('length', 'between', ['10', '']), 'LENGTH at least 10'],
    [createCondition('length', 'between', [null, '20']), 'LENGTH at most 20'],
    [createCondition('product', 'exists'), 'PRODUCT has a value'],
    [createCondition('unknown', 'equals', 'true'), 'unknown is yes']
  ])('words %o', (condition, words) => {
    expect(describeCondition(condition, fields)).toBe(words)
  })
})
