"""
Database Models and Schema for Insurance Comparator
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional
import json
import os

DATABASE_PATH = os.path.join(os.path.dirname(__file__), '..', 'insurance_data.db')


def get_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialize database with all required tables"""
    conn = get_connection()
    cursor = conn.cursor()

    # Table 0: Users - stores user accounts
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME
        )
    ''')

    # Table 1: Form Submissions - stores user form submissions with all details
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS form_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,

            -- Vehicle Information
            marque TEXT,
            modele TEXT,
            carburant TEXT,
            nombre_places INTEGER,
            puissance_fiscale INTEGER,
            date_mec TEXT,
            type_plaque TEXT,
            immatriculation TEXT,
            valeur_neuf REAL NOT NULL,
            valeur_actuelle REAL NOT NULL,

            -- Personal Information
            nom TEXT,
            prenom TEXT,
            telephone TEXT,
            email TEXT,
            date_naissance TEXT,
            date_permis TEXT,
            ville TEXT,
            agent_key TEXT,
            assureur_actuel TEXT,
            consent BOOLEAN,

            -- Metadata
            submission_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,

            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Table 2: Scraper Results - stores results from scrapers for each form submission
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scraper_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            form_submission_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            provider_code TEXT NOT NULL,
            provider_name TEXT NOT NULL,

            -- Result data
            raw_response TEXT,
            plan_count INTEGER DEFAULT 0,
            fetch_time REAL,
            status TEXT DEFAULT 'success',
            error_message TEXT,

            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (form_submission_id) REFERENCES form_submissions(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Table 1: User Requests - stores user input parameters (kept for backward compatibility)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            valeur_neuf REAL NOT NULL,
            valeur_venale REAL NOT NULL,
            request_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            total_fetch_time REAL,
            status TEXT DEFAULT 'pending'
        )
    ''')
    
    # Table 2: Provider Responses - stores raw response from each provider
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS provider_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            provider_name TEXT NOT NULL,
            provider_code TEXT NOT NULL,
            raw_response TEXT,
            fetch_time REAL,
            status TEXT DEFAULT 'success',
            error_message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (request_id) REFERENCES user_requests(id)
        )
    ''')
    
    # Table 3: Insurance Plans - stores individual plan details
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS insurance_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            response_id INTEGER NOT NULL,
            request_id INTEGER NOT NULL,
            provider_name TEXT NOT NULL,
            plan_name TEXT NOT NULL,
            plan_code TEXT,
            
            -- Annual pricing
            prime_net_annual REAL,
            taxes_annual REAL,
            prime_total_annual REAL,
            
            -- Semi-annual pricing (6 months)
            prime_net_semi_annual REAL,
            taxes_semi_annual REAL,
            prime_total_semi_annual REAL,
            
            -- Additional fees
            cnpac REAL DEFAULT 0,
            accessoires REAL DEFAULT 0,
            timbre REAL DEFAULT 0,
            
            -- Metadata
            is_promoted BOOLEAN DEFAULT 0,
            is_eligible BOOLEAN DEFAULT 1,
            color TEXT,
            plan_order INTEGER,
            
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (response_id) REFERENCES provider_responses(id),
            FOREIGN KEY (request_id) REFERENCES user_requests(id)
        )
    ''')
    
    # Table 4: Plan Guarantees - stores guarantees/coverages for each plan
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS plan_guarantees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            guarantee_name TEXT NOT NULL,
            guarantee_code TEXT,
            description TEXT,

            -- Coverage details
            capital_guarantee REAL,
            franchise TEXT,
            prime_annual REAL DEFAULT 0,

            -- Status flags
            is_included BOOLEAN DEFAULT 1,
            is_obligatory BOOLEAN DEFAULT 0,
            is_optional BOOLEAN DEFAULT 0,

            -- For selectable options (like Bris de glace amounts)
            has_options BOOLEAN DEFAULT 0,
            options_json TEXT,
            selected_option TEXT,

            display_order INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (plan_id) REFERENCES insurance_plans(id)
        )
    ''')

    # Table 5: Selectable Fields - stores selectable field definitions for plans
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS selectable_fields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            field_name TEXT NOT NULL,
            field_title TEXT,
            field_order INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (plan_id) REFERENCES insurance_plans(id)
        )
    ''')

    # Table 6: Selectable Options - stores options for each selectable field
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS selectable_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field_id INTEGER NOT NULL,
            option_id TEXT NOT NULL,
            option_label TEXT NOT NULL,
            is_default BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (field_id) REFERENCES selectable_fields(id)
        )
    ''')

    # Table 7: Option Combinations Pricing - stores pricing for different option combinations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS option_combinations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            combination_key TEXT NOT NULL,
            combination_params TEXT,

            -- Annual pricing
            prime_net_annual REAL,
            taxes_annual REAL,
            prime_total_annual REAL,

            -- Semi-annual pricing
            prime_net_semi_annual REAL,
            taxes_semi_annual REAL,
            prime_total_semi_annual REAL,

            is_default BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (plan_id) REFERENCES insurance_plans(id)
        )
    ''')

    # Create indexes for better query performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_form_submissions_user ON form_submissions(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_scraper_results_form ON scraper_results(form_submission_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_scraper_results_user ON scraper_results(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_requests_timestamp ON user_requests(request_timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_responses_request ON provider_responses(request_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_plans_response ON insurance_plans(response_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_guarantees_plan ON plan_guarantees(plan_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_fields_plan ON selectable_fields(plan_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_combinations_plan ON option_combinations(plan_id)')

    conn.commit()
    conn.close()
    print("Database initialized successfully")


