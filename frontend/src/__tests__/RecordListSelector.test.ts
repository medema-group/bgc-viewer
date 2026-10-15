import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import RecordListSelector from '@/components/RecordListSelector.vue'

vi.mock('axios', () => ({
  default: {
    post: vi.fn()
  }
}))

vi.mock('@/services/dataProviders/BGCViewerAPIProvider', () => ({
  BGCViewerAPIProvider: class {
    searchRecords() {
      return Promise.resolve({ records: [] })
    }
  }
}))

describe('RecordListSelector', () => {
  it('updates its selected entry without emitting a record selection', async () => {
    const wrapper = mount(RecordListSelector, {
      global: {
        stubs: {
          LoadingSpinner: true
        }
      }
    })

    wrapper.vm.setSelectedEntry('NC_003888.3.json:NC_003888.3')
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.selectedEntryId).toBe('NC_003888.3.json:NC_003888.3')
    expect(wrapper.emitted('record-selected')).toBeUndefined()
  })
})