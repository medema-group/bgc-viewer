#!/bin/bash

# BGC Viewer Version Management Script
# Usage: ./scripts/version.sh [patch|minor|major|specific_version] [--commit]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

function get_current_version() {
    grep '^version = ' "$ROOT_DIR/backend/pyproject.toml" | sed 's/^version = "\(.*\)"/\1/'
}

function update_version() {
    local new_version=$1
    local file=$2
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/\"version\": \".*\"/\"version\": \"$new_version\"/" "$file"
    else
        # Linux
        sed -i "s/\"version\": \".*\"/\"version\": \"$new_version\"/" "$file"
    fi
}

function update_python_version() {
    local new_version=$1
    local file=$2
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/version = \".*\"/version = \"$new_version\"/" "$file"
    else
        # Linux
        sed -i "s/version = \".*\"/version = \"$new_version\"/" "$file"
    fi
}

function update_python_init_version() {
    local new_version=$1
    local file=$2
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/__version__ = \".*\"/__version__ = \"$new_version-dev\"/" "$file"
    else
        # Linux
        sed -i "s/__version__ = \".*\"/__version__ = \"$new_version-dev\"/" "$file"
    fi
}

function regenerate_lockfiles() {
    echo "🔄 Regenerating lock files..."
    
    # Regenerate uv.lock for backend
    if command -v uv &> /dev/null; then
        (cd "$ROOT_DIR/backend" && uv lock)
        echo "  ✅ Regenerated backend/uv.lock"
    else
        echo "  ⚠️  uv not found, skipping backend/uv.lock regeneration"
    fi
    
    # Regenerate package-lock.json for frontend
    if command -v npm &> /dev/null; then
        (cd "$ROOT_DIR/frontend" && npm install --package-lock-only)
        echo "  ✅ Regenerated frontend/package-lock.json"
    else
        echo "  ⚠️  npm not found, skipping package-lock.json regeneration"
    fi
}

function increment_version() {
    local version=$1
    local increment=$2
    
    IFS='.' read -ra PARTS <<< "$version"
    major=${PARTS[0]}
    minor=${PARTS[1]}
    patch=${PARTS[2]}
    
    case $increment in
        patch)
            patch=$((patch + 1))
            ;;
        minor)
            minor=$((minor + 1))
            patch=0
            ;;
        major)
            major=$((major + 1))
            minor=0
            patch=0
            ;;
    esac
    
    echo "$major.$minor.$patch"
}

# Main logic
if [ $# -eq 0 ]; then
    echo "Current version: $(get_current_version)"
    echo "Usage: $0 <version> [--commit]"
    echo "  version: Specific version like 0.2.3"
    echo "  --commit: Automatically commit changes, create tag, and push"
    exit 0
fi

# Parse arguments
auto_commit=false
version_arg=""

for arg in "$@"; do
    case $arg in
        --commit)
            auto_commit=true
            ;;
        *)
            if [ -z "$version_arg" ]; then
                version_arg="$arg"
            fi
            ;;
    esac
done

if [ -z "$version_arg" ]; then
    echo "Error: Version argument required"
    echo "Usage: $0 <version> [--commit]"
    echo "  Example: $0 0.2.3"
    exit 1
fi

current_version=$(get_current_version)

if [[ ! $version_arg =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: Invalid version format. Please use semantic versioning (e.g., 0.2.3)"
    exit 1
fi

new_version=$version_arg

echo "Updating version from $current_version to $new_version"

# Update all package.json files
update_version "$new_version" "$ROOT_DIR/frontend/package.json"

# Update Python backend version
update_python_version "$new_version" "$ROOT_DIR/backend/pyproject.toml"

# Update Python __init__.py fallback version
update_python_init_version "$new_version" "$ROOT_DIR/backend/bgc_viewer/__init__.py"

# Regenerate lock files to match new versions
regenerate_lockfiles

echo "✅ Version updated to $new_version in all packages (frontend, backend)"
echo "✅ Lock files regenerated to match new version"

if [ "$auto_commit" = true ]; then
    echo "� Auto-committing and pushing..."
    
    # Check if there are any changes to commit
    if ! git diff --quiet || ! git diff --cached --quiet; then
        # Stage only modified (tracked) files, not untracked files
        git add -u
        
        # Commit with version message
        git commit -m "Bump version to $new_version"
        
        # Create annotated tag
        git tag -a "v$new_version" -m "Release version $new_version"
        
        # Push commits and tags
        git push origin --follow-tags
        
        echo "✅ Committed, tagged (v$new_version), and pushed to origin"
    else
        echo "⚠️  No changes detected to commit"
    fi
else
    echo "📝 To commit and tag manually:"
    echo "   git add -u  # Only modified files"
    echo "   git commit -m \"Bump version to $new_version\""
    echo "   git tag v$new_version"
    echo "   git push origin --follow-tags"
fi
