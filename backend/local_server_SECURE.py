# backend/local_server_SECURE.py
"""
Secure Local Development Server for Sea Level Monitoring System
Fixed security vulnerabilities and improved error handling
"""

from fastapi import FastAPI, HTTPException, Query, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer
import json
import pandas as pd
from datetime import datetime, timedelta
import logging
import os
import sys
import threading
import subprocess
import time
import webbrowser
import shutil
from pathlib import Path
from typing import Optional
import ipaddress
from urllib.parse import urlparse

# Add shared modules to path
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir / "shared"))

# Import enhanced security module
try:
    from security_ENHANCED import (
        secure_log, validate_station_name, validate_date_format,
        sanitize_file_path, create_security_headers, validate_ip_address
    )
    SECURITY_ENHANCED = True
except ImportError:
    from security import secure_log
    SECURITY_ENHANCED = False
    print("Warning: Enhanced security module not available")

# Import Lambda handlers with better error handling
LAMBDA_HANDLERS_AVAILABLE = False
lambda_import_errors = []

try:
    # Import individual handlers
    sys.path.insert(0, str(current_dir / "lambdas" / "get_stations"))
    from lambdas.get_stations.main import handler as get_stations_handler
    
    sys.path.insert(0, str(current_dir / "lambdas" / "get_data"))
    from lambdas.get_data.main import handler as get_data_handler
    
    sys.path.insert(0, str(current_dir / "lambdas" / "get_live_data"))
    from lambdas.get_live_data.main import handler as get_live_data_handler
    
    sys.path.insert(0, str(current_dir / "lambdas" / "get_yesterday_data"))
    from lambdas.get_yesterday_data.main import handler as get_yesterday_data_handler
    
    sys.path.insert(0, str(current_dir / "lambdas" / "get_predictions"))
    from lambdas.get_predictions.main import handler as get_predictions_handler
    
    sys.path.insert(0, str(current_dir / "lambdas" / "get_station_map"))
    from lambdas.get_station_map.main import handler as get_station_map_handler
    
    sys.path.insert(0, str(current_dir / "lambdas" / "get_sea_forecast"))
    from lambdas.get_sea_forecast.main import lambda_handler as get_sea_forecast_handler
    
    LAMBDA_HANDLERS_AVAILABLE = True
    print("✅ Lambda handlers loaded successfully")
    
except ImportError as e:
    lambda_import_errors.append(str(e))
    print(f"⚠️  Warning: Lambda handlers not available: {e}")

# Configure logging with security considerations
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Security configuration
security = HTTPBearer(auto_error=False)

# Rate limiting storage (in production, use Redis)
rate_limit_storage = {}

def check_rate_limit(client_ip: str, limit: int = 100, window: int = 3600) -> bool:
    """
    Simple rate limiting check
    
    Args:
        client_ip: Client IP address
        limit: Request limit per window
        window: Time window in seconds
    
    Returns:
        True if within limit, False otherwise
    """
    now = time.time()
    
    # Clean old entries
    rate_limit_storage[client_ip] = [
        timestamp for timestamp in rate_limit_storage.get(client_ip, [])
        if now - timestamp < window
    ]
    
    # Check limit
    if len(rate_limit_storage.get(client_ip, [])) >= limit:
        return False
    
    # Add current request
    if client_ip not in rate_limit_storage:
        rate_limit_storage[client_ip] = []
    rate_limit_storage[client_ip].append(now)
    
    return True

def get_client_ip(request: Request) -> str:
    """
    Safely extract client IP address
    
    Args:
        request: FastAPI request object
    
    Returns:
        Client IP address
    """
    # Check for forwarded headers (be careful with these in production)
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        # Take the first IP (client IP)
        client_ip = forwarded_for.split(',')[0].strip()
        if validate_ip_address(client_ip):
            return client_ip
    
    # Fallback to direct connection
    return str(request.client.host) if request.client else 'unknown'

# Create FastAPI app with security headers
app = FastAPI(
    title="Sea Level Monitoring API",
    description="Secure local development server for Sea Level Monitoring System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enhanced CORS configuration
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001"
]

