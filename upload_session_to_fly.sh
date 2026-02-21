#!/bin/bash
# Upload LinkedIn session to Fly.io persistent volume

echo "Uploading LinkedIn browser session to Fly.io..."

# Create a tarball of the session
cd profileAnalyst
tar -czf linkedin_session.tar.gz linkedin_browser_data/

# Upload to Fly.io
fly ssh console -C "mkdir -p /data"
cat linkedin_session.tar.gz | fly ssh console -C "cat > /tmp/session.tar.gz && cd /data && tar -xzf /tmp/session.tar.gz && rm /tmp/session.tar.gz"

# Cleanup
rm linkedin_session.tar.gz

echo "Session uploaded successfully!"
