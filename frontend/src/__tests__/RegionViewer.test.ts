import { flushPromises, shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ viewers: [] as any[] }))

vi.mock('@/TrackViewer', () => ({
  TrackViewer: class {
    options: any
    zoomTo = vi.fn()
    resetZoom = vi.fn()
    drawTracks = vi.fn()
    setData = vi.fn()

    constructor(options: any) {
      this.options = options
      mocks.viewers.push(this)
    }

    destroy() {}
    getCurrentDomain() { return [0, 3000] }
  }
}))

import RegionViewer from '@/components/RegionViewer.vue'

const protocluster = (number: number, location: string) => ({
  type: 'protocluster',
  location,
  qualifiers: {
    protocluster_number: [String(number)],
    category: ['NRPS'],
    product: ['NRPS']
  }
})

// Region 1 holds two overlapping protoclusters; region 2 is elsewhere in the record.
const features = [
  { type: 'region', location: '[0:1000](+)', qualifiers: { region_number: ['1'] } },
  protocluster(4, '[100:600](+)'),
  protocluster(5, '[400:900](+)'),
  { type: 'region', location: '[2000:3000](+)', qualifiers: { region_number: ['2'] } }
]

const regions = [
  { id: 'region_1', region_number: 1, product: ['NRPS'], start: 0, end: 1000 },
  { id: 'region_2', region_number: 2, product: ['terpene'], start: 2000, end: 3000 }
]

async function mountViewer(props: Record<string, unknown>) {
  const wrapper = shallowMount(RegionViewer, {
    props: { features, regions, selectedRegionId: 'region_1', ...props }
  })
  await flushPromises()
  return { wrapper, viewer: mocks.viewers[mocks.viewers.length - 1] }
}

// zoomTo is called with the span padded by 2% of its length on either side
const padded = (start: number, end: number) => [start - (end - start) * 0.02, end + (end - start) * 0.02]

describe('RegionViewer protocluster focus', () => {
  it('starts zoomed to the protocluster and selects it', async () => {
    const { wrapper, viewer } = await mountViewer({ selectedProtoclusterNumber: 5 })

    expect(viewer.zoomTo).toHaveBeenLastCalledWith(...padded(400, 900), 0)
    expect(wrapper.vm.selectedElement).toEqual(features[2])
  })

  it('zooms to the region without a protocluster, or when it is not in the record', async () => {
    for (const selectedProtoclusterNumber of [null, 99]) {
      const { wrapper, viewer } = await mountViewer({ selectedProtoclusterNumber })
      expect(viewer.zoomTo).toHaveBeenLastCalledWith(...padded(0, 1000), 0)
      expect(wrapper.vm.selectedElement).toBeNull()
    }
  })

  it('moves to another protocluster of the same region', async () => {
    const { wrapper, viewer } = await mountViewer({ selectedProtoclusterNumber: 4 })

    await wrapper.setProps({ selectedProtoclusterNumber: 5 })

    expect(viewer.zoomTo).toHaveBeenLastCalledWith(...padded(400, 900), 1500)
    expect(wrapper.vm.selectedElement).toEqual(features[2])
  })

  it('zooms once when the region and protocluster change together', async () => {
    const { wrapper, viewer } = await mountViewer({ selectedRegionId: 'region_2' })
    viewer.zoomTo.mockClear()

    await wrapper.setProps({ selectedRegionId: 'region_1', selectedProtoclusterNumber: 4 })

    expect(viewer.zoomTo.mock.calls).toEqual([[...padded(100, 600), 1500]])
  })

  it('goes back to the region when the protocluster is cleared', async () => {
    const { wrapper, viewer } = await mountViewer({ selectedProtoclusterNumber: 4 })

    // The prop is a nullable Number at runtime; its inferred type leaves out null
    await wrapper.setProps({ selectedProtoclusterNumber: null as unknown as undefined })

    expect(viewer.zoomTo).toHaveBeenLastCalledWith(...padded(0, 1000), 1500)
    expect(wrapper.vm.selectedElement).toBeNull()
  })

  it('drops the protocluster when a region is picked from the menu', async () => {
    const { wrapper, viewer } = await mountViewer({ selectedProtoclusterNumber: 4 })
    const zoomMenu = viewer.options.menuItems()[0].children
    const regionOne = zoomMenu.find((item: any) => item.label?.startsWith('Region 1'))

    regionOne.action()
    await flushPromises()

    expect(viewer.zoomTo).toHaveBeenLastCalledWith(...padded(0, 1000), 1500)
    expect(wrapper.vm.selectedElement).toBeNull()
    // Picked again, the region is zoomed back to without the protocluster coming back
    regionOne.action()
    await flushPromises()
    expect(viewer.zoomTo).toHaveBeenCalledTimes(3)
    expect(viewer.zoomTo).toHaveBeenLastCalledWith(...padded(0, 1000), 1500)
  })
})
