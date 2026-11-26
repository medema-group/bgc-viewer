import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import SearchPanel from '@/components/SearchPanel.vue'
import { AUTO_SEARCH_DELAY, useAdvancedSearch } from '@/composables/useAdvancedSearch'
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
      total: 1,
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

  it('lists every region of a newly opened index under one starter condition', async () => {
    const { provider, wrapper } = await mountPanel()

    // A blank condition asks nothing, so there is no summary to show
    expect(wrapper.find('[aria-label="Search summary"]').exists()).toBe(false)

    expect(provider.search).toHaveBeenCalledTimes(1)
    expect(provider.search.mock.calls[0][0]).toBe('region')
    // The blank starter condition is left out, so nothing narrows the search, which the row shows
    expect(provider.search.mock.calls[0][1].filter).toMatchObject({ conditions: [], groups: [] })
    expect(wrapper.findAll('.condition-row')).toHaveLength(1)
    expect(wrapper.get('.condition-row').classes()).toContain('incomplete')
    expect(wrapper.get<HTMLSelectElement>('[aria-label="Field"]').element.value).toBe('text')
    expect(wrapper.find('button[type="submit"]').exists()).toBe(false)
    wrapper.unmount()
  })

  describe('searching by itself', () => {
    beforeEach(() => {
      vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    })

    afterEach(() => {
      vi.useRealTimers()
    })

    const lastFilter = (provider: { search: ReturnType<typeof vi.fn> }) =>
      provider.search.mock.calls.slice(-1)[0][1].filter

    it('searches once after a pause in typing', async () => {
      const { provider, wrapper } = await mountPanel()
      const value = wrapper.get('[aria-label="Value"]')
      for (const typed of ['c', 'co', 'coeli', 'coelicolor']) {
        await value.setValue(typed)
        vi.advanceTimersByTime(AUTO_SEARCH_DELAY / 2)
      }
      expect(provider.search).toHaveBeenCalledTimes(1)
      expect(wrapper.find('.condition-row.incomplete').exists()).toBe(false)

      // The summary is the tooltip of its button
      const summaryButton = wrapper.get('[aria-label="Search summary"]')
      const tooltip = wrapper.get(`#${summaryButton.attributes('aria-describedby')}`)
      expect(tooltip.attributes('role')).toBe('tooltip')
      expect(tooltip.text()).toBe('Any text contains coelicolor')

      vi.advanceTimersByTime(AUTO_SEARCH_DELAY)
      await flushPromises()
      expect(provider.search).toHaveBeenCalledTimes(2)
      expect(lastFilter(provider).conditions[0]).toMatchObject({ field: 'text', operator: 'contains', value: 'coelicolor' })
      wrapper.unmount()
    })

    it('does not search for changes that leave the query as it was', async () => {
      const { provider, wrapper } = await mountPanel()

      // Another operator for a condition without a value asks nothing new
      await wrapper.get('[aria-label="Operator"]').setValue('not_contains')
      await wrapper.findAll('button').find(button => button.text() === '+ Add condition')!.trigger('click')
      vi.advanceTimersByTime(AUTO_SEARCH_DELAY * 2)
      await flushPromises()

      expect(provider.search).toHaveBeenCalledTimes(1)
      expect(wrapper.findAll('.condition-row.incomplete')).toHaveLength(2)
      wrapper.unmount()
    })

    it('searches right away on Enter', async () => {
      const { provider, wrapper } = await mountPanel()
      const value = wrapper.get('[aria-label="Value"]')
      await value.setValue('coelicolor')
      await value.trigger('keydown', { key: 'Enter' })
      await flushPromises()

      expect(provider.search).toHaveBeenCalledTimes(2)
      expect(lastFilter(provider).conditions[0]).toMatchObject({ value: 'coelicolor' })

      // The pause after typing does not search the same again
      vi.advanceTimersByTime(AUTO_SEARCH_DELAY * 2)
      await flushPromises()
      expect(provider.search).toHaveBeenCalledTimes(2)
      wrapper.unmount()
    })
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
