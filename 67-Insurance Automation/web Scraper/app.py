"""
Insurance Comparator API
Flask backend for the insurance comparison application
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os

from comparison_service import ComparisonService

app = Flask(__name__, static_folder='static')
CORS(app)

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
        
        # Fetch quotes
        result = comparison_service.get_all_quotes({
            "valeur_neuf": valeur_neuf,
            "valeur_venale": valeur_venale
        })
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "providers": ["AXA", "MCMA", "RMA"]
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
