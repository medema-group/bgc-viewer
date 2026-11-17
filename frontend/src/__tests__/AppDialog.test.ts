import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { defineComponent, h, onMounted } from 'vue'

import AppDialog from '@/components/AppDialog.vue'

describe('AppDialog', () => {
  it('keeps its content mounted while hidden', () => {
    let mounted = 0
    const Content = defineComponent({ setup: () => { onMounted(() => { mounted += 1 }); return () => h('p', 'content') } })

    const wrapper = mount(AppDialog, { props: { open: false, title: 'Index' }, slots: { default: Content } })

    expect(mounted).toBe(1)
    expect((wrapper.element as HTMLElement).style.display).toBe('none')
    expect(wrapper.get('h2').text()).toBe('Index')
  })

  it('closes on Escape only while open, and on the backdrop and close button', async () => {
    const wrapper = mount(AppDialog, { props: { open: false, title: 'Index' }, attachTo: document.body })

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(wrapper.emitted('close')).toBeUndefined()

    await wrapper.setProps({ open: true })
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await wrapper.trigger('mousedown')
    await wrapper.get('[aria-label="Close Index"]').trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(3)
    wrapper.unmount()
  })
})
