"""
Insurance Comparator API
Flask backend for the insurance comparison application
"""

from flask import Flask, request, jsonify, send_from_directory, send_file, session, redirect, url_for
from flask_cors import CORS
import os
from datetime import datetime
from dotenv import load_dotenv

from comparison_service import get_all_quotes, compare_insurance
from scrapers import SCRAPER_FUNCTIONS, shutdown_rma_manager
from database.models import init_database, DatabaseManager
from auth import init_admin_user, login_required, admin_required, api_key_or_login_required, get_current_user, login_user, logout_user
import atexit

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

# Register cleanup for RMA browser manager on app shutdown
atexit.register(shutdown_rma_manager)

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


@app.route('/settings')
@login_required
def settings():
    """Serve the settings page - requires authentication"""
    return send_from_directory('static', 'settings.html')


@app.route('/admin/scrapers')
@admin_required
def admin_scrapers():
    """Serve the scraper management page - requires admin privileges"""
    return send_from_directory('static', 'admin_scrapers.html')


@app.route('/api/admin/scrapers', methods=['GET'])
@admin_required
def get_scrapers():
    """Get all scrapers with their status"""
    try:
        from database.models import DatabaseManager
        scrapers = DatabaseManager.get_all_scrapers()
        return jsonify({"success": True, "scrapers": scrapers})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/admin/toggle-scraper', methods=['POST'])