# Only add custom hosts in development
if os.getenv('ENV') != 'production':
    allowed_origins.extend([
        "http://sea-level-dash-local:3000",
        "http://sea-level-dash-local:8001"
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Security middleware
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """Add security headers and rate limiting"""
    
    # Get client IP
    client_ip = get_client_ip(request)
    
    # Rate limiting
    if not check_rate_limit(client_ip):
        secure_log(logger, 'warning', 'Rate limit exceeded', client_ip=client_ip)
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    # Process request
    response = await call_next(request)
    
    # Add security headers
    if SECURITY_ENHANCED:
        security_headers = create_security_headers()
        for header, value in security_headers.items():
            response.headers[header] = value
    
    return response

# Mount static files securely
frontend_assets_path = project_root / "frontend" / "public" / "assets"
if frontend_assets_path.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_assets_path)), name="assets")

# Global variables for server management
frontend_process = None
frontend_thread = None

def lambda_response_to_fastapi(lambda_response):
    """Convert Lambda response format to FastAPI response"""
    try:
        status_code = lambda_response.get("statusCode", 200)
        body = lambda_response.get("body", "{}")
        
        if isinstance(body, str):
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return {"data": body}
        return body
    except Exception as e:
        secure_log(logger, 'error', 'Error converting lambda response', error=str(e))
        return {"error": "Internal server error"}

def find_executable(name: str, paths: list = None) -> Optional[str]:
    """
    Safely find executable without shell injection
    
    Args:
        name: Executable name
        paths: Optional list of paths to search
    
    Returns:
        Path to executable or None
    """
    # Use shutil.which for safe executable finding
    executable = shutil.which(name)
    if executable:
        return executable
    
    # Check additional paths if provided
    if paths:
        for path in paths:
            full_path = Path(path) / name
            if full_path.exists() and os.access(full_path, os.X_OK):
                return str(full_path)
    
    return None

def safe_subprocess_run(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    """
    Safely run subprocess without shell injection
    
    Args:
        cmd: Command as list (not string)
        **kwargs: Additional subprocess arguments
    
    Returns:
        CompletedProcess result
    """
    # Ensure shell=False for security
    kwargs['shell'] = False
    
    # Set secure defaults
    kwargs.setdefault('capture_output', True)
    kwargs.setdefault('text', True)
    kwargs.setdefault('timeout', 30)
    
    # On Windows, hide console window
    if os.name == 'nt':
        kwargs.setdefault('creationflags', subprocess.CREATE_NO_WINDOW)
    
    return subprocess.run(cmd, **kwargs)

def check_frontend_dependencies():
    """Check if frontend dependencies are available - secure version"""
    try:
        frontend_dir = project_root / "frontend"
        
        if not frontend_dir.exists():
            logger.warning(f"Frontend directory not found: {frontend_dir}")
            return False
        
        # Check if package.json exists
        package_json = frontend_dir / "package.json"
        if not package_json.exists():
            logger.warning(f"Frontend package.json not found: {package_json}")
            return False
        
        # Find Node.js executable safely
        node_exe = find_executable('node')
        if not node_exe:
            logger.warning("Node.js executable not found")
            return False
        
        # Check if Node.js works
        try:
            result = safe_subprocess_run([node_exe, '--version'])
            if result.returncode != 0:
                logger.warning(f"Node.js check failed: {result.stderr}")
                return False
            logger.info(f"✅ Node.js found: {result.stdout.strip()}")
        except Exception as e:
            logger.warning(f"Node.js check error: {e}")
            return False
        
        # Find npm executable safely
        npm_exe = find_executable('npm')
        if not npm_exe:
            logger.warning("npm executable not found")
            return False
        
        # Check if npm works
        try:
            result = safe_subprocess_run([npm_exe, '--version'])
            if result.returncode != 0:
                logger.warning(f"npm check failed: {result.stderr}")
                return False
            logger.info(f"✅ npm found: {result.stdout.strip()}")
        except Exception as e:
            logger.warning(f"npm check error: {e}")
            return False
        
        logger.info("✅ Frontend dependencies available")
        return True
        
    except Exception as e:
        logger.error(f"Error checking frontend dependencies: {e}")
        return False

# API Routes with enhanced security
@app.get("/")
async def root(request: Request):
    """Root endpoint with API information"""
    client_ip = get_client_ip(request)
    secure_log(logger, 'info', 'Root endpoint accessed', client_ip=client_ip)
    
    return {
        "message": "Sea Level Monitoring API",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "lambda_handlers": LAMBDA_HANDLERS_AVAILABLE,
        "security_enhanced": SECURITY_ENHANCED,
        "endpoints": {
            "health": "/health",
            "stations": "/stations",
            "data": "/data",
            "live": "/live",
            "predictions": "/predictions",
            "map": "/stations/map",
            "docs": "/docs"
        }
    }

@app.get("/health")
async def health_check(request: Request):
    """Health check endpoint"""
    client_ip = get_client_ip(request)
    
    # Test database connection
    db_status = "unknown"
    try:
        from shared.database import db_manager
        if db_manager and db_manager.health_check():
            db_status = "connected"
        else:
            db_status = "disconnected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    health_data = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": db_status,
        "lambda_handlers": LAMBDA_HANDLERS_AVAILABLE,
        "security_enhanced": SECURITY_ENHANCED,
        "frontend": frontend_process is not None and frontend_process.poll() is None,
        "node_available": find_executable('node') is not None,
        "npm_available": find_executable('npm') is not None
    }
    
    secure_log(logger, 'info', 'Health check performed', 
               client_ip=client_ip, status=health_data["status"])
    
    return health_data

