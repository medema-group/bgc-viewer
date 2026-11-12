import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import RefinePanel from '@/components/RefinePanel.vue'
import SearchResultsTable from '@/components/SearchResultsTable.vue'
import type { RecordSearchHit, RegionSearchHit, SearchSort } from '@/services/dataProviders/types'

const regionHit = (record: string, region: number): RegionSearchHit => ({
  score: 1,
  fields: {
    record,
    region,
    start: 1000,
    end: 25000,
    product: ['NRPS', 'T1PKS'],
    product_category: ['NRPS', 'PKS'],
    organism: 'Streptomyces coelicolor',
    output_file: `${record}.json`
  }
})

const recordHit: RecordSearchHit = { score: null, record: 'recA', output_file: 'recA.json', input_file: 'recA.gbk' }

function mountTable(props: Partial<InstanceType<typeof SearchResultsTable>['$props']> = {}) {
  return mount(SearchResultsTable, {
    props: {
      level: 'region',
      response: { hits: [regionHit('recA', 1), regionHit('recB', 2)], has_more: true, total_regions: 45, facets: {} },
      page: 2,
      perPage: 20,
      sort: null,
      sortableFields: ['record', 'region', 'start', 'organism'],
      selectedHit: null,
      ...props
    }
  })
}

describe('SearchResultsTable', () => {
  it('shows region rows with products, location, and paging status', () => {
    const wrapper = mountTable()
    const cells = wrapper.findAll('tbody tr')[0].findAll('td').map(td => td.text())

    expect(cells).toEqual(['recA', '1', '1,000–25,000', 'NRPS, T1PKS', 'NRPS, PKS', 'Streptomyces coelicolor', 'recA.json'])
    expect(wrapper.get('.pager-status').text()).toBe('21–22 of 45 matching regions')
  })

  it('shows record rows', () => {
    const wrapper = mountTable({
      level: 'record',
      page: 1,
      response: { hits: [recordHit], has_more: false, total_regions: 3, facets: {} }
    })
    expect(wrapper.get('tbody tr').findAll('td').map(td => td.text())).toEqual(['recA', 'recA.json', 'recA.gbk'])
    expect(wrapper.get('.pager-status').text()).toBe('Records 1–1 · 3 matching regions')
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
      response: { hits: [regionHit('recA', 1)], has_more: false, total_regions: 1, facets: {} },
      selectedHit: regionHit('recA', 1)
    })
    expect(wrapper.get('[aria-label="Previous page"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[aria-label="Next page"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('tbody tr').classes()).toContain('selected')
  })

  it('says when nothing matches', () => {
    const wrapper = mountTable({ response: { hits: [], has_more: false, total_regions: 0, facets: {} } })
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
