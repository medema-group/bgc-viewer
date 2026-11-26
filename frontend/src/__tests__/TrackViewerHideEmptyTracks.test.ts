import { describe, test, expect, beforeEach, afterEach, vi } from 'vitest';
import { TrackViewer, TrackViewerData } from '../TrackViewer';

/**
 * Tests of hiding the tracks that have nothing in the visible part of the domain
 */

describe('TrackViewer hiding empty tracks', () => {
  let container: HTMLDivElement;
  let viewer: TrackViewer | null;

  // Three tracks of 30px: genes over the whole domain, a site on the left, a site on the right.
  // The right track also has a line primitive over the whole domain, which is not content.
  const data = (): TrackViewerData => ({
    tracks: [
      { id: 'genes', label: 'Genes' },
      { id: 'left', label: 'Left' },
      { id: 'right', label: 'Right' }
    ],
    annotations: [
      { id: 'gene1', trackId: 'genes', type: 'arrow', classes: [], label: '', start: 0, end: 45 },
      { id: 'gene2', trackId: 'genes', type: 'arrow', classes: [], label: '', start: 55, end: 100 },
      { id: 'site1', trackId: 'left', type: 'box', classes: [], label: '', start: 10, end: 20 },
      { id: 'site2', trackId: 'right', type: 'box', classes: [], label: '', start: 80, end: 90 }
    ],
    primitives: [
      { id: 'line', trackId: 'right', type: 'horizontal-line', class: 'line', start: 0, end: 100 }
    ]
  });

  // The shown tracks, each with its vertical position
  const shownTracks = () => Array.from(container.querySelectorAll<SVGGElement>('g.track'))
    .filter(track => track.style.display !== 'none')
    .map(track => [track.id, track.getAttribute('transform')]);
  const shownLabels = () => Array.from(container.querySelectorAll<SVGGElement>('g.track-label-group'))
    .filter(label => label.style.display !== 'none')
    .map(label => label.id);
  const svgHeight = () => Number(container.querySelector('svg')!.getAttribute('height'));

  const makeViewer = (config: { hideEmptyTracks?: boolean; onHideEmptyTracksChange?: (hide: boolean) => void } = {}) => {
    viewer = new TrackViewer({
      container,
      width: 800,
      trackHeight: 30,
      domain: [0, 100],
      zoomExtent: [1, 100],
      margin: { top: 20, right: 10, bottom: 20, left: 60 },
      ...config
    });
    viewer.setData(data());
    return viewer;
  };

  beforeEach(() => {
    global.ResizeObserver = vi.fn().mockImplementation(() => ({
      observe: vi.fn(),
      unobserve: vi.fn(),
      disconnect: vi.fn(),
    }));
    container = document.createElement('div');
    document.body.appendChild(container);
    viewer = null;
  });

  afterEach(() => {
    viewer?.destroy();
    container.remove();
  });

  test('shows every track by default, even where it is empty', () => {
    makeViewer().zoomTo(50, 70, 0);

    expect(shownTracks()).toEqual([
      ['genes', 'translate(0, 0)'],
      ['left', 'translate(0, 30)'],
      ['right', 'translate(0, 60)']
    ]);
    expect(svgHeight()).toBe(90 + 40);
  });

  test('hides the tracks without annotations in view and stacks the others', () => {
    const viewer = makeViewer({ hideEmptyTracks: true });
    expect(shownTracks()).toHaveLength(3);

    // Only the genes are in this part; the line primitive of the right track does not count
    viewer.zoomTo(50, 70, 0);
    expect(shownTracks()).toEqual([['genes', 'translate(0, 0)']]);
    expect(shownLabels()).toEqual(['genes-label']);
    expect(svgHeight()).toBe(30 + 40);

    // Panning to the right brings the right track back, below the genes
    viewer.zoomTo(75, 95, 0);
    expect(shownTracks()).toEqual([
      ['genes', 'translate(0, 0)'],
      ['right', 'translate(0, 30)']
    ]);
    expect(svgHeight()).toBe(60 + 40);
    // A track that comes back is drawn for the part in view
    expect(container.querySelector('g.track#right #site2 rect')).not.toBeNull();

    // Zoomed out, every track has something again
    viewer.resetZoom(0);
    expect(shownTracks()).toHaveLength(3);
    expect(svgHeight()).toBe(90 + 40);
  });

  test('switches between hiding and showing the empty tracks', () => {
    const viewer = makeViewer();
    viewer.zoomTo(5, 25, 0);
    expect(shownTracks()).toHaveLength(3);

    viewer.setHideEmptyTracks(true);
    expect(viewer.getHideEmptyTracks()).toBe(true);
    expect(shownTracks().map(([id]) => id)).toEqual(['genes', 'left']);

    viewer.setHideEmptyTracks(false);
    expect(shownTracks().map(([id]) => id)).toEqual(['genes', 'left', 'right']);
  });

  test('offers the option in the menu and reports the change', () => {
    const onChange = vi.fn();
    const viewer = makeViewer({ onHideEmptyTracksChange: onChange });
    viewer.zoomTo(50, 70, 0);

    (document.querySelector('.track-viewer-menu-button') as HTMLElement).click();
    const item = Array.from(document.querySelectorAll<HTMLElement>('.track-viewer-menu-item'))
      .find(element => element.textContent?.includes('Hide empty tracks'))!;
    item.click();

    expect(onChange).toHaveBeenCalledWith(true);
    expect(shownTracks().map(([id]) => id)).toEqual(['genes']);
  });
});
