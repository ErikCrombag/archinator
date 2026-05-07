#!/bin/sh
cat > /usr/share/nginx/html/env-config.js << EOF
window._env_ = { API_URL: "${VITE_API_URL:-http://localhost:8000}" };
EOF
exec nginx -g 'daemon off;'
