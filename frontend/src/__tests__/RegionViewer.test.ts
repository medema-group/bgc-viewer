import { flushPromises, shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ viewerInstances: [] as any[] }))

vi.mock('@/TrackViewer', () => ({
  TrackViewer: class {
    data = null
    drawTracks = vi.fn()
    zoomTo = vi.fn()

    constructor() {
      mocks.viewerInstances.push(this)
    }

    destroy() {}
    getCurrentDomain() { return [0, 1000] }
    setData(data) { this.data = data }
  }
}))

import RegionViewer from '@/components/RegionViewer.vue'

const protocluster = {
  type: 'protocluster',
  location: '[100:250](+)',
  qualifiers: {
    protocluster_number: ['3'],
    category: ['Peptide'],
    product: ['NRPS'],
    core_location: ['[140:210](+)']
  }
}

describe('RegionViewer protocluster focus', () => {
  it('selects and zooms to the target after building tracks', async () => {
    const wrapper = shallowMount(RegionViewer, {
      props: {
        features: [protocluster],
        initialProtoclusterNumber: 3
      }
    })
    await flushPromises()

    const viewer = mocks.viewerInstances.at(-1)!
    expect(wrapper.vm.selectedElement).toEqual(protocluster)
    expect(viewer.drawTracks).toHaveBeenCalled()
    expect(viewer.zoomTo).toHaveBeenCalledWith(100, 250)
  })

  it('ignores a target absent from the selected region', async () => {
    const wrapper = shallowMount(RegionViewer, {
      props: {
        features: [protocluster],
        initialProtoclusterNumber: 99
      }
    })
    await flushPromises()

    const viewer = mocks.viewerInstances.at(-1)!
    expect(wrapper.vm.selectedElement).toBeNull()
    expect(viewer.zoomTo).not.toHaveBeenCalled()
  })

  it('clears a stale selection when the target is removed', async () => {
    const wrapper = shallowMount(RegionViewer, {
      props: {
        features: [protocluster],
        initialProtoclusterNumber: 3
      }
    })
    await flushPromises()

    await wrapper.setProps({ initialProtoclusterNumber: null })

    expect(wrapper.vm.selectedElement).toBeNull()
    expect(mocks.viewerInstances.at(-1)!.drawTracks).toHaveBeenCalledTimes(2)
  })
})