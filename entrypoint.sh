#!/bin/sh
# If a config template exists, substitute ENV variables into a config.js file
if [ -f ./build/config.js.template ]; then
  echo "Generating front-end config from environment variables..."
  envsubst < ./build/config.js.template > ./build/config.js
fi

# Start the Flask server (which uses SocketIO)
exec python server.py