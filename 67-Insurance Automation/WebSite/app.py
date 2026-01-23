"""
Insurance Comparator API
Flask backend for the insurance comparison application
"""

from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for
from flask_cors import CORS
import os
from dotenv import load_dotenv

from comparison_service import get_all_quotes, compare_insurance
from scrapers import SCRAPER_FUNCTIONS
from database.models import init_database, DatabaseManager
from auth import init_admin_user, login_required, admin_required, get_current_user, login_user, logout_user

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='static')

# Set secret key for sessions
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-this-in-production')

# Enable CORS - Allow any website to hit this API
CORS(app,
     resources={
         r"/api/*": {
             "origins": "*",
             "methods": ["GET", "POST", "OPTIONS"],
             "allow_headers": ["Content-Type", "Authorization"],
             "expose_headers": ["Content-Type"],
             "max_age": 3600
         }
     },
     supports_credentials=True
)

# Initialize database and admin user
init_database()
init_admin_user()

print("Flask app initialized")
print(f"Loaded {len(SCRAPER_FUNCTIONS)} scrapers: {list(SCRAPER_FUNCTIONS.keys())}")


@app.route('/')
@login_required
def index():
    """Serve the main HTML page - requires authentication"""
    return send_from_directory('static', 'index.html')


@app.route('/login')
def login():
    """Serve the login page"""
    # If already logged in, redirect appropriately
    user = get_current_user()
    if user:
        if user['is_admin']:
            return redirect(url_for('admin'))
        return redirect(url_for('index'))
    return send_from_directory('static', 'login.html')


@app.route('/admin')
@admin_required
def admin():
    """Serve the admin dashboard - requires admin privileges"""
    return send_from_directory('static', 'admin.html')


