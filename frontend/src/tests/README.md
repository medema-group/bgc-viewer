# Frontend Tests

This directory contains tests for the BGC Viewer frontend components and web components.

## Running Tests

```bash
# Run tests in watch mode (interactive)
npm test

# Run tests once (CI mode)
npm run test:run

# Run tests with coverage report
npm run test:coverage

# Run tests with UI (browser-based interface)
npm run test:ui
```

## Test Files

- **`web-components.test.js`** - Tests for web component registration, initialization, and circular dependency detection
- **`data-providers.test.js`** - Tests for JSONFileProvider and BGCViewerAPIProvider
- **`setup.js`** - Test setup and mocks (runs before all tests)

## Writing Tests

Tests use [Vitest](https://vitest.dev/) which is compatible with Jest syntax.

### Example Test

```javascript
import { describe, it, expect, beforeEach } from 'vitest'

describe('MyComponent', () => {
  it('should work correctly', () => {
    expect(true).toBe(true)
  })
})
```

### Testing Web Components

```javascript
it('should create custom element', () => {
  const element = document.createElement('bgc-region-viewer')
  expect(element).toBeInstanceOf(HTMLElement)
})
```

### Mocking

The `setup.js` file provides mocks for:
- `window.BGCViewer.TrackViewer` - Mock D3 visualization component
- `window.d3` - D3.js library

## Coverage

Coverage reports are generated in the `coverage/` directory when running `npm run test:coverage`.

Target coverage goals:
- Statements: > 80%
- Branches: > 75%
- Functions: > 80%
- Lines: > 80%

## CI/CD Integration

Tests can be run in CI pipelines:

```yaml
# GitHub Actions example
- name: Run tests
  run: npm run test:run

- name: Generate coverage
  run: npm run test:coverage
```

## Troubleshooting

### Module Import Errors

If you see errors about ES modules, ensure:
1. `vitest.config.js` has the correct `resolve.alias` configuration
2. Test files use `.js` extensions (not `.mjs`)

### Component Not Rendering

Web components need to be connected to the DOM:
```javascript
const element = document.createElement('bgc-region-viewer')
document.body.appendChild(element)
await new Promise(resolve => setTimeout(resolve, 10)) // Wait for connection
```
