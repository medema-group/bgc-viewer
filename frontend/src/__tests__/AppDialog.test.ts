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

  describe('focus', () => {
    const tab = (shiftKey = false) => {
      const event = new KeyboardEvent('keydown', { key: 'Tab', shiftKey, cancelable: true })
      document.dispatchEvent(event)
      return event.defaultPrevented
    }

    function mountWithOpener(content = '<input id="first"><button id="last">Go</button><a href="#" hidden>Hidden</a>') {
      const opener = document.createElement('button')
      opener.textContent = 'Open'
      document.body.appendChild(opener)
      opener.focus()
      const wrapper = mount(AppDialog, {
        props: { open: false, title: 'Index' },
        slots: { default: content },
        attachTo: document.body
      })
      const dialog = wrapper.get('[role="dialog"]').element as HTMLElement
      const cleanup = () => { wrapper.unmount(); opener.remove() }
      return { wrapper, opener, dialog, cleanup }
    }

    it('moves focus into the dialog when it opens, and back to the opener when it closes', async () => {
      const { wrapper, opener, dialog, cleanup } = mountWithOpener()

      await wrapper.setProps({ open: true })
      expect(document.activeElement).toBe(dialog)

      await wrapper.setProps({ open: false })
      expect(document.activeElement).toBe(opener)
      cleanup()
    })

    it('focuses an autofocus control when the content has one', async () => {
      const { wrapper, cleanup } = mountWithOpener('<input id="a"><input id="b" autofocus>')

      await wrapper.setProps({ open: true })

      expect(document.activeElement?.id).toBe('b')
      cleanup()
    })

    it('keeps Tab and Shift+Tab within the dialog, skipping hidden controls', async () => {
      const { wrapper, opener, cleanup } = mountWithOpener()
      await wrapper.setProps({ open: true })
      const closeButton = wrapper.get('[aria-label="Close Index"]').element
      const last = wrapper.get('#last').element as HTMLElement

      // From the dialog itself, Tab enters at the first control: the close button
      expect(tab()).toBe(true)
      expect(document.activeElement).toBe(closeButton)
      // From the last control, Tab wraps to the first, and Shift+Tab back again
      last.focus()
      expect(tab()).toBe(true)
      expect(document.activeElement).toBe(closeButton)
      expect(tab(true)).toBe(true)
      expect(document.activeElement).toBe(last)
      // In between, the browser moves focus as usual
      ;(wrapper.get('#first').element as HTMLElement).focus()
      expect(tab()).toBe(false)
      // Focus that has escaped is brought back in
      opener.focus()
      expect(tab()).toBe(true)
      expect(document.activeElement).toBe(closeButton)
      cleanup()
    })

    it('leaves Tab alone while closed', () => {
      const { cleanup } = mountWithOpener()
      expect(tab()).toBe(false)
      cleanup()
    })

    it('gives focus back when unmounted while open', async () => {
      const { wrapper, opener } = mountWithOpener()
      await wrapper.setProps({ open: true })

      wrapper.unmount()

      expect(document.activeElement).toBe(opener)
      opener.remove()
    })
  })
})
