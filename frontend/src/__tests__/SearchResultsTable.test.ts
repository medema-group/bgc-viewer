import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import RefinePanel from '@/components/RefinePanel.vue'
import SearchResultsTable from '@/components/SearchResultsTable.vue'
import type {
  ProtoclusterSearchHit,
  RecordSearchHit,
  RegionSearchHit,
  SearchSort
} from '@/services/dataProviders/types'

const regionHit = (record: string, region: number): RegionSearchHit => ({
  score: 1,
  fields: {
    record,
    region,
    start: 1000,
    end: 25000,
    length: 24000,
    product: ['NRPS', 'T1PKS'],
    product_category: ['NRPS', 'PKS'],
    organism: 'Streptomyces coelicolor',
    output_file: `${record}.json`
  }
})

const protoclusterHit = (record: string, region: number, number: number): ProtoclusterSearchHit => ({
  score: 1,
  fields: {
    ...regionHit(record, region).fields,
    start: 4000,
    end: 16500,
    length: 12500,
    product: ['NRPS'],
    product_category: ['NRPS'],
    protocluster_number: number
  }
})

const recordHit: RecordSearchHit = {
  score: null,
  record: 'recA',
  output_file: 'recA.json',
  input_file: 'recA.gbk',
  description: 'Streptomyces coelicolor A3(2), complete genome',
  organism: 'Streptomyces coelicolor A3(2)',
  region_count: 29,
  feature_count: 17892
}

function mountTable(props: Partial<InstanceType<typeof SearchResultsTable>['$props']> = {}) {
  return mount(SearchResultsTable, {
    props: {
      level: 'region',
      response: { hits: [regionHit('recA', 1), regionHit('recB', 2)], has_more: true, total: 45, facets: {} },
      page: 2,
      perPage: 20,
      sort: null,
      sortableFields: ['record', 'region', 'length', 'organism'],
      selectedHit: null,
      ...props
    }
  })
}

describe('SearchResultsTable', () => {
  it('shows region rows with products, length, and paging status', () => {
    const wrapper = mountTable()
    const cells = wrapper.findAll('tbody tr')[0].findAll('td').map(td => td.text())

    expect(cells).toEqual(['recA', '1', '24.0', 'NRPS, T1PKS', 'NRPS, PKS', 'Streptomyces coelicolor', 'recA.json'])
    expect(wrapper.get('.pager-status').text()).toBe('21–22 of 45 matching regions')
    // Number columns are right-aligned, headers included
    expect(wrapper.findAll('th.number').map(th => th.text())).toEqual(['Region ↕', 'Length (kb) ↕'])
  })

  it('shows record rows', () => {
    const wrapper = mountTable({
      level: 'record',
      page: 1,
      response: { hits: [recordHit], has_more: false, total: 3, facets: {} }
    })
    expect(wrapper.get('tbody tr').findAll('td').map(td => td.text())).toEqual([
      'recA',
      'Streptomyces coelicolor A3(2)',
      'Streptomyces coelicolor A3(2), complete genome',
      '29',
      '17,892',
      'recA.json',
      'recA.gbk'
    ])
    expect(wrapper.get('.pager-status').text()).toBe('Records 1–1 · 3 matching regions')
  })

  it('shows protocluster rows with their parent region and counts protoclusters', () => {
    const wrapper = mountTable({
      level: 'protocluster',
      page: 1,
      response: {
        hits: [protoclusterHit('recA', 4, 5), protoclusterHit('recA', 4, 6)],
        has_more: false,
        total: 2,
        facets: {}
      },
      sortableFields: ['protocluster_number']
    })
    expect(wrapper.findAll('thead th').map(th => th.text())).toEqual([
      'Record',
      'Region',
      'Protocluster ↕',
      'Length (kb)',
      'Product',
      'Category',
      'Organism',
      'File'
    ])
    expect(wrapper.get('tbody tr').findAll('td').map(td => td.text())).toEqual([
      'recA', '4', '5', '12.5', 'NRPS', 'NRPS', 'Streptomyces coelicolor', 'recA.json'
    ])
    expect(wrapper.get('.pager-status').text()).toBe('1–2 of 2 matching protoclusters')
  })

  it('keeps protoclusters of one region apart when selecting', () => {
    const wrapper = mountTable({
      level: 'protocluster',
      response: {
        hits: [protoclusterHit('recA', 4, 5), protoclusterHit('recA', 4, 6)],
        has_more: false,
        total: 2,
        facets: {}
      },
      selectedHit: protoclusterHit('recA', 4, 6)
    })
    expect(wrapper.findAll('tbody tr').map(row => row.classes().includes('selected'))).toEqual([false, true])
  })

  it('leaves record details empty when the record index lacks them', () => {
    const wrapper = mountTable({
      level: 'record',
      page: 1,
      response: {
        hits: [{ ...recordHit, description: null, organism: null, region_count: null, feature_count: null }],
        has_more: false,
        total: 1,
        facets: {}
      }
    })
    expect(wrapper.get('tbody tr').findAll('td').map(td => td.text())).toEqual(['recA', '', '', '', '', 'recA.json', 'recA.gbk'])
  })

  it('only offers sorting on sortable fields and cycles asc, desc, relevance', async () => {
    const sorts: (SearchSort | null)[] = [null, { field: 'organism', order: 'asc' }, { field: 'organism', order: 'desc' }]
    const emitted = []
    for (const sort of sorts) {
      const wrapper = mountTable({ sort, sortableFields: ['organism'] })
      expect(wrapper.findAll('.sort-button')).toHaveLength(1)
      await wrapper.get('.sort-button').trigger('click')
      emitted.push(wrapper.emitted('sort')![0][0])
    }
    expect(emitted).toEqual([{ field: 'organism', order: 'asc' }, { field: 'organism', order: 'desc' }, null])
  })

  it('pages and selects', async () => {
    const wrapper = mountTable()
    await wrapper.get('[aria-label="Previous page"]').trigger('click')
    await wrapper.get('[aria-label="Next page"]').trigger('click')
    await wrapper.findAll('tbody tr')[1].trigger('click')

    expect(wrapper.emitted('page')).toEqual([[1], [3]])
    expect(wrapper.emitted('select')).toEqual([[regionHit('recB', 2)]])
  })

  it('disables paging at the ends and marks the selected row', () => {
    const wrapper = mountTable({
      page: 1,
      response: { hits: [regionHit('recA', 1)], has_more: false, total: 1, facets: {} },
      selectedHit: regionHit('recA', 1)
    })
    expect(wrapper.get('[aria-label="Previous page"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[aria-label="Next page"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('tbody tr').classes()).toContain('selected')
  })

  it('says when nothing matches', () => {
    const wrapper = mountTable({ response: { hits: [], has_more: false, total: 0, facets: {} } })
    expect(wrapper.get('td.empty').text()).toBe('No regions match this search.')
  })
})

describe('RefinePanel', () => {
  it('lists facet values with counts and adds one as a filter', async () => {
    const wrapper = mount(RefinePanel, {
      props: {
        facets: { product: [{ value: 'NRPS', count: 1200 }], organism: [] },
        labels: new Map([['product', 'Product']])
      }
    })

    expect(wrapper.findAll('h4').map(h => h.text())).toEqual(['Product'])
    expect(wrapper.get('li').text()).toBe('NRPS1,200')
    await wrapper.get('li button').trigger('click')
    expect(wrapper.emitted('add')).toEqual([['product', 'NRPS']])
  })
})
