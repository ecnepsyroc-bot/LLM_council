#!/bin/bash
# Test Docker build and deployment for LLM Council

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="llm-council"
CONTAINER_NAME="llm-council-test"
PORT=8001
HEALTH_TIMEOUT=60

echo -e "${YELLOW}=== LLM Council Docker Test ===${NC}"
echo ""

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Cleaning up...${NC}"
    docker stop $CONTAINER_NAME 2>/dev/null || true
    docker rm $CONTAINER_NAME 2>/dev/null || true
}

# Set trap for cleanup on exit
trap cleanup EXIT

# Step 1: Build image
echo -e "${YELLOW}[1/6] Building Docker image...${NC}"
docker build \
    --build-arg VERSION=test \
    --build-arg BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ") \
    --build-arg GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown") \
    -t $IMAGE_NAME:test \
    .

if [ $? -ne 0 ]; then
    echo -e "${RED}Build failed!${NC}"
    exit 1
fi

echo -e "${GREEN}Build successful${NC}"

# Step 2: Check image size
echo -e "\n${YELLOW}[2/6] Checking image size...${NC}"
IMAGE_SIZE=$(docker image inspect $IMAGE_NAME:test --format='{{.Size}}' | awk '{printf "%.0f", $1/1024/1024}')
echo "Image size: ${IMAGE_SIZE}MB"

if [ $IMAGE_SIZE -gt 500 ]; then
    echo -e "${YELLOW}Warning: Image size exceeds 500MB target${NC}"
else
    echo -e "${GREEN}Image size within target${NC}"
fi

# Step 3: Run container
echo -e "\n${YELLOW}[3/6] Starting container...${NC}"

# Create a temporary env file for testing
cat > /tmp/test.env << EOF
OPENROUTER_API_KEY=test-key
BYPASS_AUTH=true
LOG_LEVEL=INFO
EOF

docker run -d \
    --name $CONTAINER_NAME \
    -p $PORT:8001 \
    --env-file /tmp/test.env \
    $IMAGE_NAME:test

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to start container!${NC}"
    exit 1
fi

echo -e "${GREEN}Container started${NC}"

# Step 4: Wait for health check
echo -e "\n${YELLOW}[4/6] Waiting for health check...${NC}"

ELAPSED=0
HEALTHY=false

while [ $ELAPSED -lt $HEALTH_TIMEOUT ]; do
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' $CONTAINER_NAME 2>/dev/null || echo "starting")

    if [ "$STATUS" == "healthy" ]; then
        HEALTHY=true
        break
    fi

    echo -n "."
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done

echo ""

if [ "$HEALTHY" = true ]; then
    echo -e "${GREEN}Container is healthy${NC}"
else
    echo -e "${RED}Health check timeout after ${HEALTH_TIMEOUT}s${NC}"
    echo "Container logs:"
    docker logs $CONTAINER_NAME --tail 50
    exit 1
fi

# Step 5: Test API endpoints
echo -e "\n${YELLOW}[5/6] Testing API endpoints...${NC}"

# Test health endpoint
echo -n "  /health: "
HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$PORT/health)
if [ "$HEALTH_RESPONSE" == "200" ]; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED (HTTP $HEALTH_RESPONSE)${NC}"
    exit 1
fi

# Test API config endpoint
echo -n "  /api/config: "
CONFIG_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$PORT/api/config)
if [ "$CONFIG_RESPONSE" == "200" ]; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED (HTTP $CONFIG_RESPONSE)${NC}"
    exit 1
fi

# Test conversations endpoint
echo -n "  /api/conversations: "
CONV_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$PORT/api/conversations)
if [ "$CONV_RESPONSE" == "200" ]; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED (HTTP $CONV_RESPONSE)${NC}"
    exit 1
fi

# Step 6: Check logs for errors
echo -e "\n${YELLOW}[6/6] Checking logs for errors...${NC}"

ERROR_COUNT=$(docker logs $CONTAINER_NAME 2>&1 | grep -ci "error" || true)
WARNING_COUNT=$(docker logs $CONTAINER_NAME 2>&1 | grep -ci "warning" || true)

echo "  Errors found: $ERROR_COUNT"
echo "  Warnings found: $WARNING_COUNT"

if [ $ERROR_COUNT -gt 0 ]; then
    echo -e "${YELLOW}Warning: Errors found in logs${NC}"
    echo "Recent error logs:"
    docker logs $CONTAINER_NAME 2>&1 | grep -i "error" | tail -5
fi

# Summary
echo -e "\n${GREEN}=== All Tests Passed ===${NC}"
echo ""
echo "Image: $IMAGE_NAME:test"
echo "Size: ${IMAGE_SIZE}MB"
echo "Container: $CONTAINER_NAME"
echo ""
echo "The Docker image is ready for production."
echo ""
