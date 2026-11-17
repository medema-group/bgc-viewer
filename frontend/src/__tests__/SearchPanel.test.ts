import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import SearchPanel from '@/components/SearchPanel.vue'
import { useAdvancedSearch } from '@/composables/useAdvancedSearch'
import type { BGCViewerAPIProvider } from '@/services/dataProviders/BGCViewerAPIProvider'
import type { SearchSchema } from '@/services/dataProviders/types'

const schema: SearchSchema = {
  fields: [
    {
      name: 'text',
      kind: 'full_text',
      label: 'Any text',
      group: 'General',
      multi: false,
      default_search: true,
      description: 'Every text value.',
      operators: ['contains', 'not_contains'],
      facet: false,
      sortable: false
    },
    {
      name: 'product',
      kind: 'exact',
      label: 'Product',
      group: 'Region',
      multi: true,
      default_search: true,
      description: 'Protocluster products.',
      operators: ['in', 'not_in', 'equals', 'not_equals'],
      facet: true,
      sortable: false
    }
  ],
  examples: ['product:NRPS'],
  query_syntax_url: 'https://example.test',
  raw_query_field: '_query'
}

const regionHit = {
  score: 1,
  fields: {
    record: 'recA',
    region: 2,
    start: 100,
    end: 900,
    product: ['NRPS'],
    product_category: ['NRPS'],
    organism: 'Streptomyces',
    output_file: 'recA.json'
  }
}

async function mountPanel({ open = true, canChooseIndex = false } = {}) {
  const provider = {
    getSearchSchema: vi.fn().mockResolvedValue(schema),
    search: vi.fn().mockResolvedValue({
      hits: [regionHit],
      has_more: false,
      total_regions: 1,
      facets: { product: [{ value: 'NRPS', count: 1 }] }
    }),
    getFieldValues: vi.fn().mockResolvedValue({ field: 'product', values: [] })
  }
  const search = useAdvancedSearch(() => provider as unknown as BGCViewerAPIProvider)
  const wrapper = mount(SearchPanel, { props: { search, canChooseIndex }, attachTo: document.body })
  if (open) await search.openIndex()
  await flushPromises()
  return { provider, search, wrapper }
}

describe('SearchPanel', () => {
  it('asks for an index until one is open', async () => {
    const { wrapper } = await mountPanel({ open: false, canChooseIndex: true })

    expect(wrapper.text()).toContain('No index is open.')
    expect(wrapper.find('.condition-row').exists()).toBe(false)
    await wrapper.get('.secondary-button').trigger('click')
    expect(wrapper.emitted('open-index')).toHaveLength(1)
    wrapper.unmount()
  })

  it('lists every record of a newly opened index under one starter condition', async () => {
    const { provider, wrapper } = await mountPanel()

    expect(provider.search.mock.calls[0][0]).toBe('record')
    // Only the blank starter condition, which the backend drops
    expect(provider.search.mock.calls[0][1].filter.conditions).toMatchObject([{ field: 'text', value: '' }])
    expect(wrapper.findAll('.condition-row')).toHaveLength(1)
    expect(wrapper.get<HTMLSelectElement>('[aria-label="Field"]').element.value).toBe('text')
    expect(wrapper.get('.submit-button').text()).toBe('Browse all')
    wrapper.unmount()
  })

  it('runs the builder and reports the search', async () => {
    const { provider, wrapper } = await mountPanel()
    await wrapper.get('[aria-label="Value"]').setValue('coelicolor')

    expect(wrapper.text()).toContain('Any text contains coelicolor')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(provider.search.mock.calls.slice(-1)[0][1].filter.conditions[0]).toMatchObject({
      field: 'text',
      operator: 'contains',
      value: 'coelicolor'
    })
    expect(wrapper.emitted('searched')).toHaveLength(1)
    wrapper.unmount()
  })

  it('opens the search help in a dialog and uses an example as a query string condition', async () => {
    const { wrapper } = await mountPanel()
    const dialog = () => wrapper.get('[role="dialog"]').element.parentElement as HTMLElement

    expect(dialog().style.display).toBe('none')
    await wrapper.get('.help-button').trigger('click')
    expect(dialog().style.display).toBe('')

    await wrapper.get('[aria-label="Use example: product:NRPS"]').trigger('click')
    await flushPromises()

    expect(dialog().style.display).toBe('none')
    expect(wrapper.findAll('.condition-row')).toHaveLength(1)
    expect(wrapper.get<HTMLSelectElement>('[aria-label="Field"]').element.value).toBe('_query')
    expect(wrapper.get<HTMLInputElement>('.query-input').element.value).toBe('product:NRPS')
    wrapper.unmount()
  })
})
