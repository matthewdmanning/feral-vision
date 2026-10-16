#!/bin/bash

# Define an array of sensitive files or wildcard patterns
SECRET_PATTERNS=(
    ".env.local*"
    "*.pem"
    "*.key"
    "secrets.json"
    "read_blocker.sh"
    "settings.json"
)

input=$(cat)

tool_name=$(echo "$input" | jq -r '.tool_name // empty')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')
command_str=$(echo "$input" | jq -r '.tool_input.command // empty')

# 1. Check direct file-reading tools against array patterns
if [[ -n "$file_path" ]]; then
    for pattern in "${SECRET_PATTERNS[@]}"; do
        # Use bash pattern matching (glob)
        if [[ "$file_path" == $pattern || "$file_path" == */$pattern ]]; then
            echo "Access denied: Reading or modifying $file_path matches protected pattern '$pattern'." >&2
            exit 2
        fi
    done
fi

# 2. Check Bash or PowerShell execution attempts against array patterns
if [[ "$tool_name" == "Bash" ]] && [[ -n "$command_str" ]]; then
    for pattern in "${SECRET_PATTERNS[@]}"; do
        # Convert simple wildcards to a regex-friendly form if needed, or check exact substring
        # Here we check if the command contains common read tools/cmdlets alongside the pattern name
        CLEAN_PATTERN="${pattern//\*/.*}" # Convert glob '*' to regex '.*'

        # Check Unix read utilities
        if echo "$command_str" | grep -qE "(cat|less|more|head|tail|grep|awk|sed|cp|scp|mv|nano|vim|vi|base64).*\b$CLEAN_PATTERN\b"; then
            echo "Access denied: Executing shell commands on pattern '$pattern' is prohibited." >&2
            exit 2
        fi

        # Check PowerShell read utilities
        if echo "$command_str" | grep -qE "(powershell|pwsh|Get-Content|gc|type|Copy-Item|Move-Item|Select-String)"; then
            if echo "$command_str" | grep -qE "\b$CLEAN_PATTERN\b"; then
                echo "Access denied: Executing PowerShell operations on pattern '$pattern' is prohibited." >&2
                exit 2
            fi
        fi
    done
fi

exit 0
