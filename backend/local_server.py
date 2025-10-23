# backend/local_server.py
"""
Local Development Server for Sea Level Monitoring System
Windows-compatible version with better error handling
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
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
from typing import Optional, List

# Add shared modules to path
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir / "shared"))

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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Sea Level Monitoring API",
    description="Local development server for Sea Level Monitoring System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://sea-level-dash-local:3000",
        "http://sea-level-dash-local:8001",
        "*"  # Allow all origins for development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for assets
frontend_assets_path = project_root / "frontend" / "public" / "assets"
if frontend_assets_path.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_assets_path)), name="assets")

# Server state management class to avoid global variables
class ServerState:
    def __init__(self):
        self.frontend_process = None
        self.frontend_thread = None
        self.auto_start_frontend = False

server_state = ServerState()

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
        logger.error(f"Error converting lambda response: {e}")
        return {"error": "Internal server error"}

def find_node_executable():
    """Find Node.js executable on Windows"""
    # Common Node.js installation paths on Windows
    common_paths = [
        "node",  # If in PATH
        "node.exe",
        r"C:\Program Files\nodejs\node.exe",
        r"C:\Program Files (x86)\nodejs\node.exe",
        os.path.expanduser(r"~\AppData\Roaming\npm\node.exe"),
    ]
    
    for path in common_paths:
        try:
            if shutil.which(path):
                return path
        except:
            continue
    
    return None

def find_npm_executable():
    """Find npm executable on Windows - fixed version"""
    # Try different npm commands with shell=True for Windows
    npm_commands = ["npm", "npm.cmd"]
    
    for cmd in npm_commands:
        try:
            result = subprocess.run(
                [cmd, "--version"], 
                capture_output=True, 
                text=True,
                timeout=10,
                shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            if result.returncode == 0:
                return cmd
        except Exception as e:
            logger.warning(f"Failed to check npm command {cmd}: {e}")
            continue
    
    # Try with full paths
    common_paths = [
        r"C:\Program Files\nodejs\npm.cmd",
        r"C:\Program Files (x86)\nodejs\npm.cmd",
        os.path.expanduser(r"~\AppData\Roaming\npm\npm.cmd"),
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            try:
                result = subprocess.run(
                    [path, "--version"], 
                    capture_output=True, 
                    text=True,
                    timeout=10,
                    shell=False,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                if result.returncode == 0:
                    return path
            except:
                continue
    
    return None

def check_frontend_dependencies():
    """Check if frontend dependencies are available - Windows compatible"""
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
        
        # Find Node.js executable
        node_exe = find_node_executable()
        if not node_exe:
            logger.warning("Node.js executable not found")
            return False
        
        # Check if Node.js works
        try:
            result = subprocess.run(
                [node_exe, "--version"], 
                capture_output=True, 
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            if result.returncode != 0:
                logger.warning(f"Node.js check failed: {result.stderr}")
                return False
            logger.info(f"✅ Node.js found: {result.stdout.strip()}")
        except Exception as e:
            logger.warning(f"Node.js check error: {e}")
            return False
        
        # Find npm executable
        npm_exe = find_npm_executable()
        if not npm_exe:
            logger.warning("npm executable not found")
            return False
        
        # Check if npm works
        try:
            result = subprocess.run(
                [npm_exe, "--version"], 
                capture_output=True, 
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
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

def install_frontend_dependencies():
    """Install frontend npm packages if needed - Windows compatible"""
    try:
        frontend_dir = project_root / "frontend"
        node_modules = frontend_dir / "node_modules"
        
        if not node_modules.exists():
            logger.info("📦 Installing npm packages...")
            
            npm_exe = find_npm_executable()
            if not npm_exe:
                logger.error("npm executable not found")
                return False
            
            result = subprocess.run(
                [npm_exe, "install"],
                cwd=frontend_dir,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes timeout
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode == 0:
                logger.info("✅ npm packages installed successfully")
                return True
            else:
                logger.error(f"❌ npm install failed: {result.stderr}")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error installing frontend dependencies: {e}")
        return False

def start_frontend_server():
    """Start React development server in a separate process - Windows compatible"""
    global frontend_process
    
    try:
        frontend_dir = project_root / "frontend"
        
        if not frontend_dir.exists():
            logger.error("Frontend directory not found")
            return False
        
        # Install dependencies if needed
        if not install_frontend_dependencies():
            logger.error("Failed to install frontend dependencies")
            return False
        
        logger.info("🎨 Starting React development server...")
        
        npm_exe = find_npm_executable()
        if not npm_exe:
            logger.error("npm executable not found")
            return False
        
        # Set environment variables to prevent browser auto-opening
        env = os.environ.copy()
        env["BROWSER"] = "none"
        
        # Start npm start process
        frontend_process = subprocess.Popen(
            [npm_exe, "start"],
            cwd=frontend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        # Wait a bit and check if process started successfully
        time.sleep(5)
        
        if frontend_process.poll() is None:  # Process is still running
            logger.info("✅ React development server started successfully")
            logger.info("🌐 Frontend available at: http://localhost:3000")
            
            # Open browser after 5 seconds
            def open_browser():
                time.sleep(5)
                try:
                    webbrowser.open("http://localhost:3000")
                    logger.info("🌐 Browser opened automatically")
                except Exception as e:
                    logger.warning(f"Could not open browser automatically: {e}")
            
            browser_thread = threading.Thread(target=open_browser)
            browser_thread.daemon = True
            browser_thread.start()
            
            return True
        else:
            logger.error("❌ React development server failed to start")
            if server_state.frontend_process.stderr:
                try:
                    stdout, stderr = server_state.frontend_process.communicate(timeout=5)
                    if stderr:
                        logger.error(f"Error output: {stderr}")
                except subprocess.TimeoutExpired:
                    logger.error("Process communication timeout")
            return False
            
    except Exception as e:
        logger.error(f"Error starting frontend server: {e}")
        return False

def stop_frontend_server():
    """Stop the React development server"""
    global frontend_process
    
    if frontend_process:
        try:
            frontend_process.terminate()
            frontend_process.wait(timeout=10)
            logger.info("🛑 React development server stopped")
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.error(f"Error stopping frontend server: {e}")
            try:
                frontend_process.kill()
            except (OSError, AttributeError):
                logger.warning("Could not kill frontend process")
        finally:
            frontend_process = None

# API Routes
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Sea Level Monitoring API",
        "status": "running",
        "timestamp": datetime.now().astimezone().isoformat(),
        "version": "1.0.0",
        "lambda_handlers": LAMBDA_HANDLERS_AVAILABLE,
        "lambda_errors": lambda_import_errors if lambda_import_errors else None,
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
async def health_check():
    """Health check endpoint"""
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
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().astimezone().isoformat(),
        "database": db_status,
        "lambda_handlers": LAMBDA_HANDLERS_AVAILABLE,
        "frontend": server_state.frontend_process is not None and server_state.frontend_process.poll() is None,
        "node_available": find_node_executable() is not None,
        "npm_available": find_npm_executable() is not None
    }

@app.get("/stations")
async def get_stations():
    """Get all available stations"""
    if not LAMBDA_HANDLERS_AVAILABLE:
        # Return demo data if handlers not available
        return {
            "stations": ["All Stations", "Demo Station 1", "Demo Station 2", "Demo Station 3"],
            "note": "Demo data - Lambda handlers not available"
        }
    
    try:
        event = {}
        response = get_stations_handler(event, None)
        return lambda_response_to_fastapi(response)
    except Exception as e:
        logger.error(f"Error in get_stations: {e}")
        # Return demo data on error
        return {
            "stations": ["All Stations", "Error Station"],
            "error": str(e)
        }

@app.get("/data")
async def get_data(
    station: Optional[str] = Query(None, description="Station name"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    data_source: str = Query("default", description="Data source (default|tides)"),
    show_anomalies: bool = Query(False, description="Include anomaly detection")
):
    """Get data with optional filters"""
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
        return lambda_response_to_fastapi(response)
    except Exception as e:
        logger.error(f"Error in get_data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Add the remaining endpoints (live, yesterday, predictions, map, mapframe)
@app.get("/live")
async def get_live_data_all():
    """Get live data for all stations"""
    if not LAMBDA_HANDLERS_AVAILABLE:
        return {"message": "Demo data - Lambda handlers not available", "data": []}
    
    try:
        event = {}
        response = get_live_data_handler(event, None)
        return lambda_response_to_fastapi(response)
    except Exception as e:
        logger.error(f"Error in get_live_data: {e}")
        return {"error": str(e), "data": []}

@app.get("/live/{station}")
async def get_live_data_station(station: str):
    """Get live data for specific station"""
    if not LAMBDA_HANDLERS_AVAILABLE:
        return {"message": f"Demo data for {station} - Lambda handlers not available", "data": []}
    
    try:
        event = {"pathParameters": {"station": station}}
        response = get_live_data_handler(event, None)
        return lambda_response_to_fastapi(response)
    except Exception as e:
        logger.error(f"Error in get_live_data for station {station}: {e}")
        return {"error": str(e), "station": station, "data": []}

@app.get("/predictions")
async def get_predictions(
    station: Optional[str] = Query(None, description="Station name (legacy)"),
    stations: Optional[str] = Query(None, description="Station names (comma-separated)"),
    model: str = Query("all", description="Model type (arima|kalman|ensemble|all)"),
    steps: int = Query(240, description="Number of hours to forecast")
):
    """Get predictions for station(s)"""
    # Support both 'station' and 'stations' parameters
    station_param = stations or station
    
    if not station_param:
        raise HTTPException(status_code=400, detail="Station parameter is required")
    
    if not LAMBDA_HANDLERS_AVAILABLE:
        return {
            "message": f"Demo predictions for {station_param} - Lambda handlers not available",
            "arima": None,
            "kalman": None,
            "ensemble": None
        }
    
    try:
        event = {
            "queryStringParameters": {
                "stations": station_param,
                "model": model,
                "steps": str(steps)
            }
        }
        response = get_predictions_handler(event, None)
        return lambda_response_to_fastapi(response)
    except Exception as e:
        from security import secure_log
        secure_log(logger, 'error', 'Error in get_predictions', error=str(e))
        return {"error": str(e), "arima": None, "kalman": None, "ensemble": None}

@app.get("/stations/map")
async def get_station_map(end_date: str = None):
    """Get station map data"""
    if not LAMBDA_HANDLERS_AVAILABLE:
        return {"message": "Demo map data - Lambda handlers not available", "stations": []}
    
    try:
        event = {
            "queryStringParameters": {
                "end_date": end_date
            } if end_date else {}
        }
        response = get_station_map_handler(event, None)
        return lambda_response_to_fastapi(response)
    except Exception as e:
        logger.error(f"Error in get_station_map: {e}")
        return {"error": str(e), "stations": []}

@app.get("/api/stations/map")
async def get_api_station_map():
    """Get station map data - API endpoint matching Python version"""
    if not LAMBDA_HANDLERS_AVAILABLE:
        return []
    
    try:
        event = {}
        response = get_station_map_handler(event, None)
        data = lambda_response_to_fastapi(response)
        # Return the data directly as array, not wrapped in response object
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"Error in get_api_station_map: {e}")
        return []

@app.get("/sea-forecast")
async def get_sea_forecast():
    """Get IMS sea forecast data"""
    if not LAMBDA_HANDLERS_AVAILABLE:
        return {"message": "Demo forecast data - Lambda handlers not available", "locations": []}
    
    try:
        event = {}
        response = get_sea_forecast_handler(event, None)
        return lambda_response_to_fastapi(response)
    except Exception as e:
        logger.error(f"Error in get_sea_forecast: {e}")
        return {"error": str(e), "locations": []}

@app.get("/warnings")
async def get_warnings():
    """Get IMS sea warnings from RSS feed"""
    try:
        import xml.etree.ElementTree as ET
        import requests
        from datetime import datetime
        
        # Fetch RSS feed
        response = requests.get(
            "https://ims.gov.il/sites/default/files/ims_data/rss/alert/rssAlert_general_country_en.xml",
            timeout=10
        )
        response.raise_for_status()
        
        # Parse XML
        root = ET.fromstring(response.content)
        warnings = []
        
        for item in root.findall('.//item'):
            title = item.find('title')
            description = item.find('description') 
            pub_date = item.find('pubDate')
            
            if title is not None:
                warning = {
                    'title': title.text or '',
                    'description': description.text or '' if description is not None else '',
                    'pubDate': pub_date.text or '' if pub_date is not None else ''
                }
                warnings.append(warning)
        
        return {
            'warnings': warnings,
            'count': len(warnings),
            'fetched_at': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error fetching warnings: {e}")
        return {
            'warnings': [],
            'count': 0,
            'error': str(e)
        }

@app.get("/assets/{filename}")
async def get_asset(filename: str):
    """Serve static assets like icons"""
    # Sanitize filename to prevent path traversal
    safe_filename = filename.replace('..', '').replace('/', '').replace('\\', '')
    if not safe_filename or safe_filename != filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    asset_path = project_root / "frontend" / "public" / "assets" / safe_filename
    
    # Ensure path is within assets directory
    try:
        asset_path = asset_path.resolve()
        assets_dir = (project_root / "frontend" / "public" / "assets").resolve()
        if not str(asset_path).startswith(str(assets_dir)):
            raise HTTPException(status_code=403, detail="Access denied")
    except:
        raise HTTPException(status_code=400, detail="Invalid path")
    
    if asset_path.exists():
        return FileResponse(asset_path)
    else:
        raise HTTPException(status_code=404, detail="Asset not found")

@app.get("/mapframe")
async def get_mapframe(end_date: str = None):
    """Serve GovMap iframe with station and wave forecast data"""
    from security import secure_log
    secure_log(logger, 'info', 'mapframe requested', end_date=end_date or 'None')
    
    # Read the HTML file and serve it
    mapframe_path = current_dir / "mapframe.html"
    if mapframe_path.exists():
        with open(mapframe_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    else:
        raise HTTPException(status_code=404, detail="Mapframe HTML not found")

# Frontend management endpoints
@app.post("/dev/frontend/start")
async def start_frontend_api():
    """Development endpoint to start frontend server"""
    # Remove client-side authorization check for development endpoint
    if not check_frontend_dependencies():
        raise HTTPException(status_code=503, detail="Frontend dependencies not available")
    
    global frontend_thread
    
    if frontend_process and frontend_process.poll() is None:
        return {"message": "Frontend server is already running", "url": "http://localhost:3000"}
    
    # Start frontend in a separate thread
    frontend_thread = threading.Thread(target=start_frontend_server)
    frontend_thread.daemon = True
    frontend_thread.start()
    
    # Wait a bit to see if it started successfully
    time.sleep(5)
    
    if frontend_process and frontend_process.poll() is None:
        return {"message": "Frontend server started successfully", "url": "http://localhost:3000"}
    else:
        raise HTTPException(status_code=500, detail="Failed to start frontend server")

@app.post("/dev/frontend/stop")
async def stop_frontend_api():
    """Development endpoint to stop frontend server"""
    stop_frontend_server()
    return {"message": "Frontend server stopped"}

@app.get("/dev/frontend/status")
async def frontend_status():
    """Development endpoint to check frontend status"""
    if frontend_process and frontend_process.poll() is None:
        return {
            "status": "running",
            "url": "http://localhost:3000",
            "pid": frontend_process.pid
        }
    else:
        return {
            "status": "stopped",
            "node_available": find_node_executable() is not None,
            "npm_available": find_npm_executable() is not None,
            "frontend_dir_exists": (project_root / "frontend").exists()
        }

def main():
    """Main function to run the development server"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Sea Level Monitoring Development Server")
    parser.add_argument("--host", default="sea-level-dash-local", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8001, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--auto-frontend", action="store_true", help="Auto-start frontend server")
    parser.add_argument("--no-frontend", action="store_true", help="Don't check for frontend")
    
    args = parser.parse_args()
    
    global auto_start_frontend
    auto_start_frontend = args.auto_frontend
    
    print("=" * 70)
    print("🌊 Sea Level Monitoring System - Development Server")
    print("=" * 70)
    print(f"🚀 Backend API: http://{args.host}:{args.port}")
    print(f"📚 API Docs: http://{args.host}:{args.port}/docs")
    
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
            print("   🔧 Start Frontend: POST /dev/frontend/start")
            if args.auto_frontend:
                print("   ⚡ Auto-start: ENABLED")
        else:
            print("⚠️  Frontend: Dependencies not available")
            node_exe = find_node_executable()
            npm_exe = find_npm_executable()
            print(f"   Node.js: {'✅' if node_exe else '❌'}")
            print(f"   npm: {'✅' if npm_exe else '❌'}")
            print(f"   Frontend dir: {'✅' if (project_root / 'frontend').exists() else '❌'}")
    
    print("=" * 70)
    print("💡 Usage Tips:")
    print("   - Use /health to check system status")
    print("   - Use /docs for interactive API documentation")
    print("   - Press Ctrl+C to stop the server")
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
        stop_frontend_server()
        print("👋 Goodbye!")

if __name__ == "__main__":
    main()