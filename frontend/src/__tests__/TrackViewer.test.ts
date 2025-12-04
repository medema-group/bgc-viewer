import { describe, test, expect, beforeEach, afterEach, vi } from 'vitest';
import { TrackViewer, TrackViewerData, TrackData, AnnotationData, DrawingPrimitive } from '../TrackViewer';

/**
 * TrackViewer tests
 */

describe('TrackViewer', () => {
  let container: HTMLDivElement;

  beforeEach(() => {
    // Mock ResizeObserver for jsdom environment
    global.ResizeObserver = vi.fn().mockImplementation(() => ({
      observe: vi.fn(),
      unobserve: vi.fn(),
      disconnect: vi.fn(),
    }));

    // Set up a minimal DOM structure for jsdom
    if (!document.body) {
      document.documentElement.appendChild(document.createElement('body'));
    }
    
    container = document.createElement('div');
    container.id = 'test-container';
    document.body.appendChild(container);
  });

  afterEach(() => {
    // Clean up
    if (container.parentNode) {
      document.body.removeChild(container);
    }
    
    // Remove any tooltips that were created
    const tooltips = document.querySelectorAll('.track-viewer-tooltip');
    tooltips.forEach(tooltip => tooltip.remove());
  });

  test('should create TrackViewer instance with default config', () => {
    const viewer = new TrackViewer({
      container: '#test-container',
      width: 800 // Explicitly set width to test default behavior
    });

    expect(viewer).toBeInstanceOf(TrackViewer);
    const config = viewer.getConfig();
    expect(config.width).toBe(800);
    expect(config.height).toBe(300);
    expect(config.trackHeight).toBe(30);
  });

  test('should create TrackViewer instance with custom config', () => {
    const onAnnotationClick = vi.fn();
    const viewer = new TrackViewer({
      container: '#test-container',
      width: 1000,
      height: 400,
      trackHeight: 40,
      domain: [0, 200],
      onAnnotationClick
    });

    const config = viewer.getConfig();
    expect(config.width).toBe(1000);
    expect(config.height).toBe(400);
    expect(config.trackHeight).toBe(40);
    expect(config.domain).toEqual([0, 200]);
    expect(config.onAnnotationClick).toBe(onAnnotationClick);
  });

  test('should set and get data correctly using new format', () => {
    const viewer = new TrackViewer({
      container: '#test-container'
    });

    const testData: TrackViewerData = {
      tracks: [{ id: 'track1', label: 'Test Track' }],
      annotations: [{
        id: 'gene1',
        trackId: 'track1',
        type: 'box',
        classes: ['test-blue', 'test-feature'],
        label: 'Gene1',
        start: 10,
        end: 30
      }],
      primitives: []
    };

    viewer.setData(testData);
    const retrievedData = viewer.getData();
    
    expect(retrievedData).toEqual(testData);
    expect(retrievedData).not.toBe(testData); // Should be a copy
  });

  test('should add track correctly', () => {
    const viewer = new TrackViewer({
      container: '#test-container'
    });

    const initialData: TrackViewerData = {
      tracks: [{ id: 'track1', label: 'Initial Track' }],
      annotations: [{
        id: 'initial1',
        trackId: 'track1',
        type: 'box',
        classes: ['test-blue', 'test-feature'],
        label: 'Initial',
        start: 5,
        end: 15
      }]
    };

    const newTrack: TrackData = { id: 'track2', label: 'New Track' };
    const newAnnotations: AnnotationData[] = [{
      id: 'new1',
      trackId: 'track2',
      type: 'arrow',
      classes: ['test-green'],
      label: 'New Gene',
      start: 20,
      end: 40,
      direction: 'right'
    }];

    viewer.setData(initialData);
    viewer.addTrack(newTrack, newAnnotations);

    const data = viewer.getData();
    expect(data.tracks).toHaveLength(2);
    expect(data.annotations).toHaveLength(2);
    expect(data.tracks[1]).toEqual(newTrack);
    expect(data.annotations[1]).toEqual(newAnnotations[0]);
  });

  test('should remove track correctly', () => {
    const viewer = new TrackViewer({
      container: '#test-container'
    });

    const data: TrackViewerData = {
      tracks: [
        { id: 'track1', label: 'Track 1' },
        { id: 'track2', label: 'Track 2' }
      ],
      annotations: [
        {
          id: 'gene1',
          trackId: 'track1',
          type: 'box',
          classes: ['test-blue'],
          label: 'Gene1',
          start: 5,
          end: 15,
        },
        {
          id: 'gene2',
          trackId: 'track2',
          type: 'box',
          classes: ['test-green'],
          label: 'Gene2',
          start: 20,
          end: 40,
        }
      ]
    };

    viewer.setData(data);
    viewer.removeTrack('track1');

    const resultData = viewer.getData();
    expect(resultData.tracks).toHaveLength(1);
    expect(resultData.annotations).toHaveLength(1);
    expect(resultData.tracks[0].id).toBe('track2');
    expect(resultData.annotations[0].id).toBe('gene2');
  });

  test('should update domain correctly', () => {
    const viewer = new TrackViewer({
      container: '#test-container',
      domain: [0, 100]
    });

    viewer.updateDomain([0, 500]);
    
    const config = viewer.getConfig();
    expect(config.domain).toEqual([0, 500]);
  });

  test('should throw error for invalid container', () => {
    expect(() => {
      new TrackViewer({
        container: '#nonexistent-container'
      });
    }).toThrow('Container element not found');
  });

  test('should accept HTMLElement as container', () => {
    const viewer = new TrackViewer({
      container: container
    });

    expect(viewer).toBeInstanceOf(TrackViewer);
  });

  test('should add and remove individual annotations', () => {
    const viewer = new TrackViewer({
      container: '#test-container'
    });

    const initialData: TrackViewerData = {
      tracks: [{ id: 'track1', label: 'Test Track' }],
      annotations: []
    };

    viewer.setData(initialData);

    const annotation: AnnotationData = {
      id: 'anno1',
      trackId: 'track1',
      type: 'arrow',
      classes: ['test-red'],
      label: 'Test Gene',
      start: 10,
      end: 30,
      direction: 'right'
    };

    viewer.addAnnotation(annotation);
    let data = viewer.getData();
    expect(data.annotations).toHaveLength(1);
    expect(data.annotations[0]).toEqual(annotation);

    viewer.removeAnnotation('anno1');
    data = viewer.getData();
    expect(data.annotations).toHaveLength(0);
  });

  test('should handle different annotation types and classes', () => {
    const viewer = new TrackViewer({
      container: '#test-container'
    });

    const data: TrackViewerData = {
      tracks: [{ id: 'track1', label: 'Mixed Track' }],
      annotations: [
        {
          id: 'arrow1',
          trackId: 'track1',
          type: 'arrow',
          classes: ['annotation-gene'],
          label: 'Gene',
          start: 10,
          end: 30,
          direction: 'right',
          heightFraction: 0.8
        },
        {
          id: 'box1',
          trackId: 'track1',
          type: 'box',
          classes: ['annotation-domain'],
          label: 'Domain',
          start: 40,
          end: 60,
          heightFraction: 0.5
        },
        {
          id: 'marker1',
          trackId: 'track1',
          type: 'circle',
          classes: ['annotation-regulatory'],
          label: 'Site',
          start: 70,
          end: 75,
          // No heightFraction - should use default
        }
      ],
      primitives: []
    };

    viewer.setData(data);
    const retrievedData = viewer.getData();
    
    expect(retrievedData.annotations).toHaveLength(3);
    expect(retrievedData.annotations[0].type).toBe('arrow');
    expect(retrievedData.annotations[0].heightFraction).toBe(0.8);
    expect(retrievedData.annotations[1].type).toBe('box');
    expect(retrievedData.annotations[1].heightFraction).toBe(0.5);
    expect(retrievedData.annotations[2].type).toBe('circle');
    expect(retrievedData.annotations[2].heightFraction).toBeUndefined();
  });

  test('should handle drawing primitives', () => {
    const viewer = new TrackViewer({
      container: '#test-container'
    });

    const data: TrackViewerData = {
      tracks: [{ id: 'track1', label: 'Track with Primitives' }],
      annotations: [],
      primitives: [
        {
          id: 'line1',
          trackId: 'track1',
          type: 'horizontal-line',
          class: 'baseline',
          start: 10,
          end: 90
        },
        {
          id: 'line2',
          trackId: 'track1',
          type: 'horizontal-line',
          class: 'full-width',
          // No start/end - should span entire axis
        }
      ]
    };

    viewer.setData(data);
    const retrievedData = viewer.getData();
    
    expect(retrievedData.primitives).toHaveLength(2);
    expect(retrievedData.primitives![0].type).toBe('horizontal-line');
    expect(retrievedData.primitives![0].id).toBe('line1');
    expect(retrievedData.primitives![0].start).toBe(10);
    expect(retrievedData.primitives![0].end).toBe(90);
    expect(retrievedData.primitives![1].id).toBe('line2');
    expect(retrievedData.primitives![1].start).toBeUndefined();
    expect(retrievedData.primitives![1].end).toBeUndefined();
  });

  test('should add and remove primitives individually', () => {
    const viewer = new TrackViewer({
      container: '#test-container'
    });

    const initialData: TrackViewerData = {
      tracks: [{ id: 'track1', label: 'Test Track' }],
      annotations: [],
      primitives: []
    };

    viewer.setData(initialData);

    const primitive: DrawingPrimitive = {
      id: 'prim1',
      trackId: 'track1',
      type: 'horizontal-line',
      class: 'test-line',
      start: 10,
      end: 90
    };

    viewer.addPrimitive(primitive);
    let data = viewer.getData();
    expect(data.primitives).toHaveLength(1);
    expect(data.primitives![0]).toEqual(primitive);

    viewer.removePrimitive('prim1');
    data = viewer.getData();
    expect(data.primitives).toHaveLength(0);
  });

  test('should handle per-track heights', () => {
    const viewer = new TrackViewer({
      container: '#test-container',
      trackHeight: 30 // Default height
    });

    const data: TrackViewerData = {
      tracks: [
        { id: 'track1', label: 'Normal Track' }, // Will use default height (30)
        { id: 'track2', label: 'Tall Track', height: 50 }, // Custom height
        { id: 'track3', label: 'Short Track', height: 20 } // Custom height
      ],
      annotations: [
        {
          id: 'anno1',
          trackId: 'track1',
          type: 'box',
          classes: ['test'],
          label: 'Test 1',
          start: 10,
          end: 30,
        },
        {
          id: 'anno2',
          trackId: 'track2',
          type: 'box',
          classes: ['test'],
          label: 'Test 2',
          start: 40,
          end: 60,
        }
      ],
      primitives: []
    };

    viewer.setData(data);
    
    // Verify the data was set correctly
    const retrievedData = viewer.getData();
    expect(retrievedData.tracks).toHaveLength(3);
    expect(retrievedData.tracks[0].height).toBeUndefined(); // Should use default
    expect(retrievedData.tracks[1].height).toBe(50);
    expect(retrievedData.tracks[2].height).toBe(20);
  });
});
