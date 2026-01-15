# Documentation Guide

BGC Viewer documentation is built with VitePress.

## Quick Start

```bash
# Build for local preview
./scripts/build-docs.sh local

# Serve locally
./scripts/serve-docs.sh
```

Visit http://localhost:8080

## Structure

```
docs/guide/
├── guide/          # User guides and tutorials
├── components/     # Component documentation
├── api/            # REST API reference
└── examples/       # Interactive examples
```

## Development

```bash
cd docs/guide
npm install
npm run docs:dev  # Hot reload at http://localhost:5173
```

## Building

**Local preview:**
```bash
./scripts/build-docs.sh local
```

**GitHub Pages:**
```bash
./scripts/build-docs.sh
```

## Writing Docs

Documentation is written in Markdown with optional Vue components:

```markdown
# Page Title

Regular markdown content...

## Code Examples

\`\`\`javascript
const example = 'code';
\`\`\`

## Interactive Components

<script setup>
import { ref } from 'vue'
const count = ref(0)
</script>

<button @click="count++">Count: {{ count }}</button>
```

### API Documentation

REST API endpoints are documented in `docs/guide/api/` with:
- HTTP methods and endpoints
- Request/response JSON examples
- Error codes and messages
- JavaScript usage examples

See existing API docs for formatting patterns.

## Deployment

Automatic deployment to GitHub Pages on push to `main` branch.

**Setup:**
1. Go to Settings > Pages
2. Set Source to "GitHub Actions"
3. Push to main

Site will be at: `https://medema-group.github.io/bgc-viewer/`

## Customization

**Site config:** `docs/guide/.vitepress/config.mts`
- Navigation and sidebar
- Site metadata
- Social links

**Theme:** `docs/guide/.vitepress/theme/`
- Custom styles in `style.css`
- Theme extensions in `index.ts`

## Troubleshooting

```bash
# Clear and rebuild
cd docs/guide
rm -rf node_modules package-lock.json .vitepress/cache
npm install
npm run docs:build
```

## Resources

- [VitePress Guide](https://vitepress.dev/)
- [Markdown Guide](https://www.markdownguide.org/)
- [Vue 3 Docs](https://vuejs.org/)
