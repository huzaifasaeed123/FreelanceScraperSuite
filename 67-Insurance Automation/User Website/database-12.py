import sqlite3
import os
import json # Import json for handling specific_details
import click
from datetime import datetime, date
from flask import current_app, g
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash # For hashing professional user passwords

DATABASE_NAME = 'assurances.db'
# Define the absolute path for the database
DATABASE_PATH = f'{os.getcwd()}/{DATABASE_NAME}' # Using the current working directory

def get_db_path():
    """
    Returns the absolute path to the database file.
    """
    db_dir = os.path.dirname(DATABASE_PATH)
    try:
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            if current_app: # Ensure current_app context exists before logging
                current_app.logger.info(f"Created directory for database: {db_dir}")
            else:
                print(f"Created directory for database: {db_dir}")
    except OSError as e:
        click.echo(f"Error creating database directory at {db_dir}: {e}")
        if current_app:
            current_app.logger.error(f"Could not create database directory at {db_dir}: {e}")
        raise
    return DATABASE_PATH

def adapt_date(date_value):
    """Convert date to ISO format string for storage"""
    if date_value is None:
        return None
    if isinstance(date_value, (datetime, date)):
        return date_value.strftime('%Y-%m-%d')
    return str(date_value)

def convert_date(date_bytes):
    """Convert date bytes from database to date string, handling both date-only and timestamp formats"""
    if date_bytes is None:
        return None

    # Handle bytes (from SQLite) - this is what SQLite passes to the converter
    if isinstance(date_bytes, bytes):
        try:
            date_str = date_bytes.decode('utf-8').strip()
        except (UnicodeDecodeError, AttributeError):
            # If decoding fails, try to convert to string
            try:
                date_str = str(date_bytes, 'utf-8', errors='ignore').strip()
            except:
                return None
    else:
        date_str = str(date_bytes).strip()

    # Empty string handling
    if not date_str:
        return None

    # If it's already a date-only string (YYYY-MM-DD), return it
    if len(date_str) >= 10 and date_str[4] == '-' and date_str[7] == '-':
        # Check if it's date-only (exactly 10 chars) or has time component
        if len(date_str) == 10:
            # Validate it's a proper date format
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
                return date_str
            except ValueError:
                pass
        # If it has time component (longer than 10 chars), extract just the date part
        if len(date_str) > 10:
            try:
                # Try to parse as timestamp and extract date
                date_part = date_str[:10]
                datetime.strptime(date_part, '%Y-%m-%d')
                return date_part
            except (ValueError, IndexError):
                pass

    # Try to parse various date formats
    date_formats = [
        '%Y-%m-%d',           # Standard ISO date
        '%Y-%m-%d %H:%M:%S',  # ISO with time
        '%Y-%m-%d %H:%M:%S.%f',  # ISO with microseconds
    ]

    for fmt in date_formats:
        try:
            dt = datetime.strptime(date_str[:len(fmt)], fmt)
            return dt.strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            continue

    # If all parsing fails, try to extract first 10 chars if they look like a date
    if len(date_str) >= 10:
        potential_date = date_str[:10]
        if potential_date[4] == '-' and potential_date[7] == '-':
            return potential_date

    # Last resort: return None or original string
    if current_app:
        current_app.logger.warning(f"Could not parse date value: {date_str}, returning None")
    return None

# Register the converter
sqlite3.register_adapter(date, adapt_date)
sqlite3.register_adapter(datetime, adapt_date)
sqlite3.register_converter("DATE", convert_date)

