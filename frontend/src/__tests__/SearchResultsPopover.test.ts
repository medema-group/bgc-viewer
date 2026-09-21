import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SearchResultsPopover from '@/components/SearchResultsPopover.vue'

const protoclusterHits = [
  {
    score: 4.5,
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
  },
  {
    score: 3.25,
    fields: {
      record: 'record-1',
      region: 2,
      protocluster: 4,
      start: 300,
      end: 450,
      product: 'T1PKS',
      category: 'PKS',
      organism: 'Example organism',
      output_file: 'nested/example.json',
      input_file: 'example.gbk'
    }
  }
]

describe('SearchResultsPopover', () => {
  it('renders separate protocluster rows from the same parent record', () => {
    const wrapper = mount(SearchResultsPopover, {
      props: {
        query: 'pfam:PF00512',
        level: 'protocluster',
        response: { hits: protoclusterHits, total: 2 },
        page: 1,
        selectedHit: null
      }
    })

    const rows = wrapper.findAll('.result-row')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('Protocluster 3')
    expect(rows[1].text()).toContain('Protocluster 4')
    expect(rows[0].text()).toContain('100–250')
    expect(rows[0].text()).toContain('nested/example.json · example.gbk')
  })

  it('emits the full selected hit and highlights the selected row', async () => {
    const wrapper = mount(SearchResultsPopover, {
      props: {
        query: 'NRPS',
        level: 'protocluster',
        response: { hits: protoclusterHits, total: 2 },
        page: 1,
        selectedHit: protoclusterHits[1]
      }
    })

    expect(wrapper.findAll('.result-row')[1].classes()).toContain('selected')
    await wrapper.findAll('.result-row')[0].trigger('click')
    expect(wrapper.emitted('search-selected')).toEqual([[protoclusterHits[0]]])
  })

  it('renders region and record summaries', async () => {
    const regionHit = {
      score: 2,
      record: 'record-2',
      region: 7,
      output_file: 'record-2.json',
      input_file: null
    }
    const wrapper = mount(SearchResultsPopover, {
      props: {
        query: 'terpene',
        level: 'region',
        response: { hits: [regionHit], total: 1 },
        page: 1,
        selectedHit: null
      }
    })

    expect(wrapper.text()).toContain('Region 7')
    expect(wrapper.text()).toContain('record-2.json')

    await wrapper.setProps({
      level: 'record',
      response: { hits: [{ ...regionHit, region: undefined }], total: 1 }
    })
    expect(wrapper.text()).not.toContain('Region 7')
    expect(wrapper.text()).toContain('record-2')
  })

  it('shows an empty state for a completed search with no matches', () => {
    const wrapper = mount(SearchResultsPopover, {
      props: {
        query: 'terpene',
        level: 'record',
        response: { hits: [], total: 0 },
        page: 1,
        selectedHit: null
      }
    })

    expect(wrapper.text()).toContain('No results found.')
    expect(wrapper.find('.pagination').exists()).toBe(false)
  })

  it('keeps rows visible while loading and emits page requests', async () => {
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
        response: { hits: [recordHit], total: 45 },
        page: 2,
        selectedHit: null,
        loading: true
      }
    })

    expect(wrapper.findAll('.result-row')).toHaveLength(1)
    expect(wrapper.text()).toContain('Updating results...')
    expect(wrapper.text()).toContain('Page 2 of 3')

    expect(wrapper.get('[aria-label="Previous search results page"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[aria-label="Next search results page"]').attributes('disabled')).toBeDefined()

    await wrapper.setProps({ loading: false })
    await wrapper.get('[aria-label="Previous search results page"]').trigger('click')
    await wrapper.get('[aria-label="Next search results page"]').trigger('click')

    expect(wrapper.emitted('page-change')).toEqual([[1], [3]])
  })
})