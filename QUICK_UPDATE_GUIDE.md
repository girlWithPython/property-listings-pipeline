# Quick Code Update Guide

**Status**: ✅ Volume mounting is now ACTIVE in docker-compose.yml

---

## New Workflow (Fast! No Rebuild!)

### When You Change Python Code

```bash
# 1. Edit any Python file
nano scraper/search_urls.py    # Change search URLs
nano workers/geocoding.py      # Change worker logic
nano db/database.py            # Change database code

# 2. Just restart (no rebuild needed!)
docker-compose restart celery_worker

# 3. Changes take effect immediately!
```

**Time saved**: ~30 seconds per change (no rebuild!)

---

## Active Volume Mounts

The following directories are **live-mounted**:

```
Host                                Container
----                                ---------
./scraper/   →  (mounted as) →     /app/scraper/   (read-only)
./workers/   →  (mounted as) →     /app/workers/   (read-only)
./db/        →  (mounted as) →     /app/db/        (read-only)
```

**What this means**:
- Changes to these files **immediately** sync to the container
- No rebuild required - just restart the worker
- Container always runs your latest code

---

## Common Use Cases

### Change Search URLs

```bash
# Edit search URLs
nano scraper/search_urls.py

# Add new URL or change enabled status
# Save file

# Restart worker (picks up changes)
docker-compose restart celery_worker

# Done! New URLs active
```

### Change Geocoding Logic

```bash
# Edit geocoding worker
nano workers/geocoding.py

# Make changes, save

# Restart
docker-compose restart celery_worker
```

### Change Database Queries

```bash
# Edit database code
nano db/database.py

# Make changes, save

# Restart
docker-compose restart celery_worker
```

---

## What Still Requires Rebuild?

Only these changes require a rebuild:

### 1. Dependencies Change
```bash
# If you modify requirements.txt
pip install new-package
# Add to requirements.txt

# Then rebuild
docker-compose build celery_worker
docker-compose down celery_worker && docker-compose up -d celery_worker
```

### 2. Dockerfile Changes
```bash
# If you modify Dockerfile
nano Dockerfile

# Then rebuild
docker-compose build celery_worker
docker-compose down celery_worker && docker-compose up -d celery_worker
```

### 3. New Files Added (Outside Mounted Directories)
```bash
# If you add files outside scraper/, workers/, db/
# For example: new root-level Python file

# Then rebuild
docker-compose build celery_worker
docker-compose down celery_worker && docker-compose up -d celery_worker
```

---

## Environment Variables (.env)

`.env` changes still require restart (but no rebuild):

```bash
# Edit .env
nano .env

# Restart (down + up, not just restart)
docker-compose down celery_worker
docker-compose up -d celery_worker
```

**Note**: Must use `down` + `up` (not `restart`) for `.env` changes.

---

## Quick Commands Reference

```bash
# Just restart (code changes in mounted directories)
docker-compose restart celery_worker

# Recreate (for .env changes)
docker-compose down celery_worker && docker-compose up -d celery_worker

# Full rebuild (for Dockerfile or requirements.txt)
docker-compose build celery_worker && docker-compose down celery_worker && docker-compose up -d celery_worker

# Check logs
docker logs rightmove_worker --tail 50 --follow

# Verify mounts
docker inspect rightmove_worker --format='{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}'

# Test code is live
docker exec rightmove_worker cat /app/scraper/search_urls.py
```

---

## Verification

### Check if Volumes Are Mounted

```bash
docker inspect rightmove_worker --format='{{range .Mounts}}{{.Source}} -> {{.Destination}} ({{.Mode}}){{println}}{{end}}'
```

**Expected output**:
```
C:\Users\...\movePaser\scraper -> /app/scraper (ro)
C:\Users\...\movePaser\workers -> /app/workers (ro)
C:\Users\...\movePaser\db -> /app/db (ro)
```

✅ All three directories mounted as read-only (ro)

### Test Live Updates

```bash
# 1. Check current search URLs in container
docker exec rightmove_worker head -20 /app/scraper/search_urls.py

# 2. Edit search_urls.py on host
nano scraper/search_urls.py
# Add a comment at the top: # TEST CHANGE

# 3. Check again in container (should see change immediately)
docker exec rightmove_worker head -20 /app/scraper/search_urls.py

# 4. Restart worker
docker-compose restart celery_worker
```

If you see your changes in step 3, volume mounting is working! ✅

---

## Troubleshooting

### Issue: Changes Not Taking Effect

**Check**:
```bash
# 1. Verify volumes are mounted
docker inspect rightmove_worker | grep Mounts -A 20

# 2. Check file in container
docker exec rightmove_worker cat /app/scraper/search_urls.py

# 3. Compare with host file
cat scraper/search_urls.py

# Should be identical
```

**Solution**: If files don't match, recreate container:
```bash
docker-compose down celery_worker
docker-compose up -d celery_worker
```

### Issue: Permission Errors

**Symptom**: Container can't read mounted files

**Solution**: Files are mounted read-only (`:ro`), which is intentional. Container should only read, not write.

If you need to write from container (rare), change in docker-compose.yml:
```yaml
# Read-write (not recommended)
- ./scraper:/app/scraper

# Read-only (recommended, current setting)
- ./scraper:/app/scraper:ro
```

### Issue: Container Won't Start After Adding Volumes

**Check**:
```bash
# View startup errors
docker logs rightmove_worker
```

**Common causes**:
- File permissions on Windows
- Incorrect path format
- Missing directories

**Solution**: Ensure directories exist:
```bash
ls -la scraper/
ls -la workers/
ls -la db/
```

---

## Example: Updating Search URLs

**Before** (Old workflow - slow):
```bash
# 1. Edit file
nano scraper/search_urls.py

# 2. Rebuild image (30+ seconds)
docker-compose build celery_worker

# 3. Recreate container (10+ seconds)
docker-compose down celery_worker
docker-compose up -d celery_worker

# Total: ~40-50 seconds
```

**After** (New workflow - fast):
```bash
# 1. Edit file
nano scraper/search_urls.py

# 2. Restart (2-3 seconds)
docker-compose restart celery_worker

# Total: ~2-3 seconds ✅
```

**Time saved**: ~45 seconds per change!

---

## Summary

| Change Type | Old Process | New Process | Time Saved |
|-------------|-------------|-------------|------------|
| search_urls.py | Rebuild + restart | Just restart | ~45s |
| workers/*.py | Rebuild + restart | Just restart | ~45s |
| db/*.py | Rebuild + restart | Just restart | ~45s |
| .env | Restart | Restart | 0s |
| requirements.txt | Rebuild + restart | Rebuild + restart | 0s |
| Dockerfile | Rebuild + restart | Rebuild + restart | 0s |

**Development speed**: 95% faster for code changes! 🚀

---

**Status**: ✅ Ready to use!

Try it now:
1. Edit `scraper/search_urls.py`
2. Run `docker-compose restart celery_worker`
3. Changes active!
