import { RegionViewer, Track } from '../RegionViewer';

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

  test('should set and get data correctly', () => {
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

    viewer.setData(testData);
    const retrievedData = viewer.getData();
    
    expect(retrievedData).toEqual(testData);
    expect(retrievedData).not.toBe(testData); // Should be a copy
  });

  test('should add track correctly', () => {
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

    viewer.setData([initialTrack]);
    viewer.addTrack(newTrack);

    const data = viewer.getData();
    expect(data).toHaveLength(2);
    expect(data[1]).toEqual(newTrack);
  });

  test('should remove track correctly', () => {
    const viewer = new RegionViewer({
      container: '#test-container'
    });

    const tracks: Track[] = [
      {
        track: 'Track 1',
        id: 'track1',
        annotations: [{ start: 5, end: 15, label: 'Gene1' }]
      },
      {
        track: 'Track 2', 
        id: 'track2',
        annotations: [{ start: 20, end: 40, label: 'Gene2' }]
      }
    ];

    viewer.setData(tracks);
    viewer.removeTrack('track1');

    const data = viewer.getData();
    expect(data).toHaveLength(1);
    expect(data[0].id).toBe('track2');
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
});
