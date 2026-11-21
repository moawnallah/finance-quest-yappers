#!/usr/bin/env bash
# Version the web build's entry files so browsers and Cloudflare load the new
# app right after a deploy. Usage: tool/stamp_web.sh <build/web directory>
set -euo pipefail
dir="${1:?build directory}"
v=$(shasum "$dir/main.dart.js" | cut -c1-10)
sed -i '' "s#src=\"flutter_bootstrap.js\"#src=\"flutter_bootstrap.js?v=$v\"#" "$dir/index.html"
sed -i '' "s#\"mainJsPath\":\"main.dart.js\"#\"mainJsPath\":\"main.dart.js?v=$v\"#" "$dir/flutter_bootstrap.js"
# Icons change rarely but browsers (Safari especially) cache them hard: version them by their own hash.
iv=$(cat "$dir/favicon.png" "$dir/icons/Icon-192.png" | shasum | cut -c1-10)
sed -i '' -e "s#href=\"favicon.png\"#href=\"favicon.png?v=$iv\"#" -e "s#href=\"icons/Icon-192.png\"#href=\"icons/Icon-192.png?v=$iv\"#" \
  -e "s#href=\"manifest.json\"#href=\"manifest.json?v=$iv\"#" "$dir/index.html"
grep -q "flutter_bootstrap.js?v=$v" "$dir/index.html" && grep -q "main.dart.js?v=$v" "$dir/flutter_bootstrap.js"
echo "stamped $v"
