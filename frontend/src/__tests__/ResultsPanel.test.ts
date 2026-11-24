import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import ResultsPanel, { type ResultsTab } from '@/components/ResultsPanel.vue'
import { useAdvancedSearch } from '@/composables/useAdvancedSearch'
import type { LoadedRecord, LoadedRegion } from '@/composables/useLoadedRecords'
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

const regionHit = {
  score: 1,
  fields: {
    record: 'recA',
    region: 1,
    start: 0,
    end: 30000,
    length: 30000,
    product: ['NRPS'],
    product_category: ['NRPS'],
    output_file: 'recA.json'
  }
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
  regions: [{ id: 'region_1', region_number: 1, product: ['NRPS'], start: 0, end: 30000 }],
  provider: {} as DataProvider
}

const loadedRegion: LoadedRegion = {
  key: `${loadedRecord.key}#region_1`,
  record: loadedRecord,
  regionId: 'region_1',
  regionNumber: 1,
  length: 30000,
  product: ['NRPS']
}

async function mountPanel(tab: ResultsTab, loadedRecords: LoadedRecord[], searched = true) {
  const provider = {
    getSearchSchema: vi.fn().mockResolvedValue(schema),
    search: vi.fn(async (level: string) => ({
      hits: [level === 'record' ? recordHit : regionHit],
      has_more: false,
      total: 2,
      facets: { product: [{ value: 'NRPS', count: 2 }] }
    })),
    getFieldValues: vi.fn()
  }
  const search = useAdvancedSearch(() => provider as unknown as BGCViewerAPIProvider)
  if (searched) await search.openIndex()
  const loadedRegions = loadedRecords.length ? [loadedRegion] : []
  const wrapper = mount(ResultsPanel, { props: { search, tab, loadedRecords, loadedRegions } })
  await flushPromises()
  return { wrapper, provider }
}

const tabs = ({ wrapper }: Awaited<ReturnType<typeof mountPanel>>) =>
  wrapper.findAll('[role="tab"]').map(tab => [tab.text(), tab.attributes('aria-selected')])

describe('ResultsPanel', () => {
  it('shows the search results with refine values beside them', async () => {
    const panel = await mountPanel('search', [])
    const { wrapper } = panel

    expect(tabs(panel)).toEqual([['Search results', 'true']])
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    expect(wrapper.get('.refine-scroll').text()).toContain('NRPS')

    await wrapper.get('tbody tr').trigger('click')
    expect(wrapper.emitted('select-hit')).toEqual([[regionHit]])
  })

  it('offers the loaded records as a second tab', async () => {
    const panel = await mountPanel('search', [loadedRecord])
    const { wrapper } = panel

    expect(tabs(panel)).toEqual([['Search results', 'true'], ['Loaded data 1', 'false']])
    await wrapper.findAll('[role="tab"]')[1].trigger('click')
    expect(wrapper.emitted('update:tab')).toEqual([['loaded']])
  })

  it('lists the loaded records on their tab', async () => {
    const { wrapper } = await mountPanel('loaded', [loadedRecord])
    await wrapper.findAll('.level-toggle button').find(button => button.text() === 'Records')!.trigger('click')
    await flushPromises()

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
      ['Loaded data 1', 'true']
    ])
  })

  it('keeps the search tab while an open index has not returned results', async () => {
    const { wrapper, provider } = await mountPanel('search', [loadedRecord], false)
    provider.search.mockReturnValue(new Promise(() => {}))
    void wrapper.props('search').openIndex()

    await flushPromises()
    expect(tabs({ wrapper, provider })).toEqual([['Search results', 'true'], ['Loaded data 1', 'false']])

    // A failed search shows its error above the results, so the tab stays
    provider.search.mockRejectedValue(new Error('outdated index'))
    await wrapper.props('search').search()
    await flushPromises()
    expect(tabs({ wrapper, provider })).toEqual([['Search results', 'true'], ['Loaded data 1', 'false']])
  })

  it('offers protoclusters, regions, and records, with regions selected', async () => {
    const { wrapper } = await mountPanel('search', [loadedRecord])
    const buttons = wrapper.findAll('.level-toggle button')

    expect(buttons.map(button => button.text())).toEqual(['Protoclusters', 'Regions', 'Records'])
    expect(buttons.map(button => button.attributes('aria-pressed'))).toEqual(['false', 'true', 'false'])
  })

  it('switches both lists between regions and records', async () => {
    const { wrapper, provider } = await mountPanel('loaded', [loadedRecord])
    const levelButton = (label: string) =>
      wrapper.findAll('.level-toggle button').find(button => button.text() === label)!

    await levelButton('Records').trigger('click')
    await flushPromises()

    // The search is fetched again at record level, and the loaded data lists records
    expect(provider.search.mock.calls.slice(-1)[0][0]).toBe('record')
    expect(wrapper.findAll('thead th').map(th => th.text()).slice(0, 2)).toEqual(['Record', 'Source'])

    await levelButton('Regions').trigger('click')
    await flushPromises()

    // And back at region level, where the loaded data lists regions
    expect(provider.search.mock.calls.slice(-1)[0][0]).toBe('region')
    expect(tabs({ wrapper, provider })[1]).toEqual(['Loaded data 1', 'true'])
    expect(wrapper.findAll('thead th').map(th => th.text()).slice(0, 3)).toEqual(['Record', 'Region', 'Length (kb)'])
    expect(wrapper.get('tbody tr').findAll('td').map(td => td.text()).slice(0, 4)).toEqual([
      'BGC0000001',
      '1',
      '30.0',
      'NRPS'
    ])

    await wrapper.get('tbody tr').trigger('click')
    expect(wrapper.emitted('select-loaded-region')).toEqual([[loadedRegion]])
  })

  it('searches protoclusters and lists loaded data by region', async () => {
    const { wrapper, provider } = await mountPanel('loaded', [loadedRecord])
    const protoclusters = wrapper.findAll('.level-toggle button').find(button => button.text() === 'Protoclusters')!

    await protoclusters.trigger('click')
    await flushPromises()

    expect(provider.search.mock.calls.slice(-1)[0][0]).toBe('protocluster')
    expect(protoclusters.attributes('aria-pressed')).toBe('true')
    // Only the index holds protoclusters, so loaded data stays listed by region
    expect(wrapper.findAll('thead th').map(th => th.text()).slice(0, 2)).toEqual(['Record', 'Region'])
  })
})