@app.route('/api/login', methods=['POST'])
def api_login():
    """Handle user login"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({
                "success": False,
                "error": "Email et mot de passe requis"
            }), 400

        # Verify credentials
        user = DatabaseManager.verify_user(email, password)

        if not user:
            return jsonify({
                "success": False,
                "error": "Email ou mot de passe incorrect"
            }), 401

        # Set session
        login_user(user)

        return jsonify({
            "success": True,
            "message": "Connexion réussie",
            "is_admin": user.get('is_admin', False),
            "name": user.get('name')
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Erreur serveur: {str(e)}"
        }), 500


@app.route('/api/logout', methods=['POST'])
def api_logout():
    """Handle user logout"""
    logout_user()
    return jsonify({
        "success": True,
        "message": "Déconnexion réussie"
    })


@app.route('/api/admin/create-user', methods=['POST'])
@admin_required
def api_create_user():
    """Create a new user - admin only"""
    try:
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')

        if not name or not email or not password:
            return jsonify({
                "success": False,
                "error": "Tous les champs sont requis"
            }), 400

        # Create user
        user_id = DatabaseManager.create_user(name, email, password, is_admin=False)

        if not user_id:
            return jsonify({
                "success": False,
                "error": "Un utilisateur avec cet email existe déjà"
            }), 400

        return jsonify({
            "success": True,
            "message": "Utilisateur créé avec succès",
            "user_id": user_id
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Erreur serveur: {str(e)}"
        }), 500


@app.route('/api/admin/users', methods=['GET'])
@admin_required
def api_get_users():
    """Get list of all users - admin only"""
    try:
        users = DatabaseManager.get_all_users(exclude_admin=True)

        return jsonify({
            "success": True,
            "users": users
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Erreur serveur: {str(e)}"
        }), 500


@app.route('/api/admin/delete-user/<int:user_id>', methods=['DELETE'])
@admin_required
def api_delete_user(user_id):
    """Delete a user - admin only"""
    try:
        success = DatabaseManager.delete_user(user_id)

        if not success:
            return jsonify({
                "success": False,
                "error": "Impossible de supprimer cet utilisateur"
            }), 400

        return jsonify({
            "success": True,
            "message": "Utilisateur supprimé avec succès"
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Erreur serveur: {str(e)}"
        }), 500


@app.route('/api/compare', methods=['POST'])
@login_required
def compare():
    """
    Compare insurance quotes from all providers - requires authentication

    Expected JSON body (Complete Form Data):
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

    Also supports old/simple format:
    {
        "valeur_neuf": 65000,
        "valeur_venale": 45000
    }
    """
    try:
        # Get current user
        current_user = get_current_user()
        user_id = current_user['id']

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

            # Save minimal form submission for old format
            ip_address = request.remote_addr
            user_agent = request.headers.get('User-Agent')
            minimal_form_data = {
                'valeur_neuf': valeur_neuf,
                'valeur_actuelle': valeur_venale
            }
            form_submission_id = DatabaseManager.save_form_submission(
                user_id=user_id,
                form_data=minimal_form_data,
                ip_address=ip_address,
                user_agent=user_agent
            )

            # Fetch quotes with old format
            result = get_all_quotes({
                "valeur_neuf": valeur_neuf,
                "valeur_venale": valeur_venale
            }, user_id=user_id, form_submission_id=form_submission_id)

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

        # Save form submission to database
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent')
        form_submission_id = DatabaseManager.save_form_submission(
            user_id=user_id,
            form_data=data,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Fetch quotes with new format (uses field mapper internally)
        result = get_all_quotes(data, user_id=user_id, form_submission_id=form_submission_id)

        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


@app.route('/api/axa/update-quote', methods=['POST'])
@login_required
def update_axa_quote():
    """
    Update AXA quotation with selected options

    Expected JSON body:
    {
        "base_payload": {...},  // Original payload (contrat, vehicule, leadInfos)
        "quotation_id": 60273806,
        "id_lead": "00QbH00000RFPeTUAX",
        "pack_id": 3,  // 2=Basique, 3=Basique+, 4=Optimale, 5=Premium
        "user_selections": {  // Optional: user-selected option values by guarantee code
            "20": 2,  // Defense et Recours
            "500": 5  // P.F.C.P
        },
        "duration": "annual"  // "annual" or "semi"
    }
    """
    try:
        from scrapers.axa_scraper import update_axa_quotation, build_garanties_payload
        import copy

        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is required"
            }), 400

        # Extract required fields
        base_payload = data.get('base_payload')
        quotation_id = data.get('quotation_id')
        id_lead = data.get('id_lead')
        pack_id = data.get('pack_id')
        user_selections = data.get('user_selections', {})
        duration = data.get('duration', 'annual')

        if not base_payload or not quotation_id or not pack_id:
            return jsonify({
                "success": False,
                "error": "base_payload, quotation_id, and pack_id are required"
            }), 400

        # Build the update payload
        update_payload = copy.deepcopy(base_payload)

        # Set modePaiement based on duration
        if duration == 'annual':
            update_payload["contrat"]["modePaiement"] = "12"
        else:
            update_payload["contrat"]["modePaiement"] = "06"

        # Add required fields for update request
        update_payload["idQuotation"] = quotation_id
        update_payload["idPack"] = pack_id
        update_payload["idLead"] = id_lead

        # Build garanties based on pack and user selections
        garanties = build_garanties_payload(pack_id, user_selections)
        update_payload["garanties"] = garanties

        # Make the API call
        result = update_axa_quotation(quotation_id, update_payload)

        if result:
            return jsonify({
                "success": True,
                "data": result,
                "pack_id": pack_id,
                "duration": duration
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to update AXA quotation"
            }), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "providers": list(SCRAPER_FUNCTIONS.keys())
    })


@app.route('/api/providers', methods=['GET'])
def providers():
    """Get list of available providers"""
    from comparison_service import PROVIDER_INFO

    provider_list = []
    for code, info in PROVIDER_INFO.items():
        provider_list.append({
            "code": code,
            "name": info['name'],
            "color": info['color'],
            "logo": info['logo']
        })

    return jsonify({
        "success": True,
        "providers": provider_list
    })


if __name__ == '__main__':
    # Get PORT from environment (Railway sets this automatically)
    port = int(os.environ.get('PORT', 5000))

    # Get DEBUG mode from environment (set to False in production)
    debug_mode = os.environ.get('FLASK_ENV', 'development') == 'development'

    print(f"\n{'='*60}")
    print(f"🚀 Starting Insurance Comparison API")
    print(f"{'='*60}")
    print(f"   Host: 0.0.0.0")
    print(f"   Port: {port}")
    print(f"   Debug: {debug_mode}")
    print(f"   Scrapers: {', '.join(SCRAPER_FUNCTIONS.keys())}")
    print(f"{'='*60}\n")

    # Run Flask app
    # host='0.0.0.0' allows external connections (Railway requirement)
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug_mode,
        use_reloader=False  # Disable reloader for Railway compatibility
    )
