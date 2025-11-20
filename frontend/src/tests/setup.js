/**
 * Test setup file
 * Runs before each test file
 */

// Mock window.BGCViewer for tests
global.window.BGCViewer = {
  TrackViewer: class MockTrackViewer {
    constructor(config) {
      this.config = config
      this.destroyed = false
    }
    
    destroy() {
      this.destroyed = true
    }
    
    setData() {}
    update() {}
    resize() {}
  }
}

// Mock D3 if needed
global.window.d3 = {}

// Suppress console warnings in tests (optional)
// global.console.warn = vi.fn()
// global.console.error = vi.fn()
