import { RegionViewer, Track, RegionViewerData, TrackData, AnnotationData } from '../RegionViewer';

/**
 * RegionViewer tests using the real D3 library
 * This approach is more reliable than mocking and tests actual integration
 */

describe('RegionViewer', () => {
  let container: HTMLDivElement;

  beforeEach(() => {
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
    const tooltips = document.querySelectorAll('.region-viewer-tooltip');
    tooltips.forEach(tooltip => tooltip.remove());
  });

  test('should create RegionViewer instance with default config', () => {
    const viewer = new RegionViewer({
      container: '#test-container'
    });

    expect(viewer).toBeInstanceOf(RegionViewer);
    const config = viewer.getConfig();
    expect(config.width).toBe(800);
    expect(config.height).toBe(300);
    expect(config.rowHeight).toBe(30);
  });

  test('should create RegionViewer instance with custom config', () => {
    const onAnnotationClick = jest.fn();
    const viewer = new RegionViewer({
      container: '#test-container',
      width: 1000,
      height: 400,
      rowHeight: 40,
      domain: [0, 200],
      onAnnotationClick
    });

    const config = viewer.getConfig();
    expect(config.width).toBe(1000);
    expect(config.height).toBe(400);
    expect(config.rowHeight).toBe(40);
    expect(config.domain).toEqual([0, 200]);
    expect(config.onAnnotationClick).toBe(onAnnotationClick);
  });

  test('should set and get data correctly using new format', () => {
    const viewer = new RegionViewer({
      container: '#test-container'
    });

    const testData: RegionViewerData = {
      tracks: [{ id: 'track1', label: 'Test Track' }],
      annotations: [{
        id: 'gene1',
        trackId: 'track1',
        type: 'box',
        class: 'test-blue',
        label: 'Gene1',
        start: 10,
        end: 30,
        direction: 'none'
      }]
    };

    viewer.setData(testData);
    const retrievedData = viewer.getData();
    
    expect(retrievedData).toEqual(testData);
    expect(retrievedData).not.toBe(testData); // Should be a copy
  });

  test('should set data using legacy format (backward compatibility)', () => {
    const viewer = new RegionViewer({
      container: '#test-container'
    });

    const testData: Track[] = [
      {
        track: 'Test Track',
        annotations: [
          { start: 10, end: 30, label: 'Gene1', id: 'gene1' }
        ]
      }
    ];

    viewer.setTrackData(testData);
    const retrievedData = viewer.getTrackData();
    
    // The conversion process adds an id field if it wasn't present
    const expectedData = [
      {
        track: 'Test Track',
        id: 'Test Track',
        annotations: [
          { start: 10, end: 30, label: 'Gene1', id: 'gene1' }
        ]
      }
    ];
    
    expect(retrievedData).toEqual(expectedData);
    expect(retrievedData).not.toBe(testData); // Should be a copy
  });

  test('should add track correctly using new format', () => {
    const viewer = new RegionViewer({
      container: '#test-container'
    });

    const initialData: RegionViewerData = {
      tracks: [{ id: 'track1', label: 'Initial Track' }],
      annotations: [{
        id: 'initial1',
        trackId: 'track1',
        type: 'box',
        class: 'test-blue',
        label: 'Initial',
        start: 5,
        end: 15,
        direction: 'none'
      }]
    };

    const newTrack: TrackData = { id: 'track2', label: 'New Track' };
    const newAnnotations: AnnotationData[] = [{
      id: 'new1',
      trackId: 'track2',
      type: 'arrow',
      class: 'test-green',
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

  test('should add track correctly using legacy format', () => {
    const viewer = new RegionViewer({
      container: '#test-container'
    });

    const initialTrack: Track = {
      track: 'Initial Track',
      annotations: [{ start: 5, end: 15, label: 'Initial' }]
    };

    const newTrack: Track = {
      track: 'New Track',
      annotations: [{ start: 20, end: 40, label: 'New Gene' }]
    };

    viewer.setTrackData([initialTrack]);
    viewer.addTrackLegacy(newTrack);

    const data = viewer.getTrackData();
    expect(data).toHaveLength(2);
    expect(data[1].track).toBe(newTrack.track);
    expect(data[1].annotations[0].label).toBe('New Gene');
  });

  test('should remove track correctly', () => {
    const viewer = new RegionViewer({
      container: '#test-container'
    });

    const data: RegionViewerData = {
      tracks: [
        { id: 'track1', label: 'Track 1' },
        { id: 'track2', label: 'Track 2' }
      ],
      annotations: [
        {
          id: 'gene1',
          trackId: 'track1',
          type: 'box',
          class: 'test-blue',
          label: 'Gene1',
          start: 5,
          end: 15,
          direction: 'none'
        },
        {
          id: 'gene2',
          trackId: 'track2',
          type: 'box',
          class: 'test-green',
          label: 'Gene2',
          start: 20,
          end: 40,
          direction: 'none'
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
    const viewer = new RegionViewer({
      container: '#test-container',
      domain: [0, 100]
    });

    viewer.updateDomain([0, 500]);
    
    const config = viewer.getConfig();
    expect(config.domain).toEqual([0, 500]);
  });

  test('should throw error for invalid container', () => {
    expect(() => {
      new RegionViewer({
        container: '#nonexistent-container'
      });
    }).toThrow('Container element not found');
  });

  test('should accept HTMLElement as container', () => {
    const viewer = new RegionViewer({
      container: container
    });

    expect(viewer).toBeInstanceOf(RegionViewer);
  });

  test('should add and remove individual annotations', () => {
    const viewer = new RegionViewer({
      container: '#test-container'
    });

    const initialData: RegionViewerData = {
      tracks: [{ id: 'track1', label: 'Test Track' }],
      annotations: []
    };

    viewer.setData(initialData);

    const annotation: AnnotationData = {
      id: 'anno1',
      trackId: 'track1',
      type: 'arrow',
      class: 'test-red',
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
    const viewer = new RegionViewer({
      container: '#test-container'
    });

    const data: RegionViewerData = {
      tracks: [{ id: 'track1', label: 'Mixed Track' }],
      annotations: [
        {
          id: 'arrow1',
          trackId: 'track1',
          type: 'arrow',
          class: 'annotation-gene',
          label: 'Gene',
          start: 10,
          end: 30,
          direction: 'right'
        },
        {
          id: 'box1',
          trackId: 'track1',
          type: 'box',
          class: 'annotation-domain',
          label: 'Domain',
          start: 40,
          end: 60,
          direction: 'none'
        },
        {
          id: 'marker1',
          trackId: 'track1',
          type: 'marker',
          class: 'annotation-regulatory',
          label: 'Site',
          start: 70,
          end: 75,
          direction: 'none'
        }
      ]
    };

    viewer.setData(data);
    const retrievedData = viewer.getData();
    
    expect(retrievedData.annotations).toHaveLength(3);
    expect(retrievedData.annotations[0].type).toBe('arrow');
    expect(retrievedData.annotations[1].type).toBe('box');
    expect(retrievedData.annotations[2].type).toBe('marker');
  });
});
