#!/bin/bash

echo "=== Debug Completion Test ==="

# Test 1: Check if docker is available
echo "1. Testing docker availability:"
if command -v docker >/dev/null 2>&1; then
    echo "   ✓ Docker is available"
else
    echo "   ✗ Docker is NOT available"
    exit 1
fi

# Test 2: Test docker ps command
echo "2. Testing docker ps -a --format '{{.Names}}':"
container_names=$(docker ps -a --format "{{.Names}}")
echo "   Raw output: '$container_names'"

if [[ -n "${container_names}" ]]; then
    echo "   ✓ Container names found"
    echo "   Container names:"
    echo "$container_names" | while read name; do
        echo "     - $name"
    done
else
    echo "   ✗ No container names found"
fi

# Test 3: Test the old completion logic
echo "3. Testing OLD completion logic:"
cur="name=test"
prefix="${cur#name=}"
echo "   cur: '$cur'"
echo "   prefix: '$prefix'"

if [[ -n "${container_names}" ]]; then
    completions=$(compgen -W "${container_names}" -- "${prefix}" | sed 's/^/name=/')
    echo "   old completions: '$completions'"

    if [[ -n "${completions}" ]]; then
        echo "   ✓ Old completions generated"
    else
        echo "   ✗ No old completions generated"
    fi
else
    echo "   ✗ No container names to complete"
fi

# Test 4: Test the NEW completion logic
echo "4. Testing NEW completion logic:"
if [[ -n "${container_names}" ]]; then
    if [[ -n "$prefix" ]]; then
        # Filter container names that start with the prefix
        filtered_names=""
        while IFS= read -r name; do
            if [[ "$name" == "$prefix"* ]]; then
                filtered_names="$filtered_names $name"
            fi
        done <<< "$container_names"
        new_completions=$(echo "$filtered_names" | tr ' ' '\n' | sed 's/^/name=/')
    else
        # No prefix, show all container names
        new_completions=$(echo "$container_names" | tr '\n' ' ' | sed 's/^/name=/')
    fi

    echo "   new completions: '$new_completions'"

    if [[ -n "${new_completions}" ]]; then
        echo "   ✓ New completions generated"
        echo "   Completions:"
        echo "$new_completions" | while read completion; do
            echo "     - $completion"
        done
    else
        echo "   ✗ No new completions generated"
    fi
else
    echo "   ✗ No container names to complete"
fi

# Test 5: Test with different prefixes
echo "5. Testing with different prefixes:"
test_prefixes=("" "kit" "post" "mar" "xyz")

for test_prefix in "${test_prefixes[@]}"; do
    echo "   Testing prefix: '$test_prefix'"
    if [[ -n "${container_names}" ]]; then
        if [[ -n "$test_prefix" ]]; then
            # Filter container names that start with the prefix
            filtered_names=""
            while IFS= read -r name; do
                if [[ "$name" == "$test_prefix"* ]]; then
                    filtered_names="$filtered_names $name"
                fi
            done <<< "$container_names"
            completions=$(echo "$filtered_names" | tr ' ' '\n' | sed 's/^/name=/')
        else
            # No prefix, show all container names
            completions=$(echo "$container_names" | tr '\n' ' ' | sed 's/^/name=/')
        fi

        if [[ -n "${completions}" ]]; then
            echo "     ✓ Found: $(echo "$completions" | wc -l) completions"
        else
            echo "     ✗ No completions"
        fi
    fi
done

echo "=== End Debug Test ==="