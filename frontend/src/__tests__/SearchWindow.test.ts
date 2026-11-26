import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import SearchWindow from '@/components/SearchWindow.vue'
import { useAdvancedSearch } from '@/composables/useAdvancedSearch'
import type { BGCViewerAPIProvider } from '@/services/dataProviders/BGCViewerAPIProvider'
import type { SearchSchema } from '@/services/dataProviders/types'
import { conditionRow, createCondition } from '@/services/filterRows'

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

async function mountWindow({ compact = false, open = true, active = false } = {}) {
  const provider = {
    getSearchSchema: vi.fn().mockResolvedValue(schema),
    search: vi.fn(async (level: string) => ({
      hits: [level === 'record' ? recordHit : regionHit],
      has_more: false,
      total: 1234,
      facets: { product: [{ value: 'NRPS', count: 2 }] }
    })),
    getFieldValues: vi.fn()
  }
  const search = useAdvancedSearch(() => provider as unknown as BGCViewerAPIProvider)
  if (open) await search.openIndex()
  const wrapper = mount(SearchWindow, { props: { search, label: 'Search 1', compact, active } })
  await flushPromises()
  return { wrapper, provider, search }
}

describe('SearchWindow', () => {
  it('shows the query builder with the results and refine values below it', async () => {
    const { wrapper } = await mountWindow()

    expect(wrapper.find('.condition-row').exists()).toBe(true)
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    expect(wrapper.get('.refine-scroll').text()).toContain('NRPS')

    await wrapper.get('tbody tr').trigger('click')
    expect(wrapper.emitted('select-hit')).toEqual([[regionHit]])
  })

  it('offers protoclusters, regions, and records, and searches again at another level', async () => {
    const { wrapper, provider } = await mountWindow()
    const buttons = wrapper.findAll('.level-toggle button')

    expect(buttons.map(button => button.text())).toEqual(['Protoclusters', 'Regions', 'Records'])
    expect(buttons.map(button => button.attributes('aria-pressed'))).toEqual(['false', 'true', 'false'])

    await buttons[2].trigger('click')
    await flushPromises()
    expect(provider.search.mock.calls.slice(-1)[0][0]).toBe('record')
  })

  it('is renamed, duplicated, and made compact from its header, but not deleted', async () => {
    const { wrapper } = await mountWindow()
    const label = wrapper.get<HTMLInputElement>('[aria-label="Window label"]')

    expect(label.element.value).toBe('Search 1')
    await label.setValue('NRPS in Streptomyces')
    await label.setValue('   ')

    await wrapper.findAll('button').find(button => button.text() === 'Duplicate')!.trigger('click')
    await wrapper.get('[aria-label="Make compact"]').trigger('click')

    // A blank label keeps the old one
    expect(wrapper.emitted('update:label')).toEqual([['NRPS in Streptomyces']])
    expect(label.element.value).toBe('Search 1')
    expect(wrapper.emitted('duplicate')).toHaveLength(1)
    expect(wrapper.emitted('minimize')).toHaveLength(1)
    expect(wrapper.find('[aria-label="Delete Search 1"]').exists()).toBe(false)
  })

  it('shows its label, what was searched, and the number of matches when compact', async () => {
    const { wrapper, search } = await mountWindow({ compact: true })

    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.get('.compact-label').text()).toBe('Search 1')
    expect(wrapper.get('.compact-summary').text()).toBe('Everything')
    expect(wrapper.get('.compact-count').text()).toBe('1,234 matching regions')

    // The summary follows the search that ran, not the rows being edited
    search.state.rows = [conditionRow(createCondition('text', 'contains', 'coelicolor'))]
    await flushPromises()
    expect(wrapper.get('.compact-summary').text()).toBe('Everything')

    await search.search()
    await flushPromises()
    expect(wrapper.get('.compact-summary').text()).toBe('Any text contains coelicolor')

    await wrapper.get('button.compact-card').trigger('click')
    expect(wrapper.emitted('expand')).toHaveLength(1)

    // Deleting does not enlarge the window first
    await wrapper.get('[aria-label="Delete Search 1"]').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(wrapper.emitted('expand')).toHaveLength(1)
  })

  it('marks the card of the open window, which makes it compact again and cannot delete it', async () => {
    const { wrapper } = await mountWindow({ compact: true, active: true })
    const card = wrapper.get('button.compact-card')

    expect(wrapper.classes()).toContain('active')
    expect(card.attributes('aria-current')).toBe('true')
    expect(wrapper.find('[aria-label="Delete Search 1"]').exists()).toBe(false)

    await card.trigger('click')
    expect(wrapper.emitted('minimize')).toHaveLength(1)
    expect(wrapper.emitted('expand')).toBeUndefined()
  })

  it('says when no index is open or nothing was searched yet', async () => {
    const { wrapper } = await mountWindow({ compact: true, open: false })

    expect(wrapper.get('.compact-summary').text()).toBe('No index is open')
    expect(wrapper.get('.compact-count').text()).toBe('Not searched yet')
  })
})
