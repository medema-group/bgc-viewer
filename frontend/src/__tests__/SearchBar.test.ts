import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SearchBar from '@/components/SearchBar.vue'

describe('SearchBar', () => {
  it('opens search when clicked', async () => {
    const wrapper = mount(SearchBar)

    await wrapper.get('[aria-label="Open search"]').trigger('click')

    expect(wrapper.emitted('open')).toHaveLength(1)
  })

  it('opens search with Ctrl+K and Command+K', async () => {
    const wrapper = mount(SearchBar, { attachTo: document.body })

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true }))
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'K', metaKey: true }))
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('open')).toHaveLength(2)
    wrapper.unmount()
  })

  it('does not intercept unrelated shortcuts', () => {
    const wrapper = mount(SearchBar, { attachTo: document.body })

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k' }))
    expect(wrapper.emitted('open')).toBeUndefined()
    wrapper.unmount()
  })
})