import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import ResultsPanel, { type ResultsTab } from '@/components/ResultsPanel.vue'
import { useAdvancedSearch } from '@/composables/useAdvancedSearch'
import type { LoadedRecord } from '@/composables/useLoadedRecords'
import type { BGCViewerAPIProvider } from '@/services/dataProviders/BGCViewerAPIProvider'
import type { DataProvider, SearchSchema } from '@/services/dataProviders/types'

const schema: SearchSchema = {
  fields: [
    {
      name: 'text',
      kind: 'full_text',
      label: 'Any text',
      group: 'General',
      multi: false,
      default_search: true,
      description: '',
      operators: ['contains'],
      facet: false,
      sortable: false
    }
  ],
  examples: [],
  query_syntax_url: 'https://example.test',
  raw_query_field: '_query'
}

const recordHit = {
  score: 1,
  record: 'recA',
  output_file: 'recA.json',
  input_file: null,
  description: 'Record A',
  organism: 'Streptomyces',
  region_count: 2,
  feature_count: 40
}

const loadedRecord: LoadedRecord = {
  key: 'mibig/BGC.json:BGC0000001',
  source: 'mibig',
  sourceLabel: 'MIBiG',
  entryId: 'BGC.json:BGC0000001',
  recordId: 'BGC0000001',
  filename: 'BGC.json',
  description: 'An entry',
  regionCount: 1,
  featureCount: 12,
  provider: {} as DataProvider
}

async function mountPanel(tab: ResultsTab, loadedRecords: LoadedRecord[], searched = true) {
  const provider = {
    getSearchSchema: vi.fn().mockResolvedValue(schema),
    search: vi.fn().mockResolvedValue({
      hits: [recordHit],
      has_more: false,
      total_regions: 2,
      facets: { product: [{ value: 'NRPS', count: 2 }] }
    }),
    getFieldValues: vi.fn()
  }
  const search = useAdvancedSearch(() => provider as unknown as BGCViewerAPIProvider)
  if (searched) await search.openIndex()
  const wrapper = mount(ResultsPanel, { props: { search, tab, loadedRecords } })
  await flushPromises()
  return wrapper
}

const tabs = (wrapper: Awaited<ReturnType<typeof mountPanel>>) =>
  wrapper.findAll('[role="tab"]').map(tab => [tab.text(), tab.attributes('aria-selected')])

describe('ResultsPanel', () => {
  it('shows the search results with refine values beside them', async () => {
    const wrapper = await mountPanel('search', [])

    expect(tabs(wrapper)).toEqual([['Search results', 'true']])
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    expect(wrapper.get('.refine-scroll').text()).toContain('NRPS')

    await wrapper.get('tbody tr').trigger('click')
    expect(wrapper.emitted('select-hit')).toEqual([[recordHit]])
  })

  it('offers the loaded records as a second tab', async () => {
    const wrapper = await mountPanel('search', [loadedRecord])

    expect(tabs(wrapper)).toEqual([['Search results', 'true'], ['Loaded records 1', 'false']])
    await wrapper.findAll('[role="tab"]')[1].trigger('click')
    expect(wrapper.emitted('update:tab')).toEqual([['loaded']])
  })

  it('lists the loaded records on their tab', async () => {
    const wrapper = await mountPanel('loaded', [loadedRecord])

    expect(wrapper.find('.refine-scroll').exists()).toBe(false)
    await wrapper.get('tbody tr').trigger('click')
    await wrapper.get('[aria-label="Remove MIBiG records"]').trigger('click')

    expect(wrapper.emitted('select-loaded')).toEqual([[loadedRecord]])
    expect(wrapper.emitted('remove-source')).toEqual([['mibig']])
  })

  it('falls back to the tab that has something to show', async () => {
    expect(tabs(await mountPanel('loaded', []))).toEqual([['Search results', 'true']])
    expect(tabs(await mountPanel('search', [loadedRecord], false))).toEqual([
      ['Search results', 'false'],
      ['Loaded records 1', 'true']
    ])
  })
})
