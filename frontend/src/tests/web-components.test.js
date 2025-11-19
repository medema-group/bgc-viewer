/**
 * Web Components Tests
 * Tests for custom element registration and basic functionality
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'

describe('Web Components', () => {
  describe('Module Loading', () => {
    it('should load web-components module without circular dependency errors', async () => {
      // This test ensures the module can be imported without initialization errors
      const loadModule = async () => {
        // Dynamic import to catch initialization errors
        const module = await import('../web-components.js')
        return module
      }
      
      // Should not throw
      await expect(loadModule()).resolves.toBeDefined()
    })

    it('should export RegionViewerContainer', async () => {
      const module = await import('../web-components.js')
      expect(module.RegionViewerContainer).toBeDefined()
      expect(typeof module.RegionViewerContainer).toBe('function')
    })

    it('should export RegionViewer', async () => {
      const module = await import('../web-components.js')
      expect(module.RegionViewer).toBeDefined()
      expect(typeof module.RegionViewer).toBe('function')
    })

    it('should export JSONFileProvider', async () => {
      const module = await import('../web-components.js')
      expect(module.JSONFileProvider).toBeDefined()
      expect(typeof module.JSONFileProvider).toBe('function')
    })

    it('should export BGCViewerAPIProvider', async () => {
      const module = await import('../web-components.js')
      expect(module.BGCViewerAPIProvider).toBeDefined()
      expect(typeof module.BGCViewerAPIProvider).toBe('function')
    })
  })

  describe('Custom Element Registration', () => {
    it('should register bgc-region-viewer-container', () => {
      const element = customElements.get('bgc-region-viewer-container')
      expect(element).toBeDefined()
    })

    it('should register bgc-region-viewer', () => {
      const element = customElements.get('bgc-region-viewer')
      expect(element).toBeDefined()
    })
  })

  describe('Component Instantiation', () => {
    let container

    beforeEach(() => {
      container = document.createElement('div')
      document.body.appendChild(container)
    })

    it('should create bgc-region-viewer-container element', () => {
      const element = document.createElement('bgc-region-viewer-container')
      container.appendChild(element)
      
      expect(element.tagName).toBe('BGC-REGION-VIEWER-CONTAINER')
      expect(element).toBeInstanceOf(HTMLElement)
    })

    it('should create bgc-region-viewer element', () => {
      const element = document.createElement('bgc-region-viewer')
      container.appendChild(element)
      
      expect(element.tagName).toBe('BGC-REGION-VIEWER')
      expect(element).toBeInstanceOf(HTMLElement)
    })

    it('should not throw when setting properties on container', async () => {
      const { JSONFileProvider } = await import('../web-components.js')
      const element = document.createElement('bgc-region-viewer-container')
      container.appendChild(element)
      
      // Wait for component to be connected
      await new Promise(resolve => setTimeout(resolve, 10))
      
      const provider = new JSONFileProvider({ records: [] })
      
      expect(() => {
        element.dataProvider = provider
      }).not.toThrow()
    })
  })
})
