Based on my research, I can help you understand the common issues with Claude Code and FastAPI development where code updates don't show up properly. This is a frequent problem with multiple potential causes and solutions.

# FastAPI Development Server Update Issues: Complete Solution Guide

## The Core Problem

When using Claude Code with FastAPI and uvicorn, you're experiencing a common development issue where code changes aren't reflected despite the server appearing to restart. This typically manifests as:

- Code updates not showing up in the browser
- Having to switch between ports (8001, 8002, etc.)
- Server appearing to restart but serving old content
- Browser showing cached or outdated responses

## Root Causes and Solutions

### 1. **Browser Caching Issues**

**Problem**: Your browser is serving cached static files instead of fetching fresh content from the server.[1][2]

**Solutions**:
- **Hard refresh**: Use `Ctrl+F5` (Windows/Linux) or `Cmd+Shift+R` (Mac) to force browser to reload all assets
- **Disable cache during development**: Open browser developer tools → Network tab → check "Disable cache"
- **Use incognito/private browsing** for testing to avoid cache issues

### 2. **Uvicorn Auto-Reload Problems**

**Problem**: The uvicorn server's auto-reload functionality gets stuck or doesn't properly detect file changes.[3][4]

**Solutions**:

**Force proper reload**:
```bash
# Kill any existing processes first
kill -9 $(lsof -t -i:8000)  # Linux/Mac
# Or use Task Manager on Windows

# Start with explicit reload settings
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**For better file watching**:
```bash
# Install uvicorn with standard dependencies for better file watching
pip install uvicorn[standard]

# Use with specific file types to watch
uvicorn main:app --reload --reload-include '*.py' --reload-include '*.html'
```

### 3. **Port Conflicts and Stuck Processes**

**Problem**: Previous server processes remain running even after apparent shutdown, causing port conflicts.[5][6]

**Solutions**:

**Linux/Mac**:
```bash
# Find and kill process on specific port
sudo lsof -i :8000
kill -9 $(lsof -t -i:8000)

# Or use fuser
sudo fuser -k 8000/tcp
```

**Windows**:
```bash
# Find process using port
netstat -ano | findstr :8000

# Kill process by PID
taskkill /F /PID <PID_NUMBER>
```

### 4. **FastAPI Static File Caching**

**Problem**: FastAPI's StaticFiles automatically implements HTTP caching which prevents updates from showing.[1]

**Solution** - Disable caching during development:
```python
from fastapi.staticfiles import StaticFiles

# Monkey patch to disable caching
StaticFiles.is_not_modified = lambda self, *args, **kwargs: False

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
```

### 5. **IDE Integration Issues**

**Problem**: When running FastAPI through IDE (like PyCharm) instead of terminal, auto-reload can get stuck.[3]

**Solution**: Always use terminal for development:
```bash
# Don't use IDE's FastAPI launcher
# Instead, run directly in terminal:
uvicorn main:app --reload
```

### 6. **Virtual Environment and Path Issues**

**Problem**: File watching might not work properly across different path configurations.

**Solution**:
```bash
# Ensure you're in the correct directory
cd /path/to/your/project

# Activate virtual environment first
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Then start server
uvicorn main:app --reload
```

### 7. **Claude Code Specific Issues**

**Problem**: Claude Code might not properly handle server lifecycle or file watching.[7]

**Solutions**:
- **Manual server management**: Always manually start/stop servers rather than relying on Claude Code's automation
- **Use separate terminals**: Run the FastAPI server in a separate terminal from Claude Code
- **Explicit port management**: Manually specify and manage ports

## Best Practices for Development

### 1. **Clean Development Workflow**
```bash
# 1. Stop any existing servers
kill -9 $(lsof -t -i:8000) 2>/dev/null || true

# 2. Clear browser cache or use incognito mode

# 3. Start fresh server
uvicorn main:app --reload --host 0.0.0.0 --port 8000 --log-level debug
```

### 2. **Environment Configuration**
```python
# main.py - Add development settings
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Disable static file caching in development
if os.getenv("DEBUG") or os.getenv("ENVIRONMENT") == "development":
    StaticFiles.is_not_modified = lambda self, *args, **kwargs: False

app.mount("/static", StaticFiles(directory="static"), name="static")
```

### 3. **Hot Reload for Frontend Assets**
For HTML/CSS/JS changes, use additional file watching:
```bash
uvicorn main:app --reload --reload-include '*.py' --reload-include '*.html' --reload-include '*.css' --reload-include '*.js'
```

## Debugging Steps

When changes don't show up:

1. **Check server logs** - Look for reload messages in terminal
2. **Verify file saves** - Ensure auto-save is enabled in your editor
3. **Test with hard refresh** - Use `Ctrl+F5` to bypass browser cache
4. **Check process list** - Verify only one server instance is running
5. **Try different port** - Use `--port 8001` to test with fresh port
6. **Restart completely** - Kill all Python processes and restart

The key is understanding that this is typically a combination of browser caching, process management, and file watching issues rather than a problem with your code itself. By following these solutions systematically, you should be able to achieve reliable hot-reloading during development.[4][2][3]
