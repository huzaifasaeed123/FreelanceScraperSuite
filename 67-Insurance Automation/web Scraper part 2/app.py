"""
Insurance Comparator API
Flask backend for the insurance comparison application
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os

from comparison_service import ComparisonService
from database import init_database, DatabaseManager

app = Flask(__name__, static_folder='static')
CORS(app)

# Initialize database on startup
init_database()

comparison_service = ComparisonService()


@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('static', 'index.html')


@app.route('/api/compare', methods=['POST'])
def compare():
    """
    Compare insurance quotes from all providers
    
    Expected JSON body:
    {
        "valeur_neuf": 65000,
        "valeur_venale": 45000
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is required"
            }), 400
        
        valeur_neuf = data.get('valeur_neuf')
        valeur_venale = data.get('valeur_venale')
        
        # Validation
        if valeur_neuf is None or valeur_venale is None:
            return jsonify({
                "success": False,
                "error": "Both valeur_neuf and valeur_venale are required"
            }), 400
        
        try:
            valeur_neuf = float(valeur_neuf)
            valeur_venale = float(valeur_venale)
        except (TypeError, ValueError):
            return jsonify({
                "success": False,
                "error": "Values must be valid numbers"
            }), 400
        
        if valeur_neuf <= 0 or valeur_venale <= 0:
            return jsonify({
                "success": False,
                "error": "Values must be positive"
            }), 400
        
        if valeur_venale > valeur_neuf:
            return jsonify({
                "success": False,
                "error": "Current value cannot exceed new vehicle value"
            }), 400
        
        # Get client info
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')
        
        # Fetch quotes
        result = comparison_service.get_all_quotes(
            params={
                "valeur_neuf": valeur_neuf,
                "valeur_venale": valeur_venale
            },
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    from scrapers import SCRAPER_REGISTRY
    return jsonify({
        "status": "healthy",
        "providers": list(SCRAPER_REGISTRY.keys())
    })


@app.route('/api/history', methods=['GET'])
def history():
    """Get recent request history"""
    try:
        limit = request.args.get('limit', 50, type=int)
        requests_history = DatabaseManager.get_request_history(limit)
        return jsonify({
            "success": True,
            "history": requests_history
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
