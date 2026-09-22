import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SearchDialog from '@/components/SearchDialog.vue'

const defaultProps = {
  query: '',
  level: 'protocluster' as const,
  response: null,
  resultsQuery: '',
  resultsLevel: 'protocluster' as const,
  selectedHit: null,
  loading: false,
  loadingMore: false,
  error: null,
  schema: null,
  schemaLoading: false,
  schemaError: null
}

describe('SearchDialog', () => {
  it('focuses the query and submits from the single dialog form', async () => {
    const wrapper = mount(SearchDialog, { props: defaultProps, attachTo: document.body })
    const input = wrapper.get<HTMLInputElement>('[aria-label="Advanced search query"]')

    expect(document.activeElement).toBe(input.element)
    await input.setValue('pfam:PF00512')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('update:query')).toEqual([['pfam:PF00512']])
    expect(wrapper.emitted('search')).toEqual([[
      { query: 'pfam:PF00512', level: 'protocluster', page: 1 }
    ]])
    wrapper.unmount()
  })

  it('shows help inside the same dialog', async () => {
    const wrapper = mount(SearchDialog, { props: defaultProps })

    await wrapper.get('.dialog-tabs button:last-child').trigger('click')

    expect(wrapper.findAll('[role="dialog"]')).toHaveLength(1)
    expect(wrapper.emitted('request-help')).toHaveLength(1)
  })

  it('closes on Escape and backdrop interaction', async () => {
    const wrapper = mount(SearchDialog, { props: defaultProps, attachTo: document.body })

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await wrapper.get('.search-overlay').trigger('mousedown')

    expect(wrapper.emitted('close')).toHaveLength(2)
    wrapper.unmount()
  })
})