@admin_required
def toggle_scraper():
    """Toggle a scraper's enabled status"""
    try:
        from database.models import DatabaseManager
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        scraper_code = data.get('scraper_code')
        is_enabled = data.get('is_enabled')

        if not scraper_code or is_enabled is None:
            return jsonify({"success": False, "error": "Missing required fields"}), 400

        success = DatabaseManager.toggle_scraper(scraper_code, is_enabled)

        if success:
            return jsonify({"success": True, "message": "Scraper updated successfully"})
        else:
            return jsonify({"success": False, "error": "Failed to update scraper"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/scrapers/enabled', methods=['GET'])
@login_required
def get_enabled_scrapers():
    """Get list of enabled scraper codes"""
    try:
        from database.models import DatabaseManager
        enabled_scrapers = DatabaseManager.get_enabled_scrapers()
        return jsonify({"success": True, "scrapers": enabled_scrapers})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/admin/api-keys', methods=['GET'])
@admin_required
def get_api_keys():
    """Get all API keys (admin only)"""
    try:
        from database.models import DatabaseManager
        api_keys = DatabaseManager.get_all_api_keys()
        return jsonify({"success": True, "api_keys": api_keys})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/admin/create-api-key', methods=['POST'])
@admin_required
def create_api_key():
    """Create a new API key (admin only)"""
    try:
        from database.models import DatabaseManager
        data = request.get_json() or {}
        description = data.get('description', 'API Key')

        # Get current user ID
        current_user = get_current_user()
        created_by = current_user['id'] if current_user else None

        api_key = DatabaseManager.create_api_key(description=description, created_by=created_by)

        if api_key:
            return jsonify({
                "success": True,
                "api_key": api_key,
                "message": "API key created successfully"
            })
        else:
            return jsonify({"success": False, "error": "Failed to create API key"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/admin/toggle-api-key', methods=['POST'])
@admin_required
def toggle_api_key():
    """Enable or disable an API key (admin only)"""
    try:
        from database.models import DatabaseManager
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        api_key = data.get('api_key')
        is_active = data.get('is_active')

        if not api_key or is_active is None:
            return jsonify({"success": False, "error": "Missing required fields"}), 400

        success = DatabaseManager.toggle_api_key(api_key, is_active)

        if success:
            return jsonify({"success": True, "message": "API key updated successfully"})
        else:
            return jsonify({"success": False, "error": "Failed to update API key"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/admin/delete-api-key', methods=['POST'])
@admin_required
def delete_api_key():
    """Delete an API key (admin only)"""
    try:
        from database.models import DatabaseManager
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        api_key = data.get('api_key')

        if not api_key:
            return jsonify({"success": False, "error": "API key is required"}), 400

        success = DatabaseManager.delete_api_key(api_key)

        if success:
            return jsonify({"success": True, "message": "API key deleted successfully"})
        else:
            return jsonify({"success": False, "error": "Failed to delete API key"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


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


@app.route('/logout')
def logout():
    """Logout and redirect to login page"""
    logout_user()
    return redirect(url_for('login'))


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
@api_key_or_login_required
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
        # Get current user (or use special API user ID if API key auth)
        if hasattr(request, 'api_key_auth') and request.api_key_auth:
            user_id = -1  # Special ID for API key authenticated requests
            user_name = "API User"
            user_email = "api@external.com"
        else:
            current_user = get_current_user()
            user_id = current_user['id'] if current_user else None
            user_name = current_user.get('name', 'Unknown') if current_user else None
            user_email = current_user.get('email', 'unknown@email.com') if current_user else None

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
                user_agent=user_agent,
                user_name=user_name,
                user_email=user_email
            )

            # Get selected scrapers (if provided)
            selected_scrapers = data.get('selected_scrapers', None)

            # Fetch quotes with old format
            result = get_all_quotes({
                "valeur_neuf": valeur_neuf,
                "valeur_venale": valeur_venale
            }, user_id=user_id, form_submission_id=form_submission_id, selected_scrapers=selected_scrapers)

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
            user_agent=user_agent,
            user_name=user_name,
            user_email=user_email
        )

        # Get selected scrapers (if provided)
        selected_scrapers = data.get('selected_scrapers', None)

        # Fetch quotes with new format (uses field mapper internally)
        result = get_all_quotes(data, user_id=user_id, form_submission_id=form_submission_id, selected_scrapers=selected_scrapers)

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


@app.route('/api/mcma/update-quote', methods=['POST'])
@login_required
def update_mcma_quote():
    """
    Update MCMA quotation with selected options

    Expected JSON body:
    {
        "subscription_id": "...",
        "token": "...",
        "pack_name": "optimale" or "tout_risque",
        "broken_glass_value": 7000,  // 7000, 10000, or 15000
        "second_option_value": 20000  // For optimale: damageAndCollision (20000, 30000, 50000)
                                      // For tout_risque: franchise (3, 5, 10)
    }
    """
    try:
        from scrapers.mcma_scraper import update_mcma_quote as mcma_update

        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body is required"
            }), 400

        # Extract required fields
        subscription_id = data.get('subscription_id')
        token = data.get('token')
        pack_name = data.get('pack_name')
        broken_glass_value = data.get('broken_glass_value')
        second_option_value = data.get('second_option_value')

        if not subscription_id or not token or not pack_name:
            return jsonify({
                "success": False,
                "error": "subscription_id, token, and pack_name are required"
            }), 400

        if pack_name not in ['optimale', 'tout_risque']:
            return jsonify({
                "success": False,
                "error": "pack_name must be 'optimale' or 'tout_risque'"
            }), 400

        if not broken_glass_value or not second_option_value:
            return jsonify({
                "success": False,
                "error": "broken_glass_value and second_option_value are required"
            }), 400

        # Call the MCMA update function
        result = mcma_update(
            subscription_id=subscription_id,
            token=token,
            pack_name=pack_name,
            broken_glass_value=broken_glass_value,
            second_option_value=second_option_value
        )

        if result and result.get('success'):
            # Calculate taxes (16.5%)
            annual_price = result.get('annual_price', 0) or 0
            semi_annual_price = result.get('semi_annual_price', 0) or 0
            annual_taxes = round(annual_price * 0.165, 2)
            semi_annual_taxes = round(semi_annual_price * 0.165, 2)

            return jsonify({
                "success": True,
                "pack_name": pack_name,
                "broken_glass_value": broken_glass_value,
                "second_option_value": second_option_value,
                "annual": {
                    "prime_net": annual_price,
                    "taxes": annual_taxes,
                    "prime_total": round(annual_price + annual_taxes, 2)
                },
                "semi_annual": {
                    "prime_net": semi_annual_price,
                    "taxes": semi_annual_taxes,
                    "prime_total": round(semi_annual_price + semi_annual_taxes, 2)
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": result.get('error', 'Failed to update MCMA quotation')
            }), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


@app.route('/api/generate-comparison-pdf', methods=['POST'])
@login_required
def generate_comparison_pdf():
    """Generate PDF comparison of lowest offers"""
    try:
        from database.models import DatabaseManager
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from io import BytesIO
        from datetime import datetime

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        plans = data.get('plans', [])
        duration = data.get('duration', 'annual')
        vehicle_info = data.get('vehicle_info', {})

        if not plans:
            return jsonify({"success": False, "error": "No plans provided"}), 400

        # Get user settings for logo and footer
        user_id = session.get('user_id')
        user_settings = DatabaseManager.get_user_settings(user_id) if user_id else None

        # Create PDF in memory
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)

        elements = []
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1e40af'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )

        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#64748b'),
            spaceAfter=20,
            alignment=TA_CENTER
        )

        # Add custom logo if available
        if user_settings and user_settings.get('logo_filename'):
            logo_path = os.path.join('static', 'uploads', user_settings['logo_filename'])
            if os.path.exists(logo_path):
                try:
                    logo = Image(logo_path, width=2*inch, height=1*inch, kind='proportional')
                    logo.hAlign = 'CENTER'
                    elements.append(logo)
                    elements.append(Spacer(1, 0.3*inch))
                except:
                    pass

        # Title
        elements.append(Paragraph("Comparaison d'Assurance Auto", title_style))
        elements.append(Paragraph(
            f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
            subtitle_style
        ))
        elements.append(Spacer(1, 0.3*inch))

        # Vehicle Information
        vehicle_data = [
            ['Informations du Véhicule', ''],
            ['Marque', vehicle_info.get('marque', 'N/A')],
            ['Modèle', vehicle_info.get('modele', 'N/A')],
            ['Puissance Fiscale', f"{vehicle_info.get('puissance_fiscale', 'N/A')} CV"],
            ['Valeur à Neuf', f"{vehicle_info.get('valeur_neuf', 'N/A')} DH"],
            ['Valeur Actuelle', f"{vehicle_info.get('valeur_actuelle', 'N/A')} DH"],
            ['Durée', '12 Mois (Annuel)' if duration == 'annual' else '6 Mois']
        ]

        vehicle_table = Table(vehicle_data, colWidths=[3*inch, 3*inch])
        vehicle_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
        ]))

        elements.append(vehicle_table)
        elements.append(Spacer(1, 0.5*inch))

        # Comparison Table Header
        comparison_header = Paragraph("Comparaison des Offres", title_style)
        elements.append(comparison_header)
        elements.append(Spacer(1, 0.2*inch))

        # Build comparison table
        table_data = [['Rang', 'Catégorie', 'Prime TTC']]

        for idx, plan_data in enumerate(plans, 1):
            plan = plan_data['plan']
            category = plan_data['category']

            # Get pricing based on duration
            pricing = plan.get('annual') if duration == 'annual' else plan.get('semi_annual')
            if not pricing:
                continue

            prime_total = pricing.get('prime_total', 0)

            table_data.append([
                f"#{idx}",
                category,
                f"{prime_total:.2f} DH"
            ])

        comparison_table = Table(table_data, colWidths=[1*inch, 3.5*inch, 2.5*inch])
        comparison_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0fdf4')]),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#d1fae5'))  # Highlight best price
        ]))

        elements.append(comparison_table)
        elements.append(Spacer(1, 0.5*inch))

        # Footer
        footer_text = user_settings.get('footer_text') if user_settings else None
        if not footer_text:
            footer_text = "Ce document est généré automatiquement par notre système de comparaison d'assurance."

        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#9ca3af'),
            alignment=TA_CENTER
        )
        elements.append(Paragraph(footer_text, footer_style))

        # Build PDF
        doc.build(elements)

        # Get PDF from buffer
        buffer.seek(0)

        return send_file(
            buffer,
            as_attachment=True,
            download_name=f'comparaison_assurance_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf',
            mimetype='application/pdf'
        )

    except ImportError as e:
        return jsonify({
            "success": False,
            "error": f"PDF library not installed: {str(e)}. Please install reportlab: pip install reportlab"
        }), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


