import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SearchResultsPopover from '@/components/SearchResultsPopover.vue'

const regionHits = [
  {
    score: 4.5,
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
  },
  {
    score: 3.25,
    fields: {
      record: 'record-1',
      region: 3,
      start: 300,
      end: 450,
      product: ['terpene'],
      product_category: ['terpene'],
      output_file: 'nested/example.json'
    }
  }
]

describe('SearchResultsPopover', () => {
  it('renders separate region rows from the same parent record', () => {
    const wrapper = mount(SearchResultsPopover, {
      props: {
        query: 'pfam:PF00512',
        level: 'region',
        response: { hits: regionHits, has_more: false, total_regions: 1, facets: {} },
        selectedHit: null
      }
    })

    const rows = wrapper.findAll('.result-row')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('Example organism')
    expect(rows[0].text()).toContain('NRPS, T1PKS')
    expect(rows[0].text()).toContain('NRPS, PKS')
    expect(rows[0].text()).toContain('record-1 · Region 2')
    expect(rows[0].text()).toContain('100–250')
    expect(rows[0].text()).toContain('nested/example.json · example.gbk')
    // Without an organism the record names the row; without an input file
    // only the output file is shown.
    expect(rows[1].find('.primary-text').text()).toBe('record-1')
    expect(rows[1].text()).toContain('Region 3')
    expect(rows[1].find('.file-line').text()).toBe('nested/example.json')
  })

  it('emits the full selected hit and highlights the selected row', async () => {
    const wrapper = mount(SearchResultsPopover, {
      props: {
        query: 'NRPS',
        level: 'region',
        response: { hits: regionHits, has_more: false, total_regions: 1, facets: {} },
        selectedHit: regionHits[1]
      }
    })

    expect(wrapper.findAll('.result-row')[1].classes()).toContain('selected')
    await wrapper.findAll('.result-row')[0].trigger('click')
    expect(wrapper.emitted('search-selected')).toEqual([[regionHits[0]]])
  })

  it('renders record summaries', () => {
    const wrapper = mount(SearchResultsPopover, {
      props: {
        query: 'terpene',
        level: 'record',
        response: {
          hits: [{ score: 2, record: 'record-2', output_file: 'record-2.json', input_file: null }],
          has_more: false,
          total_regions: 1,
          facets: {}
        },
        selectedHit: null
      }
    })

    expect(wrapper.text()).toContain('record-2')
    expect(wrapper.text()).toContain('record-2.json')
    expect(wrapper.text()).not.toContain('Region')
  })

  it('shows an empty state for a completed search with no matches', () => {
    const wrapper = mount(SearchResultsPopover, {
      props: {
        query: 'terpene',
        level: 'record',
        response: { hits: [], has_more: false, total_regions: 1, facets: {} },
        selectedHit: null
      }
    })

    expect(wrapper.text()).toContain('No results found.')
    expect(wrapper.find('.load-more').exists()).toBe(false)
  })

  it('shows a load-more affordance only when more results remain', async () => {
    const recordHit = {
      score: 2,
      record: 'record-2',
      output_file: 'record-2.json',
      input_file: null
    }
    const wrapper = mount(SearchResultsPopover, {
      props: {
        query: 'terpene',
        level: 'record',
        response: { hits: [recordHit], has_more: false, total_regions: 1, facets: {} },
        selectedHit: null
      }
    })
    expect(wrapper.find('.load-more').exists()).toBe(false)

    await wrapper.setProps({ response: { hits: [recordHit], has_more: true, total_regions: 1, facets: {} } })
    expect(wrapper.find('.load-more').exists()).toBe(true)
  })

  it('keeps rows visible while loading more and emits load-more', async () => {
    const recordHit = {
      score: 2,
      record: 'record-2',
      output_file: 'record-2.json',
      input_file: null
    }
    const wrapper = mount(SearchResultsPopover, {
      props: {
        query: 'terpene',
        level: 'record',
        response: { hits: [recordHit], has_more: true, total_regions: 1, facets: {} },
        selectedHit: null,
        loadingMore: true
      }
    })

    expect(wrapper.findAll('.result-row')).toHaveLength(1)

    const button = wrapper.get('.load-more button')
    expect(button.attributes('disabled')).toBeDefined()
    expect(button.text()).toContain('Loading')

    await wrapper.setProps({ loadingMore: false })
    expect(wrapper.get('.load-more button').attributes('disabled')).toBeUndefined()
    await wrapper.get('.load-more button').trigger('click')

    expect(wrapper.emitted('load-more')).toEqual([[]])
  })
})
