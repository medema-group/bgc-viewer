import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SearchBar from '@/components/SearchBar.vue'

describe('SearchBar', () => {
  it('submits on Enter but not while typing', async () => {
    const wrapper = mount(SearchBar, {
      props: { query: '', level: 'protocluster', error: null }
    })
    const input = wrapper.get('input')

    await input.setValue('pfam:PF00512')
    expect(wrapper.emitted('search')).toBeUndefined()

    await input.trigger('keydown.enter')
    expect(wrapper.emitted('search')).toEqual([[
      { query: 'pfam:PF00512', level: 'protocluster', page: 1 }
    ]])
  })

  it('reruns a non-empty query when the level changes', async () => {
    const wrapper = mount(SearchBar, {
      props: { query: 'terpene', level: 'protocluster', error: null }
    })

    await wrapper.get('select').setValue('region')

    expect(wrapper.emitted('update:level')).toEqual([['region']])
    expect(wrapper.emitted('search')).toEqual([[
      { query: 'terpene', level: 'region', page: 1 }
    ]])
  })

  it('renders structured errors without replacing the query', () => {
    const wrapper = mount(SearchBar, {
      props: {
        query: 'pfam:',
        level: 'protocluster',
        error: { code: 'invalid_query', message: 'Invalid query syntax' }
      }
    })

    expect(wrapper.get('input').element.value).toBe('pfam:')
    expect(wrapper.get('[role="alert"]').text()).toContain('invalid_query')
    expect(wrapper.get('[role="alert"]').text()).toContain('Invalid query syntax')
  })
})