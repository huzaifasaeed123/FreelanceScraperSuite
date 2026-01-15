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

    Expected JSON body (New Format - Complete Form Data):
    {
        "marque": "Renault",
        "modele": "Clio",
        "carburant": "diesel",
        "nombre_places": 5,
        "puissance_fiscale": 6,
        "date_mec": "2020-05-15",
        "type_plaque": "standard",
        "immatriculation": "WW378497",
        "valeur_neuf": 200000,
        "valeur_actuelle": 150000,
        "nom": "Alami",
        "prenom": "Ahmed",
        "telephone": "0661652022",
        "email": "ahmed@email.com",
        "date_naissance": "1990-01-15",
        "date_permis": "2010-03-20",
        "ville": "Casablanca",
        "assureur_actuel": "AXA",
        "consent": true
    }

    Also supports old format for backward compatibility:
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

        # Check if it's old format or new format
        is_old_format = 'valeur_neuf' in data and 'valeur_venale' in data
        is_new_format = 'marque' in data and 'carburant' in data

        if not is_old_format and not is_new_format:
            return jsonify({
                "success": False,
                "error": "Invalid request format. Required fields missing."
            }), 400

        # Handle old format (backward compatibility)
        if is_old_format and not is_new_format:
            valeur_neuf = data.get('valeur_neuf')
            valeur_venale = data.get('valeur_venale')

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

            # Fetch quotes with old format
            result = comparison_service.get_all_quotes(
                params={
                    "valeur_neuf": valeur_neuf,
                    "valeur_venale": valeur_venale
                },
                ip_address=ip_address,
                user_agent=user_agent
            )

            return jsonify(result)

        # Handle new format (complete form data)
        # Validate required vehicle fields
        required_fields = ['marque', 'modele', 'carburant', 'nombre_places',
                          'puissance_fiscale', 'date_mec', 'type_plaque',
                          'immatriculation', 'valeur_neuf', 'valeur_actuelle']

        missing_fields = [f for f in required_fields if f not in data or data[f] == '']
        if missing_fields:
            return jsonify({
                "success": False,
                "error": f"Missing required fields: {', '.join(missing_fields)}"
            }), 400

        # Validate numeric fields
        try:
            valeur_neuf = float(data.get('valeur_neuf'))
            valeur_actuelle = float(data.get('valeur_actuelle'))
            nombre_places = int(data.get('nombre_places'))
            puissance_fiscale = int(data.get('puissance_fiscale'))
        except (TypeError, ValueError):
            return jsonify({
                "success": False,
                "error": "Invalid numeric values"
            }), 400

        if valeur_neuf <= 0 or valeur_actuelle <= 0:
            return jsonify({
                "success": False,
                "error": "Vehicle values must be positive"
            }), 400

        if valeur_actuelle > valeur_neuf:
            return jsonify({
                "success": False,
                "error": "Current value cannot exceed new vehicle value"
            }), 400

        # Get client info
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')

        # Fetch quotes with new format (uses field mapper internally)
        result = comparison_service.get_all_quotes(
            params=data,
            ip_address=ip_address,
            user_agent=user_agent,
            is_complete_form=True
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
