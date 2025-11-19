/**
 * Web Components build entry point
 * Exports RegionViewer and RegionViewerContainer as custom elements
 */

import { defineCustomElement } from 'vue'
import RegionViewerContainerComponent from './components/RegionViewerContainer.vue'
import RegionViewerComponent from './components/RegionViewer.vue'

// Define the custom elements
const RegionViewerContainer = defineCustomElement(RegionViewerContainerComponent)
const RegionViewer = defineCustomElement(RegionViewerComponent)

// Register the custom elements
customElements.define('bgc-region-viewer-container', RegionViewerContainer)
customElements.define('bgc-region-viewer', RegionViewer)

// Export for manual registration if needed
export { RegionViewerContainer, RegionViewer }

// Export data provider classes dynamically to avoid circular dependencies
export { BGCViewerAPIProvider } from './services/dataProviders/BGCViewerAPIProvider'
export { JSONFileProvider } from './services/dataProviders/JSONFileProvider'
