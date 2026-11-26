import { describe, test, expect, beforeEach, afterEach, vi } from 'vitest';
import { TrackViewer } from '../TrackViewer';

/**
 * Zoom transitions started from code (zoomTo, resetZoom) reach their target even when the
 * viewer is resized while they run, as when a scrollbar appears or disappears beside it.
 */

describe('TrackViewer zoom transitions', () => {
  let container: HTMLDivElement;
  let viewer: TrackViewer | null;
  let containerWidth: number;

  const wait = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
  const expectDomain = (domain: [number, number]) => {
    const [start, end] = viewer!.getCurrentDomain();
    expect(start).toBeCloseTo(domain[0], 1);
    expect(end).toBeCloseTo(domain[1], 1);
  };

  beforeEach(() => {
    global.ResizeObserver = vi.fn().mockImplementation(() => ({
      observe: vi.fn(),
      unobserve: vi.fn(),
      disconnect: vi.fn(),
    }));
    container = document.createElement('div');
    containerWidth = 1000;
    // The viewer takes its width from the container, as it does without a configured width
    Object.defineProperty(container, 'clientWidth', { configurable: true, get: () => containerWidth });
    document.body.appendChild(container);

    viewer = new TrackViewer({ container, domain: [0, 100], zoomExtent: [1, 100] });
    viewer.setData({
      tracks: [{ id: 'genes', label: 'Genes' }],
      annotations: [{ id: 'gene', trackId: 'genes', type: 'arrow', classes: [], label: '', start: 0, end: 100 }]
    });
  });

  afterEach(() => {
    viewer?.destroy();
    container.remove();
  });

  test('reaches the zoomed-to range without a resize', async () => {
    viewer!.zoomTo(40, 60, 150);
    await wait(350);
    expectDomain([40, 60]);
  });

  test('continues to the zoomed-to range when resized halfway', async () => {
    viewer!.zoomTo(40, 60, 300);
    await wait(100);
    // A scrollbar appears beside the viewer, narrowing it
    containerWidth = 900;
    viewer!.resize();

    await wait(450);
    expect(viewer!.getConfig().width).toBe(860);
    expectDomain([40, 60]);
  });

  test('continues zooming out to the whole domain when resized halfway', async () => {
    viewer!.zoomTo(40, 60, 0);
    viewer!.resetZoom(300);
    await wait(100);
    containerWidth = 1100;
    viewer!.resize();

    await wait(450);
    expectDomain([0, 100]);
  });

  test('keeps the shown range on a resize after the transition is done', async () => {
    viewer!.zoomTo(40, 60, 100);
    await wait(300);
    containerWidth = 900;
    viewer!.resize();

    await wait(100);
    expectDomain([40, 60]);
  });
});
