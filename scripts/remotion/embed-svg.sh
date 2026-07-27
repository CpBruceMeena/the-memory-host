#!/bin/bash
# Embed SVG diagram as base64 data URI directly into aws_flow.md
# This makes the diagram render in PyCharm, VS Code, GitHub, and anywhere the markdown is viewed.

SVG_PATH="scripts/remotion/out/diagram.svg"
MD_FILE="aws_flow.md"

# Base64 encode the SVG (no line breaks)
B64=$(base64 -i "$SVG_PATH" | tr -d '\n')

DATA_URI="data:image/svg+xml;base64,${B64}"

# Create temp file with the replacement
awk -v uri="$DATA_URI" '
/^!\[AWS Architecture Diagram\]\(/ {
    if (index($0, "data:image") == 0) {
        print "![AWS Architecture Diagram](" uri ")"
    } else {
        print $0
    }
    next
}
{ print }
' "$MD_FILE" > "${MD_FILE}.tmp"

mv "${MD_FILE}.tmp" "$MD_FILE"
echo "✅ SVG embedded as data URI in $MD_FILE"
echo "   Image size: $(echo -n "$DATA_URI" | wc -c) bytes (base64)"
