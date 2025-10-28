#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is running
print_status "Checking Docker status..."
if ! docker info >/dev/null 2>&1; then
    print_warning "Docker is not running."

    if [[ "$(uname)" == "Darwin" ]]; then
        print_status "Starting Docker Desktop..."
        open -a "Docker"

        print_status "Waiting for Docker Desktop to start..."
        for i in {1..60}; do
            if docker info >/dev/null 2>&1; then
                echo ""
                print_success "Docker Desktop is now running."
                break
            else
                echo -n "."
                sleep 2
            fi
        done

        if ! docker info >/dev/null 2>&1; then
            echo ""
            print_error "Docker failed to start. Please start Docker Desktop manually."
            exit 1
        fi
    else
        print_error "Please start Docker and try again."
        exit 1
    fi
else
    print_success "Docker is running."
fi

# Variables
CURRENT_VERSION=$(python3 -c "import app; print(app.__version__)" 2>/dev/null || echo "unknown")
DEV_IMAGE="captnio/captn:$CURRENT_VERSION"
CONTAINER_NAME="captn-dev"
DOCKERFILE_PATH="docker/DOCKERFILE"

# Check if we need to build/rebuild the development image
print_status "Checking development image..."

BUILD_NEEDED=false

if ! docker image inspect $DEV_IMAGE >/dev/null 2>&1; then
    print_status "Development image not found."
    BUILD_NEEDED=true
else
    # Check if any relevant files are newer than the image
    IMAGE_DATE=$(docker image inspect $DEV_IMAGE --format '{{.Created}}')

    # Files that should trigger a rebuild
    CHECK_FILES=(
        "docker/DOCKERFILE"
        "requirements.txt"
        "docker/entrypoint.sh"
        "app/__init__.py"
    )

    for file in "${CHECK_FILES[@]}"; do
        if [[ -f "$file" ]]; then
            if [[ "$(uname)" == "Darwin" ]]; then
                FILE_DATE=$(stat -f "%Sm" -t "%Y-%m-%dT%H:%M:%SZ" "$file" 2>/dev/null)
            else
                FILE_DATE=$(date -r "$file" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null)
            fi

            if [[ "$FILE_DATE" > "$IMAGE_DATE" ]]; then
                print_status "$file is newer than image. Rebuild needed."
                BUILD_NEEDED=true
                break
            fi
        fi
    done

    if [[ "$BUILD_NEEDED" == false ]]; then
        print_success "Development image is up to date."
    fi
fi

# Build development image if needed
if [[ "$BUILD_NEEDED" == true ]]; then
    print_status "Building development image (native architecture)..."
    print_status "Using version: $CURRENT_VERSION"

    docker build \
        -f $DOCKERFILE_PATH \
        -t $DEV_IMAGE \
        --build-arg VERSION="$CURRENT_VERSION" \
        --build-arg REVISION="$(git rev-parse HEAD 2>/dev/null || echo 'unknown')" \
        --build-arg CREATED="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
        . || {
        print_error "Failed to build development image"
        exit 1
    }
    print_success "Development image built successfully."
fi

# Stop and remove existing development container if running
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    print_status "Stopping running development container..."
    docker stop $CONTAINER_NAME >/dev/null
fi

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    print_status "Removing existing development container..."
    docker rm $CONTAINER_NAME >/dev/null
fi

# Get current user info for proper file permissions
if [[ "$(uname)" == "Darwin" ]]; then
    USER_ID=$(id -u)
    GROUP_ID=$(id -g)
else
    USER_ID=$(id -u)
    GROUP_ID=$(id -g)
fi

# Start development container
print_status "Starting development container..."
print_status "Architecture: $(uname -m)"
print_status "User ID: $USER_ID:$GROUP_ID"

docker run -it --rm \
    --name $CONTAINER_NAME \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "$(pwd)/app":/app \
    -v captn-dev-cache:/root/.cache \
    -v captn-dev-pip:/opt/venv/lib/python3.11/site-packages \
    -w /app \
    -e PYTHONPATH=/app \
    -e DEVELOPMENT=true \
    -e HOST_UID=$USER_ID \
    -e HOST_GID=$GROUP_ID \
    --entrypoint /bin/bash \
    $DEV_IMAGE \
    -c '
        echo "======================================"
        echo -e "\033[0;32mcaptn Development Container\033[0m"
        echo "======================================"
        echo "Image: captnio/captn:dev"
        echo "Version: $CURRENT_VERSION"
        echo "Architecture: $(uname -m)"
        echo "Working Directory: $(pwd)"
        echo "Python: $(python3 --version)"
        echo ""
        echo "Available commands:"
        echo "  captn           - Run captn (main command)"
        echo "  python -m app   - Run via Python module"
        echo "  pytest          - Run tests"
        echo "  black app/      - Format code"
        echo "  flake8 app/     - Lint code"
        echo "  mypy app/       - Type checking"
        echo "  cu, dcu         - Legacy aliases"
        echo ""
        echo "Configuration:"
        echo "  $(ls -la conf/ 2>/dev/null | head -3 | tail -1 | cut -c1-10) /app/conf/"
        echo ""
        echo "Quick start:"
        echo "  captn --version"
        echo "  captn --help"
        echo "  captn --dry-run"
        echo ""
        echo "Note: This container uses the SAME base as production!"
        echo "Changes to files persist on the host system."
        echo "======================================"
        echo ""

        # Verify captn is working
        if command -v captn >/dev/null 2>&1; then
            echo "✅ captn command available"
            captn --version 2>/dev/null || echo "⚠️  captn version check failed"
        else
            echo "⚠️  captn command not found"
        fi

        echo ""
        echo "Starting interactive bash shell..."
        echo ""

        exec bash
    '

print_success "Development container session ended."