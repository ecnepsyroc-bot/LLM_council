#!/bin/bash
# Release script for LLM Council
#
# Usage:
#   ./scripts/release.sh <version>
#   ./scripts/release.sh 1.0.0
#   ./scripts/release.sh 1.0.1 --dry-run

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
DOCKER_REGISTRY="ghcr.io/your-org"
IMAGE_NAME="llm-council"

# Parse arguments
VERSION=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            VERSION="$1"
            shift
            ;;
    esac
done

# Validate version
if [ -z "$VERSION" ]; then
    echo -e "${RED}Error: Version required${NC}"
    echo "Usage: $0 <version> [--dry-run]"
    echo "Example: $0 1.0.0"
    exit 1
fi

# Validate version format (semver)
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
    echo -e "${RED}Error: Invalid version format${NC}"
    echo "Version must be semver format: X.Y.Z or X.Y.Z-tag"
    exit 1
fi

echo -e "${YELLOW}=== LLM Council Release v${VERSION} ===${NC}"
echo ""

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}[DRY RUN MODE]${NC}"
    echo ""
fi

# Step 1: Check for uncommitted changes
echo -e "${YELLOW}[1/8] Checking for uncommitted changes...${NC}"
if [ -n "$(git status --porcelain)" ]; then
    echo -e "${RED}Error: Working directory has uncommitted changes${NC}"
    git status --short
    if [ "$DRY_RUN" = false ]; then
        exit 1
    fi
else
    echo -e "${GREEN}Working directory clean${NC}"
fi

# Step 2: Run tests
echo -e "\n${YELLOW}[2/8] Running backend tests...${NC}"
if [ "$DRY_RUN" = false ]; then
    BYPASS_AUTH=true pytest backend/tests/ -v --tb=short
else
    echo "[dry-run] Would run: pytest backend/tests/ -v --tb=short"
fi
echo -e "${GREEN}Backend tests passed${NC}"

echo -e "\n${YELLOW}[3/8] Running frontend tests...${NC}"
if [ "$DRY_RUN" = false ]; then
    cd frontend && npm test -- --run && cd ..
else
    echo "[dry-run] Would run: npm test -- --run"
fi
echo -e "${GREEN}Frontend tests passed${NC}"

# Step 3: Run linting
echo -e "\n${YELLOW}[4/8] Running linting...${NC}"
if [ "$DRY_RUN" = false ]; then
    ruff check backend/
    cd frontend && npm run lint && cd ..
else
    echo "[dry-run] Would run: ruff check backend/ && npm run lint"
fi
echo -e "${GREEN}Linting passed${NC}"

# Step 4: Update version in files
echo -e "\n${YELLOW}[5/8] Updating version in files...${NC}"

FILES_TO_UPDATE=(
    "pyproject.toml"
    "backend/health.py"
    "CHANGELOG.md"
)

for file in "${FILES_TO_UPDATE[@]}"; do
    if [ -f "$file" ]; then
        echo "  Checking $file"
    fi
done

if [ "$DRY_RUN" = false ]; then
    # Update pyproject.toml
    sed -i.bak "s/^version = .*/version = \"$VERSION\"/" pyproject.toml && rm pyproject.toml.bak

    # Update health.py VERSION constant
    sed -i.bak "s/^VERSION = .*/VERSION = \"$VERSION\"/" backend/health.py && rm backend/health.py.bak

    echo -e "${GREEN}Version updated to $VERSION${NC}"
else
    echo "[dry-run] Would update version to $VERSION in pyproject.toml and backend/health.py"
fi

# Step 5: Build frontend
echo -e "\n${YELLOW}[6/8] Building frontend...${NC}"
if [ "$DRY_RUN" = false ]; then
    cd frontend && npm run build && cd ..
else
    echo "[dry-run] Would run: npm run build"
fi
echo -e "${GREEN}Frontend built${NC}"

# Step 6: Create git tag
echo -e "\n${YELLOW}[7/8] Creating git tag...${NC}"
TAG_NAME="v$VERSION"

if [ "$DRY_RUN" = false ]; then
    # Stage version changes
    git add pyproject.toml backend/health.py

    # Commit version bump
    git commit -m "chore: bump version to $VERSION"

    # Create annotated tag
    git tag -a "$TAG_NAME" -m "Release $VERSION"

    echo -e "${GREEN}Created tag $TAG_NAME${NC}"
else
    echo "[dry-run] Would create tag: $TAG_NAME"
fi

# Step 7: Push tag
echo -e "\n${YELLOW}[8/8] Pushing tag...${NC}"
if [ "$DRY_RUN" = false ]; then
    read -p "Push tag to origin? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git push origin master
        git push origin "$TAG_NAME"
        echo -e "${GREEN}Tag pushed to origin${NC}"
    else
        echo -e "${YELLOW}Skipped push. To push manually:${NC}"
        echo "  git push origin master"
        echo "  git push origin $TAG_NAME"
    fi
else
    echo "[dry-run] Would push: git push origin $TAG_NAME"
fi

# Summary
echo ""
echo -e "${GREEN}=== Release Complete ===${NC}"
echo ""
echo "Version: $VERSION"
echo "Tag: $TAG_NAME"
echo ""
echo "Next steps:"
echo "  1. GitHub Actions will build and push Docker image"
echo "  2. GitHub will create a release with auto-generated notes"
echo "  3. Update documentation if needed"
echo ""
echo "Docker image will be available at:"
echo "  ${DOCKER_REGISTRY}/${IMAGE_NAME}:${VERSION}"
echo "  ${DOCKER_REGISTRY}/${IMAGE_NAME}:latest"
echo ""
