#!/usr/bin/env bash
# Version the web build's entry files so browsers and Cloudflare load the new
# app right after a deploy. Usage: tool/stamp_web.sh <build/web directory>
set -euo pipefail
dir="${1:?build directory}"
v=$(shasum "$dir/main.dart.js" | cut -c1-10)
sed -i '' "s#src=\"flutter_bootstrap.js\"#src=\"flutter_bootstrap.js?v=$v\"#" "$dir/index.html"
sed -i '' "s#\"mainJsPath\":\"main.dart.js\"#\"mainJsPath\":\"main.dart.js?v=$v\"#" "$dir/flutter_bootstrap.js"
grep -q "flutter_bootstrap.js?v=$v" "$dir/index.html" && grep -q "main.dart.js?v=$v" "$dir/flutter_bootstrap.js"
echo "stamped $v"
