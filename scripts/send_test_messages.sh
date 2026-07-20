#!/usr/bin/env bash
# Send test messages to a local Gotify instance
# Usage: ./scripts/send_test_messages.sh [APP_TOKEN]
#
# First create an app in Gotify UI at http://localhost:8888
# and copy the app token.

set -euo pipefail

GOTIFY_URL="${GOTIFY_URL:-http://localhost:8888}"
APP_TOKEN="${1:?Usage: $0 <APP_TOKEN>}"

send_msg() {
    local title="$1"
    local message="$2"
    local priority="${3:-4}"

    curl -s -X POST "${GOTIFY_URL}/message?token=${APP_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{\"title\": \"${title}\", \"message\": \"${message}\", \"priority\": ${priority}}" \
        | python3 -m json.tool
    echo "---"
}

echo "Sending test messages to ${GOTIFY_URL}..."
send_msg "Backup Complete" "Nightly backup finished successfully at $(date)" 4
sleep 1
send_msg "Disk Warning" "Disk usage at 85% on /dev/sda1" 7
sleep 1
send_msg "Service Down" "**nginx** is not responding on port 443" 9
sleep 1
send_msg "Update Available" "Home Assistant 2025.7.2 is available" 2
sleep 1
send_msg "Temperature Alert" "Server room temperature is 32°C" 8

echo ""
echo "Done! Sent 5 test messages with varying priorities."
