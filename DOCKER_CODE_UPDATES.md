# Docker Code Updates Guide

**Issue**: Modified Python files (like `search_urls.py`) not taking effect in Docker worker

**Root Cause**: Docker containers run with code copied during build, not live files

---

## Quick Fix (Recommended)

When you modify **any Python file**, rebuild and restart the worker:

```bash
# Rebuild container with updated code
docker-compose build celery_worker

# Restart with new image
docker-compose down celery_worker
docker-compose up -d celery_worker
```

**Important**: Use `down` + `up`, NOT just `restart`:
```bash
# ❌ WRONG - Doesn't reload code changes
docker-compose restart celery_worker

# ✅ CORRECT - Recreates container with new code
docker-compose down celery_worker && docker-compose up -d celery_worker
```

---

## Why This Happens

### Dockerfile COPY Command

```dockerfile
# Dockerfile (line 13)
COPY . .
```

This copies **all files** from your host into the container **at build time**:

```
Build Time (docker-compose build):
  Host Files → Container Image

  /app/scraper/search_urls.py    [OLD CODE]
                ↓
  Container: /app/scraper/search_urls.py [FROZEN]
```

After this, the container has a **snapshot** of your code. Changes to host files don't affect the running container.

### Container Lifecycle

```
1. Build Image:        docker-compose build
   └─> Copies code into image

2. Create Container:   docker-compose up
   └─> Runs code from image (not from host)

3. Modify Code:        Edit search_urls.py
   └─> Container still has OLD code!

4. Rebuild Required:   docker-compose build
   └─> Updates image with NEW code
```

---

## Solution Options

### Option 1: Rebuild + Restart (Current Approach)

**When to use**: Production deployments, after code changes

**Pros**:
- Clean, deterministic builds
- Same code everywhere
- Docker best practices

**Cons**:
- Slower iteration (rebuild takes time)
- Manual process

**Commands**:
```bash
# Full rebuild and restart
docker-compose build celery_worker
docker-compose down celery_worker
docker-compose up -d celery_worker

# Or in one line
docker-compose build celery_worker && docker-compose down celery_worker && docker-compose up -d celery_worker
```

---

### Option 2: Volume Mounting (Development Mode)

**When to use**: Active development, frequent code changes

**How it works**: Mount host directory as volume, code changes take effect immediately

#### Step 1: Modify `docker-compose.yml`

```yaml
# docker-compose.yml
services:
  celery_worker:
    build: .
    # Add volumes to mount live code
    volumes:
      - ./scraper:/app/scraper:ro          # Mount scraper directory (read-only)
      - ./workers:/app/workers:ro          # Mount workers directory (read-only)
      - ./db:/app/db:ro                    # Mount db directory (read-only)
      # Don't mount venv or cache directories
    command: celery -A workers.celery_app worker --loglevel=info
    depends_on:
      - redis
      - postgres
    env_file:
      - .env
    environment:
      - PYTHONPATH=/app
      - PYTHONUNBUFFERED=1
```