def get_db():
    """
    Connects to the application's configured database.
    The connection is unique for each request and will be reused if called again during the same request.
    """
    if 'db' not in g:
        try:
            db_path = get_db_path()
            g.db = sqlite3.connect(
                db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            g.db.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            if current_app:
                current_app.logger.error(f"Database connection error to {db_path}: {e}")
            click.echo(f"FATAL: Database connection failed: {e}. Ensure path {db_path} is writable.")
            raise
    return g.db

def close_db(e=None):
    """Closes the database connection at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

# --- DATABASE SCHEMA ---
# IMPORTANT: All 'CREATE TABLE' statements use 'IF NOT EXISTS' to avoid errors if tables already exist.
# The 'DROP TABLE' statements are commented out to prevent accidental data loss,
# especially your valuable leads, if 'init-db' is run on an existing database.
# Only uncomment DROP TABLE if you specifically intend to reset the entire database.
SCHEMA = """
-- DROP TABLE IF EXISTS users;
-- DROP TABLE IF EXISTS posts;

-- DROP TABLE IF EXISTS assurance_auto;
-- DROP TABLE IF EXISTS assurance_moto;
-- DROP TABLE IF EXISTS assurance_habitation;
-- DROP TABLE IF EXISTS assurance_sante;
-- DROP TABLE IF EXISTS assurance_emprunteur;
-- DROP TABLE IF EXISTS assurance_voyage;
-- DROP TABLE IF EXISTS assurance_loisirs;
-- DROP TABLE IF EXISTS assurance_animaux;
-- DROP TABLE IF EXISTS assurance_flotte;
-- DROP TABLE IF EXISTS assurance_maritime;
-- DROP TABLE IF EXISTS assurance_marchandise;
-- DROP TABLE IF EXISTS assurance_credit;
-- DROP TABLE IF EXISTS assurance_accident_travail;
-- DROP TABLE IF EXISTS assurance_retraite;
-- DROP TABLE IF EXISTS assurance_patrimoine;
-- DROP TABLE IF EXISTS assurance_cnops;
-- DROP TABLE IF EXISTS assurance_rc_pro;
-- DROP TABLE IF EXISTS assurance_maladie_complementaire_groupe;
-- DROP TABLE IF EXISTS alertes;
-- DROP TABLE IF EXISTS avis_assureurs;
-- DROP TABLE IF EXISTS avis_plateforme;
-- DROP TABLE IF EXISTS dashboard_user_policies;
-- DROP TABLE IF EXISTS professional_users;
-- DROP TABLE IF EXISTS taken_leads;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    google_id TEXT UNIQUE,
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    first_login_email_sent INTEGER DEFAULT 0,
    username TEXT UNIQUE,
    password_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_id INTEGER NOT NULL,
    created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    FOREIGN KEY (author_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS assurance_auto (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    marque TEXT,
    modele TEXT,
    prix_estime REAL,
    valeur_neuf REAL,
    carburant TEXT,
    annee_circulation INTEGER,
    date_mec DATE,
    puissance_fiscale INTEGER,
    type_plaque TEXT,
    immatriculation TEXT,
    nombre_places INTEGER,
    ville TEXT,
    email TEXT,
    telephone TEXT,
    nom TEXT,
    prenom TEXT,
    date_naissance DATE,
    date_permis DATE,
    assureur_actuel TEXT,
    consentement TEXT,
    action_type TEXT,
    date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' NOT NULL,
    admin_notes TEXT,
    verified BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS assurance_moto (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type_moto TEXT,
    cylindree TEXT,
    usage_moto TEXT,
    mode_stationnement TEXT,
    code_postal TEXT,
    ville TEXT,
    email TEXT,
    telephone TEXT,
    consentement TEXT,
    action_type TEXT,
    date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' NOT NULL,
    admin_notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS assurance_habitation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type_logement TEXT,
    statut_occupation TEXT,
    residence_principale TEXT,
    surface_habitable TEXT,
    nombre_pieces TEXT,
    code_postal TEXT,
    ville TEXT,
    email TEXT,
    telephone TEXT,
    consentement TEXT,
    action_type TEXT,
    date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' NOT NULL,
    admin_notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS assurance_sante (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    besoins TEXT,
    regime_social TEXT,
    code_postal TEXT,
    ville TEXT,
    email TEXT,
    telephone TEXT,
    consentement TEXT,
    action_type TEXT,
    date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' NOT NULL,
    admin_notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS assurance_emprunteur (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type_pret TEXT,
    montant_emprunt TEXT,
    duree_emprunt TEXT,
    date_naissance TEXT,
    situation_professionnelle TEXT,
    fumeur TEXT,
    code_postal TEXT,
    ville TEXT,
    email TEXT,
    telephone TEXT,
    consentement TEXT,
    action_type TEXT,
    date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' NOT NULL,
    admin_notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS assurance_voyage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    destination TEXT,
    ville TEXT,
    date_depart TEXT,
    date_retour TEXT,
    nombre_personnes TEXT,
    email TEXT,
    telephone TEXT,
    consentement TEXT,
    action_type TEXT,
    date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' NOT NULL,
    admin_notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS assurance_loisirs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type_loisir TEXT,
    description_bien TEXT,
    valeur_bien TEXT,
    code_postal TEXT,
    ville TEXT,
    email TEXT,
    telephone TEXT,
    consentement TEXT,
    action_type TEXT,
    date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' NOT NULL,
    admin_notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS assurance_animaux (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type_animal TEXT,
    race_animal TEXT,
    age_animal TEXT,
    identification_animal TEXT,
    code_postal TEXT,
    ville TEXT,
    email TEXT,
    telephone TEXT,
    consentement TEXT,
    action_type TEXT,
    date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' NOT NULL,
    admin_notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS assurance_flotte (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type_vehicules TEXT,
    nombre_vehicules TEXT,
    secteur_activite TEXT,
    code_postal TEXT,
    ville TEXT,
    email TEXT,
    telephone TEXT,
    consentement TEXT,
    action_type TEXT,
    date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' NOT NULL,
    admin_notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS assurance_maritime (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type_bateau TEXT,
    usage_bateau TEXT,
    zone_navigation TEXT,
    valeur_bateau TEXT,
    code_postal TEXT,
    email TEXT,
    telephone TEXT,
    consentement TEXT,
    action_type TEXT,
    date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' NOT NULL,
    admin_notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS assurance_marchandise (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type_marchandise TEXT,
    valeur_marchandise TEXT,
    mode_transport TEXT,
    destination TEXT,
    code_postal TEXT,
    email TEXT,
    telephone TEXT,
    consentement TEXT,
    action_type TEXT,
    date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' NOT NULL,
    admin_notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS assurance_credit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type_credit TEXT,
    montant_credit TEXT,
    duree_remboursement TEXT,
    organisme_preteur TEXT,
    code_postal TEXT,
    ville TEXT,
    email TEXT,
    telephone TEXT,
    consentement TEXT,
    action_type TEXT,
    date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' NOT NULL,
    admin_notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS assurance_accident_travail (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    secteur_activite TEXT,
    nombre_salaries TEXT,
    code_postal TEXT,
    ville TEXT,
    email TEXT,
    telephone TEXT,
    consentement TEXT,
    action_type TEXT,
    date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' NOT NULL,
    admin_notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS assurance_retraite (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    situation_actuelle TEXT,
    revenu_mensuel TEXT,
    capacite_epargne TEXT,
    age_depart_souhaite TEXT,
    code_postal TEXT,
    ville TEXT,
    email TEXT,
    telephone TEXT,
    consentement TEXT,
    action_type TEXT,
    date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' NOT NULL,
    admin_notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS assurance_patrimoine (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type_patrimoine TEXT,
    valeur_estimee TEXT,
    objectif_principal TEXT,
    code_postal TEXT,
    ville TEXT,
    email TEXT,
    telephone TEXT,
    consentement TEXT,
    action_type TEXT,
    date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' NOT NULL,
    admin_notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS assurance_cnops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    matricule_cnops TEXT,
    type_couverture_cnops TEXT,
    nom_complet TEXT,
    date_naissance_cnops TEXT,
    code_postal TEXT,
    ville TEXT,
    email TEXT,
    telephone TEXT,
    consentement TEXT,
    action_type TEXT,
    date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' NOT NULL,
    admin_notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS alertes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    email_utilisateur TEXT NOT NULL,
    type_alerte TEXT NOT NULL,
    criteres_alerte TEXT,
    statut TEXT DEFAULT 'active',
    date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS avis_assureurs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    nom_assureur TEXT,
    note_prix INTEGER,
    note_couverture INTEGER,
    note_service_client INTEGER,
    note_gestion_sinistres INTEGER,
    note_transparence INTEGER,
    note_experience_digitale INTEGER,
    note_globale_calculee REAL,
    titre_avis TEXT,
    commentaire TEXT,
    nom_utilisateur TEXT,
    email_utilisateur TEXT,
    ville_utilisateur TEXT,
    consentement TEXT,
    date_avis TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending' NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS avis_plateforme (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    note INTEGER,
    titre_avis TEXT,
    commentaire TEXT,
    nom_utilisateur TEXT,
    email_utilisateur TEXT,
    ville_utilisateur TEXT,
    consentement TEXT,
    date_avis TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending' NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS dashboard_user_policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    insurance_type TEXT NOT NULL,
    insurer TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    amount REAL,
    payment_frequency TEXT,
    notes TEXT,
    alert_active BOOLEAN DEFAULT TRUE,
    status TEXT DEFAULT 'active',
    specific_details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS professional_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    company_name TEXT,
    email TEXT UNIQUE,
    is_admin BOOLEAN DEFAULT FALSE NOT NULL,
    two_fa_code TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS taken_leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    professional_user_id INTEGER NOT NULL,
    lead_id INTEGER NOT NULL,
    lead_table_name TEXT NOT NULL,
    price_at_claim REAL,
    taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_exclusive_take BOOLEAN DEFAULT FALSE NOT NULL,
    -- New columns for lead management
    lead_status TEXT DEFAULT 'Nouveau' NOT NULL, -- e.g., 'Nouveau', 'En cours', 'Fermé', 'Perdu', 'Mauvaise qualité'
    contact_date TEXT, -- Date of last contact
    lead_quality TEXT DEFAULT 'medium' NOT NULL, -- e.g., 'high', 'medium', 'low'
    probability INTEGER DEFAULT 0 NOT NULL, -- Probability of conversion (0-100)
    estimated_value REAL DEFAULT 0.0 NOT NULL, -- Estimated value of the lead
    next_action TEXT, -- Next action planned for the lead
    comment TEXT, -- General comments about the lead
    FOREIGN KEY (professional_user_id) REFERENCES professional_users (id)
);

-- Updated Assurance Stage Table
CREATE TABLE IF NOT EXISTS assurance_stage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    ecole_university_name TEXT NOT NULL,
    organisme_de_stage TEXT NOT NULL,
    industry TEXT NOT NULL,
    periode_de_stage TEXT NOT NULL,
    telephone TEXT NOT NULL,
    email TEXT NOT NULL,
    ville TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' NOT NULL, -- Added status column
    admin_notes TEXT, -- Added admin_notes column
    FOREIGN KEY (user_id) REFERENCES users (id)
);

-- Updated Assurance Ecole Table
CREATE TABLE IF NOT EXISTS assurance_ecole (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    ecole_university_name TEXT NOT NULL,
    number_of_students INTEGER NOT NULL,
    telephone TEXT NOT NULL,
    email TEXT NOT NULL,
    ville TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' NOT NULL, -- Added status column
    admin_notes TEXT, -- Added admin_notes column
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS assurance_cybersecurity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    secteur_activite TEXT,
    chiffre_affaires TEXT,
    nombre_employes TEXT,
    types_donnees TEXT,
    ville TEXT,
    email TEXT,
    telephone TEXT,
    consentement TEXT,
    action_type TEXT,
    date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' NOT NULL,
    admin_notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS assurance_autoentrepreneur (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    domaine_activite TEXT,
    chiffre_affaires TEXT,
    nombre_clients TEXT,
    anciennete TEXT,
    ville TEXT,
    email TEXT,
    telephone TEXT,
    consentement TEXT,
    action_type TEXT,
    date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' NOT NULL,
    admin_notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS assurance_rc_pro (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    company_name TEXT,
    activity TEXT,
    ville TEXT,
    turnover TEXT,
    employees TEXT,
    coverage TEXT,
    franchise TEXT,
    projects TEXT,
    email TEXT,
    telephone TEXT,
    consentement TEXT,
    action_type TEXT,
    date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' NOT NULL,
    admin_notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS assurance_maladie_complementaire_groupe (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    company_name TEXT,
    industry TEXT,
    ville TEXT,
    headcount TEXT,
    spouses_count TEXT,
    children_count TEXT,
    annual_payroll TEXT,
    email TEXT,
    telephone TEXT,
    consentement TEXT,
    action_type TEXT,
    date_soumission TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' NOT NULL,
    admin_notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);
"""

# Function to add or update a single professional user
def add_or_update_professional_user(username, password, company_name, email, is_admin=False):
    """
    Adds a new professional user or updates an existing one if the username already exists.
    Hashes the password before storing, as required by the 'password_hash' column.
    This function will NOT drop or recreate any tables.
    """
    db_path = get_db_path()
    db = None
    try:
        db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = db.cursor()

        # Always hash the password before storing it in password_hash column
        hashed_password = generate_password_hash(password)

        try:
            cursor.execute(
                "INSERT INTO professional_users (username, password_hash, company_name, email, is_admin) VALUES (?, ?, ?, ?, ?)",
                (username, hashed_password, company_name, email, is_admin)
            )
            log_msg = f"Successfully inserted new professional user: '{username}'."
            if current_app: current_app.logger.info(log_msg)
            else: print(log_msg)
        except sqlite3.IntegrityError:
            # User exists (username is UNIQUE), so update their data.
            cursor.execute(
                "UPDATE professional_users SET password_hash = ?, company_name = ?, email = ?, is_admin = ? WHERE username = ?",
                (hashed_password, company_name, email, is_admin, username)
            )
            log_msg = f"Successfully updated existing professional user: '{username}'."
            if current_app: current_app.logger.info(log_msg)
            else: print(log_msg)

        db.commit()
        click.echo(f"Operation successful for professional user '{username}'.")

    except sqlite3.Error as e:
        error_msg = f"Database error adding/updating professional user '{username}': {e}"
        click.echo(f"ERROR: {error_msg}")
        if current_app: current_app.logger.error(error_msg)
    except Exception as e:
        error_msg = f"An unexpected error occurred while adding/updating professional user '{username}': {e}"
        click.echo(f"ERROR: {error_msg}")
        if current_app: current_app.logger.error(error_msg)
    finally:
        if db:
            db.close()


def init_db():
    """
    Initializes the database schema and populates initial professional users from environment variables.
    This function is intended for initial setup or full resets.
    It uses 'CREATE TABLE IF NOT EXISTS' for all tables and skips DROP TABLE to preserve data by default.
    """
    db_path = get_db_path()
    db = None
    try:
        db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        # Execute the schema. With 'IF NOT EXISTS' and commented out 'DROP TABLE',
        # this will not delete existing tables or data.
        db.executescript(SCHEMA)

        # Define prefixes for environment variables for each professional user.
        # These should be UNIQUE and match the prefixes used in your WSGI file.
        professional_user_env_prefixes = [
            "COURTIERTEST",
            "ASSUREURA",
            "AGECAP", # This should now be its own unique prefix as per your WSGI
            "ABDELMOUMEN",
            "ATLANTIQUE",
            "BENMOUSSA",
            "ADMINLEADS",
            "ADMINREVIEWS"
        ]

        cursor = db.cursor()
        for env_prefix in professional_user_env_prefixes:
            username = os.environ.get(f'PROF_USER_{env_prefix}_USERNAME')
            password = os.environ.get(f'PROF_USER_{env_prefix}_PASSWORD')
            company = os.environ.get(f'PROF_USER_{env_prefix}_COMPANY')
            email = os.environ.get(f'PROF_USER_{env_prefix}_EMAIL')
            is_admin_str = os.environ.get(f'PROF_USER_{env_prefix}_IS_ADMIN', 'False')
            is_admin = is_admin_str.lower() == 'true'
            two_fa_code = os.environ.get(f'PROF_USER_{env_prefix}_TWO_FA_CODE')  # Add this line

            if not all([username, password, company, email]):
                if current_app:
                    current_app.logger.warning(
                        f"Missing one or more environment variables for professional user with prefix '{env_prefix}'. "
                        f"Skipping user creation/update. Ensure PROF_USER_{env_prefix}_USERNAME, "
                        f"PROF_USER_{env_prefix}_PASSWORD, PROF_USER_{env_prefix}_COMPANY, "
                        f"and PROF_USER_{env_prefix}_EMAIL are all set in your WSGI file."
                    )
                else:
                    print(f"Missing environment variables for user {env_prefix}. Skipping user creation/update.")
                continue

            # This calls the same logic as add_or_update_professional_user
            # It will hash the password and insert/update the user.
            add_or_update_professional_user(username, password, company, email, is_admin)

            # Set 2FA code if provided
            if two_fa_code:
                try:
                    cursor.execute('UPDATE professional_users SET two_fa_code = ? WHERE username = ?', (two_fa_code, username))
                    db.commit()
                    if current_app:
                        current_app.logger.info(f"Set 2FA code for user {username}")
                    else:
                        print(f"✓ Set 2FA code for user {username}")
                except sqlite3.Error as e:
                    if current_app:
                        current_app.logger.error(f"Error setting 2FA code for user {username}: {e}")
                    else:
                        print(f"✗ Error setting 2FA code for user {username}: {e}")

        # Note: add_or_update_professional_user commits internally, so no need for db.commit() here
        # unless other operations are performed directly in init_db that need committing.
        click.echo(f'Initialized the database at {db_path}')
        click.echo(f'Professional users are now populated from environment variables defined in WSGI.')

    except sqlite3.Error as e:
        click.echo(f"Failed to initialize database: {e}")
        if current_app:
            current_app.logger.error(f"Failed to initialize database at {db_path}: {e}")
    except Exception as e:
        click.echo(f"An unexpected error occurred during DB initialization: {e}")
        if current_app:
            current_app.logger.error(f"Unexpected error during DB initialization at {db_path}: {e}")
    finally:
        if db:
            db.close()


@click.command('init-db')
@with_appcontext
def init_db_command():
    """CLI command to initialize the database."""
    init_db()

@click.command('add-prof-user')
@click.argument('username')
@click.argument('password')
@click.argument('company_name')
@click.argument('email')
@click.option('--is-admin/--no-admin', default=False, help='Set if the user should have admin privileges. Use --is-admin for True, --no-admin for False.')
@with_appcontext
def add_prof_user_command(username, password, company_name, email, is_admin):
    """
    Adds a new professional user or updates an existing one without affecting other database tables.
    The password will be hashed and stored.
    Example: flask add-prof-user mybroker strongpass "My Brokerage" broker@example.com --no-admin
    Example: flask add-prof-user adminuser adminpass "Admin Dept" admin@company.com --is-admin
    """
    add_or_update_professional_user(username, password, company_name, email, is_admin)

@click.command('migrate-workspace')
@click.option('--dry-run', is_flag=True, help='Run migration in dry-run mode (no changes)')
@with_appcontext
def migrate_workspace_command(dry_run):
    """
    Migrate from taken_leads to workspace system
    Example: flask migrate-workspace --dry-run
    Example: flask migrate-workspace
    """
    db = get_db()

    if dry_run:
        click.echo("DRY RUN MODE - No changes will be made")
        # Just count the leads that would be migrated
        cursor = db.execute("SELECT COUNT(*) as count FROM taken_leads")
        count = cursor.fetchone()['count']
        click.echo(f"Would migrate {count} leads to workspace system")
        return

    click.echo("Starting migration from taken_leads to workspace system...")

    # Perform migration
    migration_stats = migrate_taken_leads_to_workspace(db)

    if 'error' in migration_stats:
        click.echo(f"Migration failed: {migration_stats['error']}")
        return

    click.echo("\n" + "="*50)
    click.echo("MIGRATION STATISTICS")
    click.echo("="*50)
    click.echo(f"Total leads: {migration_stats['total_leads']}")
    click.echo(f"Successfully migrated: {migration_stats['migrated_leads']}")
    click.echo(f"Failed migrations: {migration_stats['failed_leads']}")
    click.echo(f"Professional users affected: {len(migration_stats['professional_users'])}")
    click.echo(f"Insurance categories affected: {len(migration_stats['insurance_categories'])}")

    if migration_stats['failed_leads'] == 0:
        click.echo("\n✓ Migration completed successfully!")
        click.echo("Next steps:")
        click.echo("1. Update application code to use workspace system")
        click.echo("2. Test the new system thoroughly")
        click.echo("3. Consider removing taken_leads table after validation")
    else:
        click.echo(f"\n✗ Migration completed with {migration_stats['failed_leads']} failures")


# =====================================================
# WORKSPACE MANAGEMENT FUNCTIONS
# =====================================================

def convert_http_date_to_iso(date_value):
    """
    Convert HTTP format date (e.g., 'Mon, 02 Feb 1998 00:00:00 GMT') to ISO format (YYYY-MM-DD).
    Returns the original value if conversion fails or if it's already in ISO format.
    """
    if not date_value or date_value is None:
        return date_value

    # If it's already a date object or None, return as is
    if isinstance(date_value, (int, float)):
        return date_value

    # Handle bytes (common in SQLite when dates are stored incorrectly)
    if isinstance(date_value, bytes):
        try:
            date_str = date_value.decode('utf-8', errors='ignore')
        except:
            date_str = str(date_value)
    else:
        date_str = str(date_value)

    # If already in ISO format (YYYY-MM-DD), return as is
    if len(date_str) >= 10 and date_str[4] == '-' and date_str[7] == '-':
        try:
            # Validate it's a valid ISO date
            datetime.strptime(date_str[:10], '%Y-%m-%d')
            return date_str[:10] if len(date_str) > 10 else date_str
        except (ValueError, IndexError):
            pass

    # Try to parse HTTP format dates
    http_formats = [
        '%a, %d %b %Y %H:%M:%S %Z',  # Mon, 02 Feb 1998 00:00:00 GMT
        '%a, %d %b %Y %H:%M:%S GMT',  # Mon, 02 Feb 1998 00:00:00 GMT (without timezone)
        '%d %b %Y',  # 02 Feb 1998
        '%Y-%m-%d',  # ISO format
        '%Y-%m-%d %H:%M:%S',  # ISO with time
    ]

    for fmt in http_formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except (ValueError, AttributeError):
            continue

    # If all parsing fails, return original value
    if current_app:
        current_app.logger.warning(f"Could not parse date format: {date_str}, returning as-is")
    return date_value

def get_workspace_table_name(professional_user_id: int, insurance_category: str) -> str:
    """Generate workspace table name for a professional user and insurance category"""
    return f"workspace_{professional_user_id}_{insurance_category}"

def create_workspace_table(db, professional_user_id: int, insurance_category: str) -> bool:
    """
    Create a workspace table for a professional user and insurance category
    Returns True if created successfully, False if already exists
    """
    table_name = get_workspace_table_name(professional_user_id, insurance_category)

    # Check if table already exists
    cursor = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    if cursor.fetchone():
        return False  # Table already exists

    # Get the schema of the source table to create workspace table
    cursor = db.execute(f"PRAGMA table_info({insurance_category})")
    source_columns = cursor.fetchall()

    if not source_columns:
        if current_app:
            current_app.logger.error(f"Source table schema not found for {insurance_category}")
        return False

    # Create workspace table with source columns + workspace columns
    schema_parts = [f"CREATE TABLE {table_name} ("]

    # Add source columns (keeping original data types)
    for col in source_columns:
        col_name = col[1]  # Column name
        col_type = col[2]  # Data type
        col_not_null = "NOT NULL" if col[3] else ""
        col_default = f"DEFAULT {col[4]}" if col[4] else ""

        schema_parts.append(f"    {col_name} {col_type} {col_not_null} {col_default},")

    # Add workspace-specific columns
    workspace_columns = [
        "professional_user_id INTEGER NOT NULL",
        "taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "is_exclusive_take BOOLEAN DEFAULT FALSE",
        "lead_status TEXT DEFAULT 'Nouveau'",
        "contact_date TEXT",
        "lead_quality TEXT DEFAULT 'medium'",
        "probability INTEGER DEFAULT 0",
        "estimated_value REAL DEFAULT 0.0",
        "next_action TEXT",
        "comment TEXT",
        "last_contact_attempt TEXT",
        "follow_up_date TEXT",
        "conversion_date TEXT",
        "lost_reason TEXT",
        "source_table TEXT NOT NULL",
        "source_updated_at TIMESTAMP",
        "workspace_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        # Add the three new financial columns
        "premium_amount REAL DEFAULT 0.0",
        "commission_rate REAL DEFAULT 0.0",
        "commission_amount REAL DEFAULT 0.0"
    ]

    for col in workspace_columns:
        schema_parts.append(f"    {col},")

    # Add foreign key constraint
    schema_parts.append("    FOREIGN KEY (professional_user_id) REFERENCES professional_users (id)")
    schema_parts.append(");")

    workspace_schema = "\n".join(schema_parts)

    try:
        db.executescript(workspace_schema)
        db.commit()

        # Create indexes for performance
        indexes = [
            f"CREATE INDEX idx_{table_name}_professional_user_id ON {table_name}(professional_user_id)",
            f"CREATE INDEX idx_{table_name}_lead_status ON {table_name}(lead_status)",
            f"CREATE INDEX idx_{table_name}_taken_at ON {table_name}(taken_at)",
            f"CREATE INDEX idx_{table_name}_follow_up_date ON {table_name}(follow_up_date)",
            f"CREATE INDEX idx_{table_name}_workspace_updated_at ON {table_name}(workspace_updated_at)"
        ]

        for index_sql in indexes:
            try:
                db.execute(index_sql)
            except sqlite3.Error as e:
                if current_app:
                    current_app.logger.warning(f"Could not create index: {e}")

        if current_app:
            current_app.logger.info(f"Created workspace table: {table_name}")
        return True

    except sqlite3.Error as e:
        if current_app:
            current_app.logger.error(f"Error creating workspace table {table_name}: {e}")
        db.rollback()
        return False

def copy_lead_to_workspace(db, professional_user_id: int, lead_id: int,
                          source_table: str, is_exclusive: bool = False) -> bool:
    """
    Copy a lead from source table to professional user's workspace
    Returns True if successful, False otherwise
    """
    try:
        # Ensure workspace table exists
        if not create_workspace_table(db, professional_user_id, source_table):
            # Table might already exist, check if lead is already in workspace
            workspace_table = get_workspace_table_name(professional_user_id, source_table)
            cursor = db.execute(
                f"SELECT id FROM {workspace_table} WHERE id = ?",
                (lead_id,)
            )
            if cursor.fetchone():
                if current_app:
                    current_app.logger.warning(f"Lead {lead_id} already in workspace {workspace_table}")
                return True

        workspace_table = get_workspace_table_name(professional_user_id, source_table)

        # Get all columns from source table
        cursor = db.execute(f"PRAGMA table_info({source_table})")
        source_columns = [col[1] for col in cursor.fetchall()]

        # Get columns from workspace table to find common columns
        cursor = db.execute(f"PRAGMA table_info({workspace_table})")
        workspace_source_columns = [col[1] for col in cursor.fetchall()]

        # Find common columns (intersection) - only copy columns that exist in both tables
        common_columns = [col for col in source_columns if col in workspace_source_columns]

        # Ensure we have at least the basic columns (id should always be common)
        if not common_columns:
            if current_app:
                current_app.logger.error(f"No common columns found between {source_table} and {workspace_table}")
            return False

        if current_app:
            current_app.logger.info(f"Source columns: {source_columns}")
            current_app.logger.info(f"Workspace source columns: {workspace_source_columns}")
            current_app.logger.info(f"Common columns: {common_columns}")

        # Build INSERT query with only common columns
        common_columns_str = ", ".join(common_columns)
        workspace_columns = [
            "professional_user_id", "taken_at", "is_exclusive_take",
            "lead_status", "contact_date", "lead_quality", "probability",
            "estimated_value", "next_action", "comment", "source_table",
            "premium_amount", "commission_rate", "commission_amount"
        ]
        all_columns = common_columns + workspace_columns
        columns_str = ", ".join(all_columns)

        # Build VALUES placeholders
        common_placeholders = ", ".join(["?"] * len(common_columns))
        workspace_placeholders = ", ".join(["?"] * len(workspace_columns))
        all_placeholders = common_placeholders + ", " + workspace_placeholders

        # Get lead data from source table (only common columns)
        cursor = db.execute(f"SELECT {common_columns_str} FROM {source_table} WHERE id = ?", (lead_id,))
        source_data = cursor.fetchone()

        if not source_data:
            if current_app:
                current_app.logger.error(f"Lead {lead_id} not found in source table {source_table}")
            return False

        # Get column types to identify DATE columns
        cursor = db.execute(f"PRAGMA table_info({source_table})")
        column_info = {col[1]: col[2] for col in cursor.fetchall()}

        # Convert sqlite3.Row to list and convert date columns
        source_data_list = list(source_data)
        for idx, col_name in enumerate(common_columns):
            # Check if this column is a DATE type or contains 'date' in its name
            col_type = column_info.get(col_name, '').upper()
            if 'DATE' in col_type or 'date' in col_name.lower():
                if source_data_list[idx] is not None:
                    source_data_list[idx] = convert_http_date_to_iso(source_data_list[idx])

        # Convert back to tuple
        source_data_tuple = tuple(source_data_list)

        # Prepare workspace data
        workspace_data = (
            professional_user_id,
            None,  # taken_at (will use DEFAULT)
            is_exclusive,
            'Nouveau',  # lead_status
            None,  # contact_date
            'medium',  # lead_quality
            0,  # probability
            0.0,  # estimated_value
            None,  # next_action
            None,  # comment
            source_table,  # source_table
            0.0,  # premium_amount
            0.0,  # commission_rate
            0.0   # commission_amount
        )

        # Insert into workspace
        insert_sql = f"""
            INSERT INTO {workspace_table} ({columns_str})
            VALUES ({all_placeholders})
        """

        all_data = source_data_tuple + workspace_data
        db.execute(insert_sql, all_data)
        db.commit()

        if current_app:
            current_app.logger.info(f"Copied lead {lead_id} to workspace {workspace_table}")
        return True

    except sqlite3.Error as e:
        if current_app:
            current_app.logger.error(f"Error copying lead to workspace: {e}")
        db.rollback()
        return False

def get_workspace_leads(db, professional_user_id: int, insurance_category: str = None,
                       filters: dict = None) -> list:
    """
    Get leads from professional user's workspace(s)
    If insurance_category is None, get leads from all categories
    """
    try:
        if insurance_category:
            # Get leads from specific category
            workspace_table = get_workspace_table_name(professional_user_id, insurance_category)
            return query_workspace_table(db, workspace_table, professional_user_id, filters)
        else:
            # Get leads from all categories
            all_leads = []
            cursor = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'assurance_%'"
            )
            insurance_categories = [row[0] for row in cursor.fetchall()]

            for category in insurance_categories:
                workspace_table = get_workspace_table_name(professional_user_id, category)
                if table_exists(db, workspace_table):
                    category_leads = query_workspace_table(db, workspace_table, professional_user_id, filters)
                    for lead in category_leads:
                        lead['insurance_category'] = category
                    all_leads.extend(category_leads)

            return all_leads

    except sqlite3.Error as e:
        if current_app:
            current_app.logger.error(f"Error getting workspace leads: {e}")
        return []

def query_workspace_table(db, workspace_table: str, professional_user_id: int,
                         filters: dict = None) -> list:
    """Query a specific workspace table with filters"""
    if not table_exists(db, workspace_table):
        return []

    query = f"SELECT * FROM {workspace_table} WHERE professional_user_id = ?"
    params = [professional_user_id]

    if filters:
        if filters.get('lead_status'):
            query += " AND lead_status = ?"
            params.append(filters['lead_status'])

        if filters.get('date_from'):
            query += " AND date(taken_at) >= ?"
            params.append(filters['date_from'])

        if filters.get('date_to'):
            query += " AND date(taken_at) <= ?"
            params.append(filters['date_to'])

    query += " ORDER BY taken_at DESC"

    # Get column info to identify DATE columns
    try:
        col_info_cursor = db.execute(f"PRAGMA table_info({workspace_table})")
        column_info = {col[1]: col[2] for col in col_info_cursor.fetchall()}
        date_columns = {col_name for col_name, col_type in column_info.items()
                        if 'DATE' in col_type.upper()}
    except:
        date_columns = set()

    # Create a temporary connection without PARSE_DECLTYPES to avoid auto date conversion errors
    # This prevents SQLite from trying to auto-convert malformed HTTP format dates
    try:
        # Get database path from the connection
        db_path = get_db_path()
        # Create temporary connection without PARSE_DECLTYPES
        temp_db = sqlite3.connect(db_path, detect_types=0)  # No auto type detection
        temp_db.row_factory = sqlite3.Row
        use_temp_connection = True
    except Exception as conn_error:
        if current_app:
            current_app.logger.warning(f"Could not create temp connection, using original: {conn_error}")
        # Fallback: use original connection but handle errors
        temp_db = db
        use_temp_connection = False

    try:
        cursor = temp_db.execute(query, params)
        columns = [description[0] for description in cursor.description]

        leads = []
        rows = cursor.fetchall()

        for row in rows:
            lead_dict = {}
            for idx, col_name in enumerate(columns):
                value = row[idx]

                # Convert HTTP format dates to ISO format for DATE columns
                if col_name in date_columns and value is not None:
                    value = convert_http_date_to_iso(value)

                lead_dict[col_name] = value

            leads.append(lead_dict)

        return leads

    except Exception as e:
        if current_app:
            current_app.logger.error(f"Error querying workspace table {workspace_table}: {e}")
        return []

    finally:
        # Close temporary connection if we created one
        if use_temp_connection and temp_db != db:
            temp_db.close()

def table_exists(db, table_name: str) -> bool:
    """Check if a table exists"""
    cursor = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None

def calculate_commission_amount(premium_amount, commission_rate):
    """Calculate commission amount from premium and rate"""
    try:
        premium = float(premium_amount or 0)
        rate = float(commission_rate or 0)
        return round(premium * (rate / 100), 2)
    except (ValueError, TypeError):
        return 0.0

def update_workspace_lead(db, professional_user_id: int, workspace_table: str,
                         lead_id: int, updates: dict, is_admin: bool = False) -> bool:
    """
    Update lead management data in workspace table
    Returns True if successful, False otherwise
    """
    try:
        if not table_exists(db, workspace_table):
            if current_app:
                current_app.logger.error(f"Workspace table {workspace_table} does not exist")
            return False

        # Get actual table columns to validate field names
        cursor = db.execute(f"PRAGMA table_info({workspace_table})")
        table_columns = [row[1] for row in cursor.fetchall()]  # Column name is at index 1

        if current_app:
            current_app.logger.debug(f"Table {workspace_table} columns: {table_columns}")

        # Build UPDATE query
        set_clauses = []
        params = []

        # Define allowed fields for updates (excluding system fields)
        system_fields = {
            'id', 'professional_user_id', 'taken_at', 'is_exclusive_take',
            'source_table', 'source_updated_at', 'workspace_updated_at',
            'commission_amount'  # This is calculated automatically
        }

        invalid_fields = []
        for field, value in updates.items():
            # Skip system fields
            if field in system_fields:
                invalid_fields.append(field)
                continue

            # Validate that field exists in table schema
            if field not in table_columns:
                if current_app:
                    current_app.logger.warning(f"Field '{field}' does not exist in table {workspace_table}. Available columns: {table_columns}")
                invalid_fields.append(field)
                continue

            # Field is valid, add to update
            set_clauses.append(f"{field} = ?")
            params.append(value)

        if invalid_fields and current_app:
            current_app.logger.warning(f"Skipping invalid fields: {invalid_fields}")

        # Auto-calculate commission_amount if premium_amount or commission_rate are being updated
        if 'premium_amount' in updates or 'commission_rate' in updates:
            # Get current values from database
            # For admin users, don't filter by professional_user_id
            if is_admin:
                cursor = db.execute(
                    f"SELECT premium_amount, commission_rate FROM {workspace_table} WHERE id = ?",
                    (lead_id,)
                )
            else:
                cursor = db.execute(
                    f"SELECT premium_amount, commission_rate FROM {workspace_table} WHERE professional_user_id = ? AND id = ?",
                    (professional_user_id, lead_id)
                )
            current_values = cursor.fetchone()

            if current_values:
                current_premium = updates.get('premium_amount', current_values[0])
                current_rate = updates.get('commission_rate', current_values[1])

                # Calculate new commission amount
                commission_amount = calculate_commission_amount(current_premium, current_rate)
                # Only add if commission_amount column exists
                if 'commission_amount' in table_columns:
                    set_clauses.append("commission_amount = ?")
                    params.append(commission_amount)

        if not set_clauses:
            if current_app:
                current_app.logger.warning(f"No valid fields to update. Updates provided: {list(updates.keys())}")
            return False

        # Add workspace_updated_at if column exists
        if 'workspace_updated_at' in table_columns:
            set_clauses.append("workspace_updated_at = CURRENT_TIMESTAMP")

        # Build WHERE clause
        # For admin users, update by id only; for regular users, check ownership
        if is_admin:
            params.append(lead_id)
            where_clause = "id = ?"
        else:
            params.extend([professional_user_id, lead_id])
            where_clause = "professional_user_id = ? AND id = ?"

        update_sql = f"""
            UPDATE {workspace_table}
            SET {', '.join(set_clauses)}
            WHERE {where_clause}
        """

        if current_app:
            current_app.logger.debug(f"Executing SQL: {update_sql} with params: {params}")

        db.execute(update_sql, params)
        db.commit()

        if current_app:
            current_app.logger.info(f"Updated lead {lead_id} in workspace {workspace_table} (admin={is_admin})")
        return True

    except sqlite3.Error as e:
        if current_app:
            current_app.logger.error(f"Error updating workspace lead: {e}", exc_info=True)
            import traceback
            current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        db.rollback()
        return False
    except Exception as e:
        if current_app:
            current_app.logger.error(f"Unexpected error in update_workspace_lead: {e}", exc_info=True)
            import traceback
            current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        db.rollback()
        return False

def migrate_taken_leads_to_workspace(db) -> dict:
    """
    Migrate existing taken_leads data to workspace tables
    Returns migration statistics
    """
    try:
        # Get all taken leads
        cursor = db.execute("""
            SELECT tl.*, p.company_name
            FROM taken_leads tl
            JOIN professional_users p ON tl.professional_user_id = p.id
            ORDER BY tl.professional_user_id, tl.lead_table_name
        """)

        taken_leads = cursor.fetchall()

        migration_stats = {
            'total_leads': len(taken_leads),
            'migrated_leads': 0,
            'failed_leads': 0,
            'professional_users': set(),
            'insurance_categories': set()
        }

        for taken_lead in taken_leads:
            professional_user_id = taken_lead['professional_user_id']
            lead_id = taken_lead['lead_id']
            lead_table_name = taken_lead['lead_table_name']
            is_exclusive = taken_lead['is_exclusive_take']

            migration_stats['professional_users'].add(professional_user_id)
            migration_stats['insurance_categories'].add(lead_table_name)

            try:
                # Copy lead to workspace
                success = copy_lead_to_workspace(db, professional_user_id, lead_id, lead_table_name, is_exclusive)

                if success:
                    # Update workspace with existing lead management data
                    workspace_table = get_workspace_table_name(professional_user_id, lead_table_name)

                    updates = {
                        'lead_status': taken_lead['lead_status'],
                        'contact_date': taken_lead['contact_date'],
                        'lead_quality': taken_lead['lead_quality'],
                        'probability': taken_lead['probability'],
                        'estimated_value': taken_lead['estimated_value'],
                        'next_action': taken_lead['next_action'],
                        'comment': taken_lead['comment']
                    }

                    update_workspace_lead(db, professional_user_id, workspace_table, lead_id, updates)

                    migration_stats['migrated_leads'] += 1
                    if current_app:
                        current_app.logger.info(f"Migrated lead {lead_id} from {lead_table_name} for user {professional_user_id}")
                else:
                    migration_stats['failed_leads'] += 1
                    if current_app:
                        current_app.logger.error(f"Failed to migrate lead {lead_id} from {lead_table_name} for user {professional_user_id}")

            except Exception as e:
                migration_stats['failed_leads'] += 1
                if current_app:
                    current_app.logger.error(f"Error migrating lead {lead_id}: {e}")

        # Convert sets to lists for JSON serialization
        migration_stats['professional_users'] = list(migration_stats['professional_users'])
        migration_stats['insurance_categories'] = list(migration_stats['insurance_categories'])

        return migration_stats

    except sqlite3.Error as e:
        if current_app:
            current_app.logger.error(f"Migration failed: {e}")
        return {'error': str(e)}

def migrate_workspace_tables_add_financial_columns(db):
    """
    Add financial columns to existing workspace tables
    """
    try:
        # Get all existing workspace tables
        cursor = db.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name LIKE 'workspace_%'
        """)

        workspace_tables = cursor.fetchall()

        if current_app:
            current_app.logger.info(f"Migrating {len(workspace_tables)} workspace tables")

        columns_added = 0

        for table_name, in workspace_tables:
            # Check existing columns
            cursor.execute(f"PRAGMA table_info({table_name})")
            existing_columns = [col[1] for col in cursor.fetchall()]

            # Add missing financial columns
            new_columns = [
                ('premium_amount', 'REAL DEFAULT 0.0'),
                ('commission_rate', 'REAL DEFAULT 0.0'),
                ('commission_amount', 'REAL DEFAULT 0.0')
            ]

            for col_name, col_def in new_columns:
                if col_name not in existing_columns:
                    try:
                        alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"
                        db.execute(alter_sql)
                        columns_added += 1

                        if current_app:
                            current_app.logger.info(f"Added column {col_name} to {table_name}")
                    except sqlite3.Error as e:
                        if current_app:
                            current_app.logger.warning(f"Column {col_name} might already exist in {table_name}: {e}")

        db.commit()

        if current_app:
            current_app.logger.info(f"Migration completed: {columns_added} columns added")

        return True

    except sqlite3.Error as e:
        if current_app:
            current_app.logger.error(f"Migration error: {e}")
        db.rollback()
        return False

def calculate_commission_amount(premium_amount: float, commission_rate: float) -> float:
    """
    Calculate commission amount based on premium amount and commission rate
    """
    if premium_amount and commission_rate:
        return premium_amount * (commission_rate / 100.0)
    return 0.0

@click.command('migrate-workspace-financial')
@with_appcontext
def migrate_workspace_financial_command():
    """Add financial columns to existing workspace tables"""
    db = get_db()

    if migrate_workspace_tables_add_financial_columns(db):
        click.echo("✓ Successfully added financial columns to workspace tables")
    else:
        click.echo("✗ Failed to migrate workspace tables")

def add_first_login_email_flag_column():
    """
    Add first_login_email_sent column to users table if it does not exist.
    """
    db_path = get_db_path()
    db = None
    try:
        db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = db.cursor()

        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'first_login_email_sent' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN first_login_email_sent INTEGER DEFAULT 0")
            db.commit()
            message = "Added first_login_email_sent column to users table"
        else:
            message = "first_login_email_sent column already exists on users table"

        if current_app:
            current_app.logger.info(message)
        else:
            print(f"✓ {message}")
        return True

    except sqlite3.Error as e:
        error_msg = f"Database error adding first_login_email_sent column: {e}"
        if current_app:
            current_app.logger.error(error_msg)
        else:
            print(f"✗ ERROR: {error_msg}")
        return False
    finally:
        if db:
            db.close()

@click.command('add-first-login-email-flag')
@with_appcontext
def add_first_login_email_flag_command():
    """Add first_login_email_sent column to users table."""
    if add_first_login_email_flag_column():
        click.echo("✓ first_login_email_sent column ensured on users table")
    else:
        click.echo("✗ Failed to add first_login_email_sent column")

def migrate_add_2fa_code():
    """
    Add two_fa_code column to professional_users table
    """
    db_path = get_db_path()
    db = None
    try:
        db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = db.cursor()

        # Check if column already exists
        cursor.execute("PRAGMA table_info(professional_users)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'two_fa_code' not in columns:
            cursor.execute("ALTER TABLE professional_users ADD COLUMN two_fa_code TEXT")
            db.commit()
            if current_app:
                current_app.logger.info("Added two_fa_code column to professional_users table")
            else:
                print("✓ Added two_fa_code column to professional_users table")
            return True
        else:
            if current_app:
                current_app.logger.info("two_fa_code column already exists")
            else:
                print("✓ two_fa_code column already exists")
            return True

    except sqlite3.Error as e:
        error_msg = f"Database error adding two_fa_code column: {e}"
        if current_app:
            current_app.logger.error(error_msg)
        else:
            print(f"✗ ERROR: {error_msg}")
        return False
    finally:
        if db:
            db.close()

@click.command('add-2fa-column')
@with_appcontext
def add_2fa_column_command():
    """Add two_fa_code column to professional_users table"""
    if migrate_add_2fa_code():
        click.echo("✓ Successfully added two_fa_code column to professional_users table")
    else:
        click.echo("✗ Failed to add two_fa_code column")

def migrate_assurance_auto_add_columns():
    """
    Add new columns to assurance_auto table for enhanced form fields.
    This migration preserves existing data and only adds missing columns.
    """
    db_path = get_db_path()
    db = None
    try:
        db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = db.cursor()

        # Check existing columns
        cursor.execute("PRAGMA table_info(assurance_auto)")
        existing_columns = [col[1] for col in cursor.fetchall()]

        # Define new columns to add
        new_columns = [
            ('nom', 'TEXT'),
            ('prenom', 'TEXT'),
            ('date_naissance', 'DATE'),
            ('date_permis', 'DATE'),
            ('date_mec', 'DATE'),
            ('type_plaque', 'TEXT'),
            ('immatriculation', 'TEXT'),
            ('nombre_places', 'INTEGER'),
            ('valeur_neuf', 'REAL')
        ]

        columns_added = 0
        for col_name, col_type in new_columns:
            if col_name not in existing_columns:
                try:
                    alter_sql = f"ALTER TABLE assurance_auto ADD COLUMN {col_name} {col_type}"
                    cursor.execute(alter_sql)
                    columns_added += 1
                    if current_app:
                        current_app.logger.info(f"Added column {col_name} to assurance_auto table")
                    else:
                        print(f"✓ Added column {col_name} to assurance_auto table")
                except sqlite3.Error as e:
                    if current_app:
                        current_app.logger.warning(f"Column {col_name} might already exist in assurance_auto: {e}")
                    else:
                        print(f"⚠ Column {col_name} might already exist: {e}")

        db.commit()

        if current_app:
            current_app.logger.info(f"Migration completed: {columns_added} columns added to assurance_auto")
        else:
            print(f"✓ Migration completed: {columns_added} columns added to assurance_auto")

        return True

    except sqlite3.Error as e:
        error_msg = f"Database error migrating assurance_auto table: {e}"
        if current_app:
            current_app.logger.error(error_msg)
        else:
            print(f"✗ ERROR: {error_msg}")
        if db:
            db.rollback()
        return False
    except Exception as e:
        error_msg = f"Unexpected error migrating assurance_auto table: {e}"
        if current_app:
            current_app.logger.error(error_msg)
        else:
            print(f"✗ ERROR: {error_msg}")
        if db:
            db.rollback()
        return False
    finally:
        if db:
            db.close()

@click.command('migrate-assurance-auto')
@with_appcontext
def migrate_assurance_auto_command():
    """Add new columns to assurance_auto table for enhanced form fields"""
    if migrate_assurance_auto_add_columns():
        click.echo("✓ Successfully migrated assurance_auto table")
    else:
        click.echo("✗ Failed to migrate assurance_auto table")

def migrate_workspace_tables_add_auto_columns(db):
    """
    Add new assurance_auto columns to existing workspace tables for assurance_auto category
    """
    try:
        # Get all existing workspace tables for assurance_auto
        cursor = db.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name LIKE 'workspace_%_assurance_auto'
        """)

        workspace_tables = cursor.fetchall()

        if current_app:
            current_app.logger.info(f"Migrating {len(workspace_tables)} assurance_auto workspace tables")
        else:
            print(f"Found {len(workspace_tables)} assurance_auto workspace tables to migrate")

        columns_added = 0

        # Define new columns to add (same as in assurance_auto table migration)
        new_columns = [
            ('nom', 'TEXT'),
            ('prenom', 'TEXT'),
            ('date_naissance', 'DATE'),
            ('date_permis', 'DATE'),
            ('date_mec', 'DATE'),
            ('type_plaque', 'TEXT'),
            ('immatriculation', 'TEXT'),
            ('nombre_places', 'INTEGER'),
            ('valeur_neuf', 'REAL')
        ]

        for table_name, in workspace_tables:
            # Check existing columns
            cursor.execute(f"PRAGMA table_info({table_name})")
            existing_columns = [col[1] for col in cursor.fetchall()]

            table_columns_added = 0
            for col_name, col_type in new_columns:
                if col_name not in existing_columns:
                    try:
                        alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"
                        db.execute(alter_sql)
                        columns_added += 1
                        table_columns_added += 1

                        if current_app:
                            current_app.logger.info(f"Added column {col_name} to {table_name}")
                        else:
                            print(f"✓ Added column {col_name} to {table_name}")
                    except sqlite3.Error as e:
                        if current_app:
                            current_app.logger.warning(f"Column {col_name} might already exist in {table_name}: {e}")
                        else:
                            print(f"⚠ Column {col_name} might already exist in {table_name}: {e}")

            if table_columns_added > 0:
                if current_app:
                    current_app.logger.info(f"Added {table_columns_added} columns to {table_name}")
                else:
                    print(f"✓ Added {table_columns_added} columns to {table_name}")

        db.commit()

        if current_app:
            current_app.logger.info(f"Migration completed: {columns_added} columns added to assurance_auto workspace tables")
        else:
            print(f"✓ Migration completed: {columns_added} columns added to assurance_auto workspace tables")

        return True

    except sqlite3.Error as e:
        error_msg = f"Database error migrating workspace tables: {e}"
        if current_app:
            current_app.logger.error(error_msg)
        else:
            print(f"✗ ERROR: {error_msg}")
        if db:
            db.rollback()
        return False
    except Exception as e:
        error_msg = f"Unexpected error migrating workspace tables: {e}"
        if current_app:
            current_app.logger.error(error_msg)
        else:
            print(f"✗ ERROR: {error_msg}")
        if db:
            db.rollback()
        return False

@click.command('migrate-workspace-auto-columns')
@with_appcontext
def migrate_workspace_auto_columns_command():
    """Add new columns to existing assurance_auto workspace tables"""
    db = get_db()
    if migrate_workspace_tables_add_auto_columns(db):
        click.echo("✓ Successfully migrated assurance_auto workspace tables")
    else:
        click.echo("✗ Failed to migrate assurance_auto workspace tables")

@click.command('set-2fa-code')
@click.argument('username')
@click.argument('code')
@with_appcontext
def set_2fa_code_command(username, code):
    """
    Set 2FA code for a professional user
    Example: flask set-2fa-code mybroker 123456
    """
    db = get_db()
    try:
        # Validate code is 6 digits
        if not code.isdigit() or len(code) != 6:
            click.echo("✗ ERROR: 2FA code must be exactly 6 digits")
            return

        db.execute('UPDATE professional_users SET two_fa_code = ? WHERE username = ?', (code, username))
        db.commit()
        click.echo(f"✓ Successfully set 2FA code for user '{username}'")
    except sqlite3.Error as e:
        click.echo(f"✗ ERROR: Database error: {e}")

@click.command('remove-2fa-code')
@click.argument('username')
@with_appcontext
def remove_2fa_code_command(username):
    """
    Remove 2FA code for a professional user
    Example: flask remove-2fa-code mybroker
    """
    db = get_db()
    try:
        db.execute('UPDATE professional_users SET two_fa_code = NULL WHERE username = ?', (username,))
        db.commit()
        click.echo(f"✓ Successfully removed 2FA code for user '{username}'")
    except sqlite3.Error as e:
        click.echo(f"✗ ERROR: Database error: {e}")

def init_app(app):
    """
    Register database functions with the Flask app.
    """
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(add_prof_user_command)
    app.cli.add_command(migrate_workspace_command)
    app.cli.add_command(migrate_workspace_financial_command)
    app.cli.add_command(add_2fa_column_command)
    app.cli.add_command(set_2fa_code_command)
    app.cli.add_command(remove_2fa_code_command)
    app.cli.add_command(add_first_login_email_flag_command)
    app.cli.add_command(migrate_assurance_auto_command)
    app.cli.add_command(migrate_workspace_auto_columns_command)
