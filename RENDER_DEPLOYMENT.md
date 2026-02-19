# Render Deployment Instructions

## Setup Steps for Render:

1. **Connect your GitHub repository** to Render

2. **Configure the service**:
   - **Build Command**: `./build.sh`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Environment**: Python 3
   
3. **Add Environment Variables** in Render Dashboard:
   - `PYTHON_VERSION`: `3.10.16`
   - `PLAYWRIGHT_BROWSERS_PATH`: `/opt/render/.cache`
   - Add all your other environment variables from `.env` file:
     - `OPENAI_API_KEY`
     - `FIREBASE_CREDENTIALS` (your Firebase JSON content)
     - etc.

4. **Deploy!**
   - Render will automatically run `build.sh` which installs Playwright browsers
   - The build process includes `playwright install --with-deps chromium`

## Troubleshooting

If you still get browser errors:
- Ensure `build.sh` is executable: `chmod +x build.sh`
- Check Render logs to see if Playwright installation succeeded
- Verify all system dependencies are installed with `--with-deps` flag

## Alternative: Use render.yaml

If you prefer, you can use the included `render.yaml` file for Infrastructure as Code deployment.
Simply push it to your repo and Render will automatically detect it.