**Key points**:
- `:ro` = read-only (container can't modify host files)
- Only mount directories you're actively changing
- Don't mount `.venv`, `__pycache__`, or binary directories

#### Step 2: Restart Container (No Rebuild Needed)

```bash
# After modifying search_urls.py, just restart:
docker-compose restart celery_worker
```

Changes take effect **immediately**!

**Pros**:
- Instant code updates (no rebuild)
- Fast iteration during development
- Edit code, restart, test

**Cons**:
- Slightly different from production (production uses COPY)
- Need to be careful with file permissions
- Slower runtime (slight overhead from volume mounting)

---

### Option 3: Configuration File Strategy

**When to use**: Only search URLs change frequently

**How it works**: Load search URLs from external file, not Python code

#### Step 1: Create JSON Config

```bash
# Create config file (outside container)
touch search_config.json
```

```json
{
  "search_urls": [
    {
      "url": "https://example.com/listing/?...",
      "enabled": true,
      "description": "Guildford - 3+ beds, max £400k"
    },
    {
      "url": "https://example.com/listing/?...",
      "enabled": false,
      "description": "Stevenage"
    }
  ],
  "max_pages": 50
}
```

#### Step 2: Mount Config as Volume

```yaml
# docker-compose.yml
services:
  celery_worker:
    volumes:
      - ./search_config.json:/app/search_config.json:ro
```

#### Step 3: Load Config in Code

```python
# scraper/search_urls.py
import json
import os

# Load from JSON file
config_path = os.path.join(os.path.dirname(__file__), '../search_config.json')

try:
    with open(config_path, 'r') as f:
        config = json.load(f)
        SEARCH_URLS = config['search_urls']
        MAX_PAGES = config.get('max_pages', 50)
except FileNotFoundError:
    # Fallback to hardcoded values
    SEARCH_URLS = [
        # ... existing URLs
    ]
    MAX_PAGES = 50
```

#### Step 4: Update Config Without Rebuild

```bash
# Edit search_config.json
nano search_config.json

# Just restart (no rebuild!)
docker-compose restart celery_worker
```

**Pros**:
- Update URLs without rebuilding
- Clean separation of code and config
- Can version control separately

**Cons**:
- Adds complexity
- Two files to maintain
- Need error handling for missing config

---

## Recommended Workflow

### Development Phase

Use **Volume Mounting** for fast iteration:

```yaml
# docker-compose.dev.yml
services:
  celery_worker:
    volumes:
      - ./scraper:/app/scraper:ro
      - ./workers:/app/workers:ro
      - ./db:/app/db:ro
```

```bash
# Development workflow
docker-compose -f docker-compose.dev.yml up -d celery_worker

# Edit code...
# Edit search_urls.py...

# Quick restart (no rebuild)
docker-compose -f docker-compose.dev.yml restart celery_worker
```

### Production Deployment

Use **Rebuild + Restart** for clean, deterministic builds:

```bash
# Production workflow
docker-compose build celery_worker
docker-compose down celery_worker
docker-compose up -d celery_worker
```

---

## Common Mistakes

### Mistake 1: Using `restart` Instead of `down` + `up`

```bash
# ❌ WRONG - Doesn't reload rebuilt image
docker-compose build celery_worker
docker-compose restart celery_worker

# ✅ CORRECT - Recreates container from new image
docker-compose build celery_worker
docker-compose down celery_worker
docker-compose up -d celery_worker
```

**Why**: `restart` keeps the same container, `down` + `up` creates a new one from the updated image.

### Mistake 2: Forgetting to Rebuild

```bash
# Edit search_urls.py
nano scraper/search_urls.py

# ❌ WRONG - Old code still in container
docker-compose restart celery_worker

# ✅ CORRECT - Rebuild first
docker-compose build celery_worker
docker-compose down celery_worker && docker-compose up -d celery_worker
```

### Mistake 3: Modifying `.env` and Using `restart`

```bash
# Edit .env
nano .env

# ❌ WRONG - Environment variables not reloaded
docker-compose restart celery_worker

# ✅ CORRECT - Recreate container
docker-compose down celery_worker
docker-compose up -d celery_worker
```

---

## Verification Commands

### Check If Code Updated

```bash
# View code inside container
docker exec worker cat /app/scraper/search_urls.py

# Compare with host file
cat scraper/search_urls.py

# Should match if rebuild was successful
```

### Check Container Creation Time

```bash
# Check when container was created
docker ps -a --filter name=worker --format "table {{.CreatedAt}}\t{{.Names}}"
```

If created time is **before** your code changes, container needs to be recreated.

### Check Image Build Time

```bash
# Check when image was built
docker images movepaser-celery_worker --format "table {{.CreatedAt}}\t{{.Repository}}"
```

If build time is **before** your code changes, image needs to be rebuilt.

---

## Automation Scripts

### Auto-Rebuild Script

Create `rebuild_worker.sh`:

```bash
#!/bin/bash
set -e

echo "Rebuilding worker with latest code..."
docker-compose build celery_worker

echo "Restarting worker..."
docker-compose down celery_worker
docker-compose up -d celery_worker

echo "Checking logs..."
docker logs worker --tail 20

echo "Worker restarted successfully!"
```

```bash
# Make executable
chmod +x rebuild_worker.sh

# Use it
./rebuild_worker.sh
```

### Watch and Rebuild (Advanced)

Install file watcher:

```bash
pip install watchdog
```

Create `watch_and_rebuild.py`:

```python
import subprocess
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class CodeChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('.py'):
            print(f"Detected change: {event.src_path}")
            print("Rebuilding worker...")
            subprocess.run(['docker-compose', 'build', 'celery_worker'])
            subprocess.run(['docker-compose', 'down', 'celery_worker'])
            subprocess.run(['docker-compose', 'up', '-d', 'celery_worker'])
            print("Worker restarted!")

if __name__ == "__main__":
    event_handler = CodeChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path='./scraper', recursive=True)
    observer.schedule(event_handler, path='./workers', recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
```

```bash
# Run watcher
python watch_and_rebuild.py
```

Auto-rebuilds on any `.py` file change!

---

## Best Practices

### 1. Clear Workflow Documentation

Add to README.md:

```markdown
## Updating Code

After modifying Python files:
1. Rebuild: `docker-compose build celery_worker`
2. Restart: `docker-compose down celery_worker && docker-compose up -d celery_worker`
3. Verify: `docker logs worker --tail 50`
```

### 2. Git Hooks

Create `.git/hooks/post-merge`:

```bash
#!/bin/bash
echo "Code updated, remember to rebuild Docker containers!"
echo "Run: docker-compose build celery_worker"
```

### 3. Version Tagging

Tag your images:

```yaml
# docker-compose.yml
services:
  celery_worker:
    image: worker:${VERSION:-latest}
    build: .
```

```bash
# Build with version
VERSION=1.2.3 docker-compose build celery_worker
VERSION=1.2.3 docker-compose up -d celery_worker
```

### 4. Development vs Production Configs

```
docker-compose.yml          # Production (COPY files)
docker-compose.dev.yml      # Development (volume mounts)
```

```bash
# Development
docker-compose -f docker-compose.dev.yml up -d

# Production
docker-compose up -d
```

---

## Summary

| Method | Use Case | Rebuild? | Restart Type | Speed |
|--------|----------|----------|--------------|-------|
| Rebuild + Restart | Production | Yes | `down` + `up` | Slow |
| Volume Mounting | Development | No | `restart` | Fast |
| Config File | URL changes only | No | `restart` | Fast |

**Recommendation for your use case** (changing `search_urls.py`):

**Quick Fix** (works now):
```bash
docker-compose build celery_worker && \
docker-compose down celery_worker && \
docker-compose up -d celery_worker
```

**Long-term Fix** (easier workflow):
- Add volume mounting for development in `docker-compose.dev.yml`
- Or use configuration file approach for search URLs

---

## Troubleshooting

### Issue: "Code still old after rebuild"

**Check**:
```bash
# 1. Verify build completed
docker images | grep celery_worker

# 2. Verify container is using new image
docker ps -a | grep worker

# 3. Check code in container
docker exec worker head -20 /app/scraper/search_urls.py
```

**Solution**: Make sure you used `down` + `up`, not just `restart`

### Issue: "Changes work locally but not in Docker"

**Cause**: Forgot to rebuild container

**Solution**: Always rebuild after code changes (unless using volumes)

---

**End of Guide**