@app.route('/api/settings', methods=['GET'])
@login_required
def get_settings():
    """Get user settings"""
    try:
        from database.models import DatabaseManager
        user_id = session.get('user_id')

        settings = DatabaseManager.get_user_settings(user_id)
        if not settings:
            settings = {
                'company_name': '',
                'logo_filename': '',
                'footer_text': ''
            }

        return jsonify({
            "success": True,
            "settings": settings
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


@app.route('/api/settings', methods=['POST'])
@login_required
def update_settings():
    """Update user settings"""
    try:
        from database.models import DatabaseManager
        user_id = session.get('user_id')
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        company_name = data.get('company_name')
        footer_text = data.get('footer_text')

        # Get current settings to preserve logo if not updating
        current_settings = DatabaseManager.get_user_settings(user_id)
        logo_filename = current_settings.get('logo_filename') if current_settings else None

        success = DatabaseManager.save_user_settings(
            user_id=user_id,
            company_name=company_name,
            logo_filename=logo_filename,
            footer_text=footer_text
        )

        if success:
            return jsonify({"success": True, "message": "Settings updated successfully"})
        else:
            return jsonify({"success": False, "error": "Failed to update settings"}), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


@app.route('/api/upload-logo', methods=['POST'])
@login_required
def upload_logo():
    """Upload user logo"""
    try:
        from database.models import DatabaseManager
        from werkzeug.utils import secure_filename

        user_id = session.get('user_id')

        if 'logo' not in request.files:
            return jsonify({"success": False, "error": "No file provided"}), 400

        file = request.files['logo']

        if file.filename == '':
            return jsonify({"success": False, "error": "No file selected"}), 400

        # Validate file type
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'svg'}
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''

        if file_ext not in allowed_extensions:
            return jsonify({
                "success": False,
                "error": "Invalid file type. Allowed: PNG, JPG, JPEG, GIF, SVG"
            }), 400

        # Create uploads directory if not exists
        uploads_dir = os.path.join('static', 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)

        # Generate unique filename
        filename = secure_filename(f"logo_{user_id}_{int(datetime.now().timestamp())}.{file_ext}")
        filepath = os.path.join(uploads_dir, filename)

        # Save file
        file.save(filepath)

        # Update database
        success = DatabaseManager.update_user_logo(user_id, filename)

        if success:
            return jsonify({
                "success": True,
                "filename": filename,
                "url": f"/static/uploads/{filename}"
            })
        else:
            # Clean up file if database update failed
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({"success": False, "error": "Failed to update database"}), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500


@app.route('/api/admin/export-database', methods=['GET'])
@admin_required
def export_database():
    """Export complete database to Excel - Admin only"""
    try:
        import tempfile
        from datetime import datetime
        from database.models import DatabaseManager

        # Create temporary file for Excel
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_dir = tempfile.gettempdir()
        excel_file = os.path.join(temp_dir, f'insurance_database_{timestamp}.xlsx')

        # Export database to Excel
        success = DatabaseManager.export_database_to_excel(excel_file)

        if not success:
            return jsonify({
                "success": False,
                "error": "Failed to export database"
            }), 500

        # Send file to client
        return send_file(
            excel_file,
            as_attachment=True,
            download_name=f'insurance_database_{timestamp}.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

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
