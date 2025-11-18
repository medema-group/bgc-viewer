# BGC Viewer Data Providers

This directory contains data provider implementations for the BGC Viewer. Data providers are responsible for fetching and formatting data from various sources (APIs, files, etc.) for display in the viewer components.

## Architecture

All data providers implement the `DataProvider` base class defined in `types.js`, which ensures a consistent interface regardless of the data source.

### Available Providers

#### 1. BGCViewerAPIProvider
Fetches data from the BGC Viewer backend API (current implementation).

```javascript
import { BGCViewerAPIProvider } from '@/services/dataProviders'

const provider = new BGCViewerAPIProvider({
  baseURL: '' // optional, defaults to current origin
})

// Get regions for a record
const { regions } = await provider.getRegions('NC_003888.3')

// Get all features for a record
const { features } = await provider.getRecordFeatures('NC_003888.3')

// Get features for a specific region
const { features, region_boundaries } = await provider.getRegionFeatures('NC_003888.3', 'region-1')

// Get PFAM color mapping
const colorMap = await provider.getPfamColorMap()
```

#### 2. JSONFileProvider
Loads data directly from antiSMASH JSON files (for offline/browser-only usage).

```javascript
import { JSONFileProvider } from '@/services/dataProviders'

const provider = new JSONFileProvider()

// Load from a File object (file input)
await provider.loadFromFile(fileObject)

// Or load from a URL
await provider.loadFromFile('/data/my-record.json')

// Optionally set PFAM colors
provider.setPfamColorMap(colorMap)

// Then use the same interface as other providers
const { regions } = await provider.getRegions('record-0')
```

## DataProvider Interface

All providers must implement these methods:

### `async getRecords()`
Returns a list of available records.

**Returns:** `Promise<RecordInfo[]>`

### `async getRegions(recordId)`
Returns regions for a specific record.

**Parameters:**
- `recordId` (string) - The record identifier

**Returns:** `Promise<{regions: Region[]}>`

### `async getRecordFeatures(recordId)`
Returns all features for a record (no region filtering).

**Parameters:**
- `recordId` (string) - The record identifier

**Returns:** `Promise<{features: Feature[]}>`

### `async getRegionFeatures(recordId, regionId)`
Returns features for a specific region within a record.

**Parameters:**
- `recordId` (string) - The record identifier
- `regionId` (string) - The region identifier

**Returns:** `Promise<{features: Feature[], region_boundaries?: {start: number, end: number}}>`

### `async getPfamColorMap()`
Returns PFAM domain color mapping.

**Returns:** `Promise<Object<string, string>>` - Map of PFAM IDs to hex colors

## Creating a New Provider

To add support for a new data source:

1. Create a new file in this directory (e.g., `MyCustomProvider.js`)
2. Import and extend the `DataProvider` base class
3. Implement all required methods
4. Export your provider in `index.js`

```javascript
import { DataProvider } from './types.js'

export class MyCustomProvider extends DataProvider {
  constructor(options = {}) {
    super()
    // Initialize your provider
  }

  async getRegions(recordId) {
    // Implement your data fetching logic
  }

  // ... implement other required methods
}
```

## Usage in Components

Components should receive a data provider instance and use it to fetch data:

```javascript
import { ref, onMounted } from 'vue'

export default {
  props: {
    dataProvider: {
      type: Object,
      required: true
    },
    recordId: {
      type: String,
      required: true
    }
  },
  setup(props) {
    const regions = ref([])
    
    onMounted(async () => {
      const data = await props.dataProvider.getRegions(props.recordId)
      regions.value = data.regions
    })
    
    return { regions }
  }
}
```
