#!/bin/bash
# Link SVG diagram as a relative file path in aws_flow.md
# A relative path works reliably in GitHub, VS Code, PyCharm, and most markdown viewers
# without the base64 encoding issues that plague very large SVGs (>40K chars).

SVG_PATH="scripts/remotion/out/diagram.svg"
MD_FILE="aws_flow.md"

# Replace any data URI or stale path with the correct relative path
sed -i '' 's|^!\[AWS Architecture Diagram\](.*|![AWS Architecture Diagram]('"$SVG_PATH"')|' "$MD_FILE"

echo "✅ SVG linked as relative path in $MD_FILE"
echo "   Path: $SVG_PATH"
