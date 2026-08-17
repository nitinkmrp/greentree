from flask import Flask
from flask_cors import CORS
import logging
import os

from config import get_config
from api.routes import create_api
from loki_logger import configure_app_logging
from models.database import initialize_database

def create_app(config_name: str = None) -> Flask:
    """Application factory function"""
    
    # Create Flask app
    app = Flask(__name__)
    
    # Load configuration
    config = get_config(config_name)
    app.config.from_object(config)
    
    # Setup CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": ["*"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        },
        r"/docs/*": {
            "origins": ["*"],
            "methods": ["GET"],
            "allow_headers": ["Content-Type"]
        }
    })
    
    # Setup logging
    setup_logging(app, config)
    # Initialize database tables gracefully if DB available
    try:
        initialize_database()
    except Exception as e:
        app.logger.warning(f"Database initial setup notice: {e}")
    
    api = create_api()
    # Initialize Flask-RESTX API
    api.init_app(app)
    
    # Custom root health check endpoint
    @app.route('/health', endpoint='custom_health')
    def custom_health():
        return {
            "status": "healthy",
            "service": "hubspot_deals",
            "version": "1.0.0",
            "documentation": "/docs"
        }, 200

    # Root route
    @app.route('/')
    def index():
        return {
            "service": config.APP_TITLE,
            "version": config.APP_VERSION,
            "documentation": config.API_DOCS_PATH,
            "health": "/health",
            "endpoints": {
                "start_scan": "POST /api/v1/scan/start",
                "scan_status": "GET /api/v1/scan/{scan_id}/status",
                "cancel_scan": "POST /api/v1/scan/{scan_id}/cancel",
                "list_scans": "GET /api/v1/scan/list",
                "pipeline_info": "GET /api/v1/pipeline/info",
                "cleanup": "POST /api/v1/maintenance/cleanup"
            }
        }
    
    return app


def setup_logging(app: Flask, config):
    """Setup application logging"""
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format=config.LOG_FORMAT
    )
    
    if config.LOKI_ENABLED and not hasattr(app, '_loki_configured'):
        try:
            configure_app_logging(app)
            app._loki_configured = True
            app.logger.info("Loki logging enabled")
        except Exception as e:
            app.logger.warning(f"Failed to setup Loki logging: {e}")


app = create_app()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5200))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    app.run(host=host, port=port, debug=debug)
