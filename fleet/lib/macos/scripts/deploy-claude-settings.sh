#!/bin/bash
# Deploys our org-standard Claude Code managed settings. Managed settings override
# user and project settings, so developers can't loosen these rules.
set -euo pipefail

dir="/Library/Application Support/ClaudeCode"
mkdir -p "$dir"
cat > "$dir/managed-settings.json" <<'JSON'
{
  "forceLoginMethod": "claudeai",
  "permissions": {
    "disableBypassPermissionsMode": "disable",
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)"
    ]
  }
}
JSON
chmod 644 "$dir/managed-settings.json"
echo "Deployed Claude Code managed settings to $dir/managed-settings.json"
