#!/bin/bash
# Publish script for baidu-netdisk-skills
# Syncs code from clawhub.ai remote and publishes a new version

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Project directory
PROJECT_DIR="/Users/reky/Documents/GitHub/baidu-netdisk-skills"
CLAWHUB_REMOTE="https://clawhub.ai/may-yaha/baidu-netdisk-storage"
CLAWHUB_REMOTE_NAME="clawhub"

# Parse arguments
VERSION=""
CHANGELOG=""

usage() {
    echo "Usage: $0 --version <semver> [--changelog <text>]"
    echo ""
    echo "Options:"
    echo "  --version <version>    Version to publish (required, semver format, e.g. 1.0.0)"
    echo "  --changelog <text>     Changelog text (optional)"
    echo "  --help                 Show this help message"
    echo ""
    echo "Example:"
    echo "  $0 --version 1.0.0"
    echo "  $0 --version 1.1.0 --changelog 'Added new features'"
    exit 0
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --version|-v)
            VERSION="$2"
            shift 2
            ;;
        --changelog|-c)
            CHANGELOG="$2"
            shift 2
            ;;
        --help|-h)
            usage
            ;;
        *)
            log_error "Unknown argument: $1"
            usage
            ;;
    esac
done

if [ -z "$VERSION" ]; then
    log_error "Version is required. Use --version <semver>"
    echo ""
    usage
fi

# Validate semver format
if ! echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$'; then
    log_error "Invalid version format: $VERSION (expected semver, e.g. 1.0.0)"
    exit 1
fi

log_info "Publishing baidu-netdisk-skills v${VERSION}"
echo ""

# Step 1: Sync code from clawhub remote
log_info "Step 1: Syncing code from ${CLAWHUB_REMOTE}..."

cd "$PROJECT_DIR"

# Add clawhub remote if not exists
if ! git remote get-url "$CLAWHUB_REMOTE_NAME" &>/dev/null; then
    log_info "Adding clawhub remote..."
    git remote add "$CLAWHUB_REMOTE_NAME" "$CLAWHUB_REMOTE"
else
    # Ensure remote URL is correct
    current_url=$(git remote get-url "$CLAWHUB_REMOTE_NAME")
    if [ "$current_url" != "$CLAWHUB_REMOTE" ]; then
        log_warn "Updating clawhub remote URL from ${current_url} to ${CLAWHUB_REMOTE}"
        git remote set-url "$CLAWHUB_REMOTE_NAME" "$CLAWHUB_REMOTE"
    fi
fi

# Fetch from clawhub remote
log_info "Fetching from clawhub remote..."
git fetch "$CLAWHUB_REMOTE_NAME"

# Push current code to clawhub remote
log_info "Pushing code to clawhub remote..."
CURRENT_BRANCH=$(git branch --show-current)
git push "$CLAWHUB_REMOTE_NAME" "${CURRENT_BRANCH}" --force

log_info "✓ Code synced to clawhub remote"
echo ""

# Step 2: Publish version
log_info "Step 2: Publishing version ${VERSION}..."

PUBLISH_CMD="clawhub publish ${PROJECT_DIR} --version ${VERSION}"

if [ -n "$CHANGELOG" ]; then
    PUBLISH_CMD="${PUBLISH_CMD} --changelog \"${CHANGELOG}\""
fi

log_info "Running: ${PUBLISH_CMD}"
echo ""

if [ -n "$CHANGELOG" ]; then
    clawhub publish "$PROJECT_DIR" --version "$VERSION" --changelog "$CHANGELOG"
else
    clawhub publish "$PROJECT_DIR" --version "$VERSION"
fi

echo ""
log_info "✓ Successfully published baidu-netdisk-skills v${VERSION}"
log_info "View at: ${CLAWHUB_REMOTE}"
