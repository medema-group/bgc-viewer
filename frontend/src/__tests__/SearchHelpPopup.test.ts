import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import SearchHelpPopup from '@/components/SearchHelpPopup.vue'

const schema = {
  fields: [
    {
      name: 'pfam',
      kind: 'exact' as const,
      unqualified: true,
      description: 'PFAM accessions overlapping the protocluster.'
    },
    {
      name: 'region',
      kind: 'numeric' as const,
      unqualified: false,
      description: 'Parent region number.'
    }
  ],
  examples: ['pfam:PF00512'],
  query_syntax_url: 'https://docs.example.test/query-parser'
}

describe('SearchHelpPopup', () => {
  beforeEach(() => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) }
    })
  })

  it('renders field metadata, examples, operators, and the grammar link', () => {
    const wrapper = mount(SearchHelpPopup, {
      props: { schema, loading: false, error: null }
    })

    expect(wrapper.text()).toContain('pfam')
    expect(wrapper.text()).toContain('exact')
    expect(wrapper.text()).toContain('Included in unqualified search')
    expect(wrapper.text()).toContain('pfam:PF00512')
    expect(wrapper.text()).toContain('"a b"~N')
    expect(wrapper.text()).toContain('"a b"*')

    const headings = wrapper.findAll('.help-section h3').map(heading => heading.text())
    expect(headings).toEqual(['Example queries', 'Available fields', 'Operators'])

    const link = wrapper.get('a')
    expect(link.attributes('href')).toBe(schema.query_syntax_url)
    expect(link.attributes('target')).toBe('_blank')
    expect(link.attributes('rel')).toBe('noopener noreferrer')
  })

  it('copies an example query', async () => {
    const wrapper = mount(SearchHelpPopup, {
      props: { schema, loading: false, error: null }
    })

    await wrapper.get('[aria-label="Copy example: pfam:PF00512"]').trigger('click')
    await flushPromises()

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('pfam:PF00512')
    expect(wrapper.text()).toContain('Copied')
  })

  it('reports when an example cannot be copied', async () => {
    vi.mocked(navigator.clipboard.writeText).mockRejectedValueOnce(new Error('denied'))
    const wrapper = mount(SearchHelpPopup, {
      props: { schema, loading: false, error: null }
    })

    await wrapper.get('[aria-label="Copy example: pfam:PF00512"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Copy failed')
  })

  it('closes from the close button and overlay', async () => {
    const wrapper = mount(SearchHelpPopup, {
      props: { schema, loading: false, error: null }
    })

    await wrapper.get('[aria-label="Close search help"]').trigger('click')
    await wrapper.get('.modal-overlay').trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(2)
  })
})