@app.get("/stations")
async def get_stations(request: Request):
    """Get all available stations"""
    client_ip = get_client_ip(request)
    
    if not LAMBDA_HANDLERS_AVAILABLE:
        # Return demo data if handlers not available
        return {
            "stations": ["All Stations", "Demo Station 1", "Demo Station 2", "Demo Station 3"],
            "note": "Demo data - Lambda handlers not available"
        }
    
    try:
        event = {}
        response = get_stations_handler(event, None)
        result = lambda_response_to_fastapi(response)
        
        secure_log(logger, 'info', 'Stations data requested', 
                   client_ip=client_ip, station_count=len(result.get('stations', [])))
        
        return result
    except Exception as e:
        secure_log(logger, 'error', 'Error in get_stations', 
                   client_ip=client_ip, error=str(e))
        # Return demo data on error
        return {
            "stations": ["All Stations", "Error Station"],
            "error": "Service temporarily unavailable"
        }

@app.get("/data")
async def get_data(
    request: Request,
    station: Optional[str] = Query(None, description="Station name"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    data_source: str = Query("default", description="Data source (default|tides)"),
    show_anomalies: bool = Query(False, description="Include anomaly detection")
):
    """Get data with optional filters and input validation"""
    client_ip = get_client_ip(request)
    
    # Input validation
    if SECURITY_ENHANCED:
        if station and not validate_station_name(station):
            secure_log(logger, 'warning', 'Invalid station name provided', 
                       client_ip=client_ip, station=station)
            raise HTTPException(status_code=400, detail="Invalid station name")
        
        if start_date and not validate_date_format(start_date):
            secure_log(logger, 'warning', 'Invalid start date format', 
                       client_ip=client_ip, start_date=start_date)
            raise HTTPException(status_code=400, detail="Invalid start date format")
        
        if end_date and not validate_date_format(end_date):
            secure_log(logger, 'warning', 'Invalid end date format', 
                       client_ip=client_ip, end_date=end_date)
            raise HTTPException(status_code=400, detail="Invalid end date format")
    
    if not LAMBDA_HANDLERS_AVAILABLE:
        return {
            "message": "Demo data - Lambda handlers not available",
            "parameters": {
                "station": station,
                "start_date": start_date,
                "end_date": end_date,
                "data_source": data_source,
                "show_anomalies": show_anomalies
            }
        }
    
    try:
        event = {
            "queryStringParameters": {
                "station": station,
                "start_date": start_date,
                "end_date": end_date,
                "data_source": data_source,
                "show_anomalies": str(show_anomalies).lower()
            }
        }
        response = get_data_handler(event, None)
        result = lambda_response_to_fastapi(response)
        
        secure_log(logger, 'info', 'Data requested', 
                   client_ip=client_ip, station=station, 
                   start_date=start_date, end_date=end_date)
        
        return result
    except Exception as e:
        secure_log(logger, 'error', 'Error in get_data', 
                   client_ip=client_ip, error=str(e))
        raise HTTPException(status_code=500, detail="Service temporarily unavailable")

@app.get("/assets/{filename}")
async def get_asset(filename: str, request: Request):
    """Serve static assets with path validation"""
    client_ip = get_client_ip(request)
    
    # Validate and sanitize filename
    if SECURITY_ENHANCED:
        safe_filename = sanitize_file_path(filename, allowed_extensions=['.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico'])
        if not safe_filename:
            secure_log(logger, 'warning', 'Invalid asset filename', 
                       client_ip=client_ip, filename=filename)
            raise HTTPException(status_code=400, detail="Invalid filename")
        filename = safe_filename
    
    asset_path = project_root / "frontend" / "public" / "assets" / filename
    
    # Additional security check - ensure path is within assets directory
    try:
        asset_path = asset_path.resolve()
        assets_dir = (project_root / "frontend" / "public" / "assets").resolve()
        
        if not str(asset_path).startswith(str(assets_dir)):
            secure_log(logger, 'warning', 'Path traversal attempt detected', 
                       client_ip=client_ip, requested_path=str(asset_path))
            raise HTTPException(status_code=403, detail="Access denied")
        
        if asset_path.exists() and asset_path.is_file():
            return FileResponse(asset_path)
        else:
            raise HTTPException(status_code=404, detail="Asset not found")
            
    except Exception as e:
        secure_log(logger, 'error', 'Error serving asset', 
                   client_ip=client_ip, filename=filename, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/mapframe")
async def get_mapframe(request: Request, end_date: str = None):
    """Serve GovMap iframe with input validation"""
    client_ip = get_client_ip(request)
    
    # Validate end_date if provided
    if SECURITY_ENHANCED and end_date and not validate_date_format(end_date):
        secure_log(logger, 'warning', 'Invalid end_date in mapframe request', 
                   client_ip=client_ip, end_date=end_date)
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    secure_log(logger, 'info', 'Mapframe requested', 
               client_ip=client_ip, end_date=end_date or 'None')
    
    # Read the HTML file and serve it
    mapframe_path = current_dir / "mapframe.html"
    if mapframe_path.exists():
        try:
            with open(mapframe_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            return HTMLResponse(content=html_content)
        except Exception as e:
            secure_log(logger, 'error', 'Error reading mapframe HTML', 
                       client_ip=client_ip, error=str(e))
            raise HTTPException(status_code=500, detail="Internal server error")
    else:
        raise HTTPException(status_code=404, detail="Mapframe HTML not found")

def main():
    """Main function to run the secure development server"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Sea Level Monitoring Secure Development Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8001, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--no-frontend", action="store_true", help="Don't check for frontend")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("🌊 Sea Level Monitoring System - Secure Development Server")
    print("=" * 70)
    print(f"🚀 Backend API: http://{args.host}:{args.port}")
    print(f"📚 API Docs: http://{args.host}:{args.port}/docs")
    print(f"🔒 Security Enhanced: {SECURITY_ENHANCED}")
    
    # Lambda handlers status
    if LAMBDA_HANDLERS_AVAILABLE:
        print("✅ Lambda handlers: Available")
    else:
        print("⚠️  Lambda handlers: Not available (using demo data)")
        if lambda_import_errors:
            print(f"   Errors: {lambda_import_errors[0]}")
    
    # Frontend status
    if not args.no_frontend:
        if check_frontend_dependencies():
            print("✅ Frontend: Available")
            print("   📱 Frontend URL: http://localhost:3000")
        else:
            print("⚠️  Frontend: Dependencies not available")
    
    print("=" * 70)
    print("💡 Security Features:")
    print("   - Rate limiting enabled")
    print("   - Input validation active")
    print("   - Security headers added")
    print("   - Path traversal protection")
    print("   - Safe subprocess execution")
    print("=" * 70)
    
    try:
        import uvicorn
        uvicorn.run(
            app, 
            host=args.host, 
            port=args.port, 
            reload=args.reload,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
    finally:
        print("👋 Goodbye!")

if __name__ == "__main__":
    main()