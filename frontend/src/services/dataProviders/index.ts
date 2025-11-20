/**
 * Data Providers for BGC Viewer
 * 
 * This module provides different data sources for the BGC Viewer components.
 * All providers implement the DataProvider interface defined in types.ts
 */

export * from './types'
export { BGCViewerAPIProvider } from './BGCViewerAPIProvider'
export { JSONFileProvider } from './JSONFileProvider'

import { DataProvider } from './types'
import { BGCViewerAPIProvider } from './BGCViewerAPIProvider'
import { JSONFileProvider } from './JSONFileProvider'

export type ProviderType = 'api' | 'json'

export interface ProviderOptions {
  baseURL?: string
  records?: any[]
  pfamColorMap?: Record<string, string>
}

/**
 * Create a data provider based on configuration
 * @param type - Provider type: 'api', 'json'
 * @param options - Provider-specific options
 * @returns DataProvider instance
 */
export async function createDataProvider(
  type: ProviderType, 
  options: ProviderOptions = {}
): Promise<DataProvider> {
  switch (type) {
    case 'api':
      return new BGCViewerAPIProvider(options)
    case 'json':
      return new JSONFileProvider(options)
    default:
      throw new Error(`Unknown provider type: ${type}`)
  }
}
