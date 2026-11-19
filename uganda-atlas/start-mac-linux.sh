#!/bin/sh
cd "$(dirname "$0")"
(sleep 1; (open http://localhost:8000 || xdg-open http://localhost:8000) 2>/dev/null) &
python3 -m http.server 8000
