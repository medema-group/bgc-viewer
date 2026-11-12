import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import SearchDialog from '@/components/SearchDialog.vue'
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

function mountDialog() {
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
  const wrapper = mount(SearchDialog, { props: { search }, attachTo: document.body })
  return { provider, search, wrapper }
}

describe('SearchDialog', () => {
  it('opens on the builder with one condition from the schema', async () => {
    const { wrapper } = mountDialog()
    await flushPromises()

    expect(wrapper.findAll('.condition-row')).toHaveLength(1)
    expect(wrapper.get<HTMLSelectElement>('[aria-label="Field"]').element.value).toBe('text')
    expect(wrapper.get('.submit-button').text()).toBe('Browse all')
    wrapper.unmount()
  })

  it('runs the builder and shows results with refine values', async () => {
    const { provider, wrapper } = mountDialog()
    await flushPromises()
    await wrapper.get('[aria-label="Value"]').setValue('coelicolor')

    expect(wrapper.text()).toContain('Any text contains coelicolor')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(provider.search.mock.calls[0][1].filter.conditions[0]).toMatchObject({
      field: 'text',
      operator: 'contains',
      value: 'coelicolor'
    })
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    expect(wrapper.get('.refine-panel').text()).toContain('NRPS')
    wrapper.unmount()
  })

  it('searches a query string and emits the selected hit', async () => {
    const { provider, wrapper } = mountDialog()
    await flushPromises()

    await wrapper.findAll('.dialog-tabs button')[1].trigger('click')
    await wrapper.get('[aria-label="Advanced search query"]').setValue('product:NRPS')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(provider.search.mock.calls[0][1]).toEqual({ query: 'product:NRPS' })
    await wrapper.get('tbody tr').trigger('click')
    expect(wrapper.emitted('select')).toEqual([[regionHit]])
    wrapper.unmount()
  })

  it('switches the result level of the shown search', async () => {
    const { provider, wrapper } = mountDialog()
    await flushPromises()
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    await wrapper.findAll('.level-toggle button')[1].trigger('click')
    await flushPromises()

    expect(provider.search.mock.calls.slice(-1)[0]![0]).toBe('record')
    wrapper.unmount()
  })

  it('uses a help example as the query string', async () => {
    const { wrapper } = mountDialog()
    await flushPromises()

    await wrapper.findAll('.dialog-tabs button')[2].trigger('click')
    await wrapper.get('[aria-label="Use example: product:NRPS"]').trigger('click')
    await flushPromises()

    expect(wrapper.get<HTMLInputElement>('[aria-label="Advanced search query"]').element.value).toBe('product:NRPS')
    wrapper.unmount()
  })

  it('closes on Escape and backdrop interaction', async () => {
    const { wrapper } = mountDialog()

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await wrapper.get('.search-overlay').trigger('mousedown')

    expect(wrapper.emitted('close')).toHaveLength(2)
    wrapper.unmount()
  })
})
