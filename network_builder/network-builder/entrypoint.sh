#!/bin/bash
# Run the network builder, tee-ing stdout+stderr to a timestamped log file
# when the output volume is mounted, while still streaming to stdout.
set -o pipefail

OUTPUT_DIR="${OUTPUT_DIR:-/app/output}"

if [ -d "$OUTPUT_DIR" ]; then
    LOG_FILE="$OUTPUT_DIR/build_$(date +%Y%m%d_%H%M%S).log"
    python network-builder/build_network.py "$@" 2>&1 | tee "$LOG_FILE"
else
    exec python network-builder/build_network.py "$@"
fi
