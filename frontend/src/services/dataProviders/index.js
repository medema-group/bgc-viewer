/**
 * Data Providers for BGC Viewer
 * 
 * This module provides different data sources for the BGC Viewer components.
 * All providers implement the DataProvider interface defined in types.js
 */

export { DataProvider } from './types.js'
export { BGCViewerAPIProvider } from './BGCViewerAPIProvider.js'
export { JSONFileProvider } from './JSONFileProvider.js'

/**
 * Create a data provider based on configuration
 * @param {string} type - Provider type: 'api', 'json'
 * @param {Object} options - Provider-specific options
 * @returns {DataProvider}
 */
export async function createDataProvider(type, options = {}) {
  switch (type) {
    case 'api':
      return new (await import('./BGCViewerAPIProvider.js')).BGCViewerAPIProvider(options)
    case 'json':
      return new (await import('./JSONFileProvider.js')).JSONFileProvider(options)
    default:
      throw new Error(`Unknown provider type: ${type}`)
  }
}