class DatabaseManager:
    """Manager class for database operations"""

    # ============ User Management ============
    @staticmethod
    def create_user(name: str, email: str, password: str, is_admin: bool = False) -> int:
        """Create a new user and return its ID"""
        import hashlib
        conn = get_connection()
        cursor = conn.cursor()

        # Hash the password
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        try:
            cursor.execute('''
                INSERT INTO users (name, email, password, is_admin)
                VALUES (?, ?, ?, ?)
            ''', (name, email, password_hash, is_admin))

            user_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return user_id
        except sqlite3.IntegrityError:
            conn.close()
            return None  # Email already exists

    @staticmethod
    def get_user_by_email(email: str) -> Optional[Dict]:
        """Get user by email"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    @staticmethod
    def verify_user(email: str, password: str) -> Optional[Dict]:
        """Verify user credentials and return user data if valid"""
        import hashlib
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password_hash))
        row = cursor.fetchone()

        if row:
            # Update last login
            cursor.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (row['id'],))
            conn.commit()

        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_all_users(exclude_admin: bool = False) -> List[Dict]:
        """Get all users"""
        conn = get_connection()
        cursor = conn.cursor()

        if exclude_admin:
            cursor.execute('SELECT id, name, email, created_at, last_login FROM users WHERE is_admin = 0 ORDER BY created_at DESC')
        else:
            cursor.execute('SELECT id, name, email, is_admin, created_at, last_login FROM users ORDER BY created_at DESC')

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ============ Form Submission Management ============
    @staticmethod
    def save_form_submission(user_id: int, form_data: dict, ip_address: str = None, user_agent: str = None) -> int:
        """Save form submission and return its ID"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO form_submissions
            (user_id, marque, modele, carburant, nombre_places, puissance_fiscale,
             date_mec, type_plaque, immatriculation, valeur_neuf, valeur_actuelle,
             nom, prenom, telephone, email, date_naissance, date_permis, ville,
             agent_key, assureur_actuel, consent, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            form_data.get('marque'),
            form_data.get('modele'),
            form_data.get('carburant'),
            form_data.get('nombre_places'),
            form_data.get('puissance_fiscale'),
            form_data.get('date_mec'),
            form_data.get('type_plaque'),
            form_data.get('immatriculation'),
            form_data.get('valeur_neuf'),
            form_data.get('valeur_actuelle'),
            form_data.get('nom'),
            form_data.get('prenom'),
            form_data.get('telephone'),
            form_data.get('email'),
            form_data.get('date_naissance'),
            form_data.get('date_permis'),
            form_data.get('ville'),
            form_data.get('agent_key'),
            form_data.get('assureur_actuel'),
            form_data.get('consent'),
            ip_address,
            user_agent
        ))

        submission_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return submission_id

    @staticmethod
    def save_scraper_result(form_submission_id: int, user_id: int, provider_code: str,
                           provider_name: str, raw_response: dict, plan_count: int,
                           fetch_time: float, status: str = 'success', error_message: str = None) -> int:
        """Save scraper result and return its ID"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO scraper_results
            (form_submission_id, user_id, provider_code, provider_name, raw_response,
             plan_count, fetch_time, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            form_submission_id, user_id, provider_code, provider_name,
            json.dumps(raw_response, ensure_ascii=False) if raw_response else None,
            plan_count, fetch_time, status, error_message
        ))

        result_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return result_id

    @staticmethod
    def get_user_submissions(user_id: int, limit: int = 50) -> List[Dict]:
        """Get form submissions for a user"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM form_submissions
            WHERE user_id = ?
            ORDER BY submission_timestamp DESC
            LIMIT ?
        ''', (user_id, limit))

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def create_request(valeur_neuf: float, valeur_venale: float,
                       ip_address: str = None, user_agent: str = None) -> int:
        """Create a new user request and return its ID"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO user_requests (valeur_neuf, valeur_venale, ip_address, user_agent)
            VALUES (?, ?, ?, ?)
        ''', (valeur_neuf, valeur_venale, ip_address, user_agent))
        
        request_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return request_id
    
    @staticmethod
    def update_request_status(request_id: int, status: str, fetch_time: float = None):
        """Update request status and fetch time"""
        conn = get_connection()
        cursor = conn.cursor()
        
        if fetch_time:
            cursor.execute('''
                UPDATE user_requests SET status = ?, total_fetch_time = ? WHERE id = ?
            ''', (status, fetch_time, request_id))
        else:
            cursor.execute('''
                UPDATE user_requests SET status = ? WHERE id = ?
            ''', (status, request_id))
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def save_provider_response(request_id: int, provider_name: str, provider_code: str,
                                raw_response: dict, fetch_time: float, 
                                status: str = 'success', error_message: str = None) -> int:
        """Save provider response and return its ID"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO provider_responses 
            (request_id, provider_name, provider_code, raw_response, fetch_time, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (request_id, provider_name, provider_code, 
              json.dumps(raw_response, ensure_ascii=False) if raw_response else None,
              fetch_time, status, error_message))
        
        response_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return response_id
    
    @staticmethod
    def save_insurance_plan(response_id: int, request_id: int, plan_data: dict) -> int:
        """Save insurance plan and return its ID"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO insurance_plans 
            (response_id, request_id, provider_name, plan_name, plan_code,
             prime_net_annual, taxes_annual, prime_total_annual,
             prime_net_semi_annual, taxes_semi_annual, prime_total_semi_annual,
             cnpac, accessoires, timbre, is_promoted, is_eligible, color, plan_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            response_id, request_id,
            plan_data.get('provider_name'),
            plan_data.get('plan_name'),
            plan_data.get('plan_code'),
            plan_data.get('prime_net_annual'),
            plan_data.get('taxes_annual'),
            plan_data.get('prime_total_annual'),
            plan_data.get('prime_net_semi_annual'),
            plan_data.get('taxes_semi_annual'),
            plan_data.get('prime_total_semi_annual'),
            plan_data.get('cnpac', 0),
            plan_data.get('accessoires', 0),
            plan_data.get('timbre', 0),
            plan_data.get('is_promoted', False),
            plan_data.get('is_eligible', True),
            plan_data.get('color'),
            plan_data.get('plan_order', 0)
        ))
        
        plan_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return plan_id
    
    @staticmethod
    def save_plan_guarantee(plan_id: int, guarantee_data: dict) -> int:
        """Save plan guarantee and return its ID"""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO plan_guarantees 
            (plan_id, guarantee_name, guarantee_code, description,
             capital_guarantee, franchise, prime_annual,
             is_included, is_obligatory, is_optional,
             has_options, options_json, selected_option, display_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            plan_id,
            guarantee_data.get('guarantee_name'),
            guarantee_data.get('guarantee_code'),
            guarantee_data.get('description'),
            guarantee_data.get('capital_guarantee'),
            guarantee_data.get('franchise'),
            guarantee_data.get('prime_annual', 0),
            guarantee_data.get('is_included', True),
            guarantee_data.get('is_obligatory', False),
            guarantee_data.get('is_optional', False),
            guarantee_data.get('has_options', False),
            json.dumps(guarantee_data.get('options', [])) if guarantee_data.get('options') else None,
            guarantee_data.get('selected_option'),
            guarantee_data.get('display_order', 0)
        ))
        
        guarantee_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return guarantee_id
    
    @staticmethod
    def save_selectable_field(plan_id: int, field_name: str, field_title: str, field_order: int = 0) -> int:
        """Save selectable field and return its ID"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO selectable_fields (plan_id, field_name, field_title, field_order)
            VALUES (?, ?, ?, ?)
        ''', (plan_id, field_name, field_title, field_order))

        field_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return field_id

    @staticmethod
    def save_selectable_option(field_id: int, option_id: str, option_label: str, is_default: bool = False) -> int:
        """Save selectable option and return its ID"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO selectable_options (field_id, option_id, option_label, is_default)
            VALUES (?, ?, ?, ?)
        ''', (field_id, option_id, option_label, is_default))

        option_id_pk = cursor.lastrowid
        conn.commit()
        conn.close()
        return option_id_pk

    @staticmethod
    def save_option_combination(plan_id: int, combination_key: str, combination_params: str,
                               pricing_data: dict, is_default: bool = False) -> int:
        """Save option combination pricing and return its ID"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO option_combinations
            (plan_id, combination_key, combination_params,
             prime_net_annual, taxes_annual, prime_total_annual,
             prime_net_semi_annual, taxes_semi_annual, prime_total_semi_annual,
             is_default)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            plan_id, combination_key, combination_params,
            pricing_data.get('prime_net_annual'),
            pricing_data.get('taxes_annual'),
            pricing_data.get('prime_total_annual'),
            pricing_data.get('prime_net_semi_annual'),
            pricing_data.get('taxes_semi_annual'),
            pricing_data.get('prime_total_semi_annual'),
            is_default
        ))

        combination_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return combination_id

    @staticmethod
    def get_option_combinations(plan_id: int) -> List[Dict]:
        """Get all option combinations for a plan"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM option_combinations
            WHERE plan_id = ?
            ORDER BY is_default DESC
        ''', (plan_id,))

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_request_history(limit: int = 50) -> List[Dict]:
        """Get recent request history"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM user_requests
            ORDER BY request_timestamp DESC
            LIMIT ?
        ''', (limit,))

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]


# Initialize database on module import
if __name__ == "__main__":
    init_database()
