import os
import sqlite3
import json
import time # Added for exponential backoff in API calls
import secrets # For generating secure OTP codes
from flask import send_from_directory
from datetime import datetime, date, timedelta # Ensure date and timedelta are imported
from flask import (
    Flask, render_template, request, redirect, url_for, flash, session, g, current_app, jsonify, send_file
)
from werkzeug.security import check_password_hash, generate_password_hash
import requests
from functools import wraps # For decorators
import statistics # For calculating the average
import base64
import random # Added for random selection
import string
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# For Google OAuth
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# Import Mail, Message from Flask-Mail
from flask_mail import Mail, Message

import database # Your custom database module

# SECURITY IMPORTS - Added for enhanced security
from security_config import (
    FORM_VALIDATION_RULES,
    InputValidator,
    secure_session_config,
    setup_security_logging,
    rate_limit
)
from security_middleware import (
    init_security_middleware,
    create_secure_form_handler,
    secure_google_oauth_validation
)

# ---------- Rate Limiter and Bot Detection for AI API (Free Plan) ----------
from collections import defaultdict
import re

class SimpleRateLimiter:
    """Simple in-memory rate limiter to prevent exceeding API limits"""
    def __init__(self, max_requests=12, window_seconds=60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)

    def is_allowed(self, identifier=None):
        """Check if request is allowed. If identifier is None, checks global limit."""
        now = datetime.now()
        window_start = now - timedelta(seconds=self.window_seconds)

        # For global limiter, use 'global' as identifier
        key = identifier if identifier else 'global'

        # Clean old requests outside the window
        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if req_time > window_start
        ]

        # Check if limit exceeded
        if len(self.requests[key]) >= self.max_requests:
            return False

        # Add current request timestamp
        self.requests[key].append(now)
        return True

    def get_remaining_requests(self, identifier=None):
        """Get number of remaining requests"""
        now = datetime.now()
        window_start = now - timedelta(seconds=self.window_seconds)
        key = identifier if identifier else 'global'

        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if req_time > window_start
        ]

        return max(0, self.max_requests - len(self.requests[key]))

def detect_bot(user_agent, ip_address, referer, db=None):
    """
    Detect if request is from a bot based on various patterns.
    Returns (is_bot, reason)
    """
    reasons = []
    is_bot = False

    # Check user agent for bot patterns
    if user_agent:
        bot_patterns = [
            r'bot', r'crawler', r'spider', r'scraper', r'curl', r'wget',
            r'python-requests', r'go-http-client', r'java/', r'postman',
            r'httpie', r'insomnia', r'apache-httpclient', r'okhttp',
            r'node-fetch', r'axios', r'urllib', r'scrapy', r'requests/',
            r'python/', r'go/', r'java/', r'ruby/', r'perl/', r'php/'
        ]
        user_agent_lower = user_agent.lower()
        for pattern in bot_patterns:
            if re.search(pattern, user_agent_lower):
                reasons.append(f"Bot pattern in User-Agent: {pattern}")
                is_bot = True
                break

    # Check for missing or suspicious user agent
    if not user_agent or user_agent.strip() == '':
        reasons.append("Missing User-Agent")
        is_bot = True

    # Check for suspicious referer patterns
    if referer:
        suspicious_referers = ['localhost', '127.0.0.1', 'test', 'example.com', 'http://']
        referer_lower = referer.lower()
        if any(sus in referer_lower for sus in suspicious_referers) and 'mesassurances.ma' not in referer_lower:
            reasons.append(f"Suspicious referer: {referer}")
            # Don't mark as bot for referer alone, just log

    return is_bot, "; ".join(reasons) if reasons else None

def get_client_info(request):
    """Extract client information from request"""
    # Get real IP (handles proxies)
    ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    if ip_address:
        ip_address = ip_address.split(',')[0].strip()
    else:
        ip_address = request.remote_addr or 'unknown'

    user_agent = request.headers.get('User-Agent', '')
    referer = request.headers.get('Referer', '')

    return ip_address, user_agent, referer

# Create rate limiters for free plan (15 RPM limit)
# Global limiter: 3 req/min (conservative to stay well under Gemini's 15 RPM limit)
global_rate_limiter = SimpleRateLimiter(max_requests=3, window_seconds=60)

# Per-IP limiter: 2 req/min (prevents abuse)
ip_rate_limiter = SimpleRateLimiter(max_requests=2, window_seconds=60)

# ---------- AMC Individuelle calculation data (moved from frontend) ----------
AMC_AGE_BRACKETS = [
    {"label": "0-9", "min": 0, "max": 9},
    {"label": "10-26", "min": 10, "max": 26},  # extended for enfants
    {"label": "20-24", "min": 20, "max": 24},
    {"label": "25-29", "min": 25, "max": 29},
    {"label": "30-34", "min": 30, "max": 34},
    {"label": "35-39", "min": 35, "max": 39},
    {"label": "40-44", "min": 40, "max": 44},
    {"label": "45-49", "min": 45, "max": 49},
    {"label": "50-54", "min": 50, "max": 54},
    {"label": "55-59", "min": 55, "max": 59},
]

AMC_PLAN_KEYS = ["e80", "e90", "e95", "o80", "o90", "o95", "i80", "i90", "i95"]
AMC_FREQUENCIES = ["annuel", "semestrielle", "trimestrielle", "mensuelle"]

AMC_INSURANCE_DATA = [
    {"age": "0-9", "e80": 705.71, "e90": 793.49, "e95": 837.38, "o80": 1027.95, "o90": 1246.55, "o95": 1220.84, "i80": 1097.25, "i90": 1234.14, "i95": 1302.84, "deces": 0.0},
    {"age": "10-19", "e80": 483.95, "e90": 545.34, "e95": 574.69, "o80": 706.07, "o90": 793.49, "o95": 837.38, "i80": 753.26, "i90": 847.67, "i95": 893.87, "deces": 0.0},
    {"age": "20-24", "e80": 1886.12, "e90": 2113.65, "e95": 2226.84, "o80": 2629.94, "o90": 2944.1, "o95": 3101.18, "i80": 2979.9, "i90": 3328.71, "i95": 3503.12, "deces": 137.4},
    {"age": "25-29", "e80": 1886.12, "e90": 2113.65, "e95": 2226.84, "o80": 2629.94, "o90": 2944.1, "o95": 3101.18, "i80": 2979.9, "i90": 3328.71, "i95": 3503.12, "deces": 144.4},
    {"age": "30-34", "e80": 2161.01, "e90": 2420.88, "e95": 2551.4, "o80": 3013.4, "o90": 3373.76, "o95": 3552.78, "i80": 3414.18, "i90": 3813.81, "i95": 4013.63, "deces": 149.4},
    {"age": "35-39", "e80": 2160.55, "e90": 2419.98, "e95": 2550.49, "o80": 3012.49, "o90": 3372.85, "o95": 3551.88, "i80": 3413.28, "i90": 3812.91, "i95": 4012.72, "deces": 184.3},
    {"age": "40-44", "e80": 2422.04, "e90": 2713.1, "e95": 2858.63, "o80": 3377.22, "o90": 3780.32, "o95": 3981.29, "i80": 3825.36, "i90": 4273.5, "i95": 4497.57, "deces": 241.4},
    {"age": "45-49", "e80": 2422.04, "e90": 2713.1, "e95": 2858.63, "o80": 3377.22, "o90": 3689.92, "o95": 3981.29, "i80": 3825.36, "i90": 4273.5, "i95": 4497.57, "deces": 341.4},
    {"age": "50-54", "e80": 2815.89, "e90": 3155.28, "e95": 3324.09, "o80": 3926.64, "o90": 4395.93, "o95": 4630.4, "i80": 4448.88, "i90": 4969.97, "i95": 5229.84, "deces": 523.4},
    {"age": "55-59", "e80": 2815.89, "e90": 3155.46, "e95": 3324.09, "o80": 3927.0, "o90": 4395.93, "o95": 4630.4, "i80": 4449.06, "i90": 4969.97, "i95": 5229.84, "deces": 775.4}
]

AMC_SEM_FACTORS = {
    "e80": 0.53, "e90": 0.521, "e95": 0.521,
    "o80": 0.521, "o90": 0.521, "o95": 0.522,
    "i80": 0.521, "i90": 0.522, "i95": 0.522
}
AMC_TRI_FACTORS = {
    "e80": 0.2622, "e90": 0.263, "e95": 0.263,
    "o80": 0.263, "o90": 0.263, "o95": 0.263,
    "i80": 0.263, "i90": 0.264, "i95": 0.263
}
AMC_MENS_FACTORS = {
    "e80": 0.091, "e90": 0.091, "e95": 0.091,
    "o80": 0.091, "o90": 0.091, "o95": 0.091,
    "i80": 0.091, "i90": 0.091, "i95": 0.091
}


# Data for blog posts and outils pages (Skipped as requested)
BLOG_AND_OUTILS_DATA = [
    {
        "slug": "cnss-maroc",
        "title": "CNSS Maroc : Le Guide Complet 2025 (Services, Prestations, Démarches)",
        "url": "/blog/cnss-maroc",
        "image_filename": "images/cnss-maroc.jpg",
        "alt_text": "CNSS Maroc : Le Guide Complet 2025 (Services, Prestations, Démarches)",
        "description": "Le guide complet de la CNSS au Maroc pour 2025. Découvrez tous les services, les prestations (retraite, AMO, indemnités), et les démarches en ligne sur le portail MACNSS.",
        "badge_text": "Guide Complet",
        "badge_color_class": "!bg-indigo-100 !text-indigo-700",
        "category": "blog",
        "template_file": "blog/cnss-maroc.html"
    },
    {
        "slug": "maroc-assistance-guide-complet",
        "title": "Maroc Assistance : Guide Complet des Services d'Assistance Assurance",
        "url": "/blog/maroc-assistance-guide-complet",
        "image_filename": "images/maroc-assistance-guide.jpg",
        "alt_text": "Maroc Assistance : Guide Complet des Services d'Assistance Assurance",
        "description": "Découvrez tout sur les services d'assistance assurance au Maroc : types de services, principales compagnies (MAI, AXA, Mondial), tarifs et comment choisir.",
        "badge_text": "Guide Complet",
        "badge_color_class": "!bg-blue-100 !text-blue-700",
        "category": "blog",
        "template_file": "blog/maroc-assistance-guide-complet.html"
    },
    {
        "slug": "maroc-assistance-internationale-mai",
        "title": "Maroc Assistance Internationale (MAI) : Services et Tarifs 2025",
        "url": "/blog/maroc-assistance-internationale-mai",
        "image_filename": "images/mai-assistance-services.jpg",
        "alt_text": "Maroc Assistance Internationale (MAI) : Services et Tarifs 2025",
        "description": "Découvrez Maroc Assistance Internationale (MAI) : leader de l'assistance au Maroc depuis 1976. Services, tarifs, produits Injad Achamil et Injad Monde, contact.",
        "badge_text": "MAI Assistance",
        "badge_color_class": "!bg-purple-100 !text-purple-700",
        "category": "blog",
        "template_file": "blog/maroc-assistance-internationale-mai.html"
    },
    {
        "slug": "axa-assistance-maroc-numeros-urgence",
        "title": "AXA Assistance Maroc : Numéros d'Urgence et Services 24h/24",
        "url": "/blog/axa-assistance-maroc-numeros-urgence",
        "image_filename": "images/axa-assistance-maroc.jpg",
        "alt_text": "AXA Assistance Maroc : Numéros d'Urgence et Services 24h/24",
        "description": "Découvrez AXA Assistance Maroc : numéros d'urgence 24h/24, services d'assistance médicale, voyage et technique. Contact, tarifs et garanties 2025.",
        "badge_text": "AXA Assistance",
        "badge_color_class": "!bg-emerald-100 !text-emerald-700",
        "category": "blog",
        "template_file": "blog/axa-assistance-maroc-numeros-urgence.html"
    },
    {
        "slug": "amc-groupe-vs-mutuelle",
        "title": "AMC Groupe vs Mutuelle Individuelle : Quel choix pour votre entreprise au Maroc ?",
        "url": "/blog/amc-groupe-vs-mutuelle",
        "image_filename": "images/amc-groupe-vs-mutuelle.jpg",
        "alt_text": "Comparatif AMC Groupe vs mutuelle individuelle",
        "description": "Analyse des coûts, garanties et obligations RH pour décider entre une AMC collective et des contrats individuels.",
        "badge_text": "AMC Groupe",
        "badge_color_class": "!bg-purple-100 !text-purple-700",
        "category": "blog",
        "template_file": "blog/amc-groupe-vs-mutuelle.html"
    },
    {
        "slug": "negocier-amc-groupe",
        "title": "Négocier votre AMC Groupe : Méthode & Checklists",
        "url": "/blog/negocier-amc-groupe",
        "image_filename": "images/negocier-amc-groupe.jpg",
        "alt_text": "Guide négociation AMC Groupe",
        "description": "Processus en 5 étapes pour analyser la sinistralité, rédiger un cahier des charges et challenger les assureurs santé collective.",
        "badge_text": "RH & People",
        "badge_color_class": "!bg-rose-100 !text-rose-700",
        "category": "blog",
        "template_file": "blog/negocier-amc-groupe.html"
    },
    {
        "slug": "amc-groupe-partage-cout",
        "title": "AMC Groupe : Optimiser le partage employeur / salarié",
        "url": "/blog/amc-groupe-partage-cout",
        "image_filename": "images/amc-groupe-partage-cout.jpg",
        "alt_text": "Partage employeur salarié AMC",
        "description": "Scénarios 50/50, 70/30 et 80/20, fiscalité CNSS/IR et communication RH pour financer la mutuelle collective.",
        "badge_text": "Budget RH",
        "badge_color_class": "!bg-amber-100 !text-amber-700",
        "category": "blog",
        "template_file": "blog/amc-groupe-partage-cout.html"
    },
    {
        "slug": "amc-groupe-marque-employeur",
        "title": "AMC Groupe : l'arme secrète de votre marque employeur",
        "url": "/blog/amc-groupe-marque-employeur",
        "image_filename": "images/amc-groupe-marque-employeur.jpg",
        "alt_text": "AMC Groupe et marque employeur",
        "description": "Comment transformer la mutuelle collective en avantage compétitif : onboarding, communication interne et KPI RH.",
        "badge_text": "Marque Employeur",
        "badge_color_class": "!bg-fuchsia-100 !text-fuchsia-700",
        "category": "blog",
        "template_file": "blog/amc-groupe-marque-employeur.html"
    },
    {
        "slug": "rc-pro-vs-rc-exploitation",
        "title": "RC Pro vs RC Exploitation : comprendre les différences en 2025",
        "url": "/blog/rc-pro-vs-rc-exploitation",
        "image_filename": "images/rc-pro-vs-rc-exploitation.jpg",
        "alt_text": "Comparatif RC Pro et RC Exploitation",
        "description": "Garanties, sinistres couverts et cas métiers pour combiner RC professionnelle et RC exploitation au Maroc.",
        "badge_text": "RC Pro",
        "badge_color_class": "!bg-emerald-100 !text-emerald-700",
        "category": "blog",
        "template_file": "blog/rc-pro-vs-rc-exploitation.html"
    },
    {
        "slug": "rc-pro-obligatoire-maroc",
        "title": "RC Pro obligatoire au Maroc : professions et contrôles 2025",
        "url": "/blog/rc-pro-obligatoire-maroc",
        "image_filename": "images/rc-pro-obligatoire-maroc.jpg",
        "alt_text": "Professions à RC Pro obligatoire",
        "description": "Liste des métiers réglementés, plafonds exigés et pièces à fournir pour obtenir une attestation RC professionnelle.",
        "badge_text": "Conformité",
        "badge_color_class": "!bg-sky-100 !text-sky-700",
        "category": "blog",
        "template_file": "blog/rc-pro-obligatoire-maroc.html"
    },
    {
        "slug": "rc-pro-plafond-garantie",
        "title": "Choisir le plafond de votre Responsabilité Civile Professionnelle",
        "url": "/blog/rc-pro-plafond-garantie",
        "image_filename": "images/rc-pro-plafond-garantie.jpg",
        "alt_text": "Choisir son plafond RC Pro",
        "description": "Méthode pas à pas pour sélectionner 2, 5 ou 10 M MAD de couverture selon vos contrats clients et votre exposition.",
        "badge_text": "Gestion des risques",
        "badge_color_class": "!bg-amber-100 !text-amber-700",
        "category": "blog",
        "template_file": "blog/rc-pro-plafond-garantie.html"
    },
    {
        "slug": "comprendre-rc-pro",
        "title": "Comprendre la Responsabilité Civile Professionnelle au Maroc",
        "url": "/blog/comprendre-rc-pro",
        "image_filename": "images/comprendre-rc-pro.jpg",
        "alt_text": "Guide pour comprendre la RC Pro",
        "description": "Décryptage des garanties, exclusions, extensions et démarches pour sécuriser vos contrats B2B avec une RC Pro.",
        "badge_text": "Guide RC Pro",
        "badge_color_class": "!bg-teal-100 !text-teal-700",
        "category": "blog",
        "template_file": "blog/comprendre-rc-pro.html"
    },
    {
        "slug": "comparatif-assistance-assurance-maroc",
        "title": "Comparatif Assistance Assurance Maroc : MAI vs AXA vs Mondial vs Wafa",
        "url": "/blog/comparatif-assistance-assurance-maroc",
        "image_filename": "images/comparatif-assistance-maroc.jpg",
        "alt_text": "Comparatif Assistance Assurance Maroc : MAI vs AXA vs Mondial vs Wafa",
        "description": "Comparatif complet des services d'assistance au Maroc : MAI, AXA Assistance, Mondial Assistance et Wafa IMA. Tarifs, garanties, avis et conseils pour choisir.",
        "badge_text": "Comparatif",
        "badge_color_class": "!bg-amber-100 !text-amber-700",
        "category": "blog",
        "template_file": "blog/comparatif-assistance-assurance-maroc.html"
    },
    {
        "slug": "constateur-assurance-maroc",
        "title": "Constateur Assurance Maroc : Rôle, Mission et Différences avec l'Expert",
        "url": "/blog/constateur-assurance-maroc",
        "image_filename": "images/constateur-assurance-maroc.jpg",
        "alt_text": "Constateur d'assurance au Maroc expliquant son rôle et ses missions",
        "description": "Découvrez le rôle du constateur d'assurance au Maroc, ses missions et les différences avec l'expert. Guide complet pour comprendre ce métier essentiel de l'assurance.",
        "badge_text": "Guide Constateur",
        "badge_color_class": "!bg-slate-100 !text-slate-800",
        "category": "blog",
        "template_file": "blog/constateur-assurance-maroc.html"
    },
    {
        "slug": "constateur-auto-accident-maroc",
        "title": "Constateur Auto : Guide Accident de Voiture au Maroc 2025",
        "url": "/blog/constateur-auto-accident-maroc",
        "image_filename": "images/constateur-auto-accident.jpg",
        "alt_text": "Constateur automobile évaluant les dommages d'un accident de voiture au Maroc",
        "description": "Comment travailler avec un constateur auto lors d'un accident au Maroc ? Guide étape par étape, droits et obligations, procédures et conseils pratiques.",
        "badge_text": "Assurance Auto",
        "badge_color_class": "!bg-orange-100 !text-orange-700",
        "category": "blog",
        "template_file": "blog/constateur-auto-accident-maroc.html"
    },
    {
        "slug": "constateur-habitation-dommages",
        "title": "Constateur Habitation : Évaluation des Dommages au Maroc 2025",
        "url": "/blog/constateur-habitation-dommages",
        "image_filename": "images/constateur-habitation-dommages.jpg",
        "alt_text": "Constateur habitation évaluant les dommages d'une propriété au Maroc",
        "description": "Guide complet sur l'évaluation des dommages par un constateur habitation au Maroc. Préparation, procédures, documents requis et conseils pour propriétaires.",
        "badge_text": "Assurance Habitation",
        "badge_color_class": "!bg-blue-100 !text-blue-700",
        "category": "blog",
        "template_file": "blog/constateur-habitation-dommages.html"
    },
    {
        "slug": "devenir-constateur-assurance-maroc",
        "title": "Devenir Constateur d'Assurance au Maroc : Formation, Salaire et Carrière",
        "url": "/blog/devenir-constateur-assurance-maroc",
        "image_filename": "images/devenir-constateur-assurance.jpg",
        "alt_text": "Formation pour devenir constateur d'assurance au Maroc",
        "description": "Guide complet pour devenir constateur d'assurance au Maroc. Formations requises, qualifications, salaires, opportunités de carrière et débouchés professionnels.",
        "badge_text": "Carrière",
        "badge_color_class": "!bg-green-100 !text-green-700",
        "category": "blog",
        "template_file": "blog/devenir-constateur-assurance-maroc.html"
    },
    {
        "slug": "choisir-assurance-services-constateur",
        "title": "Choisir son Assurance : Évaluer les Services de Constateur au Maroc",
        "url": "/blog/choisir-assurance-services-constateur",
        "image_filename": "images/choisir-assurance-constateur.jpg",
        "alt_text": "Comparaison des services de constateur entre différentes compagnies d'assurance au Maroc",
        "description": "Comment évaluer les services de constateur lors du choix de votre assurance au Maroc ? Critères de qualité, questions à poser et comparaison des assureurs.",
        "badge_text": "Guide d'Achat",
        "badge_color_class": "!bg-purple-100 !text-purple-700",
        "category": "blog",
        "template_file": "blog/choisir-assurance-services-constateur.html"
    },
    {
        "slug": "obligations-employeur-cnss",
        "title": "Obligations Employeur CNSS : Déclarations et Cotisations 2025",
        "url": "/blog/obligations-employeur-cnss",
        "image_filename": "images/obligations-employeur-cnss.jpg",
        "alt_text": "Obligations Employeur CNSS : Déclarations et Cotisations 2025",
        "description": "Le guide complet pour les employeurs sur leurs obligations envers la CNSS : affiliation, immatriculation des salariés, déclarations de salaires (Damancom) et paiement des cotisations.",
        "badge_text": "Guide Complet",
        "badge_color_class": "!bg-indigo-100 !text-indigo-700",
        "category": "blog",
        "template_file": "blog/obligations-employeur-cnss.html"
    },
    {
        "slug": "rsu-maroc-guide",
        "title": "RSU Maroc : Guide Complet du Registre Social Unifié 2025",
        "url": "/blog/rsu-maroc-guide",
        "image_filename": "images/rsu-maroc-guide.jpg",
        "alt_text": "RSU Maroc : Guide Complet du Registre Social Unifié 2025",
        "description": "Le guide complet du Registre Social Unifié (RSU) au Maroc. Découvrez son utilité, comment s'inscrire, le calcul du score et son rôle pour les aides sociales comme AMO Tadamon.",
        "badge_text": "Guide Complet",
        "badge_color_class": "!bg-indigo-100 !text-indigo-700",
        "category": "blog",
        "template_file": "blog/rsu-maroc-guide.html"
    },
    {
        "slug": "remboursement-amo-tadamon",
        "title": "Remboursement AMO Tadamon : Procédures, Avantages et Accès aux Soins",
        "url": "/blog/remboursement-amo-tadamon",
        "image_filename": "images/remboursement-amo-tadamon.jpg",
        "alt_text": "Remboursement AMO Tadamon : Procédures, Avantages et Accès aux Soins",
        "description": "Découvrez comment fonctionne le remboursement des frais médicaux avec AMO Tadamon. Procédures, documents nécessaires et avantages pour l'accès aux soins dans les secteurs public et privé.",
        "badge_text": "Guide Complet",
        "badge_color_class": "!bg-indigo-100 !text-indigo-700",
        "category": "blog",
        "template_file": "blog/remboursement-amo-tadamon.html"
    },
    {
        "slug": "amo-tadamon-maroc",
        "title": "AMO Tadamon Maroc : Le Guide Complet 2025 pour les Bénéficiaires",
        "url": "/blog/amo-tadamon-maroc",
        "image_filename": "images/amo-tadamon-maroc.jpg",
        "alt_text": "AMO Tadamon Maroc : Le Guide Complet 2025 pour les Bénéficiaires",
        "description": "Le guide complet sur AMO Tadamon au Maroc. Découvrez ce qu'est ce régime, qui est éligible, les prestations couvertes et comment s'inscrire via le RSU.",
        "badge_text": "Guide Complet",
        "badge_color_class": "!bg-indigo-100 !text-indigo-700",
        "category": "blog",
        "template_file": "blog/amo-tadamon-maroc.html"
    },
    {
        "slug": "remboursement-cnss-procedures",
        "title": "Remboursement CNSS (AMO) : Procédures, Délais et Suivi 2025",
        "url": "/blog/remboursement-cnss-procedures",
        "image_filename": "images/remboursement-cnss-procedures.jpg",
        "alt_text": "Remboursement CNSS (AMO) : Procédures, Délais et Suivi 2025",
        "description": "Le guide pratique pour le remboursement de vos frais médicaux par l'AMO gérée par la CNSS. Découvrez les procédures, les documents requis, les délais de traitement et comment suivre votre dossier.",
        "badge_text": "Guide Complet",
        "badge_color_class": "!bg-indigo-100 !text-indigo-700",
        "category": "blog",
        "template_file": "blog/remboursement-cnss-procedures.html"
    },
    {
        "slug": "inscription-amo-tadamon",
        "title": "Inscription AMO Tadamon : Le Guide des Démarches via le RSU 2025",
        "url": "/blog/inscription-amo-tadamon",
        "image_filename": "images/inscription-amo-tadamon.jpg",
        "alt_text": "Inscription AMO Tadamon : Le Guide des Démarches via le RSU 2025",
        "description": "Le guide étape par étape pour s'inscrire à AMO Tadamon. Découvrez le rôle du RSU (Registre Social Unifié), comment vous inscrire en ligne et vérifier votre éligibilité.",
        "badge_text": "Guide Complet",
        "badge_color_class": "!bg-indigo-100 !text-indigo-700",
        "category": "blog",
        "template_file": "blog/inscription-amo-tadamon.html"
    },
    {
        "slug": "pension-retraite-cnss",
        "title": "Pension de Retraite CNSS : Calcul, Conditions et Démarches 2025",
        "url": "/blog/pension-retraite-cnss",
        "image_filename": "images/pension-retraite-cnss.jpg",
        "alt_text": "Pension de Retraite CNSS : Calcul, Conditions et Démarches 2025",
        "description": "Découvrez comment fonctionne la pension de retraite de la CNSS au Maroc. Guide sur les conditions d'éligibilité, le calcul du montant de votre pension et les démarches à suivre.",
        "badge_text": "Guide Complet",
        "badge_color_class": "!bg-indigo-100 !text-indigo-700",
        "category": "blog",
        "template_file": "blog/pension-retraite-cnss.html"
    },
    {
        "slug": "quest-ce-que-l-assurance",
        "title": "Qu'est-ce que l'Assurance ? Le Guide Complet pour Comprendre l'Assurance",
        "url": "/blog/quest-ce-que-l-assurance",
        "image_filename": "images/comprendre-assurance.jpg",
        "alt_text": "Illustration des concepts fondamentaux de l'assurance",
        "description": "Démystifiez le monde de l'assurance : définitions, concepts clés, types de couvertures et conseils pour choisir la meilleure protection.",
        "badge_text": "Guide Général",
        "badge_color_class": "!bg-sky-100 !text-sky-700",
        "category": "blog",
        "template_file": "blog/comprendre-assurance.html"
    },
    {
        "slug": "guide-assurance-stage",
        "title": "Assurance Stage Maroc : Le Guide Complet 2025 (Prix, Devis en Ligne, Obligations)",
        "url": "/blog/guide-assurance-stage",
        "image_filename": "images/guide-assurance-stage.jpg",
        "alt_text": "Guide Assurance Stage",
        "description": "Le guide complet de l'assurance stage pour étudiant au Maroc. Découvrez si elle est obligatoire, les garanties (RC, accidents), le prix moyen et comment obtenir un devis en ligne via un courtier agréé.",
        "badge_text": "Guide Complet",
        "badge_color_class": "!bg-indigo-100 !text-indigo-700",
        "category": "blog",
        "template_file": "blog/guide-assurance-stage.html"
    },
    {
        "slug": "prix-assurance-stage",
        "title": "Prix Assurance Stage au Maroc : Tarifs 2025 et Devis en Ligne",
        "url": "/blog/prix-assurance-stage",
        "image_filename": "images/prix-assurance-stage.jpg",
        "alt_text": "Prix Assurance Stage",
        "description": "Découvrez combien coûte une assurance stage au Maroc. Analyse des tarifs 2025, prix de base à 70 DH, et comment obtenir un devis en ligne gratuit via un courtier.",
        "badge_text": "Prix & Tarifs",
        "badge_color_class": "!bg-amber-100 !text-amber-700",
        "category": "blog",
        "template_file": "blog/prix-assurance-stage.html"
    },
    {
        "slug": "choisir-assurance-stage",
        "title": "Comment Choisir son Assurance Stage au Maroc ? Le Guide 2025",
        "url": "/blog/choisir-assurance-stage",
        "image_filename": "images/choisir-assurance-stage.jpg",
        "alt_text": "Choisir Assurance Stage",
        "description": "Le guide pour choisir la meilleure assurance stage au Maroc. Analysez les types d'assureurs (AXA, Sanlam, Wafa...) et les critères clés pour trouver la bonne offre.",
        "badge_text": "Guide d'Achat",
        "badge_color_class": "!bg-slate-100 !text-slate-700",
        "category": "blog",
        "template_file": "blog/choisir-assurance-stage.html"
    },
    {
        "slug": "assurance-stage-etranger",
        "title": "Assurance Stage à l'Étranger : Guide pour Étudiants Marocains",
        "url": "/blog/assurance-stage-etranger",
        "image_filename": "images/assurance-stage-etranger.jpg",
        "alt_text": "Assurance Stage Etranger",
        "description": "Le guide complet de l'assurance pour un stage à l'étranger. Garanties indispensables (frais médicaux, rapatriement), visa Schengen, et comment obtenir un devis.",
        "badge_text": "International",
        "badge_color_class": "!bg-sky-100 !text-sky-700",
        "category": "blog",
        "template_file": "blog/assurance-stage-etranger.html"
    },
    {
        "slug": "assurance-stage-entreprise",
        "title": "Assurance Stagiaire : Obligations et Avantages pour l'Entreprise au Maroc",
        "url": "/blog/assurance-stage-entreprise",
        "image_filename": "images/assurance-stage-entreprise.jpg",
        "alt_text": "Assurance Stage Entreprise",
        "description": "Guide pour les entreprises sur l'assurance stagiaire au Maroc. Découvrez les obligations légales, les avantages et comment vérifier l'assurance d'un stagiaire.",
        "badge_text": "Pour Entreprises",
        "badge_color_class": "!bg-blue-100 !text-blue-800",
        "category": "blog",
        "template_file": "blog/assurance-stage-entreprise.html"
    },
    {
        "slug": "accident-stage",
        "title": "Accident en Stage : Le Guide Complet pour Déclarer un Sinistre",
        "url": "/blog/accident-stage",
        "image_filename": "images/accident-stage.jpg",
        "alt_text": "Accident Assurance Stage",
        "description": "Que faire en cas d'accident pendant un stage ? Guide étape par étape pour déclarer un sinistre à votre assurance stage (RC ou accident corporel).",
        "badge_text": "Procédure Sinistre",
        "badge_color_class": "!bg-red-100 !text-red-700",
        "category": "blog",
        "template_file": "blog/accident-stage.html"
    },
    {
        "slug": "assurance-stage-vs-scolaire",
        "title": "Assurance Stage vs. Assurance Scolaire : Quelles Différences ?",
        "url": "/blog/assurance-stage-vs-scolaire",
        "image_filename": "images/assurance-stage-vs-scolaire.jpg",
        "alt_text": "Assurance Stage vs Scolaire",
        "description": "Ne faites pas l'erreur ! Découvrez les différences clés entre l'assurance stage et l'assurance scolaire au Maroc. Comprenez pourquoi l'une ne remplace pas l'autre.",
        "badge_text": "Comparatif",
        "badge_color_class": "!bg-green-100 !text-green-800",
        "category": "blog",
        "template_file": "blog/assurance-stage-vs-scolaire.html"
    },
    {
        "slug": "prix-assurance-auto-6cv-diesel-maroc",
        "title": "Prix Assurance Auto 6 CV Diesel Maroc : Le Guide Complet 2025",
        "url": "/blog/prix-assurance-auto-6cv-diesel-maroc",
        "image_filename": "images/assurance-auto-6cv.jpg",
        "alt_text": "Illustration du coût de l'assurance pour une voiture 6CV diesel au Maroc.",
        "description": "Découvrez le prix moyen d'une assurance auto pour une voiture 6 CV diesel au Maroc en 2025. Guide complet des tarifs, garanties (Tiers, Tous Risques) et astuces pour payer moins cher.",
        "badge_text": "Assurance Auto",
        "badge_color_class": "!bg-orange-100 !text-orange-700",
        "category": "blog",
        "template_file": "blog/assurance-auto-6cv.html"
    },
    {
        "slug": "assurance-voiture-remplacement-maroc",
        "title": "Voiture de Remplacement : Le Guide Complet de votre Assurance au Maroc",
        "url": "/blog/assurance-voiture-remplacement-maroc",
        "image_filename": "images/voiture-remplacement.jpg",
        "alt_text": "Une voiture de location fournie par une assurance.",
        "description": "Votre voiture est immobilisée ? Découvrez comment bénéficier d'un véhicule de remplacement grâce à votre assurance auto au Maroc. Conditions, durée, et démarches expliquées.",
        "badge_text": "Assistance Auto",
        "badge_color_class": "!bg-slate-100 !text-slate-700",
        "category": "blog",
        "template_file": "blog/assurance-voiture-remplacement.html"
    },
    {
        "slug": "assurance-moto-49cc-maroc",
        "title": "Assurance Moto 49cc Maroc : Prix et Garanties pour 2025",
        "url": "/blog/assurance-moto-49cc-maroc",
        "image_filename": "images/assurance-moto-49cc.jpg",
        "alt_text": "Un scooter 49cc en ville, symbolisant le besoin d'assurance.",
        "description": "Quel est le prix d'une assurance pour une moto 49cc au Maroc ? Découvrez les garanties obligatoires, les tarifs moyens en 2025 et nos conseils pour assurer votre scooter.",
        "badge_text": "Assurance Moto",
        "badge_color_class": "!bg-slate-100 !text-slate-700",
        "category": "blog",
        "template_file": "blog/assurance-moto-49cc.html"
    },
    {
        "slug": "bonus-malus-assurance-auto-maroc",
        "title": "Bonus-Malus Assurance Auto Maroc : Le Guide Ultime 2025",
        "url": "/blog/bonus-malus-assurance-auto-maroc",
        "image_filename": "images/bonus-malus-maroc.jpg",
        "alt_text": "Jauge de bonus-malus pour l'assurance auto au Maroc.",
        "description": "Le guide complet pour comprendre le calcul du bonus-malus (CRM) en assurance auto au Maroc. Découvrez son impact sur votre prime et nos astuces pour l'améliorer.",
        "badge_text": "Guide Pratique",
        "badge_color_class": "!bg-teal-100 !text-teal-700",
        "category": "blog",
        "template_file": "blog/assurance-bonus-malus.html"
    },
    {
        "slug": "comparatif-mutuelles-sante-maroc",
        "title": "Tableau Comparatif des Mutuelles Santé au Maroc pour 2025",
        "url": "/blog/comparatif-mutuelles-sante-maroc",
        "image_filename": "images/comparatif-mutuelles.jpg",
        "alt_text": "Tableau comparant différentes offres de mutuelles santé.",
        "description": "Comparez les meilleures mutuelles santé au Maroc en 2025. Notre tableau comparatif analyse les offres (AXA, Sanlam, Wafa...) sur les taux, plafonds et garanties.",
        "badge_text": "Mutuelle Santé",
        "badge_color_class": "!bg-green-100 !text-green-700",
        "category": "blog",
        "template_file": "blog/comparatif-mutuelles-sante.html"
    },
    {
        "slug": "assurance-tiers-vs-tous-risques-maroc",
        "title": "Assurance Tiers vs. Tous Risques Maroc : Le Guide pour Choisir",
        "url": "/blog/assurance-tiers-vs-tous-risques-maroc",
        "image_filename": "images/tiers-vs-tousrisques.jpg",
        "alt_text": "Balance comparant l'assurance Tiers et l'assurance Tous Risques.",
        "description": "Tiers ou Tous Risques ? Le guide complet pour choisir la meilleure assurance auto au Maroc. Comprenez les garanties, comparez les prix et faites le bon choix pour votre voiture.",
        "badge_text": "Guide d'Achat",
        "badge_color_class": "!bg-purple-100 !text-purple-700",
        "category": "blog",
        "template_file": "blog/assuranc-rc-versus-tous-risques.html"
    },
    {
        "slug": "changer-assurance-auto-maroc",
        "title": "Changer d'Assurance Auto au Maroc : Le Guide Pas-à-Pas 2025",
        "url": "/blog/changer-assurance-auto-maroc",
        "image_filename": "images/changer-assurance.jpg",
        "alt_text": "Personne changeant de contrat d'assurance auto.",
        "description": "Le guide complet pour changer d'assurance auto au Maroc. Découvrez quand et comment résilier votre contrat, les documents nécessaires et le processus étape par étape.",
        "badge_text": "Guide Pratique",
        "badge_color_class": "!bg-blue-100 !text-blue-700",
        "category": "blog",
        "template_file": "blog/changer-assurance-maroc.html"
    },
    {
        "slug": "amo-cnss-cnops-differences",
        "title": "AMO, CNOPS, CNSS : Quelles Différences ?",
        "url": "/blog/amo-cnss-cnops-differences",
        "image_filename": "images/amo-cnss-cnops-differences.jpg",
        "alt_text": "AMO, CNSS, CNOPS, AMI... Le système de santé marocain peut sembler complexe. Notre guide simple et clair vous explique qui fait quoi pour y voir plus clair.",
        "description": "AMO, CNSS, CNOPS, AMI... Le système de santé marocain peut sembler complexe. Notre guide simple et clair vous explique qui fait quoi pour y voir plus clair.",
        "badge_text": "Santé Maroc",
        "badge_color_class": "!bg-teal-100 !text-teal-700",
        "category": "blog",
        "template_file": "blog/amo-cnss-cnops-differences.html"
    },
    {
        "slug": "amo-independents",
        "title": "AMO pour Indépendants (AMI) : Inscription et Coût",
        "url": "/blog/amo-independents",
        "image_filename": "images/amo-independents.jpg",
        "alt_text": "Auto-entrepreneur, commerçant, profession libérale ? Découvrez le guide complet pour vous inscrire à l'AMO des Indépendants (AMI) et comprendre le calcul de vos cotisations.",
        "description": "Auto-entrepreneur, commerçant, profession libérale ? Découvrez le guide complet pour vous inscrire à l'AMO des Indépendants (AMI) et comprendre le calcul de vos cotisations.",
        "badge_text": "Santé Maroc",
        "badge_color_class": "!bg-purple-100 !text-purple-700",
        "category": "blog",
        "template_file": "blog/amo-independents.html"
    },
    {
        "slug": "cnops-mobile-app",
        "title": "CNOPS Assurés : Le Guide de l'Application Mobile",
        "url": "/blog/cnops-mobile-app",
        "image_filename": "images/cnops-mobile-app.jpg",
        "alt_text": "Suivez vos remboursements, trouvez un professionnel de santé et gérez votre dossier AMO du secteur public directement depuis votre smartphone avec l'application SMART CNOPS.",
        "description": "Suivez vos remboursements, trouvez un professionnel de santé et gérez votre dossier AMO du secteur public directement depuis votre smartphone avec l'application SMART CNOPS.",
        "badge_text": "Santé Maroc",
        "badge_color_class": "!bg-emerald-100 !text-emerald-700",
        "category": "blog",
        "template_file": "blog/cnops-mobile-app.html"
    },
    {
        "slug": "cnss-cnops-fusion",
        "title": "Fusion CNOPS et CNSS en 2025 : Le Guide Complet",
        "url": "/blog/cnss-cnops-fusion",
        "image_filename": "images/cnss-cnops-fusion.jpg",
        "alt_text": "La fusion de la CNOPS et de la CNSS est la plus grande réforme sociale au Maroc. Découvrez ce que cela signifie pour votre couverture santé, vos remboursements et votre retraite.",
        "description": "La fusion de la CNOPS et de la CNSS est la plus grande réforme sociale au Maroc. Découvrez ce que cela signifie pour votre couverture santé, vos remboursements et votre retraite.",
        "badge_text": "Santé Maroc",
        "badge_color_class": "!bg-blue-100 !text-blue-700",
        "category": "blog",
        "template_file": "blog/cnss-cnops-fusion.html"
    },
    {
        "slug": "cnss-login-guide",
        "title": "\"www.cnss.ma تسجيل الدخول\" : Résoudre les Problèmes de Connexion",
        "url": "/blog/cnss-login-guide",
        "image_filename": "images/cnss-login-guide.jpg",
        "alt_text": "Mot de passe oublié ? Compte non activé ? Erreur d'identifiant ? Suivez notre guide de dépannage pour résoudre les problèmes de connexion au portail Ma CNSS.",
        "description": "Mot de passe oublié ? Compte non activé ? Erreur d'identifiant ? Suivez our guide de dépannage pour résoudre les problèmes de connexion au portail Ma CNSS.",
        "badge_text": "Guide Général",
        "badge_color_class": "!bg-rose-100 !text-rose-700",
        "category": "blog",
        "template_file": "blog/cnss-login-guide.html"
    },
    {
        "slug": "damancom",
        "title": "Portail Damancom / Ma CNSS : Le Tutoriel Simple",
        "url": "/blog/damancom",
        "image_filename": "images/damancom.jpg",
        "alt_text": "Un guide pas-à-pas pour créer votre compte sur le portail CNSS (Damancom), vous connecter à votre espace 'Ma CNSS' et suivre facilement vos remboursements maladie.",
        "description": "Un guide pas-à-pas pour créer votre compte sur le portail CNSS (Damancom), vous connecter à votre espace 'Ma CNSS' et suivre facilement vos remboursements maladie.",
        "badge_text": "Guide Général",
        "badge_color_class": "!bg-indigo-100 !text-indigo-700",
        "category": "blog",
        "template_file": "blog/damankom.html"
    },
    {
        "slug": "guide-indemnites-journalieres",
        "title": "Guide des Indemnités Journalières CNSS (Maladie, Maternité)",
        "url": "/blog/guide-indemnites-journalieres",
        "image_filename": "images/guide-indemnites-journalieres.jpg",
        "alt_text": "En arrêt maladie ou en congé maternité ? Découvrez comment sont calculées les indemnités journalières de la CNSS, les conditions à remplir et les démarches à suivre.",
        "description": "En arrêt maladie ou en congé maternité ? Découvrez comment sont calculées les indemnités journalières de la CNSS, les conditions à remplir et les démarches à suivre.",
        "badge_text": "Santé Maroc",
        "badge_color_class": "!bg-red-100 !text-red-700",
        "category": "blog",
        "template_file": "blog/guide-indemnites-journalieres.html"
    },
    {
        "slug": "ramed-amo",
        "title": "Passage du RAMED à AMO Tadamon : Le Guide Complet",
        "url": "/blog/ramed-amo",
        "image_filename": "images/ramed-amo.jpg",
        "alt_text": "Le RAMED n'existe plus et a été remplacé par AMO Tadamon. Découvrez qui est concerné, comment en bénéficier via le RSU et ce que cela change pour votre accès aux soins.",
        "description": "Le RAMED n'existe plus et a été remplacé par AMO Tadamon. Découvrez qui est concerné, comment en bénéficier via le RSU et ce que cela change pour votre accès aux soins.",
        "badge_text": "Santé Maroc",
        "badge_color_class": "!bg-sky-100 !text-sky-700",
        "category": "blog",
        "template_file": "blog/ramed-amo.html"
    },
    {
        "slug": "sinscrire-amo",
        "title": "Comment s'inscrire à l'AMO ? La Démarche Complète",
        "url": "/blog/sinscrire-amo",
        "image_filename": "images/sinscrire-amo.jpg",
        "alt_text": "Salarié, indépendant ou bénéficiaire de Tadamon ? Découvrez le guide complet et les démarches pas à pas pour vous inscrire à l'Assurance Maladie Obligatoire (AMO) au Maroc.",
        "description": "Salarié, indépendant ou bénéficiaire de Tadamon ? Découvrez le guide complet et les démarches pas à pas pour vous inscrire à l'Assurance Maladie Obligatoire (AMO) au Maroc.",
        "badge_text": "Santé Maroc",
        "badge_color_class": "!bg-green-100 !text-green-700",
        "category": "blog",
        "template_file": "blog/sinscrire-amo.html"
    },
    {
        "slug": "assurance-perte-emploi-maroc",
        "title": "Assurance Perte d'Emploi au Maroc : Une Protection Essentielle ?",
        "url": "/blog/assurance-perte-emploi-maroc",
        "image_filename": "images/assurance-perte-emploi.jpg",
        "alt_text": "Illustration de la sécurité financière en cas de perte d'emploi",
        "description": "Découvrez comment l'assurance perte d'emploi au Maroc peut sécuriser votre avenir financier. Notre guide complet explore son fonctionnement, ses avantages et les critères d'éligibilité.",
        "badge_text": "Guide Prévoyance",
        "badge_color_class": "!bg-sky-100 !text-sky-700",
        "category": "blog",
        "template_file": "blog/assurance-perte-demploi.html"
    },
    {
        "slug": "assurance-scolaire-maroc",
        "title": "Le Guide Complet de l'Assurance Scolaire au Maroc",
        "url": "/blog/assurance-scolaire-maroc",
        "image_filename": "images/assurance-scolaire.jpg",
        "alt_text": "Illustration de la protection des éleves à l'école",
        "description": "L'assurance scolaire au Maroc est-elle obligatoire ? Que couvre-t-elle ? Découvrez tout ce qu'il faut savoir pour garantir la sécurité de votre enfant à l'école et en dehors.",
        "badge_text": "Guide Famille",
        "badge_color_class": "!bg-orange-100 !text-orange-800",
        "category": "blog",
        "template_file": "blog/assurance-scolaire.html"
    },
    {
        "slug": "assurance-cyber-risques-maroc",
        "title": "L'Assurance Cyber-Risques : Protégez Votre Entreprise Marocaine des Menaces en Ligne",
        "url": "/blog/assurance-cyber-risques-maroc",
        "image_filename": "images/assurance-cyber-risques.jpg",
        "alt_text": "Illustration de la cybersécurité pour les entreprises",
        "description": "Ransomware, vol de données, fraude... Découvrez pourquoi l'assurance cyber-risques est devenue essentielle pour la survie et la réputation des entreprises au Maroc.",
        "badge_text": "Guide Entreprise",
        "badge_color_class": "!bg-violet-100 !text-violet-800",
        "category": "blog",
        "template_file": "blog/assurance-cybersecurite.html"
    },
    {
        "slug": "code-des-assurances-maroc",
        "title": "Le Code des Assurances au Maroc : Ce que Tout Assuré Doit Savoir",
        "url": "/blog/code-des-assurances-maroc",
        "image_filename": "images/code-assurances-maroc.jpg",
        "alt_text": "Illustration du cadre légal de l'assurance au Maroc",
        "description": "Démystifiez le Code des Assurances marocain (Loi n° 17-99). Notre guide vous explique vos droits et obligations en tant qu'assuré pour mieux naviguer vos contrats.",
        "badge_text": "Guide Légal",
        "badge_color_class": "!bg-emerald-100 !text-emerald-800",
        "category": "blog",
        "template_file": "blog/code-des-assurances-maroc.html"
    },
    {
        "slug": "role-expert-assurance-sinistre",
        "title": "Le Rôle de l'Expert en Assurance lors d'un Sinistre au Maroc",
        "url": "/blog/role-expert-assurance-sinistre",
        "image_filename": "images/role-expert-assurance.jpg",
        "alt_text": "Illustration du travail d'un expert en assurance lors d'un sinistre",
        "description": "Qui est l'expert d'assurance et quelle est sa mission ? Découvrez le rôle clé de cet acteur lors d'un sinistre et comment interagir avec lui pour une indemnisation juste.",
        "badge_text": "Guide Sinistre",
        "badge_color_class": "!bg-slate-100 !text-slate-800",
        "category": "blog",
        "template_file": "blog/role-expert-assurance.html"
    },
    {
        "slug": "assurance-auto-temporaire",
        "title": "Assurance Auto Temporaire Maroc (1 à 90 jours) : Solutions et Tarifs",
        "url": "/blog/assurance-auto-temporaire",
        "image_filename": "images/assurance-auto-temporaire.jpg",
        "alt_text": "Assurance auto temporaire au Maroc pour courtes durées",
        "description": "Besoin d'une assurance auto temporaire au Maroc (1 à 90 jours) ? Découvrez les solutions, tarifs et garanties pour une couverture courte durée.",
        "badge_text": "Guide Auto",
        "badge_color_class": "!bg-purple-100 !text-purple-700",
        "category": "blog",
        "template_file": "Assurance-auto-temporaire.html"
    },
    {
        "slug": "calculateur-mutuelle",
        "title": "Outil Interactif : Estimer vos Besoins en Mutuelle Santé au Maroc",
        "url": "/outils/calculateur-mutuelle",
        "image_filename": "images/calculateur-sante.jpg",
        "alt_text": "Outil d'estimation des besoins en mutuelle santé",
        "description": "Guidez votre choix de mutuelle santé au Maroc. Estimez vos besoins pour les consultations, pharmacie, hospitalisation et obtenez des ordres de grandeur de coûts.",
        "badge_text": "Outil Interactif",
        "badge_color_class": "!bg-green-100 !text-green-800",
        "category": "outils",
        "template_file": "calculateur-mutuelle.html"
    },
    {
        "slug": "checklist-assurance-habitation",
        "title": "Checklist Assurance Habitation Maroc",
        "url": "/blog/checklist-assurance-habitation",
        "image_filename": "images/assurance-habitation-checklist.jpg",
        "alt_text": "Checklist complète pour l'assurance habitation au Maroc",
        "description": "Les points essentiels à vérifier (garanties, capital mobilier, exclusions...) avant de souscrire une assurance habitation au Maroc.",
        "badge_text": "Checklist Habitation",
        "badge_color_class": "!bg-purple-100 !text-purple-700",
        "category": "blog",
        "template_file": "checklist-assurance-habitation.html"
    },
    {
        "slug": "constat-amiable",
        "title": "Guide : Bien Remplir un Constat Amiable Auto au Maroc",
        "url": "/blog/constat-amiable",
        "image_filename": "images/constat-amiable.jpg",
        "alt_text": "Comment bien remplir un constat amiable auto",
        "description": "Nos conseils pratiques pour remplir correctement votre constat amiable après un accident de voiture au Maroc et faciliter votre indemnisation.",
        "badge_text": "Conseils Auto",
        "badge_color_class": "!bg-cyan-100 !text-cyan-700",
        "category": "blog",
        "template_file": "constat-amiable.html"
    },
    {
        "slug": "degats-eau",
        "title": "Dégât des Eaux : Que Faire et Comment Être Indemnisé ?",
        "url": "/blog/degats-eau",
        "image_filename": "images/degats-eau.jpg",
        "alt_text": "Gestion et indemnisation d'un dégât des eaux",
        "description": "Découvrez les bons réflexes à adopter en cas de dégât des eaux chez vous, les démarches auprès de votre assurance et comment obtenir une indemnisation.",
        "badge_text": "Sécurité Maison",
        "badge_color_class": "!bg-blue-100 !text-blue-700",
        "category": "blog",
        "template_file": "degats-eau.html"
    },
    {
        "slug": "guide-auto",
        "title": "Guide Assurance Auto Maroc : Choisir les Bonnes Garanties",
        "url": "/blog/guide-auto",
        "image_filename": "images/guide_auto_maroc.jpg",
        "alt_text": "Guide complet sur l'assurance auto au Maroc",
        "description": "RC, Dommages, Vol, Incendie... Décryptez les options pour faire le meilleur choix d'assurance auto adapté à votre véhicule et usage au Maroc.",
        "badge_text": "Guide Auto",
        "badge_color_class": "!bg-blue-100 !text-blue-700",
        "category": "blog",
        "template_file": "guide-auto.html"
    },
    {
        "slug": "habitation-locataire",
        "title": "Assurance Habitation Locataire : Vos Obligations au Maroc",
        "url": "/blog/habitation-locataire",
        "image_filename": "images/habitation-locataire.jpg",
        "alt_text": "Assurance habitation pour locataires au Maroc : obligations",
        "description": "En tant que locataire au Maroc, comprenez vos obligations en matière d'assurance habitation : garanties obligatoires (risques locatifs) et recommandées.",
        "badge_text": "Habitation Locataire",
        "badge_color_class": "!bg-green-100 !text-green-700",
        "category": "blog",
        "template_file": "habitation-locataire.html"
    },
    {
        "slug": "lexique-assurance",
        "title": "Glossaire de l'Assurance au Maroc",
        "url": "/blog/lexique-assurance",
        "image_filename": "images/lexique-assurance-maroc.jpg",
        "alt_text": "Glossaire des termes d'assurance expliqués",
        "description": "Comprenez facilement les termes techniques de l'assurance au Maroc (franchise, avenant, sinistre...) avec notre glossaire complet.",
        "badge_text": "Lexique",
        "badge_color_class": "!bg-yellow-100 !text-yellow-700",
        "category": "blog",
        "template_file": "lexique-assurance.html"
    },
    {
        "slug": "mobilier-assurance",
        "title": "Bien Évaluer Ses Biens Mobiliers pour l'Assurance Habitation",
        "url": "/blog/mobilier-assurance",
        "image_filename": "images/mobilier-assurance.jpg",
        "alt_text": "Évaluation des biens mobiliers pour l'assurance habitation",
        "description": "Conseils pratiques pour évaluer correctement la valeur de vos biens mobiliers (meubles, électroménager...) pour votre assurance habitation au Maroc.",
        "badge_text": "Conseils Habitation",
        "badge_color_class": "!bg-amber-100 !text-amber-700",
        "category": "blog",
        "template_file": "mobilier-assurance.html"
    },
    {
        "slug": "resiliation-contrat",
        "title": "Guide Résiliation Contrat Assurance Maroc",
        "url": "/blog/resiliation-contrat",
        "image_filename": "images/resiliation-contrat-assurance-maroc.jpg",
        "alt_text": "Guide pour la résiliation de contrat d'assurance",
        "description": "Comprenez les règles et délais pour résilier votre contrat d'assurance (auto, habitation, santé) au Maroc : échéance, loi, changement de situation.",
        "badge_text": "Guide Pratique",
        "badge_color_class": "!bg-pink-100 !text-pink-700",
        "category": "blog",
        "template_file": "résiliation-contrat.html" # Actual filename, with accent
    },
    {
        "slug": "resultat-t1-2025-assurance-maroc",
        "title": "Performance du secteur d'assurance au Maroc au 1er trimestre 2025",
        "url": "/blog/resultat-t1-2025-assurance-maroc",
        "image_filename": "images/resultat-assurance-t1-maroc.jpg",
        "alt_text": "Résultats Financiers Assurance Maroc 1er Trimestre 2025",
        "description": "Les chiffres du premier trimestre 2025 révèlent un dynamisme notable avec des primes émises atteignant 18,2 milliards de dirhams.",
        "badge_text": "News Assurance",
        "badge_color_class": "!bg-pink-100 !text-pink-700",
        "category": "blog",
        "template_file": "resultat-t1-2025-assurance-maroc.html" # Actual filename, with accent
    },
    {
        "slug": "simulateur-assurance-auto", # This was category: "blog" in original data
        "title": "Estimation de l'Assurance Auto (exemple sur mesassurances.ma)",
        "url": "/blog/simulateur-assurance-auto", # URL implies blog, but content is a simulator guide
        "image_filename": "images/estimation-assurance-auto.jpg",
        "alt_text": "Simulateur assurance auto Maroc",
        "description": "Découvrez comment obtenir un devis d'assurance auto personnalisé en quelques clics et les astuces pour bien comparer les offres au Maroc.",
        "badge_text": "Guide Pratique", # Could also be "Outil" or "Guide Outil"
        "badge_color_class": "!bg-amber-100 !text-amber-700",
        "category": "blog", # Consider changing to "outils" if it's more of a tool itself, or keep as "blog" if it's a guide ABOUT a tool.
        "template_file": "simulateur-assurance-auto.html" # Actual filename, with accent
    },
    {
        "slug": "frais-veterinaires-maroc",
        "title": "Frais Vétérinaires Maroc : Pourquoi une Mutuelle Animale est Utile ?",
        "url": "/blog/frais-veterinaires-maroc",
        "image_filename": "images/sante-animale-frais-veterinaires.jpg",
        "alt_text": "Frais vétérinaires et mutuelle animale au Maroc",
        "description": "Comprenez les coûts des soins vétérinaires pour chiens et chats au Maroc et découvrez comment une mutuelle animale peut alléger la facture.",
        "badge_text": "Santé Animale",
        "badge_color_class": "!bg-green-100 !text-green-700",
        "category": "blog",
        "template_file": "frais-veterinaires-maroc.html"
  },
  {
        "slug": "assurance-chien-chat-differences",
        "title": "Assurance Chien vs Chat Maroc : Différences de Couverture",
        "url": "/blog/assurance-chien-chat-differences",
        "image_filename": "images/assurance-chien-chat-differences.jpg",
        "alt_text": "Différences assurance chien et chat Maroc",
        "description": "Explorez les spécificités des contrats d'assurance pour chiens et chats au Maroc. Comprenez les différences de couverture et de tarifs.",
        "badge_text": "Choisir sa Mutuelle",
        "badge_color_class": "!bg-blue-100 !text-blue-700",
        "category": "blog",
        "template_file": "assurance-chien-vs-chat.html"
  },
  {
        "slug": "delais-carence-exclusions-assurance-animaux",
        "title": "Assurance Animaux : Délais de Carence et Exclusions à Vérifier",
        "url": "/blog/delais-carence-exclusions-assurance-animaux",
        "image_filename": "images/delais-carence-exclusions-animaux.jpg",
        "alt_text": "Délais de carence et exclusions assurance animaux Maroc",
        "description": "Ne soyez pas pris au dépourvu ! Comprenez les délais de carence, les exclusions et les points clés des conditions générales de votre assurance animaux au Maroc.",
        "badge_text": "Conseils Animaux",
        "badge_color_class": "!bg-purple-100 !text-purple-700",
        "category": "blog",
        "template_file": "exclusions-assurance-animaux.html"
  },
  {
        "slug": "amo-vs-mutuelle-maroc",
        "title": "AMO vs Mutuelle : Comprendre les Différences au Maroc",
        "url": "/blog/amo-vs-mutuelle-maroc",
        "image_filename": "images/amo-vs-mutuelle.jpg",
        "alt_text": "Comparaison entre l'AMO et la mutuelle santé au Maroc",
        "description": "Décryptage des deux principaux systèmes de couverture santé au Maroc, l'AMO et la mutuelle, pour vous aider à y voir plus clair et choisir la meilleure option.",
        "badge_text": "Santé",
        "badge_color_class": "!bg-blue-100 !text-blue-700",
        "category": "blog",
        "template_file": "amo-vs-mutuelle-maroc.html"
  },
  {
        "slug": "choisir-mutuelle-complementaire-maroc",
        "title": "Comment Choisir sa Mutuelle Complémentaire au Maroc ?",
        "url": "/blog/choisir-mutuelle-complementaire-maroc",
        "image_filename": "images/choisir-mutuelle.jpg",
        "alt_text": "Guide pour sélectionner une mutuelle santé complémentaire au Maroc",
        "description": "Un guide pratique pour évaluer vos besoins personnels, comparer les offres de mutuelles santé au Maroc et faire le meilleur choix pour votre couverture complémentaire.",
        "badge_text": "Guide Pratique",
        "badge_color_class": "!bg-green-100 !text-green-700",
        "category": "blog",
        "template_file": "mutuelle-maroc.html"
  },
  {
        "slug": "assurance-sante-internationale-avantages",
        "title": "Assurance Santé Internationale : Pour Qui et Pourquoi ?",
        "url": "/blog/assurance-sante-internationale-avantages",
        "image_filename": "images/sante-internationale.jpg",
        "alt_text": "Avantages de l'assurance santé internationale pour expatriés et voyageurs",
        "description": "Explorez les avantages et les raisons de souscrire une assurance santé internationale, que vous soyez expatrié, grand voyageur ou nécessitant des soins à l'étranger.",
        "badge_text": "Internationale",
        "badge_color_class": "!bg-orange-100 !text-orange-700",
        "category": "blog",
        "template_file": "assurance-sante-internationale.html"
  },


  {
        "slug": "delegation-assurance-pret",
        "title": "Délégation d'Assurance de Prêt au Maroc : Le Guide Complet",
        "url": "/blog/delegation-assurance-pret",
        "image_filename": "images/delegation-assurance-pret.jpg", # Exemple, à remplacer par votre image
        "alt_text": "Délégation d'assurance de prêt immobilier au Maroc",
        "description": "Découvrez la délégation d'assurance de prêt immobilier au Maroc. Comprendrez les avantages, les conditions et comment changer d'assurance emprunteur.",
        "badge_text": "Prêt Immobilier",
        "badge_color_class": "!bg-blue-100 !text-blue-700",
        "category": "blog",
        "template_file": "blog/delegation-assurance-pret.html"
    },
    {
        "slug": "garanties-pret-immobilier",
        "title": "Garanties de Prêt Immobilier au Maroc : Hypothèque, Caution, Nantissement",
        "url": "/blog/garanties-pret-immobilier",
        "image_filename": "images/garanties-pret-immobilier.jpg", # Exemple
        "alt_text": "Types de garanties pour prêt immobilier au Maroc",
        "description": "Explorez les différentes garanties exigées pour un prêt immobilier au Maroc : hypothèque, caution bancaire et nantissement. Choisissez l'option la plus adaptée.",
        "badge_text": "Prêt Immobilier",
        "badge_color_class": "!bg-orange-100 !text-orange-700",
        "category": "blog",
        "template_file": "blog/garanties-pret-immobilier.html"
    },
    {
        "slug": "comparer-assurance-emprunteur",
        "title": "Comment Comparer les Offres d'Assurance Emprunteur au Maroc ?",
        "url": "/blog/comparer-assurance-emprunteur",
        "image_filename": "images/comparer-assurance-emprunteur.jpg", # Exemple
        "alt_text": "Comparaison d'assurances emprunteur au Maroc",
        "description": "Maîtrisez l'art de comparer les assurances emprunteur au Maroc. Critères, pièges à éviter, et conseils pour trouver la meilleure couverture pour votre prêt immobilier.",
        "badge_text": "Prêt Immobilier",
        "badge_color_class": "!bg-red-100 !text-red-700",
        "category": "blog",
        "template_file": "blog/comparer-assurance-emprunteur.html"
    },
    {
        "slug": "assurance-chasse-maroc",
        "title": "Assurance Chasse au Maroc : Obligations, Garanties et Responsabilité",
        "url": "/blog/assurance-chasse-maroc",
        "image_filename": "images/assurance-chasse-maroc.jpg", # Exemple
        "alt_text": "Assurance obligatoire pour la chasse au Maroc",
        "description": "Tout savoir sur l'assurance chasse au Maroc : obligatoire, types de garanties (RC, dommages corporels), et comment protéger votre passion en toute légalité.",
        "badge_text": "Loisirs",
        "badge_color_class": "!bg-green-100 !text-green-700",
        "category": "blog",
        "template_file": "blog/assurance-chasse-maroc.html"
    },
    {
        "slug": "assurance-bateau-maroc",
        "title": "Assurance Bateau au Maroc : Protégez votre Plaisir Nautique",
        "url": "/blog/assurance-bateau-maroc",
        "image_filename": "images/assurance-bateau-maroc.jpg", # Exemple
        "alt_text": "Assurance bateau et jet ski au Maroc",
        "description": "Guide complet de l'assurance bateau au Maroc : obligations légales, garanties essentielles (responsabilité civile, dommages), et conseils pour choisir votre contrat.",
        "badge_text": "Loisirs",
        "badge_color_class": "!bg-indigo-100 !text-indigo-700",
        "category": "blog",
        "template_file": "blog/assurance-bateau-maroc.html"
    },
    {
        "slug": "assurance-sports-individuels",
        "title": "Assurance Sports Individuels au Maroc : Couverture et Risques",
        "url": "/blog/assurance-sports-individuels",
        "image_filename": "images/assurance-sports-individuels.jpg", # Exemple
        "alt_text": "Assurance pour activités sportives individuelles au Maroc",
        "description": "Protégez-vous lors de vos activités sportives individuelles au Maroc. Découvrez les assurances adaptées aux risques spécifiques : RC, accidents, rapatriement.",
        "badge_text": "Loisirs",
        "badge_color_class": "!bg-pink-100 !text-pink-700",
        "category": "blog",
        "template_file": "blog/assurance-sports-individuels.html"
    },
    {
        "slug": "epargne-retraite-quand-commencer",
        "title": "Épargne Retraite au Maroc : Quand Commencer à Épargner ?",
        "url": "/blog/epargne-retraite-quand-commencer",
        "image_filename": "images/epargne-retraite-quand-commencer.jpg", # Exemple
        "alt_text": "Débuter son épargne retraite au Maroc",
        "description": "Découvrez à quel âge il est idéal de commencer à épargner pour votre retraite au Maroc. Les avantages de l'épargne précoce et les plans de retraite disponibles.",
        "badge_text": "Retraite",
        "badge_color_class": "!bg-purple-100 !text-purple-700",
        "category": "blog",
        "template_file": "blog/epargne-retraite-quand-commencer.html"
    },
    {
        "slug": "fiscalite-epargne-retraite-maroc",
        "title": "Fiscalité de l'Épargne Retraite au Maroc : Optimisez vos Impôts",
        "url": "/blog/fiscalite-epargne-retraite-maroc",
        "image_filename": "images/fiscalite-epargne-retraite-maroc.jpg", # Exemple
        "alt_text": "Avantages fiscaux épargne retraite Maroc",
        "description": "Comprenez la fiscalité de l'épargne retraite au Maroc. Découvrez les avantages fiscaux des PER (Plan d'Épargne Retraite) et optimisez votre imposition.",
        "badge_text": "Retraite",
        "badge_color_class": "!bg-amber-100 !text-amber-700",
        "category": "blog",
        "template_file": "blog/fiscalite-epargne-retraite-maroc.html"
    },
    {
        "slug": "rente-ou-capital-retraite",
        "title": "Rente ou Capital pour votre Retraite au Maroc : Que Choisir ?",
        "url": "/blog/rente-ou-capital-retraite",
        "image_filename": "images/rente-ou-capital-retraite.jpg", # Exemple
        "alt_text": "Rente viagère ou capital à la retraite au Maroc",
        "description": "Faut-il opter pour une rente viagère ou un capital à la retraite au Maroc ? Analyse des avantages et inconvénients de chaque option pour bien décider.",
        "badge_text": "Retraite",
        "badge_color_class": "!bg-cyan-100 !text-cyan-700",
        "category": "blog",
        "template_file": "blog/rente-ou-capital-retraite.html"
    },
    {
        "slug": "assurance-moto-125cc",
        "title": "Assurance Moto 125cc au Maroc : Spécificités et Conseils",
        "url": "/blog/assurance-moto-125cc",
        "image_filename": "images/assurance-moto-125cc.jpg", # Exemple
        "alt_text": "Assurance moto et scooter 125cc au Maroc",
        "description": "Tout savoir sur l'assurance moto 125cc au Maroc : permis requis, garanties adaptées, facteurs de prix et conseils pour trouver une assurance pas chère pour votre scooter ou moto légère.",
        "badge_text": "Moto",
        "badge_color_class": "!bg-indigo-100 !text-indigo-700",
        "category": "blog",
        "template_file": "blog/assurance-moto-125cc.html"
    },
    {
        "slug": "assurance-moto-guide",
        "title": "Assurance Moto au Maroc : Guide Complet des Garanties Indispensables",
        "url": "/blog/assurance-moto-guide",
        "image_filename": "images/assurance-moto-guide.jpg", # Exemple
        "alt_text": "Garanties obligatoires et optionnelles assurance moto Maroc",
        "description": "Découvrez les garanties obligatoires et optionnelles de l'assurance moto au Maroc : Responsabilité Civile, vol, incendie, assistance, individuelle pilote. Protégez votre deux-roues.",
        "badge_text": "Moto",
        "badge_color_class": "!bg-orange-100 !text-orange-700",
        "category": "blog",
        "template_file": "blog/assurance-moto-guide.html"
    },
    {
        "slug": "meilleure-assurance-moto",
        "title": "Comment Choisir la Meilleure Assurance Moto au Maroc : Critères et Astuces",
        "url": "/blog/meilleure-assurance-moto",
        "image_filename": "images/meilleure-assurance-moto.jpg", # Exemple
        "alt_text": "Comparateur et devis meilleure assurance moto Maroc",
        "description": "Guide pour choisir la meilleure assurance moto au Maroc : comparez les devis, évaluez les garanties (RC, vol, incendie, assistance), et trouvez le meilleur prix selon votre profil.",
        "badge_text": "Moto",
        "badge_color_class": "!bg-teal-100 !text-teal-700",
        "category": "blog",
        "template_file": "blog/meilleure-assurance-moto.html"
    },
    {
        "slug": "annulation-voyage",
        "title": "Annulation de Voyage : Quand Votre Assurance Peut Vous Sauver",
        "url": "/blog/annulation-voyage",
        "image_filename": "images/annulation-voyage.jpg", # Exemple
        "alt_text": "Assurance annulation de voyage au Maroc",
        "description": "Découvrez les motifs d'annulation de voyage couverts par l'assurance, les démarches pour être remboursé et comment protéger votre investissement.",
        "badge_text": "Voyage",
        "badge_color_class": "!bg-green-100 !text-green-700",
        "category": "blog",
        "template_file": "blog/annulation-voyage.html"
    },
    {
        "slug": "assurance-voyage-schengen",
        "title": "Assurance Voyage Schengen : Que Couvre-t-elle Vraiment ?",
        "url": "/blog/assurance-voyage-schengen",
        "image_filename": "images/assurance-voyage-schengen.jpg", # Exemple
        "alt_text": "Assurance obligatoire pour visa Schengen depuis le Maroc",
        "description": "Comprend les exigences et les garanties essentielles de l'assurance voyage Schengen pour l'obtention de votre visa et une protection complète en Europe.",
        "badge_text": "Voyage",
        "badge_color_class": "!bg-purple-100 !text-purple-700",
        "category": "blog",
        "template_file": "blog/assurance-voyage-schengen.html"
    },
    {
        "slug": "frais-medicaux-assurance-voyage",
        "title": "Frais Médicaux à l'Étranger : Pourquoi l'Assurance Voyage est Cruciale",
        "url": "/blog/frais-medicaux-assurance-voyage",
        "image_filename": "images/frais-medicaux-assurance-voyage.jpg", # Exemple
        "alt_text": "Couverture des frais médicaux urgents à l'étranger",
        "description": "Découvrez pourquoi une assurance voyage est indispensable pour couvrir les frais médicaux imprévus à l'étranger et éviter des dépenses exorbitantes.",
        "badge_text": "Voyage",
        "badge_color_class": "!bg-red-100 !text-red-700",
        "category": "blog",
        "template_file": "blog/frais-medicaux-assurance-voyage.html"
    },
    {
        "slug": "espace-assure-cnops",
        "title": "Espace Assuré CNOPS : Maîtrisez vos Services en Ligne (Connexion, Mot de Passe Oublié, App)",
        "url": "/blog/espace-assure-cnops",
        "image_filename": "images/espace-assure-cnops.png",
        "alt_text": "Espace Assuré CNOPS : Connexion, Mot de Passe Oublié, Application Mobile",
        "description": "Découvrez comment vous connecter à l'Espace Assuré CNOPS, récupérer votre mot de passe et utiliser l'application mobile pour gérer vos services en ligne.",
        "badge_text": "Guide CNOPS",
        "badge_color_class": "!bg-purple-100 !text-purple-700",
        "category": "blog",
        "template_file": "blog/espace-assure-cnops.html"
  },
  {
        "slug": "remboursement-cnops",
        "title": "Remboursement CNOPS : Guide Complet de Vos Dossiers Médicaux",
        "url": "/blog/remboursement-cnops",
        "image_filename": "images/remboursement-cnops.png",
        "alt_text": "Processus de remboursement des frais médicaux CNOPS",
        "description": "Découvrez les étapes, les documents nécessaires et les délais pour le remboursement de vos frais médicaux par la CNOPS.",
        "badge_text": "Santé & CNOPS",
        "badge_color_class": "!bg-lime-100 !text-lime-700",
        "category": "blog",
        "template_file": "blog/remboursement-cnops.html"
  },
  {
        "slug": "service-client-cnops",
        "title": "Contacter CNOPS : Service Client et Options d'Aide",
        "url": "/blog/service-client-cnops",
        "image_filename": "images/service-client-cnops.jpeg",
        "alt_text": "Contacter le service client CNOPS par téléphone, email ou agence",
        "description": "Découvrez les différents canaux pour contacter le service client CNOPS : téléphone, e-mail, agences physiques et conseils pour optimiser vos échanges.",
        "badge_text": "Support CNOPS",
        "badge_color_class": "!bg-orange-100 !text-orange-700",
        "category": "blog",
        "template_file": "blog/service-client-cnops.html"
  },
  {
        "slug": "assurance-navire",
        "title": "Assurance Corps de Navire : Protéger Votre Investissement Flottant - mesassurances.ma",
        "url": "/blog/assurance-navire",
        "image_filename": "images/assurance-navire.jpg",
        "alt_text": "Assurance Corps de Navire",
        "description": "Comprendre les garanties H&M (Hull & Machinery) et les risques couverts pour votre bateau.",
        "badge_text": "Guide Maritime",
        "badge_color_class": "!bg-sky-900 !text-white",
        "category": "blog",
        "template_file": "blog/assurance-navire.html"
  },
  {
        "slug": "assurance-perte-exploitation",
        "title": "Assurance Perte d'Exploitation : Sécurisez vos revenus - mesassurances.ma",
        "url": "/blog/assurance-perte-exploitation",
        "image_filename": "images/assurance-perte-exploitation.jpg",
        "alt_text": "Assurance Perte d'Exploitation",
        "description": "Comment la garantie perte d'exploitation vous aide à maintenir vos revenus et couvrir vos charges fixes après un incident.",
        "badge_text": "Guide Pro",
        "badge_color_class": "!bg-purple-500 !text-white",
        "category": "blog",
        "template_file": "blog/assurance-perte-exploitation.html"
  },
    {
        "slug": "avantages-flotte-auto",
        "title": "5 Avantages Clés de l'Assurance Flotte Auto pour Votre Entreprise - mesassurances.ma",
        "url": "/blog/avantages-flotte-auto",
        "image_filename": "images/avantages-flotte-auto.jpg",
        "alt_text": "Avantages Flotte Auto",
        "description": "Découvrez comment un contrat flotte peut simplifier votre gestion et réduire vos coûts d'assurance.",
        "badge_text": "Guide Auto Pro",
        "badge_color_class": "!bg-green-500 !text-white",
        "category": "blog",
        "template_file": "blog/avantages-flotte-auto.html"
    },
    {
        "slug": "avarie-commune",
        "title": "L'Avarie Commune en Assurance Maritime : Qu'est-ce Que C'est ? - mesassurances.ma",
        "url": "/blog/avarie-commune",
        "image_filename": "images/avarie-commune.jpg",
        "alt_text": "Avarie Commune",
        "description": "Comprendre ce principe fondamental du droit maritime et comment l'assurance intervient.",
        "badge_text": "Guide Maritime",
        "badge_color_class": "!bg-purple-500 !text-white",
        "category": "blog",
        "template_file": "blog/avarie-commune.html"
    },
    {
        "slug": "bonnes-pratiques-at",
        "title": "Réduire les Accidents du Travail : Bonnes Pratiques et Impact sur l'Assurance - mesassurances.ma",
        "url": "/blog/bonnes-pratiques-at",
        "image_filename": "images/bonnes-pratiques-at.jpg",
        "alt_text": "Bonnes Pratiques AT",
        "description": "Investir dans la prévention, c'est protéger vos salariés et potentiellement réduire votre prime AT.",
        "badge_text": "Guide Pro",
        "badge_color_class": "!bg-emerald-500 !text-white",
        "category": "blog",
        "template_file": "blog/bonnes-pratiques-at.html"
    },
    {
        "slug": "choisir-assureur-credit",
        "title": "Comment Choisir Votre Assureur Crédit au Maroc ? - mesassurances.ma",
        "url": "/blog/choisir-assureur-credit",
        "image_filename": "images/choisir-assureur-credit.jpg",
        "alt_text": "Choisir Assureur Credit",
        "description": "Critères clés à comparer : couverture géographique, limites de garantie, services de prévention et recouvrement.",
        "badge_text": "Guide Crédit",
        "badge_color_class": "!bg-violet-700 !text-white",
        "category": "blog",
        "template_file": "blog/choisir-assureur-credit.html"
    },
    {
        "slug": "clauses-marchandises",
        "title": "ICC A, B, C : Choisir la Bonne Clause pour Vos Marchandises - mesassurances.ma",
        "url": "/blog/clauses-marchandises",
        "image_filename": "images/clauses-marchandises.jpg",
        "alt_text": "Clauses Marchandises",
        "description": "Décryptez les différences entre les principales clauses de couverture pour le transport maritime et aérien.",
        "badge_text": "Guide Marchandises",
        "badge_color_class": "!bg-emerald-600 !text-white",
        "category": "blog",
        "template_file": "blog/clauses-marchandises.html"
    },
    {
        "slug": "declarer-at",
        "title": "Comment Déclarer un Accident du Travail au Maroc ? - mesassurances.ma",
        "url": "/blog/declarer-at",
        "image_filename": "images/declarer-at.jpg",
        "alt_text": "Declarer At",
        "description": "Les étapes clés et les délais à respecter pour déclarer un accident à votre assureur et aux autorités.",
        "badge_text": "Guide Pro",
        "badge_color_class": "!bg-orange-800 !text-white",
        "category": "blog",
        "template_file": "blog/declarer-at.html"
    },
    {
        "slug": "dommages-marchandises",
        "title": "Dommages aux Marchandises Transportées : Que Faire ? - mesassurances.ma",
        "url": "/blog/dommages-marchandises",
        "image_filename": "images/dommages-marchandises.jpg",
        "alt_text": "Dommages Marchandises",
        "description": "Les étapes à suivre en cas de sinistre pour préserver vos droits et obtenir une indemnisation rapide.",
        "badge_text": "Guide Marchandises",
        "badge_color_class": "!bg-sky-600 !text-white",
        "category": "blog",
        "template_file": "blog/dommages-marchandises.html"
    },
    {
        "slug": "employeur-at",
        "title": "Loi 18-12 sur les Accidents du Travail : Ce que Tout Employeur Doit Savoir - mesassurances.ma",
        "url": "/blog/employeur-at",
        "image_filename": "images/employeur-at.jpg",
        "alt_text": "Employeur At",
        "description": "Décryptage des obligations légales de l'employeur en matière d'assurance et de réparation des AT/MP.",
        "badge_text": "Guide Pro",
        "badge_color_class": "!bg-blue-700 !text-white",
        "category": "blog",
        "template_file": "blog/employeur-at.html"
    },
    {
        "slug": "exporter-assurance-credit",
        "title": "Exporter en Toute Sécurité : Le Rôle de l'Assurance Crédit - mesassurances.ma",
        "url": "/blog/exporter-assurance-credit",
        "image_filename": "images/exporter-assurance-credit.jpg",
        "alt_text": "L'assurance crédit pour sécuriser les exportations",
        "description": "Couverture des risques commerciaux et politiques pour développer vos ventes à l'international.",
        "badge_text": "Guide Crédit",
        "badge_color_class": "!bg-teal-700 !text-white",
        "category": "blog",
        "template_file": "blog/exporter-assurance-credit.html"
    },
    {
        "slug": "garanties-flotte-auto",
        "title": "Quelles Garanties Choisir pour Votre Contrat Flotte Auto ? - mesassurances.ma",
        "url": "/blog/garanties-flotte-auto",
        "image_filename": "images/garanties-flotte-auto.jpg",
        "alt_text": "Garanties d'assurance flotte auto",
        "description": "RC, Dommages, Vol, Assistance... Adaptez les garanties aux besoins spécifiques de votre activité.",
        "badge_text": "Guide Auto Pro",
        "badge_color_class": "!bg-blue-600 !text-white",
        "category": "blog",
        "template_file": "blog/garanties-flotte-auto.html"
    },
    {
        "slug": "icoterms-et-assurances",
        "title": "Incoterms et Assurance : Qui Doit Assurer Quoi ? - mesassurances.ma",
        "url": "/blog/icoterms-et-assurances",
        "image_filename": "images/icoterms-et-assurances.jpg",
        "alt_text": "Incoterms et obligations d'assurance",
        "description": "Comprenez l'impact des Incoterms (CIF, FOB, EXW...) sur vos obligations d'assurance marchandises.",
        "badge_text": "Guide Marchandises",
        "badge_color_class": "!bg-amber-600 !text-white",
        "category": "blog",
        "template_file": "blog/icoterms-et-assurances.html"
    },
    {
        "slug": "impayes-assurance-credit",
        "title": "Impayés Clients : Comment l'Assurance Crédit Protège Votre Trésorerie ? - mesassurances.ma",
        "url": "/blog/impayes-assurance-credit",
        "image_filename": "images/impayes-assurance-credit.jpg",
        "alt_text": "Assurance crédit et protection contre les impayés",
        "description": "Comprenez le mécanisme d'indemnisation et les services de recouvrement inclus dans votre contrat.",
        "badge_text": "Guide Crédit",
        "badge_color_class": "!bg-blue-800 !text-white",
        "category": "blog",
        "template_file": "blog/impayes-assurance-credit.html"
    },
    {
        "slug": "multirisque-pro",
        "title": "Bien choisir son Assurance Multirisque Professionnelle au Maroc - mesassurances.ma",
        "url": "/blog/multirisque-pro",
        "image_filename": "images/multirisque-pro.jpg",
        "alt_text": "Assurance Multirisque Professionnelle",
        "description": "Les points clés à vérifier et les garanties à ne pas négliger lors de la souscription de votre assurance pro.",
        "badge_text": "Guide Pro",
        "badge_color_class": "!bg-orange-500 !text-white",
        "category": "blog",
        "template_file": "blog/multirisque-pro.html"
    },
    {
        "slug": "reduire-sinistralite-flotte-auto",
        "title": "Comment Réduire la Sinistralité de Votre Flotte Auto ? - mesassurances.ma",
        "url": "/blog/reduire-sinistralite-flotte-auto",
        "image_filename": "images/reduire-sinistralite-flotte-auto.jpg",
        "alt_text": "Réduire la sinistralité de la flotte auto",
        "description": "Conseils pratiques pour améliorer la sécurité de vos conducteurs et maîtriser vos primes d'assurance.",
        "badge_text": "Guide Auto Pro",
        "badge_color_class": "!bg-red-500 !text-white",
        "category": "blog",
        "template_file": "blog/reduire-sinistralite-flotte-auto.html"
    },
    {
        "slug": "responsabilite-civile-pro",
        "title": "Comprendre la RC Pro : Pourquoi est-elle essentielle ? - mesassurances.ma",
        "url": "/blog/responsabilite-civile-pro",
        "image_filename": "images/responsabilite-civile-pro.jpg",
        "alt_text": "Responsabilité Civile Professionnelle",
        "description": "Découvrez en détail la Responsabilité Civile Professionnelle, les risques couverts et son importance, même si non obligatoire.",
        "badge_text": "Guide Pro",
        "badge_color_class": "!bg-teal-500 !text-white",
        "category": "blog",
        "template_file": "blog/responsabilite-civile-pro.html"
    },
    {
        "slug": "responsabilites-armateur",
        "title": "Assurance P&I : Couvrir les Responsabilités de l'Armateur - mesassurances.ma",
        "url": "/blog/responsabilites-armateur",
        "image_filename": "images/responsabilites-armateur.jpg",
        "alt_text": "Assurance P&I pour les armateurs",
        "description": "Le rôle essentiel des Clubs P&I pour couvrir les dommages aux tiers, la pollution et autres responsabilités.",
        "badge_text": "Guide Maritime",
        "badge_color_class": "!bg-teal-500 !text-white",
        "category": "blog",
        "template_file": "blog/responsabilites-armateur.html"
    },
    {
        "slug": "comparateur-de-garanties",
        "title": "Comparateur de Garanties d'Assurance : Comprendre et Choisir sa Couverture au Maroc - mesassurances.ma",
        "url": "/outils/comparateur-de-garanties",
        "image_filename": "images/comparateur-de-garanties.jpg",
        "alt_text": "Outil de comparaison de garanties d'assurance",
        "description": "Découvrez comment utiliser un comparateur de garanties pour choisir la meilleure couverture d'assurance (auto, habitation, santé) au Maroc.",
        "badge_text": "Comparateur",
        "badge_color_class": "!bg-green-100 !text-green-800",
        "category": "outils",
        "template_file": "blog/comparateur-de-garanties.html"
    },
    {
        "slug": "controle-technique",
        "title": "Le Contrôle Technique au Maroc : Guide Complet des Démarches et Papiers - mesassurances.ma",
        "url": "/blog/controle-technique",
        "image_filename": "images/controle-technique.jpg",
        "alt_text": "Guide complet du contrôle technique au Maroc",
        "description": "Découvrez le guide complet du contrôle technique au Maroc : démarches, documents nécessaires, et conseils pour une visite réussie.",
        "badge_text": "Guide Pratique",
        "badge_color_class": "!bg-blue-100 !text-blue-800",
        "category": "blog",
        "template_file": "blog/controle-technique.html"
    },
    {
        "slug": "declaration-de-sinistre",
        "title": "Guide de Déclaration de Sinistre (Auto, Habitation, Santé) au Maroc - mesassurances.ma",
        "url": "/blog/declaration-de-sinistre",
        "image_filename": "images/declaration-sinistre.jpg",
        "alt_text": "Guide de déclaration de sinistre au Maroc",
        "description": "Un guide complet pour déclarer un sinistre auto, habitation ou santé au Maroc, avec les étapes et documents essentiels.",
        "badge_text": "Déclaration Sinistre",
        "badge_color_class": "!bg-red-100 !text-red-800",
        "category": "blog",
        "template_file": "blog/declaration-de-sinistre.html"
    },
    {
        "slug": "verificateur-de-couverture-assurance",
        "title": "Vérificateur de Couverture d'Assurance : Guide pour Décrypter Votre Contrat au Maroc - mesassurances.ma",
        "url": "/outils/verificateur-de-couverture-assurance",
        "image_filename": "images/verificateur-couverture.jpg",
        "alt_text": "Outil de vérification de couverture d'assurance",
        "description": "Apprenez à décrypter votre contrat d'assurance au Maroc et à vérifier l'étendue de votre couverture pour éviter les mauvaises surprises.",
        "badge_text": "Vérificateur",
        "badge_color_class": "!bg-purple-100 !text-purple-800",
        "category": "outils",
        "template_file": "blog/verificateur-de-couverture-assurance.html"
    },
    {
        "slug": "assurance-accident-travail-obligations",
        "title": "Assurance Accidents du Travail au Maroc : Obligations Légales pour les Entreprises - mesassurances.ma",
        "url": "/blog/assurance-accident-travail-obligations",
        "image_filename": "images/assurance-accident-travail-obligations.jpg",
        "alt_text": "Obligations légales assurance accident travail Maroc",
        "description": "Découvrez les obligations légales de l'assurance accident de travail au Maroc. Cadre réglementaire, responsabilités employeur, sanctions et conformité avec la loi 18-12.",
        "badge_text": "Obligations Légales",
        "badge_color_class": "!bg-red-100 !text-red-800",
        "category": "blog",
        "template_file": "blog/assurance-accident-travail-obligations.html"
    },
    {
        "slug": "tarif-assurance-accident-travail",
        "title": "Tarif et Calcul de l'Assurance Accident de Travail au Maroc : Guide Complet 2025 - mesassurances.ma",
        "url": "/blog/tarif-assurance-accident-travail",
        "image_filename": "images/tarif-assurance-accident-travail.jpg",
        "alt_text": "Tarif assurance accident travail Maroc",
        "description": "Découvrez comment calculer le tarif de votre assurance accident de travail au Maroc. Facteurs de coût, optimisation des primes et conseils pour réduire vos frais.",
        "badge_text": "Tarifs & Coûts",
        "badge_color_class": "!bg-green-100 !text-green-800",
        "category": "blog",
        "template_file": "blog/tarif-assurance-accident-travail.html"
    },
    {
        "slug": "choisir-assurance-accident-travail",
        "title": "Comment Bien Choisir son Assurance Accidents du Travail au Maroc ? Guide 2025 - mesassurances.ma",
        "url": "/blog/choisir-assurance-accident-travail",
        "image_filename": "images/choisir-assurance-accident-travail.jpg",
        "alt_text": "Comment choisir assurance accident travail Maroc",
        "description": "Guide complet pour choisir la meilleure assurance accident de travail au Maroc. Critères de sélection, comparaison des assureurs et conseils d'experts.",
        "badge_text": "Guide d'Achat",
        "badge_color_class": "!bg-blue-100 !text-blue-800",
        "category": "blog",
        "template_file": "blog/choisir-assurance-accident-travail.html"
    },
    {
        "slug": "assurance-at-rc",
        "title": "Assurance AT & RC : Couverture Complémentaire Indispensable pour votre Entreprise - mesassurances.ma",
        "url": "/blog/assurance-at-rc",
        "image_filename": "images/assurance-at-rc.jpg",
        "alt_text": "Assurance AT et RC Maroc",
        "description": "Découvrez pourquoi combiner assurance accident de travail et responsabilité civile est essentiel. Guide complet sur la complémentarité AT et RC au Maroc.",
        "badge_text": "Couverture Complète",
        "badge_color_class": "!bg-purple-100 !text-purple-800",
        "category": "blog",
        "template_file": "blog/assurance-at-rc.html"
    },
]


# Setup Flask-Mail
mail = Mail()


def create_app(test_config=None):
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, instance_relative_config=True)

    db_directory = os.path.join(os.getcwd(), 'instance') # Use current working directory for instance folder
    db_name = 'assurances.db'
    absolute_db_path = os.path.join(db_directory, db_name)

    app.config.from_mapping(
        # SECRET_KEY for Flask session management - MUST be set in environment
        SECRET_KEY=os.environ.get('SECRET_KEY'),
        DATABASE=absolute_db_path,

        # Google OAuth Client ID - MUST be set in environment
        GOOGLE_CLIENT_ID=os.environ.get("GOOGLE_CLIENT_ID"),

        # Admin Review Panel Password - MUST be set in environment
        ADMIN_REVIEW_PASSWORD=os.environ.get('ADMIN_REVIEW_PASSWORD'),

        # Mail configuration for Zeptomail - ALL MUST be set in environment
        MAIL_SERVER=os.environ.get('MAIL_SERVER'),
        MAIL_PORT=int(os.environ.get('MAIL_PORT')) if os.environ.get('MAIL_PORT') else None, # Convert to int
        MAIL_USE_TLS=os.environ.get('MAIL_USE_TLS', 'False').lower() == 'true', # Convert string to boolean, default to False
        MAIL_USERNAME=os.environ.get('MAIL_USERNAME'),
        MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD'),
        # Default sender can be MAIL_USERNAME if MAIL_DEFAULT_SENDER is not explicitly set
        MAIL_DEFAULT_SENDER=os.environ.get('MAIL_DEFAULT_SENDER') or os.environ.get('MAIL_USERNAME'),

        # Gemini AI API Key - MUST be set in environment
        GEMINI_API_KEY=os.environ.get('GEMINI_API_KEY'),

        # Enable exception propagation for better error logging
        PROPAGATE_EXCEPTIONS=True,
        # Don't trap HTTP exceptions - let them propagate for logging
        TRAP_HTTP_EXCEPTIONS=False
    )

    # Validate essential environment variables are set.
    if not app.config.get('SECRET_KEY'):
        raise ValueError("SECRET_KEY environment variable is not set. This is critical for session security.")
    if not app.config.get('GOOGLE_CLIENT_ID'):
        app.logger.warning("GOOGLE_CLIENT_ID environment variable is not set. Google OAuth will not function.")
    if not app.config.get('ADMIN_REVIEW_PASSWORD'):
        raise ValueError("ADMIN_REVIEW_PASSWORD environment variable is not set. Admin panel access will be blocked.")

    # Mail configuration validation
    if not all([app.config.get('MAIL_SERVER'), app.config.get('MAIL_PORT'),
                app.config.get('MAIL_USERNAME'), app.config.get('MAIL_PASSWORD')]):
        app.logger.error("One or more MAIL_* environment variables are not set. Email functionality may fail.")

    if not app.config.get('GEMINI_API_KEY'):
        app.logger.warning("GEMINI_API_KEY environment variable is not set. AI functionality might be disabled.")


    if test_config is None:
        app.config.from_pyfile('config.py', silent=True)
    else:
        app.config.from_mapping(test_config)

    try:
        # Ensure the instance folder exists
        os.makedirs(app.instance_path, exist_ok=True)
        # Ensure the database directory itself exists
        if not os.path.exists(db_directory):
            os.makedirs(db_directory, exist_ok=True)
            app.logger.info(f"Created database directory: {db_directory}")
    except OSError as e:
        app.logger.error(f"Could not create instance/database folder: {e}")

    database.init_app(app)

    # SECURITY ENHANCEMENTS - Added for enhanced security
    secure_session_config(app)
    os.makedirs('logs', exist_ok=True)
    setup_security_logging(app)
    init_security_middleware(app)

    # Initialize Flask-Mail
    mail = Mail(app)

    # --- UPDATED: Location-aware notification function for confidentiality ---
    def send_notifications_for_new_lead(lead_type, lead_location):
        """Finds relevant professionals based on lead location and sends them individual email notifications for confidentiality."""

        prof_user_list_str = os.environ.get('PROF_USER_LIST', '')
        if not prof_user_list_str:
            current_app.logger.warning("PROF_USER_LIST environment variable is not set. No notifications will be sent.")
            return

        # Map lead_type (display name) to table_name
        table_name = None
        for tn, config in ASSURANCE_TABLES_CONFIG.items():
            if config["name"] == lead_type or config["name"] == f"Assurance {lead_type}":
                table_name = tn
                break

        # If no exact match, try some common mappings
        if not table_name:
            type_mapping = {
                "Stage": "assurance_stage",
                "Ecole": "assurance_ecole",
                "Cybersécurité": "assurance_cybersecurity",
                "Auto-entrepreneur": "assurance_autoentrepreneur"
            }
            table_name = type_mapping.get(lead_type)

        all_usernames = [name.strip() for name in prof_user_list_str.split(',') if name.strip()]

        recipients = []

        for username in all_usernames:
            is_admin_str = os.environ.get(f'PROF_USER_{username.upper()}_IS_ADMIN', 'False')
            is_admin = is_admin_str.lower() == 'true'

            # Check category-specific access if table_name is known
            has_access = False
            if table_name:
                category_access = get_user_category_access(username, is_admin)
            else:
                category_access = None

            if table_name:
                if category_access is None:
                    # Old behavior: use LOCATIONS
                    locations_str = os.environ.get(f'PROF_USER_{username.upper()}_LOCATIONS', '')
                    allowed_locations = [loc.strip() for loc in locations_str.split(',')] if locations_str else []
                    has_access = is_admin or not allowed_locations or (lead_location and lead_location in allowed_locations)
                else:
                    # New behavior: check category-specific access
                    if is_admin:
                        has_access = True
                    elif table_name in category_access:
                        rule = category_access[table_name]
                        if isinstance(rule, dict):
                            allowed = rule.get("allowed", [])
                            blocked = rule.get("blocked", [])
                            if blocked:
                                has_access = bool(lead_location) and lead_location not in blocked
                            elif allowed:
                                has_access = bool(lead_location) and lead_location in allowed
                            else:
                                # Empty allowed/blocked => all Morocco
                                has_access = True
                        else:
                            # Backward compatibility if rule is still a list
                            category_locations = rule
                            has_access = (not category_locations) or (lead_location and lead_location in category_locations)
                    else:
                        # No specific rule for this category - check old LOCATIONS as fallback
                        locations_str = os.environ.get(f'PROF_USER_{username.upper()}_LOCATIONS', '')
                        allowed_locations = [loc.strip() for loc in locations_str.split(',')] if locations_str else []
                        has_access = not allowed_locations or (lead_location and lead_location in allowed_locations)
            else:
                # Fallback to old behavior if table_name not found
                locations_str = os.environ.get(f'PROF_USER_{username.upper()}_LOCATIONS', '')
                allowed_locations = [loc.strip() for loc in locations_str.split(',')] if locations_str else []
                has_access = is_admin or not allowed_locations or (lead_location and lead_location in allowed_locations)

            if has_access:
                user_email = os.environ.get(f'PROF_USER_{username.upper()}_EMAIL')
                if user_email:
                    recipients.append(user_email)
                else:
                    current_app.logger.warning(f"Email not found for professional user: {username}")

        if not recipients:
            current_app.logger.info(f"No recipients found for a new {lead_type} lead in {lead_location}.")
            return

        subject = f"Nouveau lead Assurance {lead_type} sur mesassurances.ma ({lead_location})"

        # Get current date for the email template
        from datetime import datetime
        submission_date = datetime.now().strftime("%d/%m/%Y à %H:%M")

        # Render HTML template
        html_body = render_template('emails/professional_lead_notification.html',
                                  lead_type=lead_type,
                                  lead_location=lead_location,
                                  submission_date=submission_date)

        # Fallback plain text body
        text_body = f"""
        Cher partenaire,

        Un nouveau lead de type "Assurance {lead_type}" vient d'être enregistré pour la localisation : {lead_location}.

        Nous vous invitons à consulter le marché des leads sur votre espace pour plus de détails et pour y accéder :
        https://www.mesassurances.ma/business

        Cordialement,
        L'équipe mesassurances.ma
        """

        unique_recipients = list(set(recipients))

        try:
            with app.app_context():
                # Use a connection to send multiple emails efficiently and individually
                with mail.connect() as conn:
                    for recipient_email in unique_recipients:
                        msg = Message(subject,
                                      sender=current_app.config['MAIL_DEFAULT_SENDER'],
                                      recipients=[recipient_email]) # Send to one recipient at a time
                        msg.html = html_body
                        msg.body = text_body
                        conn.send(msg)
                        current_app.logger.info(f"Sent individual notification for new {lead_type} lead to: {recipient_email}")

            current_app.logger.info(f"All notifications sent successfully for new {lead_type} lead in {lead_location}.")
            return True
        except Exception as e:
            current_app.logger.error(f"Failed to send one or more emails for new {lead_type} lead in {lead_location}: {e}", exc_info=True)
            return False


    # --- UPDATED: User confirmation email function with broker name ---
    def send_user_confirmation_email(user_email, insurance_category, location):
        """
        Sends a confirmation email to the user after they fill an insurance category form.
        Attempts to include a specific broker's company name based on location.
        """
        broker_name = "courtier" # Default generic broker name

        prof_user_list_str = os.environ.get('PROF_USER_LIST', '')
        if prof_user_list_str:
            all_usernames = [name.strip() for name in prof_user_list_str.split(',') if name.strip()]
            for username in all_usernames:
                locations_str = os.environ.get(f'PROF_USER_{username.upper()}_LOCATIONS', '')
                allowed_locations = [loc.strip() for loc in locations_str.split(',')] if locations_str else []

                if location and location in allowed_locations:
                    # Found a broker for this location, use their company name
                    broker_company_name = os.environ.get(f'PROF_USER_{username.upper()}_COMPANY')
                    if broker_company_name:
                        broker_name = broker_company_name
                        break # Take the first one found for simplicity
        else:
            current_app.logger.warning("PROF_USER_LIST environment variable is not set. Cannot determine specific broker for user email.")

        subject = "Votre demande MesAssurances a été enregistrée !"

        # Get current date for the email template
        from datetime import datetime
        submission_date = datetime.now().strftime("%d/%m/%Y à %H:%M")

        # Render HTML template
        html_body = render_template('emails/user_confirmation.html',
                                  insurance_category=insurance_category,
                                  location=location,
                                  broker_name=broker_name,
                                  submission_date=submission_date)

        # Fallback plain text body
        text_body = f"""
        Bonjour,

        Votre demande de devis ou estimation "{insurance_category}" a été enregistrée et notre partenaire {broker_name} dans la région de "{location}" vous contactera dans les plus brefs délais.

        L'objectif est de comprendre votre besoin, vous conseiller et vous présenter les offres des compagnies d'assurances.

        Nous sommes ravis de vous compter parmi les utilisateurs de MesAssurances, une plateforme 100% Marocaine de mise en relation avec des courtiers de confiance.

        Cordialement,
        L'équipe MesAssurances
        """

        try:
            with app.app_context():
                msg = Message(subject,
                              sender=current_app.config['MAIL_DEFAULT_SENDER'],
                              recipients=[user_email])
                msg.html = html_body
                msg.body = text_body
                mail.send(msg)
                current_app.logger.info(f"Sent user confirmation email for {insurance_category} to: {user_email} via broker: {broker_name}")
                return True
        except Exception as e:
            current_app.logger.error(f"Failed to send user confirmation email for {insurance_category} to {user_email}: {e}", exc_info=True)
            return False


    def send_first_login_email(user_email, user_name):
        """Send the welcome email to users after their first successful login."""
        subject = "Bienvenue sur MesAssurances.ma"
        safe_name = user_name or "cher utilisateur"

        html_body = render_template(
            'emails/first_login_welcome.html',
            user_name=user_name
        )

        text_body = f"""
        Bonjour {safe_name},

        MesAssurances.ma est une plateforme de mise en relation avec des courtiers agréés. Notre mission est de faciliter l'accès à l'information et de vous aider à trouver les meilleurs conseils et offres d'assurance.

        Ajoutez vos assurances actives depuis votre espace : cela prend moins de 20 secondes et peut vous aider à obtenir une meilleure couverture, un meilleur prix et un meilleur service au moment du renouvellement.

        Accédez à votre espace : https://www.mesassurances.ma/moncompte
        Explorez toutes nos ressources : https://www.mesassurances.ma

        MesAssurances a effectué la notification CNDP relative à l'utilisation des données personnelles : nous sommes conformes.

        L'équipe MesAssurances.ma
        """

        try:
            with app.app_context():
                msg = Message(
                    subject,
                    sender=current_app.config['MAIL_DEFAULT_SENDER'],
                    recipients=[user_email]
                )
                msg.html = html_body
                msg.body = text_body
                mail.send(msg)
                current_app.logger.info(f"Sent first login email to: {user_email}")
                return True
        except Exception as e:
            current_app.logger.error(f"Failed to send first login email to {user_email}: {e}", exc_info=True)
            return False


    def send_fca_voyage_email(user_email, user_name, pdf_data, filename):
        """Send FCA voyage devis email with attached PDF."""
        subject = "Votre devis Assurance Voyage - FCA Assurances"
        safe_name = user_name.strip() if user_name and user_name.strip() else "cher client"
        whatsapp_number = "+212661094199"
        whatsapp_url = "https://wa.me/212661094199"

        html_body = f"""
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Votre devis Assurance Voyage</title>
        </head>
        <body style="margin:0;padding:0;font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;background-color:#f5f5f5;">
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color:#f5f5f5;">
                <tr>
                    <td align="center" style="padding:40px 20px;">
                        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="background-color:#ffffff;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">
                            <tr>
                                <td style="background:linear-gradient(135deg,#2563eb 0%,#1e40af 100%);padding:30px;text-align:center;border-radius:8px 8px 0 0;">
                                    <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:700;">Merci d'avoir utilisé MesAssurances.ma</h1>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding:40px 30px;">
                                    <p style="margin:0 0 20px 0;color:#1e293b;font-size:16px;line-height:1.6;">
                                        Bonjour {safe_name},
                                    </p>
                                    <p style="margin:0 0 20px 0;color:#1e293b;font-size:16px;line-height:1.6;">
                                        Nous vous remercions d'avoir utilisé <strong>MesAssurances.ma</strong> pour votre demande d'assurance voyage.
                                    </p>
                                    <p style="margin:0 0 20px 0;color:#1e293b;font-size:16px;line-height:1.6;">
                                        Votre devis, de notre partenaire <strong>FCA Assurances</strong>, est disponible en pièce jointe de cet email. Vous pouvez le télécharger et le consulter à tout moment.
                                    </p>
                                    <div style="background-color:#eff6ff;border-left:4px solid #2563eb;padding:20px;margin:30px 0;border-radius:4px;">
                                        <p style="margin:0 0 10px 0;color:#1e40af;font-size:16px;font-weight:600;">
                                            📋 Prochaines étapes
                                        </p>
                                        <p style="margin:0;color:#1e293b;font-size:15px;line-height:1.6;">
                                            Pour finaliser votre offre, contactez <strong>FCA Assurances</strong>, préparez votre carte d'identité (CIN) et le paiement par virement bancaire.
                                        </p>
                                    </div>
                                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin:30px 0;">
                                        <tr>
                                            <td align="center">
                                                <a href="{whatsapp_url}" style="display:inline-block;background-color:#25D366;color:#ffffff;text-decoration:none;padding:14px 28px;border-radius:6px;font-weight:600;font-size:16px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">
                                                    <span style="display:inline-block;margin-right:8px;">💬</span>
                                                    Contacter FCA Assurances sur WhatsApp
                                                </a>
                                            </td>
                                        </tr>
                                    </table>
                                    <p style="margin:0 0 20px 0;color:#64748b;font-size:14px;line-height:1.6;text-align:center;">
                                        Ou contactez-les directement au <strong>{whatsapp_number}</strong>
                                    </p>
                                    <hr style="border:none;border-top:1px solid #e5e7eb;margin:30px 0;">
                                    <p style="margin:0 0 10px 0;color:#64748b;font-size:14px;line-height:1.6;">
                                        <strong>Rappel :</strong> MesAssurances.ma agit uniquement en tant que plateforme de mise en relation technique.
                                        FCA Assurances est responsable de la finalisation de votre contrat d'assurance.
                                    </p>
                                </td>
                            </tr>
                            <tr>
                                <td style="background-color:#f8fafc;padding:20px 30px;text-align:center;border-radius:0 0 8px 8px;border-top:1px solid #e5e7eb;">
                                    <p style="margin:0 0 10px 0;color:#64748b;font-size:12px;">
                                        <strong>MesAssurances.ma</strong><br>
                                        Plateforme d'éducation et mise en relation technique
                                    </p>
                                    <p style="margin:0;color:#94a3b8;font-size:11px;">
                                        Cet email a été envoyé à {user_email}
                                    </p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

        text_body = f"""
Merci d'avoir utilisé MesAssurances.ma

Bonjour {safe_name},

        Nous vous remercions d'avoir utilisé MesAssurances.ma pour votre demande d'assurance voyage.

Votre devis, de notre partenaire FCA Assurances, est disponible en pièce jointe de cet email.

📋 Prochaines étapes
Contactez FCA Assurances, préparez votre carte d'identité (CIN) et le paiement par virement bancaire.

        Pour finaliser votre offre, contactez FCA Assurances, préparez votre carte d'identité (CIN) et le paiement par virement bancaire.

        💬 Contacter FCA Assurances sur WhatsApp : {whatsapp_number}
        Ou via ce lien : {whatsapp_url}

        Rappel : MesAssurances.ma agit uniquement en tant que plateforme de mise en relation technique.
        FCA Assurances est responsable de la finalisation de votre contrat d'assurance.

MesAssurances.ma
Plateforme d'éducation et mise en relation technique

Cet email a été envoyé à {user_email}
        """

        try:
            with app.app_context():
                msg = Message(
                    subject=subject,
                    sender=current_app.config['MAIL_DEFAULT_SENDER'],
                    recipients=[user_email],
                    cc=["production@fca.ma"]
                )
                msg.html = html_body
                msg.body = text_body
                msg.attach(filename, 'application/pdf', pdf_data)
                mail.send(msg)
                current_app.logger.info(f"Sent FCA voyage devis email to: {user_email}")
                return True
        except Exception as e:
            current_app.logger.error(f"Failed to send FCA voyage devis email to {user_email}: {e}", exc_info=True)
            return False
    # --- OTP Functions ---
    def generate_otp_code():
        """Generate a 4-digit OTP code"""
        return str(secrets.randbelow(9000) + 1000)  # Generates 1000-9999

    def send_otp_email(user_email, otp_code):
        """Send OTP verification email to user"""
        subject = "Code de Vérification - MesAssurances.ma"

        # Render HTML template
        html_body = render_template('emails/otp_verification.html', otp_code=otp_code)

        # Fallback plain text body
        text_body = f"""
        Bonjour,

        Votre code de vérification est : {otp_code}

        Ce code est valide pendant 2 minutes. Entrez-le dans le formulaire pour confirmer votre demande.

        Si vous n'avez pas demandé ce code, veuillez ignorer cet email.

        Cordialement,
        L'équipe MesAssurances.ma
        """

        try:
            with app.app_context():
                msg = Message(subject,
                              sender=current_app.config['MAIL_DEFAULT_SENDER'],
                              recipients=[user_email])
                msg.html = html_body
                msg.body = text_body
                mail.send(msg)
                current_app.logger.info(f"Sent OTP email to: {user_email}")
                return True
        except Exception as e:
            current_app.logger.error(f"Failed to send OTP email to {user_email}: {e}", exc_info=True)
            return False

    def store_otp_in_session(otp_code, email, lead_id):
        """Store OTP data in session for verification"""
        session['otp_code'] = otp_code
        session['otp_email'] = email
        session['otp_lead_id'] = lead_id
        session['otp_timestamp'] = time.time()

    def verify_otp_code(entered_code, email):
        """Verify OTP code from session"""
        if 'otp_code' not in session or 'otp_email' not in session or 'otp_timestamp' not in session:
            return False

        # Check if email matches
        if session['otp_email'] != email:
            return False

        # Check if code matches
        if session['otp_code'] != entered_code:
            return False

        # Check if code is still valid (2 minutes = 120 seconds)
        if time.time() - session['otp_timestamp'] > 120:
            return False

        return True

    def clear_otp_session():
        """Clear OTP data from session"""
        session.pop('otp_code', None)
        session.pop('otp_email', None)
        session.pop('otp_lead_id', None)
        session.pop('otp_timestamp', None)


    # --- Admin Decorator (for professional users) ---
    def admin_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'professional_user_id' not in session:
                return jsonify({"success": False, "message": "Authentification requise.", "redirectToLogin": True}), 401
            is_admin = session.get('professional_is_admin', False)
            if not is_admin:
                return jsonify({"success": False, "message": "Accès administrateur requis."}), 403
            return f(*args, **kwargs)
        return decorated_function

    # --- Review Admin Decorator (simple password based for /admin/reviews) ---
    def review_admin_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('review_admin_logged_in'):
                return redirect(url_for('admin_review_login', next=request.url))
            return f(*args, **kwargs)
        return decorated_function


    def get_consent_value(form_field_name):
        return 'oui' if request.form.get(form_field_name) else 'non'

    @app.route('/auth/google', methods=['POST'])
    @rate_limit('auth')  # Add rate limiting decorator
    def auth_google():
        try:
            token_id_from_client = request.json.get('token')

            # Use secure OAuth validation
            success, user_data, error_message = secure_google_oauth_validation(token_id_from_client)

            if not success:
                return jsonify({"success": False, "message": error_message}), 400

            # Use validated user_data
            google_id = user_data['google_id']
            email = user_data['email']
            name = user_data['name']

            # Database operations with validated data
            db = database.get_db()
            cursor = db.execute('SELECT * FROM users WHERE google_id = ? OR email = ?', (google_id, email))
            user = cursor.fetchone()

            needs_first_login_email = False

            if user:
                # Update existing user
                if not user['google_id']:
                    db.execute('UPDATE users SET google_id = ? WHERE id = ?', (google_id, user['id']))
                if user['name'] != name:
                    db.execute('UPDATE users SET name = ? WHERE id = ?', (name, user['id']))
                db.commit()

                user_id_in_db = user['id']
                user_flag_keys = user.keys()
                has_first_login_flag = 'first_login_email_sent' in user_flag_keys
                flag_value = user['first_login_email_sent'] if has_first_login_flag else 0
                if not flag_value:
                    needs_first_login_email = True
            else:
                # Create new user
                cursor = db.execute(
                    'INSERT INTO users (google_id, email, name) VALUES (?, ?, ?)',
                    (google_id, email, name)
                )
                db.commit()
                user_id_in_db = cursor.lastrowid
                needs_first_login_email = True

            # Set session data
            session.clear()
            session['user_id'] = user_id_in_db
            session['user_name'] = name
            session['user_email'] = email
            session['google_id'] = google_id

            # Send first login email if needed
            if needs_first_login_email:
                email_sent = send_first_login_email(email, name)
                if email_sent:
                    try:
                        db.execute('UPDATE users SET first_login_email_sent = 1 WHERE id = ?', (user_id_in_db,))
                        db.commit()
                    except sqlite3.Error as update_error:
                        db.rollback()
                        current_app.logger.error(f"Failed to update first_login_email_sent flag for {email}: {update_error}")
                else:
                    current_app.logger.warning(f"First login email could not be sent to {email}. Flag not updated.")

            current_app.logger.info(f"User {email} authenticated successfully via Google.")
            return jsonify({
                "success": True,
                "message": "Authentication successful.",
                "user": {"id": user_id_in_db, "name": name, "email": email}
            })

        except Exception as e:
            current_app.logger.error(f"OAuth error: {e}")
            return jsonify({"success": False, "message": "Erreur d'authentification"}), 500
            return jsonify({"success": False, "message": "An unexpected error occurred."}), 500

    @app.route('/auth/logout', methods=['POST'])
    def auth_logout():
        user_email = session.get('user_email', 'Unknown user')
        session.clear()
        current_app.logger.info(f"User {user_email} logged out.")
        return jsonify({"success": True, "message": "Logged out successfully."})

    @app.route('/auth/status', methods=['GET'])
    def auth_status():
        if 'user_id' in session and 'user_email' in session:
            return jsonify({
                "isLoggedIn": True,
                "user": {
                    "id": session['user_id'],
                    "name": session.get('user_name'),
                    "email": session.get('user_email')
                }
            })
        else:
            return jsonify({"isLoggedIn": False})

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/ar/')
    def index_ar():
        return render_template('index-ar.html')

    def get_current_user_id():
        return session.get('user_id')


    @app.route('/robots.txt')
    def robots_txt():
        return send_from_directory(app.static_folder, 'robots.txt')

    @app.route('/cdn-cgi/l/email-protection')
    def cloudflare_email_protection():
        return '', 200

    @app.route('/sitemap.xml')
    def sitemap_xml():
        return send_from_directory(app.static_folder, 'sitemap.xml')

    @app.route('/sitemap-images.xml')
    def sitemap_images_xml():
        """Generate and return image sitemap dynamically from blog/outil data"""
        base_url = "https://www.mesassurances.ma"

        xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml_parts.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"')
        xml_parts.append('        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">')

        # Get all items (blog and outils) that have images
        items_with_images = [
            item for item in BLOG_AND_OUTILS_DATA
            if 'image_filename' in item and item['image_filename']
        ]

        for item in items_with_images:
            page_url = f"{base_url}{item['url']}"
            image_url = f"{base_url}/static/{item['image_filename']}"

            xml_parts.append('  <url>')
            xml_parts.append(f'    <loc>{page_url}</loc>')
            xml_parts.append('    <image:image>')
            xml_parts.append(f'      <image:loc>{image_url}</image:loc>')

            # Add title and caption from alt_text or title
            if 'alt_text' in item and item['alt_text']:
                # Escape XML special characters (but not apostrophes - they're fine in text content)
                alt_text = item['alt_text'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                xml_parts.append(f'      <image:title>{alt_text}</image:title>')
                xml_parts.append(f'      <image:caption>{alt_text}</image:caption>')
            elif 'title' in item:
                title = item['title'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                xml_parts.append(f'      <image:title>{title}</image:title>')

            xml_parts.append('    </image:image>')
            xml_parts.append('  </url>')

        xml_parts.append('</urlset>')

        response = app.response_class(
            response='\n'.join(xml_parts),
            mimetype='application/xml'
        )
        return response


    # --- Insurance Form Routes ---
    @app.route('/assurance-auto', methods=['GET', 'POST'])
    def auto():
        if request.method == 'POST':
            db = None
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_auto')
                user_email_to_use = email_form

                # Step 1: Vehicle Information
                marque = request.form.get('marque')
                modele = request.form.get('modele')
                carburant = request.form.get('carburant')
                nombre_places = request.form.get('nombre-places')
                puissance_fiscale = request.form.get('puissance-fiscale')
                date_mec = request.form.get('date-mec')
                type_plaque = request.form.get('type-plaque')
                immatriculation = request.form.get('immatriculation')
                valeur_neuf = request.form.get('valeur-neuf')
                valeur_actuelle = request.form.get('valeur-actuelle')  # Maps to prix_estime column

                # Step 2: Personal Information
                nom = request.form.get('nom')
                prenom = request.form.get('prenom')
                telephone_auto = request.form.get('telephone_auto')
                date_naissance = request.form.get('date-naissance')
                date_permis = request.form.get('date-permis')
                ville_auto = request.form.get('ville_auto')
                assureur_actuel = request.form.get('assureur_actuel', '')  # Optional field
                consent_auto = get_consent_value('consent_auto')

                # Validate required fields
                if not all([marque, modele, carburant, nombre_places, puissance_fiscale, date_mec,
                           type_plaque, immatriculation, valeur_neuf, valeur_actuelle,
                           nom, prenom, date_naissance, date_permis, ville_auto, email_form,
                           telephone_auto, consent_auto == 'oui']):
                    return jsonify({"success": False, "message": "Veuillez remplir tous les champs requis, y compris le consentement."}), 400

                # Extract year from date_mec for annee_circulation (backward compatibility)
                try:
                    if date_mec:
                        mec_date = datetime.strptime(date_mec, '%Y-%m-%d')
                        annee_circulation = mec_date.year
                        if annee_circulation < 1950 or annee_circulation > datetime.now().year + 1:
                            raise ValueError("Date de mise en circulation invalide.")
                    else:
                        return jsonify({"success": False, "message": "Date de mise en circulation requise."}), 400
                except (ValueError, TypeError) as e:
                    return jsonify({"success": False, "message": "Date de mise en circulation invalide."}), 400

                # Validate valeur_neuf and valeur_actuelle
                try:
                    valeur_neuf = float(valeur_neuf)
                    valeur_actuelle = float(valeur_actuelle)
                    if valeur_neuf <= 0:
                        raise ValueError("La valeur à neuf doit être positive.")
                    if valeur_actuelle <= 0:
                        raise ValueError("La valeur actuelle doit être positive.")
                except (ValueError, TypeError):
                    return jsonify({"success": False, "message": "Valeurs invalides."}), 400

                # Validate nombre_places
                try:
                    nombre_places = int(nombre_places)
                    if nombre_places < 2 or nombre_places > 9:
                        raise ValueError("Le nombre de places doit être entre 2 et 9.")
                except (ValueError, TypeError):
                    return jsonify({"success": False, "message": "Nombre de places invalide."}), 400

                # Validate puissance_fiscale
                try:
                    puissance_fiscale = int(puissance_fiscale)
                    if puissance_fiscale < 2:
                        raise ValueError("Puissance fiscale invalide.")
                except (ValueError, TypeError):
                    return jsonify({"success": False, "message": "Puissance fiscale invalide."}), 400

                # Validate dates
                try:
                    date_naissance_obj = datetime.strptime(date_naissance, '%Y-%m-%d')
                    date_permis_obj = datetime.strptime(date_permis, '%Y-%m-%d')
                    if date_naissance_obj > datetime.now():
                        raise ValueError("La date de naissance ne peut pas être dans le futur.")
                    if date_permis_obj > datetime.now():
                        raise ValueError("La date de délivrance du permis ne peut pas être dans le futur.")
                except (ValueError, TypeError):
                    return jsonify({"success": False, "message": "Dates invalides."}), 400

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                # Insert lead into database (always record the lead)
                # Note: prix_estime column stores valeur_actuelle, valeur_neuf is stored in valeur_neuf column
                cursor = db.execute(
                    """INSERT INTO assurance_auto
                       (user_id, marque, modele, prix_estime, valeur_neuf, carburant, annee_circulation, date_mec,
                        puissance_fiscale, type_plaque, immatriculation, nombre_places, ville, email, telephone,
                        nom, prenom, date_naissance, date_permis, assureur_actuel, consentement, action_type, status, verified)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', FALSE)""",
                    (
                        current_user_id, marque, modele, valeur_actuelle, valeur_neuf, carburant, annee_circulation, date_mec,
                        puissance_fiscale, type_plaque, immatriculation, nombre_places, ville_auto, user_email_to_use, telephone_auto,
                        nom, prenom, date_naissance, date_permis, assureur_actuel, consent_auto, action_type
                    )
                )
                db.commit()
                lead_id = cursor.lastrowid

                # Generate and send OTP code
                otp_code = generate_otp_code()
                store_otp_in_session(otp_code, user_email_to_use, lead_id)

                # Send OTP email
                otp_sent = send_otp_email(user_email_to_use, otp_code)

                if not otp_sent:
                    current_app.logger.warning(f"Failed to send OTP email to {user_email_to_use}, but lead was recorded")

                # Send notifications and confirmation emails as before
                if action_type == 'quote':
                    send_notifications_for_new_lead("Auto", ville_auto)

                # Send confirmation email to user
                send_user_confirmation_email(user_email_to_use, "Auto", ville_auto)

                return jsonify({
                    "success": True,
                    "message": "Votre demande a été enregistrée. Un code de vérification a été envoyé à votre email.",
                    "otp_required": True,
                    "lead_id": lead_id
                }), 200

            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in /assurance-auto POST: {e}")
                if db: db.rollback()
                return jsonify({"success": False, "message": f"Une erreur de base de données est survenue: {e}"}), 500
            except Exception as e:
                current_app.logger.error(f"General error in /assurance-auto POST: {e}", exc_info=True)
                if db: db.rollback()
                return jsonify({"success": False, "message": f"Une erreur est survenue lors de la soumission: {e}"}), 500

        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('auto.html', user_info=user_info)

    @app.route('/ar/assurance-auto', methods=['GET', 'POST'])
    def auto_ar():
        if request.method == 'POST':
            db = None
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_auto')
                user_email_to_use = email_form

                marque = request.form.get('marque')
                modele = request.form.get('modele')
                prix_estime = request.form.get('prix-estime')
                carburant = request.form.get('carburant')
                annee_circulation = request.form.get('annee-circulation')
                puissance_fiscale = request.form.get('puissance-fiscale')
                ville_auto = request.form.get('ville_auto')
                telephone_auto = request.form.get('telephone_auto')
                consent_auto = get_consent_value('consent_auto')

                if not all([marque, modele, prix_estime, carburant, annee_circulation, ville_auto, email_form, telephone_auto, consent_auto == 'oui']):
                    return jsonify({"success": False, "message": "يرجى ملء جميع الحقول المطلوبة، بما في ذلك الموافقة."}), 400

                try:
                    annee_circulation = int(annee_circulation)
                    if annee_circulation < 1950 or annee_circulation > datetime.now().year + 1:
                        raise ValueError("سنة التداول غير صالحة.")
                except (ValueError, TypeError):
                    return jsonify({"success": False, "message": "سنة التداول غير صالحة."}), 400

                try:
                    prix_estime = float(prix_estime)
                    if prix_estime <= 0:
                        raise ValueError("يجب أن يكون السعر المقدر إيجابيًا.")
                except (ValueError, TypeError):
                    return jsonify({"success": False, "message": "السعر المقدر غير صالح."}), 400

                if puissance_fiscale:
                    try:
                        puissance_fiscale = int(puissance_fiscale)
                        if puissance_fiscale <= 0:
                            raise ValueError("القوة المالية غير صالحة.")
                    except (ValueError, TypeError):
                        return jsonify({"success": False, "message": "القوة المالية غير صالحة."}), 400

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                assureur_actuel = request.form.get('assureur_actuel', '')

                cursor = db.execute(
                    """INSERT INTO assurance_auto
                       (user_id, marque, modele, prix_estime, carburant, annee_circulation, puissance_fiscale, ville, email, telephone, assureur_actuel, consentement, action_type, status, verified)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', FALSE)""",
                    (
                        current_user_id, marque, modele, prix_estime, carburant, annee_circulation,
                        puissance_fiscale, ville_auto, user_email_to_use, telephone_auto,
                        assureur_actuel, consent_auto, action_type
                    )
                )
                db.commit()
                lead_id = cursor.lastrowid

                otp_code = generate_otp_code()
                store_otp_in_session(otp_code, user_email_to_use, lead_id)

                otp_sent = send_otp_email(user_email_to_use, otp_code)

                if not otp_sent:
                    current_app.logger.warning(f"Failed to send OTP email to {user_email_to_use}, but lead was recorded")

                if action_type == 'quote':
                    send_notifications_for_new_lead("Auto", ville_auto)

                send_user_confirmation_email(user_email_to_use, "Auto", ville_auto)

                return jsonify({
                    "success": True,
                    "message": "تم تسجيل طلبك. تم إرسال رمز التحقق إلى بريدك الإلكتروني.",
                    "otp_required": True,
                    "lead_id": lead_id
                }), 200

            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in /ar/assurance-auto POST: {e}")
                if db: db.rollback()
                return jsonify({"success": False, "message": f"حدث خطأ في قاعدة البيانات: {e}"}), 500
            except Exception as e:
                current_app.logger.error(f"General error in /ar/assurance-auto POST: {e}", exc_info=True)
                if db: db.rollback()
                return jsonify({"success": False, "message": f"حدث خطأ أثناء الإرسال: {e}"}), 500

        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('auto-ar.html', user_info=user_info)

    @app.route('/verify-otp-auto', methods=['POST'])
    def verify_otp_auto():
        """Verify OTP code for auto insurance lead"""
        try:
            data = request.get_json()
            otp_code = data.get('otp_code', '').strip()
            email = data.get('email', '').strip()
            lead_id = data.get('lead_id')

            if not otp_code or not email or not lead_id:
                return jsonify({"success": False, "message": "Données manquantes."}), 400

            # Verify OTP code
            if verify_otp_code(otp_code, email):
                # Update lead as verified
                db = database.get_db()
                db.execute(
                    "UPDATE assurance_auto SET verified = TRUE WHERE id = ? AND email = ?",
                    (lead_id, email)
                )
                db.commit()

                # Clear OTP session
                clear_otp_session()

                return jsonify({
                    "success": True,
                    "message": "Code vérifié avec succès ! Votre demande est maintenant confirmée."
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "message": "Code de vérification invalide ou expiré. Veuillez réessayer."
                }), 400

        except Exception as e:
            current_app.logger.error(f"Error verifying OTP: {e}", exc_info=True)
            return jsonify({"success": False, "message": "Une erreur est survenue lors de la vérification."}), 500

    @app.route('/resend-otp-auto', methods=['POST'])
    def resend_otp_auto():
        """Resend OTP code for auto insurance lead"""
        try:
            data = request.get_json()
            email = data.get('email', '').strip()
            lead_id = data.get('lead_id')

            if not email or not lead_id:
                return jsonify({"success": False, "message": "Données manquantes."}), 400

            # Generate new OTP code
            otp_code = generate_otp_code()
            store_otp_in_session(otp_code, email, lead_id)

            # Send new OTP email
            otp_sent = send_otp_email(email, otp_code)

            if otp_sent:
                return jsonify({
                    "success": True,
                    "message": "Un nouveau code de vérification a été envoyé à votre email."
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "message": "Erreur lors de l'envoi du code. Veuillez réessayer."
                }), 500

        except Exception as e:
            current_app.logger.error(f"Error resending OTP: {e}", exc_info=True)
            return jsonify({"success": False, "message": "Une erreur est survenue lors de l'envoi du code."}), 500

    @app.route('/assurance-moto', methods=['GET', 'POST'])
    def moto():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_moto')
                user_email_to_use = email_form
                telephone_moto = request.form.get('telephone_moto')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                type_moto = request.form.get('type_moto')
                cylindree = request.form.get('cylindree')
                usage_moto = request.form.get('usage_moto')
                mode_stationnement_moto = request.form.get('mode_stationnement_moto')
                code_postal_moto = request.form.get('code_postal_moto')
                ville_moto = request.form.get('ville_moto')
                consent_moto = get_consent_value('consent_moto')

                db.execute(
                    """INSERT INTO assurance_moto (user_id, type_moto, cylindree, usage_moto, mode_stationnement, code_postal, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, type_moto, cylindree, usage_moto, mode_stationnement_moto, code_postal_moto, ville_moto, user_email_to_use, telephone_moto, consent_moto, action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Moto", ville_moto)

                # Send confirmation email to user
                send_user_confirmation_email(user_email_to_use, "Moto", ville_moto)

                flash_message = 'Votre demande a été traitée!'
                if action_type == 'estimate':
                    flash_message = 'Votre demande d\'estimation pour une assurance moto a été enregistrée!'
                elif action_type == 'quote':
                    flash_message = 'Votre demande de devis pour une assurance moto a été soumise avec succès!'
                flash(flash_message, 'success')
                return redirect(url_for('moto'))
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in /moto POST: {e}")
                db.rollback()
                flash(f'Une erreur de base de données est survenue: {e}', 'danger')
            except Exception as e:
                current_app.logger.error(f"General error in /moto POST: {e}")
                flash(f'Une erreur est survenue: {e}', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('moto.html', user_info=user_info)

    @app.route('/ar/assurance-moto', methods=['GET', 'POST'])
    def moto_ar():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_moto')
                user_email_to_use = email_form
                telephone_moto = request.form.get('telephone_moto')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                type_moto = request.form.get('type_moto')
                cylindree = request.form.get('cylindree')
                usage_moto = request.form.get('usage_moto')
                mode_stationnement_moto = request.form.get('mode_stationnement_moto')
                code_postal_moto = request.form.get('code_postal_moto')
                ville_moto = request.form.get('ville_moto')
                consent_moto = get_consent_value('consent_moto')

                db.execute(
                    """INSERT INTO assurance_moto (user_id, type_moto, cylindree, usage_moto, mode_stationnement, code_postal, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, type_moto, cylindree, usage_moto, mode_stationnement_moto, code_postal_moto, ville_moto, user_email_to_use, telephone_moto, consent_moto, action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Moto", ville_moto)
                send_user_confirmation_email(user_email_to_use, "Moto", ville_moto)
                flash('تم إرسال طلبك بنجاح!', 'success')
                return redirect(url_for('moto_ar'))
            except Exception as e:
                current_app.logger.error(f"Error in /ar/assurance-moto POST: {e}")
                flash('حدث خطأ أثناء إرسال الطلب', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('moto-ar.html', user_info=user_info)

    @app.route('/assurance-habitation', methods=['GET', 'POST'])
    @rate_limit('form')  # Add rate limiting decorator
    def habitation():
        if request.method == 'POST':
            # SECURE FORM HANDLING
            secure_handler = create_secure_form_handler(FORM_VALIDATION_RULES['assurance_habitation'])
            is_valid, sanitized_data, errors = secure_handler(request.form)

            if not is_valid:
                user_info = {"email": session.get('user_email')} if 'user_id' in session else None
                return render_template('habitation.html', errors=errors, user_info=user_info), 400

            # Use sanitized_data instead of request.form
            db = None
            try:
                db = database.get_db()
                current_user_id = get_current_user_id()
                action_type = sanitized_data.get('action_type', 'devis')

                # Use sanitized email
                email_form = sanitized_data.get('email')
                user_email_to_use = email_form

                # Override with session email if user is logged in and no email provided
                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                cursor = db.execute(
                    """INSERT INTO assurance_habitation
                       (user_id, type_logement, statut_occupation, residence_principale,
                        surface_habitable, nombre_pieces, code_postal, ville, email,
                        telephone, consentement, action_type, status, date_soumission)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        current_user_id,
                        sanitized_data.get('type_logement'),
                        sanitized_data.get('statut_occupation'),
                        sanitized_data.get('residence_principale'),
                        sanitized_data.get('surface_habitable'),
                        sanitized_data.get('nombre_pieces'),
                        sanitized_data.get('code_postal', ''),
                        sanitized_data.get('ville'),
                        user_email_to_use,
                        sanitized_data.get('telephone'),
                        'oui',  # consentement
                        action_type,
                        'active',
                        datetime.now()
                    )
                )

                lead_id = cursor.lastrowid
                db.commit()

                # Send notifications (your existing logic)
                if action_type == 'quote':
                    send_notifications_for_new_lead("Habitation", sanitized_data.get('ville'))

                send_user_confirmation_email(
                    user_email_to_use,
                    "Assurance Habitation",
                    sanitized_data.get('ville')
                )

                # Return JSON response for AJAX or redirect for regular form
                if request.headers.get('Content-Type') == 'application/json':
                    return jsonify({
                        "success": True,
                        "message": "Votre demande a été enregistrée avec succès!"
                    })
                else:
                    flash_message = 'Votre demande a été traitée.'
                    if action_type == 'estimate_habitation':
                        flash_message = 'Votre demande d\'estimation pour une assurance habitation a été enregistrée avec succès!'
                    elif action_type == 'quote':
                        flash_message = 'Votre demande de devis pour une assurance habitation a été soumise avec succès!'
                    else:
                        flash_message = f'Votre demande pour une assurance habitation a été soumise avec succès!'
                    flash(flash_message, 'success')
                    return redirect(url_for('habitation'))

            except Exception as e:
                current_app.logger.error(f"Database error in habitation form: {e}")
                if db:
                    db.rollback()

                if request.headers.get('Content-Type') == 'application/json':
                    return jsonify({
                        "success": False,
                        "message": "Erreur système. Veuillez réessayer."
                    }), 500
                else:
                    flash('Une erreur est survenue. Veuillez réessayer.', 'danger')
            finally:
                if db:
                    db.close()

        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('habitation.html', user_info=user_info)

    @app.route('/ar/assurance-habitation', methods=['GET', 'POST'])
    def habitation_ar():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_habitation')
                user_email_to_use = email_form
                telephone_habitation = request.form.get('telephone_habitation')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                type_logement_habitation = request.form.get('type_logement_habitation')
                statut_occupation_habitation = request.form.get('statut_occupation_habitation')
                residence_principale_habitation = request.form.get('residence_principale_habitation')
                surface_habitable_habitation = request.form.get('surface_habitable_habitation')
                nombre_pieces_habitation = request.form.get('nombre_pieces_habitation')
                code_postal_habitation = request.form.get('code_postal_habitation')
                ville_habitation = request.form.get('ville_habitation')
                consent_habitation = get_consent_value('consent_habitation')

                db.execute(
                    """INSERT INTO assurance_habitation (user_id, type_logement, statut_occupation, residence_principale, surface_habitable, nombre_pieces, code_postal, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id,type_logement_habitation,statut_occupation_habitation,residence_principale_habitation,surface_habitable_habitation,nombre_pieces_habitation,code_postal_habitation,ville_habitation,user_email_to_use,telephone_habitation,consent_habitation,action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Habitation", ville_habitation)
                send_user_confirmation_email(user_email_to_use, "Habitation", ville_habitation)
                flash('تم إرسال طلبك بنجاح!', 'success')
                return redirect(url_for('habitation_ar'))
            except Exception as e:
                current_app.logger.error(f"Error in /ar/assurance-habitation POST: {e}")
                flash('حدث خطأ أثناء إرسال الطلب', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('habitation-ar.html', user_info=user_info)

    @app.route('/assurance-maladie', methods=['GET', 'POST'])
    def sante():
        # REDIRECT: Redirecting to AMC individuelle
        # To disable redirect, comment out the next line and uncomment the code below
        return redirect(url_for('assurance_maladie_complementaire_individuelle'), code=301)

        # ORIGINAL CODE BELOW - Keep for future use
        # if request.method == 'POST':
        #     try:
        #         db = database.get_db()
        #         action_type = request.form.get('action_type')
        #         current_user_id = get_current_user_id()
        #         email_form = request.form.get('email_sante')
        #         user_email_to_use = email_form
        #         telephone_sante = request.form.get('telephone_sante')
        #
        #         if current_user_id and session.get('user_email'):
        #             if not email_form or email_form == session.get('user_email'):
        #                 user_email_to_use = session.get('user_email')
        #
        #         besoin_sante = request.form.get('besoin_sante')
        #         regime_social_sante = request.form.get('regime_social_sante')
        #         code_postal_sante = request.form.get('code_postal_sante')
        #         ville_sante = request.form.get('ville_sante')
        #         consent_sante = get_consent_value('consent_sante')
        #
        #         # Validate required fields (code_postal_sante and regime_social_sante are optional)
        #         if not all([besoin_sante, ville_sante, email_form, telephone_sante, consent_sante == 'oui']):
        #             return jsonify({"success": False, "message": "Veuillez remplir tous les champs requis, y compris le consentement."}), 400
        #
        #         # Insert lead into database (always record the lead)
        #         cursor = db.execute(
        #             """INSERT INTO assurance_sante (user_id, besoins, regime_social, code_postal, ville, email, telephone, consentement, action_type, status, verified)
        #                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', FALSE)""",
        #             (current_user_id, besoin_sante, regime_social_sante, code_postal_sante, ville_sante, user_email_to_use, telephone_sante, consent_sante, action_type)
        #         )
        #         db.commit()
        #         lead_id = cursor.lastrowid
        #
        #         # Generate and send OTP code
        #         otp_code = generate_otp_code()
        #         store_otp_in_session(otp_code, user_email_to_use, lead_id)
        #
        #         # Log email details for debugging
        #         current_app.logger.info(f"Sending OTP to email: {user_email_to_use} for sante lead {lead_id}")
        #
        #         # Send OTP email
        #         otp_sent = send_otp_email(user_email_to_use, otp_code)
        #
        #         if not otp_sent:
        #             current_app.logger.warning(f"Failed to send OTP email to {user_email_to_use}, but lead was recorded")
        #
        #         # Send notifications and confirmation emails as before
        #         if action_type == 'quote':
        #             send_notifications_for_new_lead("Santé", ville_sante)
        #
        #         # Send confirmation email to user
        #         current_app.logger.info(f"Sending confirmation email to: {user_email_to_use} for sante")
        #         send_user_confirmation_email(user_email_to_use, "Santé", ville_sante)
        #
        #         return jsonify({
        #             "success": True,
        #             "message": "Votre demande a été enregistrée. Un code de vérification a été envoyé à votre email.",
        #             "otp_required": True,
        #             "lead_id": lead_id
        #         }), 200
        #
        #     except sqlite3.Error as e:
        #         current_app.logger.error(f"Database error in /assurance-maladie POST: {e}")
        #         if db: db.rollback()
        #         return jsonify({"success": False, "message": f"Une erreur de base de données est survenue: {e}"}), 500
        #     except Exception as e:
        #         current_app.logger.error(f"General error in /assurance-maladie POST: {e}", exc_info=True)
        #         if db: db.rollback()
        #         return jsonify({"success": False, "message": f"Une erreur est survenue lors de la soumission: {e}"}), 500
        #
        # user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        # return render_template('sante.html', user_info=user_info)

    @app.route('/ar/assurance-maladie', methods=['GET', 'POST'])
    def sante_ar():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_sante')
                user_email_to_use = email_form
                telephone_sante = request.form.get('telephone_sante')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                besoin_sante = request.form.get('besoin_sante')
                regime_social_sante = request.form.get('regime_social_sante')
                code_postal_sante = request.form.get('code_postal_sante')
                ville_sante = request.form.get('ville_sante')
                consent_sante = get_consent_value('consent_sante')

                if not all([besoin_sante, ville_sante, email_form, telephone_sante, consent_sante == 'oui']):
                    return jsonify({"success": False, "message": "يرجى ملء جميع الحقول المطلوبة، بما في ذلك الموافقة."}), 400

                cursor = db.execute(
                    """INSERT INTO assurance_sante (user_id, besoins, regime_social, code_postal, ville, email, telephone, consentement, action_type, status, verified)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', FALSE)""",
                    (current_user_id, besoin_sante, regime_social_sante, code_postal_sante, ville_sante, user_email_to_use, telephone_sante, consent_sante, action_type)
                )
                db.commit()
                lead_id = cursor.lastrowid

                otp_code = generate_otp_code()
                store_otp_in_session(otp_code, user_email_to_use, lead_id)

                otp_sent = send_otp_email(user_email_to_use, otp_code)

                if not otp_sent:
                    current_app.logger.warning(f"Failed to send OTP email to {user_email_to_use}, but lead was recorded")

                if action_type == 'quote':
                    send_notifications_for_new_lead("Santé", ville_sante)
                send_user_confirmation_email(user_email_to_use, "Santé", ville_sante)

                return jsonify({
                    "success": True,
                    "message": "تم تسجيل طلبك. تم إرسال رمز التحقق إلى بريدك الإلكتروني.",
                    "otp_required": True,
                    "lead_id": lead_id
                }), 200
            except Exception as e:
                current_app.logger.error(f"Error in /ar/assurance-maladie POST: {e}")
                return jsonify({"success": False, "message": f"حدث خطأ أثناء الإرسال: {e}"}), 500
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('sante-ar.html', user_info=user_info)

    @app.route('/verify-otp-sante', methods=['POST'])
    def verify_otp_sante():
        """Verify OTP code for sante insurance lead"""
        try:
            data = request.get_json()
            otp_code = data.get('otp_code', '').strip()
            email = data.get('email', '').strip()
            lead_id = data.get('lead_id')

            if not otp_code or not email or not lead_id:
                return jsonify({"success": False, "message": "Données manquantes."}), 400

            # Verify OTP code
            if verify_otp_code(otp_code, email):
                # Update lead as verified
                db = database.get_db()
                db.execute(
                    "UPDATE assurance_sante SET verified = TRUE WHERE id = ? AND email = ?",
                    (lead_id, email)
                )
                db.commit()

                # Clear OTP session
                clear_otp_session()

                return jsonify({
                    "success": True,
                    "message": "Code vérifié avec succès ! Votre demande est maintenant confirmée."
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "message": "Code de vérification invalide ou expiré. Veuillez réessayer."
                }), 400

        except Exception as e:
            current_app.logger.error(f"Error verifying OTP: {e}", exc_info=True)
            return jsonify({"success": False, "message": "Une erreur est survenue lors de la vérification."}), 500

    @app.route('/resend-otp-sante', methods=['POST'])
    def resend_otp_sante():
        """Resend OTP code for sante insurance lead"""
        try:
            data = request.get_json()
            email = data.get('email', '').strip()
            lead_id = data.get('lead_id')

            if not email or not lead_id:
                return jsonify({"success": False, "message": "Données manquantes."}), 400

            # Generate new OTP code
            otp_code = generate_otp_code()
            store_otp_in_session(otp_code, email, lead_id)

            # Send OTP email
            otp_sent = send_otp_email(email, otp_code)

            if otp_sent:
                return jsonify({
                    "success": True,
                    "message": "Un nouveau code de vérification a été envoyé à votre email."
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "message": "Impossible d'envoyer le code. Veuillez réessayer plus tard."
                }), 500

        except Exception as e:
            current_app.logger.error(f"Error resending OTP: {e}", exc_info=True)
            return jsonify({"success": False, "message": "Une erreur est survenue lors de l'envoi du code."}), 500

    @app.route('/assurance-emprunteur', methods=['GET', 'POST'])
    def emprunteur():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_emprunteur')
                user_email_to_use = email_form
                telephone_emprunteur = request.form.get('telephone_emprunteur')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                type_pret_emprunteur = request.form.get('type_pret_emprunteur')
                montant_emprunt_emprunteur = request.form.get('montant_emprunt_emprunteur')
                duree_emprunt_emprunteur = request.form.get('duree_emprunt_emprunteur')
                date_naissance_emprunteur = request.form.get('date_naissance_emprunteur')
                situation_professionnelle_emprunteur = request.form.get('situation_professionnelle_emprunteur')
                fumeur_emprunteur = request.form.get('fumeur_emprunteur')
                code_postal_emprunteur = request.form.get('code_postal_emprunteur')
                ville_emprunteur = request.form.get('ville_emprunteur')
                consent_emprunteur = get_consent_value('consent_emprunteur')

                db.execute(
                    """INSERT INTO assurance_emprunteur (user_id, type_pret, montant_emprunt, duree_emprunt, date_naissance, situation_professionnelle, fumeur, code_postal, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, type_pret_emprunteur, montant_emprunt_emprunteur, duree_emprunt_emprunteur, date_naissance_emprunteur, situation_professionnelle_emprunteur, fumeur_emprunteur, code_postal_emprunteur, ville_emprunteur, user_email_to_use, telephone_emprunteur, consent_emprunteur, action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Emprunteur", ville_emprunteur)

                # Send confirmation email to user
                send_user_confirmation_email(user_email_to_use, "Emprunteur", ville_emprunteur)

                flash_message = 'Votre demande a été traitée!'
                if action_type == 'estimate':
                    flash_message = 'Votre demande d\'estimation pour une assurance emprunteur a été enregistrée!'
                elif action_type == 'quote':
                     flash_message = 'Votre demande de devis pour une assurance emprunteur a été soumise avec succès!'
                flash(flash_message, 'success')
                return redirect(url_for('emprunteur'))
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in /emprunteur POST: {e}")
                db.rollback()
                flash(f'Une erreur de base de données est survenue: {e}', 'danger')
            except Exception as e:
                current_app.logger.error(f"General error in /emprunteur POST: {e}")
                flash(f'Une erreur est survenue: {e}', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('emprunteur.html', user_info=user_info)

    @app.route('/ar/assurance-emprunteur', methods=['GET', 'POST'])
    def emprunteur_ar():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_emprunteur')
                user_email_to_use = email_form
                telephone_emprunteur = request.form.get('telephone_emprunteur')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                type_pret_emprunteur = request.form.get('type_pret_emprunteur')
                montant_emprunt_emprunteur = request.form.get('montant_emprunt_emprunteur')
                duree_emprunt_emprunteur = request.form.get('duree_emprunt_emprunteur')
                date_naissance_emprunteur = request.form.get('date_naissance_emprunteur')
                situation_professionnelle_emprunteur = request.form.get('situation_professionnelle_emprunteur')
                fumeur_emprunteur = request.form.get('fumeur_emprunteur')
                code_postal_emprunteur = request.form.get('code_postal_emprunteur')
                ville_emprunteur = request.form.get('ville_emprunteur')
                consent_emprunteur = get_consent_value('consent_emprunteur')

                db.execute(
                    """INSERT INTO assurance_emprunteur (user_id, type_pret, montant_emprunt, duree_emprunt, date_naissance, situation_professionnelle, fumeur, code_postal, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, type_pret_emprunteur, montant_emprunt_emprunteur, duree_emprunt_emprunteur, date_naissance_emprunteur, situation_professionnelle_emprunteur, fumeur_emprunteur, code_postal_emprunteur, ville_emprunteur, user_email_to_use, telephone_emprunteur, consent_emprunteur, action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Emprunteur", ville_emprunteur)
                send_user_confirmation_email(user_email_to_use, "Emprunteur", ville_emprunteur)
                flash('تم إرسال طلبك بنجاح!', 'success')
                return redirect(url_for('emprunteur_ar'))
            except Exception as e:
                current_app.logger.error(f"Error in /ar/assurance-emprunteur POST: {e}")
                flash('حدث خطأ أثناء إرسال الطلب', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('emprunteur-ar.html', user_info=user_info)

    @app.route('/assurance-voyage', methods=['GET', 'POST'])
    def voyage():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_voyage')
                user_email_to_use = email_form
                telephone_voyage = request.form.get('telephone_voyage')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                destination_voyage = request.form.get('destination_voyage')
                ville_voyage = request.form.get('ville_voyage')
                date_depart_voyage = request.form.get('date_depart_voyage')
                date_retour_voyage = request.form.get('date_retour_voyage')
                nombre_personnes_voyage = request.form.get('nombre_personnes_voyage')
                consent_voyage = get_consent_value('consent_voyage')

                db.execute(
                    """INSERT INTO assurance_voyage (user_id, destination, ville, date_depart, date_retour, nombre_personnes, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, destination_voyage, ville_voyage, date_depart_voyage, date_retour_voyage, nombre_personnes_voyage, user_email_to_use, telephone_voyage, consent_voyage, action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Voyage", ville_voyage)
                    send_user_confirmation_email(user_email_to_use, "Voyage", ville_voyage)
                else:
                    send_user_confirmation_email(user_email_to_use, "Voyage", ville_voyage)

                flash_message = 'Votre demande a été traitée!'
                if action_type == 'estimate':
                    flash_message = 'Votre demande d\'estimation pour une assurance voyage a été enregistrée!'
                elif action_type == 'quote':
                    flash_message = 'Votre demande de devis pour une assurance voyage a été soumise avec succès!'
                flash(flash_message, 'success')
                return redirect(url_for('voyage'))
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in /voyage POST: {e}")
                db.rollback()
                flash(f'Une erreur de base de données est survenue: {e}', 'danger')
            except Exception as e:
                current_app.logger.error(f"General error in /voyage POST: {e}")
                flash(f'Une erreur est survenue: {e}', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('voyage.html', user_info=user_info)

    @app.route('/ar/assurance-voyage', methods=['GET', 'POST'])
    def voyage_ar():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_voyage')
                user_email_to_use = email_form
                telephone_voyage = request.form.get('telephone_voyage')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                destination_voyage = request.form.get('destination_voyage')
                ville_voyage = request.form.get('ville_voyage')
                date_depart_voyage = request.form.get('date_depart_voyage')
                date_retour_voyage = request.form.get('date_retour_voyage')
                nombre_personnes_voyage = request.form.get('nombre_personnes_voyage')
                consent_voyage = get_consent_value('consent_voyage')

                db.execute(
                    """INSERT INTO assurance_voyage (user_id, destination, ville, date_depart, date_retour, nombre_personnes, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, destination_voyage, ville_voyage, date_depart_voyage, date_retour_voyage, nombre_personnes_voyage, user_email_to_use, telephone_voyage, consent_voyage, action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Voyage", ville_voyage)
                send_user_confirmation_email(user_email_to_use, "Voyage", ville_voyage)
                flash('تم إرسال طلبك بنجاح!', 'success')
                return redirect(url_for('voyage_ar'))
            except Exception as e:
                current_app.logger.error(f"Error in /ar/assurance-voyage POST: {e}")
                flash('حدث خطأ أثناء إرسال الطلب', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('voyage-ar.html', user_info=user_info)

    @app.route('/assurance-loisirs', methods=['GET', 'POST'])
    def loisirs():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_loisir')
                user_email_to_use = email_form
                telephone_loisir = request.form.get('telephone_loisir')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                type_loisir_loisirs = request.form.get('type_loisir_loisirs')
                description_bien_loisir = request.form.get('description_bien_loisir')
                valeur_bien_loisir = request.form.get('valeur_bien_loisir')
                code_postal_loisir = request.form.get('code_postal_loisir')
                ville_loisir = request.form.get('ville_loisir')
                consent_loisirs = get_consent_value('consent_loisirs')

                db.execute(
                    """INSERT INTO assurance_loisirs (user_id, type_loisir, description_bien, valeur_bien, code_postal, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, type_loisir_loisirs, description_bien_loisir, valeur_bien_loisir, code_postal_loisir, ville_loisir, user_email_to_use, telephone_loisir, consent_loisirs, action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Loisirs", ville_loisir)

                # Send confirmation email to user
                send_user_confirmation_email(user_email_to_use, "Loisirs", ville_loisir)

                flash_message = 'Votre demande a été traitée!'
                if action_type == 'estimate':
                    flash_message = 'Votre demande d\'estimation pour une assurance loisirs a été enregistrée!'
                elif action_type == 'quote':
                    flash_message = 'Votre demande de devis pour une assurance loisirs a été soumise avec succès!'
                flash(flash_message, 'success')
                return redirect(url_for('loisirs'))
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in /loisirs POST: {e}")
                db.rollback()
                flash(f'Une erreur de base de données est survenue: {e}', 'danger')
            except Exception as e:
                current_app.logger.error(f"General error in /loisirs POST: {e}")
                flash(f'Une erreur est survenue: {e}', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('loisirs.html', user_info=user_info)

    @app.route('/ar/assurance-loisirs', methods=['GET', 'POST'])
    def loisirs_ar():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_loisir')
                user_email_to_use = email_form
                telephone_loisir = request.form.get('telephone_loisir')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                type_loisir_loisirs = request.form.get('type_loisir_loisirs')
                description_bien_loisir = request.form.get('description_bien_loisir')
                valeur_bien_loisir = request.form.get('valeur_bien_loisir')
                code_postal_loisir = request.form.get('code_postal_loisir')
                ville_loisir = request.form.get('ville_loisir')
                consent_loisirs = get_consent_value('consent_loisirs')

                db.execute(
                    """INSERT INTO assurance_loisirs (user_id, type_loisir, description_bien, valeur_bien, code_postal, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, type_loisir_loisirs, description_bien_loisir, valeur_bien_loisir, code_postal_loisir, ville_loisir, user_email_to_use, telephone_loisir, consent_loisirs, action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Loisirs", ville_loisir)
                send_user_confirmation_email(user_email_to_use, "Loisirs", ville_loisir)
                flash('تم إرسال طلبك بنجاح!', 'success')
                return redirect(url_for('loisirs_ar'))
            except Exception as e:
                current_app.logger.error(f"Error in /ar/assurance-loisirs POST: {e}")
                flash('حدث خطأ أثناء إرسال الطلب', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('loisirs-ar.html', user_info=user_info)

    @app.route('/assurance-animaux', methods=['GET', 'POST'])
    def animaux():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_animaux')
                user_email_to_use = email_form
                telephone_animaux = request.form.get('telephone_animaux')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                type_animal_animaux = request.form.get('type_animal_animaux')
                race_animal_animaux = request.form.get('race_animal_animaux')
                age_animal_animaux = request.form.get('age_animal_animaux')
                identification_animal_animaux = request.form.get('identification_animal_animaux')
                code_postal_animaux = request.form.get('code_postal_animaux')
                ville_animaux = request.form.get('ville_animaux')
                consent_animaux = get_consent_value('consent_animaux')

                db.execute(
                    """INSERT INTO assurance_animaux (user_id, type_animal, race_animal, age_animal, identification_animal, code_postal, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, type_animal_animaux, race_animal_animaux, age_animal_animaux, identification_animal_animaux, code_postal_animaux, ville_animaux, user_email_to_use, telephone_animaux, consent_animaux, action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Animaux", ville_animaux)

                # Send confirmation email to user
                send_user_confirmation_email(user_email_to_use, "Animaux", ville_animaux)

                flash_message = 'Votre demande a été traitée!'
                if action_type == 'estimate':
                    flash_message = 'Votre demande d\'estimation pour une assurance animaux a été enregistrée!'
                elif action_type == 'quote':
                    flash_message = 'Votre demande de devis pour une une assurance animaux a été soumise avec succès!'
                flash(flash_message, 'success')
                return redirect(url_for('animaux'))
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in /animaux POST: {e}")
                db.rollback()
                flash(f'Une erreur de base de données est survenue: {e}', 'danger')
            except Exception as e:
                current_app.logger.error(f"General error in /animaux POST: {e}")
                flash(f'Une erreur est survenue: {e}', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('animaux.html', user_info=user_info)

    @app.route('/ar/assurance-animaux', methods=['GET', 'POST'])
    def animaux_ar():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_animaux')
                user_email_to_use = email_form
                telephone_animaux = request.form.get('telephone_animaux')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                type_animal_animaux = request.form.get('type_animal_animaux')
                race_animal_animaux = request.form.get('race_animal_animaux')
                age_animal_animaux = request.form.get('age_animal_animaux')
                identification_animal_animaux = request.form.get('identification_animal_animaux')
                code_postal_animaux = request.form.get('code_postal_animaux')
                ville_animaux = request.form.get('ville_animaux')
                consent_animaux = get_consent_value('consent_animaux')

                db.execute(
                    """INSERT INTO assurance_animaux (user_id, type_animal, race_animal, age_animal, identification_animal, code_postal, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, type_animal_animaux, race_animal_animaux, age_animal_animaux, identification_animal_animaux, code_postal_animaux, ville_animaux, user_email_to_use, telephone_animaux, consent_animaux, action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Animaux", ville_animaux)
                send_user_confirmation_email(user_email_to_use, "Animaux", ville_animaux)
                flash('تم إرسال طلبك بنجاح!', 'success')
                return redirect(url_for('animaux_ar'))
            except Exception as e:
                current_app.logger.error(f"Error in /ar/assurance-animaux POST: {e}")
                flash('حدث خطأ أثناء إرسال الطلب', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('animaux-ar.html', user_info=user_info)

    @app.route('/assurance-flotte-auto', methods=['GET', 'POST'])
    def flotte():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_flotte')
                user_email_to_use = email_form
                telephone_flotte = request.form.get('telephone_flotte')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                type_vehicules_flotte = request.form.get('type_vehicules_flotte')
                nombre_vehicules_flotte = request.form.get('nombre_vehicules_flotte')
                secteur_activite_flotte = request.form.get('secteur_activite_flotte')
                code_postal_flotte = request.form.get('code_postal_flotte')
                ville_flotte = request.form.get('ville_flotte')
                consent_flotte = get_consent_value('consent_flotte')

                db.execute(
                    """INSERT INTO assurance_flotte (user_id, type_vehicules, nombre_vehicules, secteur_activite, code_postal, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, type_vehicules_flotte,nombre_vehicules_flotte,secteur_activite_flotte,code_postal_flotte, ville_flotte, user_email_to_use,telephone_flotte,consent_flotte,action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Flotte Auto", ville_flotte)

                # Send confirmation email to user
                send_user_confirmation_email(user_email_to_use, "Flotte Auto", ville_flotte)

                flash_message = 'Votre demande a été traitée!'
                if action_type == 'estimate':
                    flash_message = 'Votre demande d\'estimation pour une assurance flotte a été enregistrée!'
                elif action_type == 'quote':
                    flash_message = 'Votre demande de devis pour une assurance flotte a été soumise avec succès!'
                flash(flash_message, 'success')
                return redirect(url_for('flotte'))
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in /flotte POST: {e}")
                db.rollback()
                flash(f'Une erreur de base de données est survenue: {e}', 'danger')
            except Exception as e:
                current_app.logger.error(f"General error in /flotte POST: {e}")
                flash(f'Une erreur est survenue: {e}', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('flotte.html', user_info=user_info)

    @app.route('/ar/assurance-flotte-auto', methods=['GET', 'POST'])
    def flotte_ar():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_flotte')
                user_email_to_use = email_form
                telephone_flotte = request.form.get('telephone_flotte')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                type_vehicules_flotte = request.form.get('type_vehicules_flotte')
                nombre_vehicules_flotte = request.form.get('nombre_vehicules_flotte')
                secteur_activite_flotte = request.form.get('secteur_activite_flotte')
                code_postal_flotte = request.form.get('code_postal_flotte')
                ville_flotte = request.form.get('ville_flotte')
                consent_flotte = get_consent_value('consent_flotte')

                db.execute(
                    """INSERT INTO assurance_flotte (user_id, type_vehicules, nombre_vehicules, secteur_activite, code_postal, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, type_vehicules_flotte,nombre_vehicules_flotte,secteur_activite_flotte,code_postal_flotte, ville_flotte, user_email_to_use,telephone_flotte,consent_flotte,action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Flotte Auto", ville_flotte)
                send_user_confirmation_email(user_email_to_use, "Flotte Auto", ville_flotte)
                flash('تم إرسال طلبك بنجاح!', 'success')
                return redirect(url_for('flotte_ar'))
            except Exception as e:
                current_app.logger.error(f"Error in /ar/assurance-flotte-auto POST: {e}")
                flash('حدث خطأ أثناء إرسال الطلب', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('flotte-ar.html', user_info=user_info)

    @app.route('/assurance-maritime', methods=['GET', 'POST'])
    def maritime():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_maritime')
                user_email_to_use = email_form
                telephone_maritime = request.form.get('telephone_maritime')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                type_bateau_maritime = request.form.get('type_bateau_maritime')
                usage_bateau_maritime = request.form.get('usage_bateau_maritime')
                zone_navigation_maritime = request.form.get('zone_navigation_maritime')
                valeur_bateau_maritime = request.form.get('valeur_bateau_maritime')
                code_postal_maritime = request.form.get('code_postal_maritime')
                consent_maritime = get_consent_value('consent_maritime')

                db.execute(
                    """INSERT INTO assurance_maritime (user_id, type_bateau, usage_bateau, zone_navigation, valeur_bateau, code_postal, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, type_bateau_maritime,usage_bateau_maritime,zone_navigation_maritime,valeur_bateau_maritime,code_postal_maritime,user_email_to_use,telephone_maritime,consent_maritime,action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Maritime", zone_navigation_maritime)

                # Send confirmation email to user
                send_user_confirmation_email(user_email_to_use, "Maritime", zone_navigation_maritime)

                flash_message = 'Votre demande a été traitée!'
                if action_type == 'estimate':
                    flash_message = 'Votre demande d\'estimation pour une assurance maritime a été enregistrée!'
                elif action_type == 'quote':
                    flash_message = 'Votre demande de devis pour une assurance maritime a été soumise avec succès!'
                flash(flash_message, 'success')
                return redirect(url_for('maritime'))
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in /maritime POST: {e}")
                db.rollback()
                flash(f'Une erreur de base de données est survenue: {e}', 'danger')
            except Exception as e:
                current_app.logger.error(f"General error in /maritime POST: {e}")
                flash(f'Une erreur est survenue: {e}', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('maritime.html', user_info=user_info)

    @app.route('/ar/assurance-maritime', methods=['GET', 'POST'])
    def maritime_ar():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_maritime')
                user_email_to_use = email_form
                telephone_maritime = request.form.get('telephone_maritime')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                type_bateau_maritime = request.form.get('type_bateau_maritime')
                usage_bateau_maritime = request.form.get('usage_bateau_maritime')
                zone_navigation_maritime = request.form.get('zone_navigation_maritime')
                valeur_bateau_maritime = request.form.get('valeur_bateau_maritime')
                code_postal_maritime = request.form.get('code_postal_maritime')
                consent_maritime = get_consent_value('consent_maritime')

                db.execute(
                    """INSERT INTO assurance_maritime (user_id, type_bateau, usage_bateau, zone_navigation, valeur_bateau, code_postal, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, type_bateau_maritime,usage_bateau_maritime,zone_navigation_maritime,valeur_bateau_maritime,code_postal_maritime,user_email_to_use,telephone_maritime,consent_maritime,action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Maritime", zone_navigation_maritime)
                send_user_confirmation_email(user_email_to_use, "Maritime", zone_navigation_maritime)
                flash('تم إرسال طلبك بنجاح!', 'success')
                return redirect(url_for('maritime_ar'))
            except Exception as e:
                current_app.logger.error(f"Error in /ar/assurance-maritime POST: {e}")
                flash('حدث خطأ أثناء إرسال الطلب', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('maritime-ar.html', user_info=user_info)

    @app.route('/assurance-marchandise', methods=['GET', 'POST'])
    def marchandise():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_marchandise')
                user_email_to_use = email_form
                telephone_marchandise = request.form.get('telephone_marchandise')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                type_marchandise = request.form.get('type_marchandise')
                valeur_marchandise = request.form.get('valeur_marchandise')
                mode_transport_marchandise = request.form.get('mode_transport_marchandise')
                destination_marchandise = request.form.get('destination_marchandise')
                code_postal_marchandise = request.form.get('code_postal_marchandise')
                consent_marchandise = get_consent_value('consent_marchandise')

                db.execute(
                    """INSERT INTO assurance_marchandise (user_id, type_marchandise, valeur_marchandise, mode_transport, destination, code_postal, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, type_marchandise,valeur_marchandise,mode_transport_marchandise,destination_marchandise,code_postal_marchandise,user_email_to_use,telephone_marchandise,consent_marchandise,action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Marchandise", destination_marchandise)

                # Send confirmation email to user
                send_user_confirmation_email(user_email_to_use, "Marchandise", destination_marchandise)

                flash_message = 'Votre demande a été traitée!'
                if action_type == 'estimate':
                    flash_message = 'Votre demande d\'estimation pour une assurance marchandise a été enregistrée!'
                elif action_type == 'quote':
                    flash_message = 'Votre demande de devis pour une assurance marchandise a été soumise avec succès!'
                flash(flash_message, 'success')
                return redirect(url_for('marchandise'))
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in /marchandise POST: {e}")
                db.rollback()
                flash(f'Une erreur de base de données est survenue: {e}', 'danger')
            except Exception as e:
                current_app.logger.error(f"General error in /marchandise POST: {e}")
                flash(f'Une erreur est survenue: {e}', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('marchandise.html', user_info=user_info)

    @app.route('/ar/assurance-marchandise', methods=['GET', 'POST'])
    def marchandise_ar():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_marchandise')
                user_email_to_use = email_form
                telephone_marchandise = request.form.get('telephone_marchandise')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                type_marchandise = request.form.get('type_marchandise')
                valeur_marchandise = request.form.get('valeur_marchandise')
                mode_transport_marchandise = request.form.get('mode_transport_marchandise')
                destination_marchandise = request.form.get('destination_marchandise')
                code_postal_marchandise = request.form.get('code_postal_marchandise')
                consent_marchandise = get_consent_value('consent_marchandise')

                db.execute(
                    """INSERT INTO assurance_marchandise (user_id, type_marchandise, valeur_marchandise, mode_transport, destination, code_postal, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, type_marchandise,valeur_marchandise,mode_transport_marchandise,destination_marchandise,code_postal_marchandise,user_email_to_use,telephone_marchandise,consent_marchandise,action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Marchandise", destination_marchandise)
                send_user_confirmation_email(user_email_to_use, "Marchandise", destination_marchandise)
                flash('تم إرسال طلبك بنجاح!', 'success')
                return redirect(url_for('marchandise_ar'))
            except Exception as e:
                current_app.logger.error(f"Error in /ar/assurance-marchandise POST: {e}")
                flash('حدث خطأ أثناء إرسال الطلب', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('marchandise-ar.html', user_info=user_info)

    @app.route('/assurance-credit', methods=['GET', 'POST'])
    def assurancecredit():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_credit')
                user_email_to_use = email_form
                telephone_credit = request.form.get('telephone_credit')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                type_credit_credit = request.form.get('type_credit_credit')
                montant_credit_credit = request.form.get('montant_credit_credit')
                duree_remboursement_credit = request.form.get('duree_remboursement_credit')
                organisme_preteur_credit = request.form.get('organisme_preteur_credit')
                code_postal_credit = request.form.get('code_postal_credit')
                ville_credit = request.form.get('ville_credit')
                consent_credit = get_consent_value('consent_credit')

                db.execute(
                    """INSERT INTO assurance_credit (user_id, type_credit, montant_credit, duree_remboursement, organisme_preteur, code_postal, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, type_credit_credit,montant_credit_credit,duree_remboursement_credit,organisme_preteur_credit,code_postal_credit, ville_credit, user_email_to_use,telephone_credit,consent_credit,action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Crédit", ville_credit)

                # Send confirmation email to user
                send_user_confirmation_email(user_email_to_use, "Crédit", ville_credit)

                flash_message = 'Votre demande a été traitée!'
                if action_type == 'estimate':
                    flash_message = 'Votre demande d\'estimation pour une assurance crédit a été enregistrée!'
                elif action_type == 'quote':
                    flash_message = 'Votre demande de devis pour une assurance crédit a été soumise avec succès!'
                flash(flash_message, 'success')
                return redirect(url_for('assurancecredit'))
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in /assurancecredit POST: {e}")
                db.rollback()
                flash(f'Une erreur de base de données est survenue: {e}', 'danger')
            except Exception as e:
                current_app.logger.error(f"General error in /assurancecredit POST: {e}")
                flash(f'Une erreur est survenue: {e}', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('assurancecredit.html', user_info=user_info)

    @app.route('/ar/assurance-credit', methods=['GET', 'POST'])
    def assurancecredit_ar():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_credit')
                user_email_to_use = email_form
                telephone_credit = request.form.get('telephone_credit')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                type_credit_credit = request.form.get('type_credit_credit')
                montant_credit_credit = request.form.get('montant_credit_credit')
                duree_remboursement_credit = request.form.get('duree_remboursement_credit')
                organisme_preteur_credit = request.form.get('organisme_preteur_credit')
                code_postal_credit = request.form.get('code_postal_credit')
                ville_credit = request.form.get('ville_credit')
                consent_credit = get_consent_value('consent_credit')

                db.execute(
                    """INSERT INTO assurance_credit (user_id, type_credit, montant_credit, duree_remboursement, organisme_preteur, code_postal, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, type_credit_credit,montant_credit_credit,duree_remboursement_credit,organisme_preteur_credit,code_postal_credit, ville_credit, user_email_to_use,telephone_credit,consent_credit,action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Crédit", ville_credit)
                send_user_confirmation_email(user_email_to_use, "Crédit", ville_credit)
                flash('تم إرسال طلبك بنجاح!', 'success')
                return redirect(url_for('assurancecredit_ar'))
            except Exception as e:
                current_app.logger.error(f"Error in /ar/assurance-credit POST: {e}")
                flash('حدث خطأ أثناء إرسال الطلب', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('assurancecredit-ar.html', user_info=user_info)

    @app.route('/assurance-accident-travail', methods=['GET', 'POST'])
    def accidenttravail():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_accident')
                user_email_to_use = email_form
                telephone_accident = request.form.get('telephone_accident')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                secteur_activite_accident = request.form.get('secteur_activite_accident')
                nombre_salaries_accident = request.form.get('nombre_salaries_accident')
                code_postal_accident = request.form.get('code_postal_accident')
                ville_accident = request.form.get('ville_accident')
                consent_accident = get_consent_value('consent_accident')

                db.execute(
                    """INSERT INTO assurance_accident_travail (user_id, secteur_activite, nombre_salaries, code_postal, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, secteur_activite_accident,nombre_salaries_accident,code_postal_accident, ville_accident, user_email_to_use,telephone_accident,consent_accident,action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Accident du Travail", ville_accident)

                # Send confirmation email to user
                send_user_confirmation_email(user_email_to_use, "Accident du Travail", ville_accident)

                flash_message = 'Votre demande a été traitée!'
                if action_type == 'estimate':
                    flash_message = 'Votre demande d\'estimation pour une assurance accident du travail a été enregistrée!'
                elif action_type == 'quote':
                    flash_message = 'Votre demande de devis pour une assurance accident du travail a été soumise avec succès!'
                flash(flash_message, 'success')
                return redirect(url_for('accidenttravail'))
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in /accidenttravail POST: {e}")
                db.rollback()
                flash(f'Une erreur de base de données est survenue: {e}', 'danger')
            except Exception as e:
                current_app.logger.error(f"General error in /accidenttravail POST: {e}")
                flash(f'Une erreur est survenue: {e}', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('accidenttravail.html', user_info=user_info)

    @app.route('/ar/assurance-accident-travail', methods=['GET', 'POST'])
    def accidenttravail_ar():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_accident')
                user_email_to_use = email_form
                telephone_accident = request.form.get('telephone_accident')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                secteur_activite_accident = request.form.get('secteur_activite_accident')
                nombre_salaries_accident = request.form.get('nombre_salaries_accident')
                code_postal_accident = request.form.get('code_postal_accident')
                ville_accident = request.form.get('ville_accident')
                consent_accident = get_consent_value('consent_accident')

                db.execute(
                    """INSERT INTO assurance_accident_travail (user_id, secteur_activite, nombre_salaries, code_postal, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, secteur_activite_accident,nombre_salaries_accident,code_postal_accident, ville_accident, user_email_to_use,telephone_accident,consent_accident,action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Accident du Travail", ville_accident)
                send_user_confirmation_email(user_email_to_use, "Accident du Travail", ville_accident)
                flash('تم إرسال طلبك بنجاح!', 'success')
                return redirect(url_for('accidenttravail_ar'))
            except Exception as e:
                current_app.logger.error(f"Error in /ar/assurance-accident-travail POST: {e}")
                flash('حدث خطأ أثناء إرسال الطلب', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('accidenttravail-ar.html', user_info=user_info)

    @app.route('/assurances-entreprise', methods=['GET', 'POST'])
    def assurances_entreprise():
        if request.method == 'POST':
            # TODO: Add backend logic for B2B contact form later
            pass

        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('assurances-entreprise.html', user_info=user_info)

    @app.route('/assurance-particulier')
    def assurance_particulier():
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('assurance-particulier.html', user_info=user_info)

    @app.route('/submit-entreprise-contact', methods=['POST'])
    def submit_entreprise_contact():
        """Handle the enterprise contact form submission and send email to info@mesassurances.ma"""
        try:
            # Get form data
            company_name = request.form.get('company_name', '').strip()
            sector = request.form.get('sector', '').strip()
            contact_name = request.form.get('contact_name', '').strip()
            phone = request.form.get('phone', '').strip()
            email = request.form.get('email', '').strip()
            employees = request.form.get('employees', '').strip()
            needs = request.form.get('needs', '').strip()

            # Validate required fields
            if not all([company_name, sector, contact_name, phone, email, needs]):
                flash('Veuillez remplir tous les champs obligatoires.', 'error')
                return redirect(url_for('assurances_entreprise'))

            # Validate email format
            if '@' not in email or '.' not in email.split('@')[1]:
                flash('Veuillez entrer une adresse email valide.', 'error')
                return redirect(url_for('assurances_entreprise'))

            # Create email content
            subject = f"Nouvelle demande d'assurance entreprise - {company_name}"

            # Format sector display name
            sector_names = {
                'industrie': 'Industrie & Manufacture',
                'commerce': 'Commerce & Distribution',
                'hotellerie': 'Hôtellerie & Restauration',
                'transport': 'Transport & Logistique',
                'construction': 'Construction & BTP',
                'services': 'Services & Conseil',
                'autre': 'Autre'
            }
            sector_display = sector_names.get(sector, sector)

            # Create HTML email body
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2563eb; border-bottom: 2px solid #2563eb; padding-bottom: 10px;">
                        Nouvelle demande d'assurance entreprise
                    </h2>

                    <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="color: #1e3a8a; margin-top: 0;">Informations de l'entreprise</h3>
                        <p><strong>Nom de l'entreprise:</strong> {company_name}</p>
                        <p><strong>Secteur d'activité:</strong> {sector_display}</p>
                        <p><strong>Nombre d'employés:</strong> {employees if employees else 'Non spécifié'}</p>
                    </div>

                    <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="color: #1e3a8a; margin-top: 0;">Contact</h3>
                        <p><strong>Nom du responsable:</strong> {contact_name}</p>
                        <p><strong>Téléphone:</strong> {phone}</p>
                        <p><strong>Email:</strong> {email}</p>
                    </div>

                    <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="color: #1e3a8a; margin-top: 0;">Besoins d'assurance</h3>
                        <p style="white-space: pre-wrap;">{needs}</p>
                    </div>

                    <div style="background-color: #e0f2fe; padding: 15px; border-radius: 8px; margin: 20px 0;">
                        <p style="margin: 0; color: #0277bd;">
                            <strong>Action requise:</strong> Contacter le client dans les plus brefs délais pour proposer des devis personnalisés.
                        </p>
                    </div>

                    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
                    <p style="font-size: 12px; color: #64748b; text-align: center;">
                        Cette demande a été envoyée via le formulaire de contact de MesAssurances.ma
                    </p>
                </div>
            </body>
            </html>
            """

            # Create plain text version
            text_body = f"""
            Nouvelle demande d'assurance entreprise

            Informations de l'entreprise:
            - Nom de l'entreprise: {company_name}
            - Secteur d'activité: {sector_display}
            - Nombre d'employés: {employees if employees else 'Non spécifié'}

            Contact:
            - Nom du responsable: {contact_name}
            - Téléphone: {phone}
            - Email: {email}

            Besoins d'assurance:
            {needs}

            Action requise: Contacter le client dans les plus brefs délais pour proposer des devis personnalisés.

            Cette demande a été envoyée via le formulaire de contact de MesAssurances.ma
            """

            # Send email
            msg = Message(
                subject=subject,
                sender=current_app.config['MAIL_DEFAULT_SENDER'],
                recipients=['info@mesassurances.ma']
            )
            msg.body = text_body
            msg.html = html_body

            mail.send(msg)

            current_app.logger.info(f"Enterprise contact form submitted successfully for {company_name} by {contact_name} ({email})")
            flash('Votre demande a été envoyée avec succès ! Un courtier agréé vous contactera sous 24h.', 'success')

        except Exception as e:
            current_app.logger.error(f"Error processing enterprise contact form: {e}", exc_info=True)
            flash('Une erreur est survenue lors de l\'envoi de votre demande. Veuillez réessayer ou nous contacter directement.', 'error')

        return redirect(url_for('assurances_entreprise'))

    @app.route('/submit-particulier-contact', methods=['POST'])
    def submit_particulier_contact():
        """Handle the particulier contact form submission and send email to info@mesassurances.ma"""
        try:
            # Get form data
            firstname = request.form.get('firstname', '').strip()
            lastname = request.form.get('lastname', '').strip()
            phone = request.form.get('phone', '').strip()
            email = request.form.get('email', '').strip()
            city = request.form.get('city', '').strip()
            needs = request.form.get('needs', '').strip()

            # Validate required fields
            if not all([firstname, lastname, phone, email, city, needs]):
                flash('Veuillez remplir tous les champs obligatoires.', 'error')
                return redirect(url_for('assurance_particulier'))

            # Validate email format
            if '@' not in email or '.' not in email.split('@')[1]:
                flash('Veuillez entrer une adresse email valide.', 'error')
                return redirect(url_for('assurance_particulier'))

            # Create email content
            subject = f"Nouvelle demande d'assurance particulier - {firstname} {lastname}"

            # Create HTML email body
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2563eb; border-bottom: 2px solid #2563eb; padding-bottom: 10px;">
                        Nouvelle demande d'assurance particulier
                    </h2>

                    <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="color: #1e3a8a; margin-top: 0;">Informations Client</h3>
                        <p><strong>Nom complet:</strong> {firstname} {lastname}</p>
                        <p><strong>Ville:</strong> {city}</p>
                    </div>

                    <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="color: #1e3a8a; margin-top: 0;">Contact</h3>
                        <p><strong>Téléphone:</strong> {phone}</p>
                        <p><strong>Email:</strong> {email}</p>
                    </div>

                    <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="color: #1e3a8a; margin-top: 0;">Besoins d'assurance</h3>
                        <p style="white-space: pre-wrap;">{needs}</p>
                    </div>

                    <div style="background-color: #e0f2fe; padding: 15px; border-radius: 8px; margin: 20px 0;">
                        <p style="margin: 0; color: #0277bd;">
                            <strong>Action requise:</strong> Contacter le client dans les plus brefs délais pour proposer des devis personnalisés.
                        </p>
                    </div>

                    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
                    <p style="font-size: 12px; color: #64748b; text-align: center;">
                        Cette demande a été envoyée via le formulaire de contact de MesAssurances.ma
                    </p>
                </div>
            </body>
            </html>
            """

            # Create plain text version
            text_body = f"""
            Nouvelle demande d'assurance particulier

            Informations Client:
            - Nom complet: {firstname} {lastname}
            - Ville: {city}

            Contact:
            - Téléphone: {phone}
            - Email: {email}

            Besoins d'assurance:
            {needs}

            Action requise: Contacter le client dans les plus brefs délais pour proposer des devis personnalisés.

            Cette demande a été envoyée via le formulaire de contact de MesAssurances.ma
            """

            # Send email
            msg = Message(
                subject=subject,
                sender=current_app.config['MAIL_DEFAULT_SENDER'],
                recipients=['info@mesassurances.ma']
            )
            msg.body = text_body
            msg.html = html_body
            msg.reply_to = email

            mail.send(msg)

            current_app.logger.info(f"Particulier contact form submitted successfully for {firstname} {lastname} ({email})")
            flash('Votre demande a été envoyée avec succès ! Un conseiller vous contactera prochainement.', 'success')
            return redirect(url_for('assurance_particulier'))

        except Exception as e:
            current_app.logger.error(f"Error submitting particulier contact form: {str(e)}", exc_info=True)
            flash("Une erreur s'est produite lors de l'envoi de votre demande. Veuillez réessayer.", "error")
            return redirect(url_for('assurance_particulier'))


    @app.route('/assurance-retraite', methods=['GET', 'POST'])
    def retraite():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_retraite')
                user_email_to_use = email_form
                telephone_retraite = request.form.get('telephone_retraite')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                situation_actuelle_retraite = request.form.get('situation_actuelle_retraite')
                revenu_mensuel_retraite = request.form.get('revenu_mensuel_retraite')
                capacite_epargne_retraite = request.form.get('capacite_epargne_retraite')
                age_depart_retraite = request.form.get('age_depart_retraite')
                code_postal_retraite = request.form.get('code_postal_retraite')
                ville_retraite = request.form.get('ville_retraite')
                consent_retraite = get_consent_value('consent_retraite')


                db.execute(
                    """INSERT INTO assurance_retraite (user_id, situation_actuelle, revenu_mensuel, capacite_epargne, age_depart_souhaite, code_postal, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, situation_actuelle_retraite,revenu_mensuel_retraite,capacite_epargne_retraite,age_depart_retraite,code_postal_retraite, ville_retraite, user_email_to_use,telephone_retraite,consent_retraite,action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Retraite", ville_retraite)

                # Send confirmation email to user
                send_user_confirmation_email(user_email_to_use, "Retraite", ville_retraite)

                flash_message = 'Votre demande a été traitée!'
                if action_type == 'estimate':
                    flash_message = 'Votre demande d\'estimation pour une assurance retraite a été enregistrée!'
                elif action_type == 'quote':
                    flash_message = 'Votre demande de devis pour une assurance retraite a été soumise avec succès!'
                flash(flash_message, 'success')
                return redirect(url_for('retraite'))
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in /retraite POST: {e}")
                db.rollback()
                flash(f'Une erreur de base de données est survenue: {e}', 'danger')
            except Exception as e:
                current_app.logger.error(f"General error in /retraite POST: {e}")
                flash(f'Une erreur est survenue: {e}', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('retraite.html', user_info=user_info)

    @app.route('/ar/assurance-retraite', methods=['GET', 'POST'])
    def retraite_ar():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_retraite')
                user_email_to_use = email_form
                telephone_retraite = request.form.get('telephone_retraite')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                situation_actuelle_retraite = request.form.get('situation_actuelle_retraite')
                revenu_mensuel_retraite = request.form.get('revenu_mensuel_retraite')
                capacite_epargne_retraite = request.form.get('capacite_epargne_retraite')
                age_depart_retraite = request.form.get('age_depart_retraite')
                code_postal_retraite = request.form.get('code_postal_retraite')
                ville_retraite = request.form.get('ville_retraite')
                consent_retraite = get_consent_value('consent_retraite')

                db.execute(
                    """INSERT INTO assurance_retraite (user_id, situation_actuelle, revenu_mensuel, capacite_epargne, age_depart_souhaite, code_postal, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, situation_actuelle_retraite,revenu_mensuel_retraite,capacite_epargne_retraite,age_depart_retraite,code_postal_retraite, ville_retraite, user_email_to_use,telephone_retraite,consent_retraite,action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Retraite", ville_retraite)
                send_user_confirmation_email(user_email_to_use, "Retraite", ville_retraite)
                flash('تم إرسال طلبك بنجاح!', 'success')
                return redirect(url_for('retraite_ar'))
            except Exception as e:
                current_app.logger.error(f"Error in /ar/assurance-retraite POST: {e}")
                flash('حدث خطأ أثناء إرسال الطلب', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('retraite-ar.html', user_info=user_info)

    @app.route('/assurance-patrimoine', methods=['GET', 'POST'])
    def patrimoine():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_patrimoine')
                user_email_to_use = email_form
                telephone_patrimoine = request.form.get('telephone_patrimoine')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                type_patrimoine_patrimoine = request.form.get('type_patrimoine_patrimoine')
                valeur_estimee_patrimoine = request.form.get('valeur_estimee_patrimoine')
                objectif_principal_patrimoine = request.form.get('objectif_principal_patrimoine')
                code_postal_patrimoine = request.form.get('code_postal_patrimoine')
                ville_patrimoine = request.form.get('ville_patrimoine')
                consent_patrimoine = get_consent_value('consent_patrimoine')

                db.execute(
                    """INSERT INTO assurance_patrimoine (user_id, type_patrimoine, valeur_estimee, objectif_principal, code_postal, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, type_patrimoine_patrimoine,valeur_estimee_patrimoine,objectif_principal_patrimoine,code_postal_patrimoine, ville_patrimoine, user_email_to_use,telephone_patrimoine,consent_patrimoine,action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Patrimoine", ville_patrimoine)

                # Send confirmation email to user
                send_user_confirmation_email(user_email_to_use, "Patrimoine", ville_patrimoine)

                flash_message = 'Votre demande a été traitée!'
                if action_type == 'estimate':
                    flash_message = 'Votre demande d\'estimation pour une assurance patrimoine a été enregistrée!'
                elif action_type == 'quote':
                    flash_message = 'Votre demande de devis pour une assurance patrimoine a été soumise avec succès!'
                flash(flash_message, 'success')
                return redirect(url_for('patrimoine'))
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in /patrimoine POST: {e}")
                db.rollback()
                flash(f'Une erreur de base de données est survenue: {e}', 'danger')
            except Exception as e:
                current_app.logger.error(f"General error in /patrimoine POST: {e}")
                flash(f'Une erreur est survenue: {e}', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('patrimoine.html', user_info=user_info)

    @app.route('/ar/assurance-patrimoine', methods=['GET', 'POST'])
    def patrimoine_ar():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_patrimoine')
                user_email_to_use = email_form
                telephone_patrimoine = request.form.get('telephone_patrimoine')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                type_patrimoine_patrimoine = request.form.get('type_patrimoine_patrimoine')
                valeur_estimee_patrimoine = request.form.get('valeur_estimee_patrimoine')
                objectif_principal_patrimoine = request.form.get('objectif_principal_patrimoine')
                code_postal_patrimoine = request.form.get('code_postal_patrimoine')
                ville_patrimoine = request.form.get('ville_patrimoine')
                consent_patrimoine = get_consent_value('consent_patrimoine')

                db.execute(
                    """INSERT INTO assurance_patrimoine (user_id, type_patrimoine, valeur_estimee, objectif_principal, code_postal, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, type_patrimoine_patrimoine,valeur_estimee_patrimoine,objectif_principal_patrimoine,code_postal_patrimoine, ville_patrimoine, user_email_to_use,telephone_patrimoine,consent_patrimoine,action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Patrimoine", ville_patrimoine)
                send_user_confirmation_email(user_email_to_use, "Patrimoine", ville_patrimoine)
                flash('تم إرسال طلبك بنجاح!', 'success')
                return redirect(url_for('patrimoine_ar'))
            except Exception as e:
                current_app.logger.error(f"Error in /ar/assurance-patrimoine POST: {e}")
                flash('حدث خطأ أثناء إرسال الطلب', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('patrimoine-ar.html', user_info=user_info)

    @app.route('/assurance-complement-cnops', methods=['GET', 'POST'])
    def cnops():
        # REDIRECT: Redirecting to AMC individuelle
        # To disable redirect, comment out the next line and uncomment the code below
        return redirect(url_for('assurance_maladie_complementaire_individuelle'), code=301)

        # ORIGINAL CODE BELOW - Keep for future use
        # if request.method == 'POST':
        #     try:
        #         db = database.get_db()
        #         action_type = request.form.get('action_type')
        #         current_user_id = get_current_user_id()
        #         email_form = request.form.get('email_cnops')
        #         user_email_to_use = email_form
        #         telephone_cnops = request.form.get('telephone_cnops')
        #
        #         if current_user_id and session.get('user_email'):
        #             if not email_form or email_form == session.get('user_email'):
        #                 user_email_to_use = session.get('user_email')
        #
        #         matricule_cnops = request.form.get('matricule_cnops')
        #         type_couverture_cnops = request.form.get('type_couverture_cnops')
        #         nom_complet_cnops = request.form.get('nom_complet_cnops')
        #         date_naissance_cnops = request.form.get('date_naissance_cnops')
        #         code_postal_cnops = request.form.get('code_postal_cnops')
        #         ville_cnops = request.form.get('ville_cnops')
        #         consent_cnops = get_consent_value('consent_cnops')
        #
        #         db.execute(
        #             """INSERT INTO assurance_cnops (user_id, matricule_cnops, type_couverture_cnops, nom_complet, date_naissance_cnops, code_postal, ville, email, telephone, consentement, action_type, status)
        #                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
        #             (current_user_id, matricule_cnops,type_couverture_cnops,nom_complet_cnops, date_naissance_cnops,code_postal_cnops,ville_cnops,user_email_to_use,telephone_cnops,consent_cnops,action_type)
        #         )
        #         db.commit()
        #
        #         if action_type == 'quote':
        #             send_notifications_for_new_lead("Santé Complémentaire", ville_cnops)
        #
        #         # Send confirmation email to user
        #         send_user_confirmation_email(user_email_to_use, "Santé Complémentaire", ville_cnops)
        #
        #         flash_message = 'Votre demande a été traitée!'
        #         if action_type == 'estimate':
        #             flash_message = 'Votre demande d\'estimation CNOPS a été enregistrée!'
        #         elif action_type == 'quote':
        #              flash_message = 'Votre demande de devis CNOPS a été soumise avec succès!'
        #         flash(flash_message, 'success')
        #         return redirect(url_for('cnops'))
        #     except sqlite3.Error as e:
        #         current_app.logger.error(f"Database error in /cnops POST: {e}")
        #         db.rollback()
        #         flash(f'Une erreur de base de données est survenue: {e}', 'danger')
        #     except Exception as e:
        #         current_app.logger.error(f"General error in /cnops POST: {e}")
        #         flash(f'Une erreur est survenue lors de la soumission: {e}', 'danger')
        # user_info = None
        # if 'user_id' in session:
        #     user_info = { "email": session.get('user_email'), "name": session.get('user_name') }
        # return render_template('cnops.html', user_info=user_info)

    @app.route('/ar/assurance-complement-cnops', methods=['GET', 'POST'])
    def cnops_ar():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_cnops')
                user_email_to_use = email_form
                telephone_cnops = request.form.get('telephone_cnops')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                matricule_cnops = request.form.get('matricule_cnops')
                type_couverture_cnops = request.form.get('type_couverture_cnops')
                nom_complet_cnops = request.form.get('nom_complet_cnops')
                date_naissance_cnops = request.form.get('date_naissance_cnops')
                code_postal_cnops = request.form.get('code_postal_cnops')
                ville_cnops = request.form.get('ville_cnops')
                consent_cnops = get_consent_value('consent_cnops')

                db.execute(
                    """INSERT INTO assurance_cnops (user_id, matricule_cnops, type_couverture_cnops, nom_complet, date_naissance_cnops, code_postal, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, matricule_cnops,type_couverture_cnops,nom_complet_cnops, date_naissance_cnops,code_postal_cnops,ville_cnops,user_email_to_use,telephone_cnops,consent_cnops,action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Santé Complémentaire", ville_cnops)
                send_user_confirmation_email(user_email_to_use, "Santé Complémentaire", ville_cnops)
                flash('تم إرسال طلبك بنجاح!', 'success')
                return redirect(url_for('cnops_ar'))
            except Exception as e:
                current_app.logger.error(f"Error in /ar/assurance-complement-cnops POST: {e}")
                flash('حدث خطأ أثناء إرسال الطلب', 'danger')
        user_info = None
        if 'user_id' in session:
            user_info = { "email": session.get('user_email'), "name": session.get('user_name') }
        return render_template('cnops-ar.html', user_info=user_info)

    # --- NEW: Assurance Stage Route ---
    @app.route('/assurance-stage', methods=['GET', 'POST'])
    def assurance_stage():
        if request.method == 'POST':
            db = None
            try:
                db = database.get_db()
                action_type = request.form.get('action_type', 'quote') # Default action type to quote
                current_user_id = get_current_user_id()
                email_form = request.form.get('email')
                user_email_to_use = email_form

                # Get data from the form
                ecole_university_name = request.form.get('ecole_name')
                organisme_de_stage = request.form.get('organisme')
                industry = request.form.get('industry')
                periode_de_stage = request.form.get('periode')
                telephone = request.form.get('tel')
                ville = request.form.get('ville')
                consent = get_consent_value('consent_stage') # Assuming a consent checkbox with name 'consent_stage'

                # Basic validation
                if not all([ecole_university_name, organisme_de_stage, industry, periode_de_stage, telephone, email_form, ville, consent == 'oui']):
                    return jsonify({"success": False, "message": "Veuillez remplir tous les champs obligatoires et accepter les conditions."}), 400

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                db.execute(
                    """INSERT INTO assurance_stage
                       (user_id, ecole_university_name, organisme_de_stage, industry, periode_de_stage, telephone, email, ville, consentement, created_at, date_soumission, action_type, status, admin_notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, 'active', ?)""",
                    (current_user_id, ecole_university_name, organisme_de_stage, industry, periode_de_stage, telephone, user_email_to_use, ville, consent, action_type, None) # Passed None for admin_notes as it's new lead
                )
                db.commit()

                send_notifications_for_new_lead("Stage", ville)

                # Send confirmation email to user
                send_user_confirmation_email(user_email_to_use, "Stage", ville)

                return jsonify({"success": True, "message": "Votre demande d'assurance stage a été soumise avec succès."}), 200

            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in /assurance-stage POST: {e}", exc_info=True)
                if db: db.rollback()
                return jsonify({"success": False, "message": f"Une erreur de base de données est survenue: {e}"}), 500
            except Exception as e:
                current_app.logger.error(f"General error in /assurance-stage POST: {e}", exc_info=True)
                if db: db.rollback()
                return jsonify({"success": False, "message": f"Une erreur est survenue lors de la soumission: {e}"}), 500

        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('assurance-stage.html', user_info=user_info)

    @app.route('/ar/assurance-stage', methods=['GET', 'POST'])
    def assurance_stage_ar():
        if request.method == 'POST':
            db = None
            try:
                db = database.get_db()
                action_type = request.form.get('action_type', 'quote')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email')
                user_email_to_use = email_form

                ecole_university_name = request.form.get('ecole_name')
                organisme_de_stage = request.form.get('organisme')
                industry = request.form.get('industry')
                periode_de_stage = request.form.get('periode')
                telephone = request.form.get('tel')
                ville = request.form.get('ville')
                consent = get_consent_value('consent_stage')

                if not all([ecole_university_name, organisme_de_stage, industry, periode_de_stage, telephone, email_form, ville, consent == 'oui']):
                    return jsonify({"success": False, "message": "يرجى ملء جميع الحقول الإلزامية وقبول الشروط."}), 400

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                db.execute(
                    """INSERT INTO assurance_stage
                       (user_id, ecole_university_name, organisme_de_stage, industry, periode_de_stage, telephone, email, ville, consentement, created_at, date_soumission, action_type, status, admin_notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, 'active', ?)""",
                    (current_user_id, ecole_university_name, organisme_de_stage, industry, periode_de_stage, telephone, user_email_to_use, ville, consent, action_type, None)
                )
                db.commit()

                send_notifications_for_new_lead("Stage", ville)
                send_user_confirmation_email(user_email_to_use, "Stage", ville)

                return jsonify({"success": True, "message": "تم إرسال طلب تأمين التدريب بنجاح."}), 200

            except Exception as e:
                current_app.logger.error(f"Error in /ar/assurance-stage POST: {e}")
                if db: db.rollback()
                return jsonify({"success": False, "message": f"حدث خطأ أثناء الإرسال: {e}"}), 500

        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('assurance-stage-ar.html', user_info=user_info)

    @app.route('/generate-agecap-devis', methods=['GET'])
    def generate_agecap_devis():
        """Generate AGECAP devis PDF based on coverage and period"""
        try:
            coverage = request.args.get('coverage', '')
            period = request.args.get('period', '')
            email = request.args.get('email', '')
            ville = request.args.get('ville', '')
            prenom = request.args.get('prenom', '')
            nom = request.args.get('nom', '')

            if not all([coverage, period, email, ville]):
                return jsonify({"success": False, "message": "Paramètres manquants"}), 400

            # Use Prénom + Nom if provided, otherwise fallback to email
            souscripteur_name = f"{prenom} {nom}".strip() if prenom and nom else email
            assure_name = souscripteur_name

            # Extract period months
            period_match = period.replace(' ', '').lower()
            period_months = 0
            if '12' in period_match or 'annuel' in period_match:
                period_months = 12
            elif '6' in period_match:
                period_months = 6
            elif '3' in period_match:
                period_months = 3
            elif '1' in period_match:
                period_months = 1

            is_annual = period_months == 12
            is_high_coverage = 'IPP : 20 000' in coverage or '20 000' in coverage

            # Determine pricing scenario
            if is_high_coverage and is_annual:
                # Scenario 1: High coverage, Annual
                prime_nette = 200.00
                accessoires = 25.00
                deces = 20000.00
                ipp = 20000.00
                frais_medicaux = 1500.00
                taxe = 28.00
                taxe_parafiscale = 3.00
                prime_ttc = 256.00
                periode_previsionnelle = "12 mois"
            elif is_high_coverage and not is_annual:
                # Scenario 2: High coverage, 6 months and below
                prime_nette = 150.00
                accessoires = 25.00
                deces = 20000.00
                ipp = 20000.00
                frais_medicaux = 1500.00
                taxe = 21.00
                taxe_parafiscale = 2.25
                prime_ttc = 198.25
                periode_previsionnelle = "6 mois" if period_months >= 6 else f"{period_months} mois"
            elif not is_high_coverage and is_annual:
                # Scenario 3: Low coverage, Annual
                prime_nette = 150.00
                accessoires = 25.00
                deces = 10000.00
                ipp = 10000.00
                frais_medicaux = 1500.00
                taxe = 21.00
                taxe_parafiscale = 2.25
                prime_ttc = 198.25
                periode_previsionnelle = "12 mois"
            else:
                # Scenario 4: Low coverage, 6 months and below
                prime_nette = 112.50
                accessoires = 25.00
                deces = 10000.00
                ipp = 10000.00
                frais_medicaux = 1500.00
                taxe = 15.75
                taxe_parafiscale = 1.69
                prime_ttc = 154.94
                periode_previsionnelle = "6 mois" if period_months >= 6 else f"{period_months} mois"

            # Generate random devis number
            devis_number = f"DEV-{datetime.now().strftime('%Y')}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"
            current_date = datetime.now().strftime('%d/%m/%Y')

            # Calculate expiration date based on period duration
            # period_months is already calculated above
            # Calculate expiration:
            # - 12 months = 360 days
            # - 6 months = 180 days
            # - Shorter periods (1, 3 months) = actual duration
            if period_months == 12:
                expiration_days = 360  # 1 year = 360 days from contract activation
            elif period_months == 6:
                expiration_days = 180  # 6 months = 180 days from contract activation
            else:
                # For periods shorter than 6 months, use actual duration
                # 1 month = 30 days, 3 months = 90 days
                expiration_days = period_months * 30

            expiration_date = (datetime.now() + timedelta(days=expiration_days)).strftime('%d/%m/%Y')

            # Create PDF in memory
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=10*mm, bottomMargin=20*mm)
            story = []

            # Styles - Reduced sizes to fit on one page
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=14,
                textColor=colors.HexColor('#000000'),
                spaceAfter=6,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
            normal_style = ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontSize=7,
                textColor=colors.HexColor('#000000'),
                alignment=TA_LEFT,
                fontName='Helvetica'
            )
            underlined_style = ParagraphStyle(
                'CustomUnderlined',
                parent=styles['Normal'],
                fontSize=8,
                textColor=colors.HexColor('#000000'),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                textDecoration='underline'
            )
            footer_style = ParagraphStyle(
                'CustomFooter',
                parent=styles['Normal'],
                fontSize=6,
                textColor=colors.HexColor('#666666'),
                alignment=TA_CENTER,
                fontName='Helvetica'
            )

            # Logo at top right - fixed size 120x120 pixels
            logo_path = os.path.join(current_app.static_folder, 'logo', 'agecap.png')
            logo_img = None
            if os.path.exists(logo_path):
                try:
                    # Convert 120x120 pixels to mm (assuming 72 DPI)
                    # 120 pixels at 72 DPI = 120/72 inches = 1.67 inches = ~42.3 mm
                    logo_size_mm = (120 / 72) * 25.4
                    logo_img = Image(logo_path, width=logo_size_mm*mm, height=logo_size_mm*mm)
                except Exception as e:
                    current_app.logger.warning(f"Could not load logo: {e}")
                    # Fallback to default size
                    try:
                        logo_size_mm = (120 / 72) * 25.4
                        logo_img = Image(logo_path, width=logo_size_mm*mm, height=logo_size_mm*mm)
                    except:
                        pass

            # Header with logo on extreme top right
            if logo_img:
                # Use a table with minimal left column to push logo to extreme right
                header_data = [['', logo_img]]
                header_table = Table(header_data, colWidths=[160*mm, 30*mm])
                header_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                    ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('TOPPADDING', (1, 0), (1, 0), 0),
                    ('BOTTOMPADDING', (1, 0), (1, 0), 0),
                ]))
                story.append(header_table)
                story.append(Spacer(1, 2*mm))

            # Title
            story.append(Paragraph("DEVIS ASSURANCE STAGE ACCIDENTS", title_style))
            story.append(Spacer(1, 3*mm))

            # Devis number and date (centered)
            devis_info_data = [
                [Paragraph(f"<b>Devis n° :</b> {devis_number}", normal_style),
                 Paragraph(f"<b>Du :</b> {current_date}", normal_style)]
            ]
            devis_info_table = Table(devis_info_data, colWidths=[95*mm, 95*mm])
            devis_info_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(devis_info_table)
            story.append(Spacer(1, 4*mm))

            # First table - Subscriber info
            subscriber_data = [
                [Paragraph("<b>Souscripteur :</b>", normal_style), Paragraph(souscripteur_name, normal_style)],
                [Paragraph("<b>Adresse de quérrabilité :</b>", normal_style), Paragraph(ville, normal_style)],
                [Paragraph("<b>Assuré :</b>", normal_style), Paragraph(assure_name, normal_style)],
                [Paragraph("<b>Intermédiaire :</b>", normal_style), Paragraph("AGECAP Code 01715", normal_style)]
            ]
            subscriber_table = Table(subscriber_data, colWidths=[70*mm, 120*mm])
            subscriber_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))
            story.append(subscriber_table)
            story.append(Spacer(1, 4*mm))

            # Second table - Period info
            period_data = [
                [Paragraph("<b>Période prévisionnelle :</b>", normal_style), Paragraph(periode_previsionnelle, normal_style)],
                [Paragraph("<b>Durée du contrat :</b>", normal_style), Paragraph("Ferme", normal_style)],
                [Paragraph("<b>Date de naissance de l'assuré :</b>", normal_style), Paragraph("", normal_style)],
                [Paragraph("<b>Date d'expiration :</b>", normal_style), Paragraph(expiration_date, normal_style)]
            ]
            period_table = Table(period_data, colWidths=[70*mm, 120*mm])
            period_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))
            story.append(period_table)
            story.append(Spacer(1, 4*mm))

            # Coverage section title - left aligned with underline
            story.append(Paragraph("<u>SOMMES ASSUREES ET GARANTIES EN DH :</u>", underlined_style))
            story.append(Spacer(1, 3*mm))

            # Format numbers with spaces as thousand separators and comma as decimal separator
            def format_number(num):
                # Format with 2 decimals
                formatted = f"{num:,.2f}"
                # Replace comma (thousands) with space, period (decimal) with comma
                parts = formatted.split('.')
                integer_part = parts[0].replace(',', ' ')
                decimal_part = parts[1] if len(parts) > 1 else '00'
                return f"{integer_part},{decimal_part}"

            # Third table - Coverage items only
            coverage_items_data = [
                [Paragraph("<b>Décès Accidentel</b>", normal_style), Paragraph(format_number(deces), normal_style)],
                [Paragraph("<b>Infirmité Permanente</b>", normal_style), Paragraph(format_number(ipp) + "<br/>avec une franchise de 5% sur le taux IPP", normal_style)],
                [Paragraph("<b>Frais Médicaux</b>", normal_style), Paragraph(format_number(frais_medicaux), normal_style)],
                [Paragraph("<b>Incapacité Temporaire</b>", normal_style), Paragraph("EXCLUE", normal_style)]
            ]
            coverage_items_table = Table(coverage_items_data, colWidths=[120*mm, 70*mm])
            coverage_items_table.setStyle(TableStyle([
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))
            story.append(coverage_items_table)
            story.append(Spacer(1, 4*mm))

            # Pricing table - Columns with figures
            pricing_data = [
                [Paragraph("<b>PRIME NETTE<br/>(DH)</b>", normal_style),
                 Paragraph("<b>ACCESSOIRES<br/>(DH)</b>", normal_style),
                 Paragraph("<b>TAXE (14%)<br/>(DH)</b>", normal_style),
                 Paragraph("<b>TAXE PARAFISCALE<br/>AU PROFIT DU FSEC (DH)</b>", normal_style),
                 Paragraph("<b>PRIME TTC<br/>(DH)</b>", normal_style)],
                [Paragraph(format_number(prime_nette), normal_style),
                 Paragraph(format_number(accessoires), normal_style),
                 Paragraph(format_number(taxe), normal_style),
                 Paragraph(format_number(taxe_parafiscale), normal_style),
                 Paragraph(f"<b>{format_number(prime_ttc)}</b>", normal_style)]
            ]
            pricing_table = Table(pricing_data, colWidths=[38*mm, 38*mm, 38*mm, 38*mm, 38*mm])
            pricing_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0e0e0')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, 1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))
            story.append(pricing_table)
            story.append(Spacer(1, 4*mm))

            # Conditions table
            conditions_data = [
                [Paragraph("<b>CONDITIONS DE COUVERTURE</b>", normal_style), '', ''],
                [Paragraph("<b>Validité du devis</b>", normal_style),
                 Paragraph("Ce devis est valable pendant une durée de 30 jours à partir de la date du devis.", normal_style), '']
            ]
            conditions_table = Table(conditions_data, colWidths=[60*mm, 130*mm, 0*mm])
            conditions_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0e0e0')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('ALIGN', (0, 1), (0, 1), 'LEFT'),
                ('ALIGN', (1, 1), (1, 1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (0, 1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 1), (1, 1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (1, -1), 0.5, colors.black),
                ('SPAN', (0, 0), (1, 0)),
            ]))
            story.append(conditions_table)
            story.append(Spacer(1, 5*mm))

            # Footer
            footer_text = "88, Avenue Mers Sultan – CASABLANCA Sarl au capital 200.000 DH Tel: 0522.224.180 lg - Fax: 0522.264.522 e-mail: agecap@agecap.ma CNSS 6379087 - TP 34106020 - IF 1051078- RC 103475 - ICE 000027366000064 Intermédiaire d'assurances régi par la loi 17-99 portant Code des Assurances – Autorisation du MF n° C170635652005780 du 01 Août 2005"
            story.append(Paragraph(footer_text, footer_style))

            # Build PDF
            doc.build(story)
            buffer.seek(0)

            # Generate filename
            filename = f"devis_agecap_{devis_number}_{datetime.now().strftime('%Y%m%d')}.pdf"

            # Send email with PDF attachment
            try:
                # Get PDF data from buffer
                pdf_data = buffer.getvalue()

                # Create HTML email body
                whatsapp_number = "212666590994"  # WhatsApp number for AGECAP
                whatsapp_url = f"https://wa.me/{whatsapp_number}"

                html_body = f"""
                <!DOCTYPE html>
                <html lang="fr">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Votre devis Assurance Stage</title>
                </head>
                <body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f5f5f5;">
                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f5f5f5;">
                        <tr>
                            <td align="center" style="padding: 40px 20px;">
                                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                    <!-- Header -->
                                    <tr>
                                        <td style="background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); padding: 30px; text-align: center; border-radius: 8px 8px 0 0;">
                                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700;">Merci d'avoir utilisé MesAssurances.ma</h1>
                                        </td>
                                    </tr>

                                    <!-- Content -->
                                    <tr>
                                        <td style="padding: 40px 30px;">
                                            <p style="margin: 0 0 20px 0; color: #1e293b; font-size: 16px; line-height: 1.6;">
                                                Bonjour {souscripteur_name},
                                            </p>

                                            <p style="margin: 0 0 20px 0; color: #1e293b; font-size: 16px; line-height: 1.6;">
                                                Nous vous remercions d'avoir utilisé <strong>MesAssurances.ma</strong> pour votre demande d'assurance stage.
                                            </p>

                                            <p style="margin: 0 0 20px 0; color: #1e293b; font-size: 16px; line-height: 1.6;">
                                                Votre devis, de notre partenaire AGECAP, est disponible en pièce jointe de cet email. Vous pouvez le télécharger et le consulter à tout moment.
                                            </p>

                                            <!-- Info Box -->
                                            <div style="background-color: #eff6ff; border-left: 4px solid #2563eb; padding: 20px; margin: 30px 0; border-radius: 4px;">
                                                <p style="margin: 0 0 10px 0; color: #1e40af; font-size: 16px; font-weight: 600;">
                                                    📋 Prochaines étapes
                                                </p>
                                                <p style="margin: 0; color: #1e293b; font-size: 15px; line-height: 1.6;">
                                                    Pour finaliser votre offre, contactez <strong>AGECAP Assurances</strong>, préparez votre carte d'identité (CIN) et le paiement par virement bancaire.
                                                </p>
                                            </div>

                                            <!-- WhatsApp Button -->
                                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin: 30px 0;">
                                                <tr>
                                                    <td align="center">
                                                        <a href="{whatsapp_url}" style="display: inline-block; background-color: #25D366; color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 6px; font-weight: 600; font-size: 16px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                                            <span style="display: inline-block; margin-right: 8px;">💬</span>
                                                            Contacter AGECAP sur WhatsApp
                                                        </a>
                                                    </td>
                                                </tr>
                                            </table>

                                            <p style="margin: 20px 0 0 0; color: #64748b; font-size: 14px; line-height: 1.6; text-align: center;">
                                                Ou contactez-les directement au <strong>{whatsapp_number}</strong>
                                            </p>

                                            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">

                                            <p style="margin: 0 0 10px 0; color: #64748b; font-size: 14px; line-height: 1.6;">
                                                <strong>Rappel :</strong> MesAssurances.ma agit uniquement en tant que plateforme de mise en relation technique.
                                                AGECAP Assurances est responsable de la finalisation de votre contrat d'assurance.
                                            </p>
                                        </td>
                                    </tr>

                                    <!-- Footer -->
                                    <tr>
                                        <td style="background-color: #f8fafc; padding: 20px 30px; text-align: center; border-radius: 0 0 8px 8px; border-top: 1px solid #e5e7eb;">
                                            <p style="margin: 0 0 10px 0; color: #64748b; font-size: 12px;">
                                                <strong>MesAssurances.ma</strong><br>
                                                Plateforme d'éducation et mise en relation technique
                                            </p>
                                            <p style="margin: 0; color: #94a3b8; font-size: 11px;">
                                                Cet email a été envoyé à {email}
                                            </p>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                    </table>
                </body>
                </html>
                """

                # Plain text version
                text_body = f"""
                Merci d'avoir utilisé MesAssurances.ma

                Bonjour {souscripteur_name},

                Nous vous remercions d'avoir utilisé MesAssurances.ma pour votre demande d'assurance stage.

                Votre devis, de notre partenaire AGECAP, est disponible en pièce jointe de cet email.

                Pour finaliser votre offre, contactez AGECAP Assurances, préparez votre carte d'identité (CIN) et effectuez le paiement par virement bancaire.

                Contactez-les sur WhatsApp : {whatsapp_number}
                Ou via ce lien : {whatsapp_url}

                Rappel : MesAssurances.ma agit uniquement en tant que plateforme de mise en relation technique.
                AGECAP Assurances est responsable de la finalisation de votre contrat d'assurance.

                MesAssurances.ma
                Plateforme d'éducation et mise en relation technique
                """

                # Create email message
                msg = Message(
                    subject=f"Votre devis Assurance Stage - {devis_number}",
                    sender=("MesAssurances.ma", "notification@mesassurances.ma"),
                    recipients=[email],
                    cc=["elmahdi.boutiyeb@agecap.ma"]
                )
                msg.html = html_body
                msg.body = text_body

                # Attach PDF
                msg.attach(
                    filename=filename,
                    content_type='application/pdf',
                    data=pdf_data
                )

                # Send email
                mail.send(msg)
                current_app.logger.info(f"Sent devis PDF email to {email} for devis {devis_number}")

            except Exception as email_error:
                # Log error but don't fail the request - PDF download should still work
                current_app.logger.error(f"Failed to send email with PDF to {email}: {email_error}", exc_info=True)

            # Reset buffer position for file download
            buffer.seek(0)

            return send_file(
                buffer,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=filename
            )

        except Exception as e:
            current_app.logger.error(f"Error generating AGECAP devis PDF: {e}", exc_info=True)
            return jsonify({"success": False, "message": f"Erreur lors de la génération du PDF: {str(e)}"}), 500

    @app.route('/api/send-fca-voyage-devis', methods=['POST'])
    def api_send_fca_voyage_devis():
        """Receive FCA voyage PDF blob from frontend and email it to the user."""
        try:
            pdf_file = request.files.get('pdf_file')
            email = request.form.get('email', '').strip()
            prenom = request.form.get('prenom', '').strip()
            nom = request.form.get('nom', '').strip()

            if not pdf_file or not email:
                return jsonify({"success": False, "message": "Paramètres manquants."}), 400

            pdf_data = pdf_file.read()
            if not pdf_data:
                return jsonify({"success": False, "message": "PDF invalide."}), 400

            filename = pdf_file.filename or 'Devis_FCA_Assurance_Voyage.pdf'
            user_name = f"{prenom} {nom}".strip()

            if send_fca_voyage_email(email, user_name, pdf_data, filename):
                return jsonify({"success": True}), 200

            return jsonify({"success": False, "message": "Impossible d'envoyer l'email."}), 500
        except Exception as e:
            current_app.logger.error(f"Error sending FCA voyage devis email: {e}", exc_info=True)
            return jsonify({"success": False, "message": "Erreur lors de l'envoi de l'email."}), 500

    # --- NEW: Assurance Ecole Route ---
    @app.route('/assurance-ecole', methods=['GET', 'POST'])
    def assurance_ecole():
        if request.method == 'POST':
            db = None
            try:
                db = database.get_db()
                action_type = request.form.get('action_type', 'quote') # Default action type to quote
                current_user_id = get_current_user_id()
                email_form = request.form.get('email')
                user_email_to_use = email_form

                # Get data from the form
                ecole_university_name = request.form.get('ecole_name')
                number_of_students = request.form.get('students_number')
                telephone = request.form.get('tel')
                ville = request.form.get('ville')
                consent = get_consent_value('consent_ecole') # Assuming a consent checkbox with name 'consent_ecole'

                # Basic validation
                if not all([ecole_university_name, number_of_students, telephone, email_form, ville, consent == 'oui']):
                    return jsonify({"success": False, "message": "Veuillez remplir tous les champs obligatoires et accepter les conditions."}), 400

                try:
                    number_of_students = int(number_of_students)
                    if number_of_students <= 0:
                        return jsonify({"success": False, "message": "Le nombre d'élèves/étudiants doit être un nombre positif."}), 400
                except (ValueError, TypeError):
                    return jsonify({"success": False, "message": "Nombre d'élèves/étudiants invalide."}), 400


                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                db.execute(
                    """INSERT INTO assurance_ecole
                       (user_id, ecole_university_name, number_of_students, telephone, email, ville, consentement, created_at, date_soumission, action_type, status, admin_notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, 'active', ?)""",
                    (current_user_id, ecole_university_name, number_of_students, telephone, user_email_to_use, ville, consent, action_type, None) # Passed None for admin_notes as it's new lead
                )
                db.commit()

                send_notifications_for_new_lead("Ecole", ville)

                # Send confirmation email to user
                send_user_confirmation_email(user_email_to_use, "Ecole", ville)

                return jsonify({"success": True, "message": "Votre demande d'assurance école a été soumise avec succès."}), 200

            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in /assurance-ecole POST: {e}", exc_info=True)
                if db: db.rollback()
                return jsonify({"success": False, "message": f"Une erreur de base de données est survenue: {e}"}), 500
            except Exception as e:
                current_app.logger.error(f"General error in /assurance-ecole POST: {e}", exc_info=True)
                if db: db.rollback()
                return jsonify({"success": False, "message": f"Une erreur est survenue lors de la soumission: {e}"}), 500

        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('assurance-ecole.html', user_info=user_info)

    @app.route('/ar/assurance-ecole', methods=['GET', 'POST'])
    def assurance_ecole_ar():
        if request.method == 'POST':
            db = None
            try:
                db = database.get_db()
                action_type = request.form.get('action_type', 'quote')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email')
                user_email_to_use = email_form

                ecole_university_name = request.form.get('ecole_name')
                number_of_students = request.form.get('students_number')
                telephone = request.form.get('tel')
                ville = request.form.get('ville')
                consent = get_consent_value('consent_ecole')

                if not all([ecole_university_name, number_of_students, telephone, email_form, ville, consent == 'oui']):
                    return jsonify({"success": False, "message": "يرجى ملء جميع الحقول الإلزامية وقبول الشروط."}), 400

                try:
                    number_of_students = int(number_of_students)
                    if number_of_students <= 0:
                        return jsonify({"success": False, "message": "يجب أن يكون عدد الطلاب/التلاميذ رقماً موجباً."}), 400
                except (ValueError, TypeError):
                    return jsonify({"success": False, "message": "عدد الطلاب/التلاميذ غير صالح."}), 400

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                db.execute(
                    """INSERT INTO assurance_ecole
                       (user_id, ecole_university_name, number_of_students, telephone, email, ville, consentement, created_at, date_soumission, action_type, status, admin_notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, 'active', ?)""",
                    (current_user_id, ecole_university_name, number_of_students, telephone, user_email_to_use, ville, consent, action_type, None)
                )
                db.commit()

                send_notifications_for_new_lead("Ecole", ville)
                send_user_confirmation_email(user_email_to_use, "Ecole", ville)

                return jsonify({"success": True, "message": "تم إرسال طلب تأمين المدرسة بنجاح."}), 200

            except Exception as e:
                current_app.logger.error(f"Error in /ar/assurance-ecole POST: {e}")
                if db: db.rollback()
                return jsonify({"success": False, "message": f"حدث خطأ أثناء الإرسال: {e}"}), 500

        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('assurance-ecole-ar.html', user_info=user_info)


    # --- Review Submission Routes ---
    @app.route('/avis-assureurs', methods=['GET', 'POST'])
    def avis_assureurs():
        db = database.get_db()
        if request.method == 'POST':
            try:
                current_user_id = get_current_user_id()

                nom_assureur = request.form.get('reviewed-company')
                titre_avis = request.form.get('review-title')
                commentaire = request.form.get('review-text')
                nom_utilisateur = request.form.get('reviewer-name')
                email_utilisateur = session.get('user_email') if current_user_id else None
                ville_utilisateur = request.form.get('reviewer-location')
                consentement = get_consent_value('review-consent')

                note_prix = request.form.get('rating-prix', type=int)
                note_couverture = request.form.get('rating-couverture', type=int)
                note_service_client = request.form.get('rating-service-client', type=int)
                note_gestion_sinistres = request.form.get('rating-gestion-sinistres', type=int)
                note_transparence = request.form.get('rating-transparence', type=int)
                note_experience_digitale = request.form.get('rating-experience-digitale', type=int)

                scores = [note_prix, note_couverture, note_service_client, note_gestion_sinistres, note_transparence, note_experience_digitale]
                if not all(s is not None and 0 < s <= 5 for s in scores):
                    flash('Veuillez noter tous les critères de 1 à 5 étoiles.', 'danger')
                    approved_reviews = db.execute("SELECT * FROM avis_assureurs WHERE status = 'approved' ORDER BY date_avis DESC").fetchall()
                    user_info = { "email": session.get('user_email'), "name": session.get('user_name') } if 'user_id' in session else None
                    return render_template('avisassureurs.html', user_info=user_info, approved_reviews=approved_reviews)

                note_globale_calculee = round(statistics.mean(scores), 2) if scores else 0.0

                db.execute(
                    """INSERT INTO avis_assureurs
                       (user_id, nom_assureur, titre_avis, commentaire, nom_utilisateur, email_utilisateur, ville_utilisateur, consentement,
                        note_prix, note_couverture, note_service_client, note_gestion_sinistres, note_transparence, note_experience_digitale,
                        note_globale_calculee, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
                    (current_user_id, nom_assureur, titre_avis, commentaire, nom_utilisateur, email_utilisateur, ville_utilisateur, consentement,
                     note_prix, note_couverture, note_service_client, note_gestion_sinistres, note_transparence, note_experience_digitale,
                     note_globale_calculee)
                )
                db.commit()
                flash('Votre avis sur l\'assureur a été soumis et est en attente de modération. Merci!', 'success')
                return redirect(url_for('avis_assureurs'))
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in /avis-assureurs POST: {e}")
                db.rollback()
                flash(f'Une erreur de base de données est survenue: {e}', 'danger')
            except Exception as e:
                current_app.logger.error(f"General error in /avis-assureurs POST: {e}")
                flash(f'Une erreur est survenue: {e}', 'danger')

        user_info = None
        if 'user_id' in session:
            user_info = { "email": session.get('user_email'), "name": session.get('user_name') }

        approved_reviews = db.execute("SELECT * FROM avis_assureurs WHERE status = 'approved' ORDER BY date_avis DESC").fetchall()
        return render_template('avisassureurs.html', user_info=user_info, approved_reviews=approved_reviews)


    @app.route('/avis-plateforme', methods=['GET', 'POST'])
    def avis_plateforme():
        db = database.get_db()
        if request.method == 'POST':
            try:
                current_user_id = get_current_user_id()

                note = request.form.get('overall-rating', type=int)
                titre_avis = request.form.get('review-title')
                commentaire = request.form.get('review-text')
                nom_utilisateur = request.form.get('reviewer-name')
                email_utilisateur = session.get('user_email') if current_user_id else None
                ville_utilisateur = request.form.get('reviewer-location')
                consentement = get_consent_value('review-consent')

                if not (note and 0 < note <= 5):
                     flash('Veuillez attribuer une note générale à la plateforme.', 'danger')
                     approved_platform_reviews = db.execute("SELECT * FROM avis_plateforme WHERE status = 'approved' ORDER BY date_avis DESC").fetchall()
                     user_info = { "email": session.get('user_email'),"name": session.get('user_name')} if 'user_id' in session else None
                     return render_template('avisassurancesma.html', user_info=user_info, approved_platform_reviews=approved_platform_reviews)

                db.execute(
                    """INSERT INTO avis_plateforme
                       (user_id, note, titre_avis, commentaire, nom_utilisateur, email_utilisateur, ville_utilisateur, consentement, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
                    (current_user_id, note, titre_avis, commentaire, nom_utilisateur, email_utilisateur, ville_utilisateur, consentement)
                )
                db.commit()
                flash('Votre avis sur la plateforme a été soumis et est en attente de modération. Merci!', 'success')
                return redirect(url_for('avis_plateforme'))
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in /avis-plateforme POST: {e}")
                db.rollback()
                flash(f'Une erreur de base de données est survenue: {e}', 'danger')
            except Exception as e:
                current_app.logger.error(f"General error in /avis-plateforme POST: {e}")
                flash(f'Une erreur est survenue: {e}', 'danger')

        user_info = None
        if 'user_id' in session:
            user_info = { "email": session.get('user_email'),"name": session.get('user_name')}

        approved_platform_reviews = db.execute("SELECT * FROM avis_plateforme WHERE status = 'approved' ORDER BY date_avis DESC").fetchall()
        return render_template('avisassurancesma.html', user_info=user_info, approved_platform_reviews=approved_platform_reviews)

    # --- Admin Review Panel Routes ---
    @app.route('/admin/reviews/login', methods=['GET', 'POST'])
    def admin_review_login():
        if request.method == 'POST':
            password = request.form.get('password')
            if password == current_app.config['ADMIN_REVIEW_PASSWORD']:
                session['review_admin_logged_in'] = True
                flash('Connexion administrateur des avis réussie.', 'success')
                next_url = request.args.get('next')
                return redirect(next_url or url_for('admin_reviews_panel'))
            else:
                flash('Mot de passe incorrect.', 'danger')
        return render_template('admin_review_login.html')

    @app.route('/admin/reviews/logout')
    def admin_review_logout():
        session.pop('review_admin_logged_in', None)
        flash('Déconnecté du panneau d\'administration des avis.', 'info')
        return redirect(url_for('admin_review_login'))

    @app.route('/admin/reviews')
    @review_admin_required
    def admin_reviews_panel():
        db = database.get_db()
        pending_assureur_reviews = db.execute("SELECT * FROM avis_assureurs WHERE status = 'pending' ORDER BY date_avis DESC").fetchall()
        pending_plateforme_reviews = db.execute("SELECT * FROM avis_plateforme WHERE status = 'pending' ORDER BY date_avis DESC").fetchall()

        approved_assureur_reviews = db.execute("SELECT * FROM avis_assureurs WHERE status = 'approved' ORDER BY date_avis DESC LIMIT 10").fetchall()
        approved_plateforme_reviews = db.execute("SELECT * FROM avis_plateforme WHERE status = 'approved' ORDER BY date_avis DESC LIMIT 10").fetchall()

        rejected_assureur_reviews = db.execute("SELECT * FROM avis_assureurs WHERE status = 'rejected' ORDER BY date_avis DESC LIMIT 10").fetchall()
        rejected_plateforme_reviews = db.execute("SELECT * FROM avis_plateforme WHERE status = 'rejected' ORDER BY date_avis DESC LIMIT 10").fetchall()

        return render_template('admin_reviews.html',
                               pending_assureur_reviews=pending_assureur_reviews,
                               pending_plateforme_reviews=pending_plateforme_reviews,
                               approved_assureur_reviews=approved_assureur_reviews,
                               approved_plateforme_reviews=approved_plateforme_reviews,
                               rejected_assureur_reviews=rejected_assureur_reviews,
                               rejected_plateforme_reviews=rejected_plateforme_reviews
                               )

    @app.route('/admin/reviews/update_status/<review_type>/<int:review_id>/<new_status>', methods=['POST'])
    @review_admin_required
    def update_review_status(review_type, review_id, new_status):
        db = database.get_db()
        valid_statuses = ['approved', 'rejected', 'pending']
        if new_status not in valid_statuses:
            flash('Statut invalide.', 'danger')
            return redirect(url_for('admin_reviews_panel'))

        table_name = None
        if review_type == 'assureur':
            table_name = 'avis_assureurs'
        elif review_type == 'plateforme':
            table_name = 'avis_plateforme'
        else:
            flash('Type d\'avis invalide.', 'danger')
            return redirect(url_for('admin_reviews_panel'))

        try:
            db.execute(f"UPDATE {table_name} SET status = ? WHERE id = ?", (new_status, review_id))
            db.commit()
            if new_status == 'pending':
                flash(f'L\'approbation de l\'avis {review_id} ({review_type}) a été annulée. Il est de nouveau en attente.', 'info')
            else:
                flash(f'Statut de l\'avis {review_id} ({review_type}) mis à jour à "{new_status}".', 'success')
        except sqlite3.Error as e:
            db.rollback()
            current_app.logger.error(f"Database error updating review status: {e}")
            flash('Erreur de base de données lors de la mise à jour du statut.', 'danger')

        return redirect(url_for('admin_reviews_panel'))


    @app.route('/subscribe_price_alert', methods=['POST'])
    def subscribe_price_alert():
        if request.method == 'POST':
            email_utilisateur_form = request.form.get('alert-email')
            type_alerte = request.form.get('alert-insurance-type')
            current_user_id = get_current_user_id()
            user_email_to_use = email_utilisateur_form
            if current_user_id and session.get('user_email'):
                 if not email_utilisateur_form or email_utilisateur_form == session.get('user_email'):
                    user_email_to_use = session.get('user_email')
            if not user_email_to_use or not type_alerte:
                flash('Veuillez fournir une adresse e-mail et un type d\'assurance pour l\'alerte.', 'danger')
                return redirect(request.referrer or url_for('index'))
            try:
                db = database.get_db()
                db.execute(
                    """INSERT INTO alertes (user_id, email_utilisateur, type_alerte)
                       VALUES (?, ?, ?)""",
                    (current_user_id, user_email_to_use, type_alerte)
                )
                db.commit()
                flash(f'Alerte de prix pour {type_alerte} enregistrée pour {user_email_to_use} !', 'success')
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in /subscribe_price_alert POST: {e}")
                db.rollback()
                flash(f'Une erreur de base de données est survenue: {e}', 'danger')
            except Exception as e:
                current_app.logger.error(f"General error in /subscribe_price_alert POST: {e}")
                flash(f'Une erreur est survenue: {e}', 'danger')
            return redirect(request.referrer or url_for('index'))
        return redirect(url_for('index'))

    # --- User Account and Dashboard ---
    @app.route('/moncompte', methods=['GET'])
    def moncompte():
        return render_template('moncompte.html')

    @app.route('/ar/moncompte', methods=['GET'])
    def moncompte_ar():
        return render_template('moncompte-ar.html')

    @app.route('/dashboard')
    def dashboard():
        temp_user_id = session.get('user_id')

        if not temp_user_id:
            flash('Veuillez vous connecter pour accéder à votre tableau de bord.', 'warning')
            return redirect(url_for('moncompte'))

        try:
            user_id = int(temp_user_id)
        except ValueError:
            current_app.logger.error(f"Invalid user_id in session: {temp_user_id}. Redirecting to login.")
            flash("Une erreur est survenue avec votre session utilisateur. Veuillez vous reconnecter.", "danger")
            return redirect(url_for('moncompte'))

        user_info = {
            "name": session.get('user_name'),
            "email": session.get('user_email')
        }
        quotes = []
        tables_to_check = [
            "assurance_auto", "assurance_moto", "assurance_habitation", "assurance_sante",
            "assurance_emprunteur", "assurance_voyage", "assurance_loisirs", "assurance_animaux",
            "assurance_flotte", "assurance_maritime", "assurance_marchandise", "assurance_credit",
            "assurance_accident_travail", "assurance_retraite", "assurance_patrimoine", "assurance_cnops",
            "assurance_amc_individuelle", "assurance_stage", "assurance_ecole" # Now including new tables
        ]

        db = database.get_db()

        for table_name in tables_to_check:
            try:
                cursor = db.execute(f"PRAGMA table_info({table_name})")
                columns = [col[1] for col in cursor.fetchall()]

                # Prioritize 'date_soumission' if it exists, otherwise use 'created_at'
                date_field_name = 'date_soumission' if 'date_soumission' in columns else 'created_at'

                select_cols = ["id", date_field_name, "email", "telephone"]
                if "status" in columns:
                    select_cols.append("status")
                if "action_type" in columns:
                    select_cols.append("action_type")

                query = f"SELECT {', '.join(select_cols)} FROM {table_name} WHERE user_id = ? ORDER BY {date_field_name} DESC"

                user_quotes_for_table = db.execute(query, (user_id,)).fetchall()
                for q in user_quotes_for_table:
                    quotes.append({
                        "type": table_name.replace("assurance_", "").replace("_", " ").title(),
                        "id": q["id"],
                        "date": q[date_field_name], # Use the dynamically determined date field
                        "action": q["action_type"] if "action_type" in q.keys() else 'quote', # Default for new tables
                        "status": q["status"] if "status" in q.keys() else 'active' # Default for new tables
                    })
            except sqlite3.Error as e:
                current_app.logger.warning(f"Could not query {table_name} for dashboard quotes (error or column mismatch): {e}")

        return render_template('dashboard.html', user_info=user_info, quotes=quotes)

    # --- API Endpoints for Dashboard Policies ---
    def serialize_policy(policy_row):
        policy_dict = dict(policy_row)
        if policy_dict.get('specific_details'):
            try:
                policy_dict['specific_details'] = json.loads(policy_dict['specific_details'])
            except json.JSONDecodeError:
                current_app.logger.error(f"Error decoding JSON for policy ID {policy_dict.get('id')}")
                policy_dict['specific_details'] = {}
        else:
            policy_dict['specific_details'] = {}
        policy_dict['alert_active'] = bool(policy_dict.get('alert_active', True))
        return policy_dict

    @app.route('/api/dashboard/policies', methods=['GET'])
    def get_dashboard_policies():
        if 'user_id' not in session:
            return jsonify({"error": "Not authenticated"}), 401
        user_id = session['user_id']
        db = database.get_db()
        active_policies_rows = db.execute(
            "SELECT * FROM dashboard_user_policies WHERE user_id = ? AND status = 'active' ORDER BY end_date ASC", (user_id,)
        ).fetchall()
        active_policies = [serialize_policy(row) for row in active_policies_rows]
        history_policies_rows = db.execute(
            "SELECT * FROM dashboard_user_policies WHERE user_id = ? AND (status = 'expired' OR status = 'deleted') ORDER BY end_date DESC", (user_id,)
        ).fetchall()
        history_policies = [serialize_policy(row) for row in history_policies_rows]
        return jsonify({
            "activeInsurances": active_policies,
            "policyHistory": history_policies
        })

    @app.route('/api/dashboard/policies', methods=['POST'])
    def add_dashboard_policy():
        if 'user_id' not in session:
            return jsonify({"error": "Not authenticated"}), 401
        user_id = session['user_id']
        data = request.json
        required_fields = ['insuranceType', 'insurer', 'startDate', 'endDate', 'amount', 'paymentFrequency']
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400
        if not data.get('amount') or not isinstance(data.get('amount'), (int, float)):
             return jsonify({"error": "Invalid amount for policy"}), 400

        specific_details = {}
        insurance_type = data.get('insuranceType')
        if insurance_type == 'Auto':
            specific_details['autoMarque'] = data.get('autoMarque')
            specific_details['autoModele'] = data.get('autoModele')
            specific_details['autoTypeAssurance'] = data.get('autoTypeAssurance')
        elif insurance_type == 'Habitation':
            specific_details['habitationSurface'] = data.get('habitationSurface')
        elif insurance_type == 'Emprunteur':
            specific_details['emprunteurMontantPret'] = data.get('emprunteurMontantPret')
            specific_details['emprunteurOrganisme'] = data.get('emprunteurOrganisme')
        elif insurance_type == 'Santé':
             specific_details['santeTypeCouverture'] = data.get('santeTypeCouverture')
             specific_details['santeBeneficiaires'] = data.get('santeBeneficiaires')
        elif insurance_type == 'Moto':
            specific_details['motoMarque'] = data.get('motoMarque')
            specific_details['motoModele'] = data.get('motoModele')
            specific_details['motoCylindree'] = data.get('motoCylindree')
        elif insurance_type == 'Voyage':
            specific_details['voyageDestination'] = data.get('voyageDestination')
            specific_details['voyageDureeJours'] = data.get('voyageDureeJours')
        elif insurance_type == 'Retraite':
            specific_details['retraiteTypeProduit'] = data.get('retraiteTypeProduit')
            specific_details['retraiteVersementPeriodique'] = data.get('retraiteVersementPeriodique')

        db = database.get_db()
        try:
            cursor = db.execute(
                """INSERT INTO dashboard_user_policies
                   (user_id, insurance_type, insurer, start_date, end_date, amount, payment_frequency, notes, alert_active, status, specific_details, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, data['insuranceType'], data['insurer'], data['startDate'], data['endDate'],
                 float(data['amount']), data['paymentFrequency'], data.get('notes'), data.get('alertActive', True),
                 'active', json.dumps(specific_details), datetime.utcnow())
            )
            db.commit()
            new_policy_id = cursor.lastrowid
            new_policy_row = db.execute("SELECT * FROM dashboard_user_policies WHERE id = ?", (new_policy_id,)).fetchone()
            return jsonify(serialize_policy(new_policy_row)), 201
        except sqlite3.Error as e:
            current_app.logger.error(f"Database error adding policy: {e}")
            db.rollback()
            return jsonify({"error": "Database error"}), 500

    @app.route('/api/dashboard/policies/<int:policy_id>', methods=['PUT'])
    def update_dashboard_policy(policy_id):
        if 'user_id' not in session:
            return jsonify({"error": "Not authenticated"}), 401
        user_id = session['user_id']
        data = request.json
        required_fields = ['insuranceType', 'insurer', 'startDate', 'endDate', 'amount', 'paymentFrequency']
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields"}), 400
        if not data.get('amount') or not isinstance(data.get('amount'), (int, float)):
             return jsonify({"error": "Invalid amount for policy"}), 400

        specific_details = {}
        insurance_type = data.get('insuranceType')
        if insurance_type == 'Auto':
            specific_details['autoMarque'] = data.get('autoMarque')
            specific_details['autoModele'] = data.get('autoModele')
            specific_details['autoTypeAssurance'] = data.get('autoTypeAssurance')
        elif insurance_type == 'Habitation':
            specific_details['habitationSurface'] = data.get('habitationSurface')
        elif insurance_type == 'Emprunteur':
            specific_details['emprunteurMontantPret'] = data.get('emprunteurMontantPret')
            specific_details['emprunteurOrganisme'] = data.get('emprunteurOrganisme')
        elif insurance_type == 'Santé':
             specific_details['santeTypeCouverture'] = data.get('santeTypeCouverture')
             specific_details['santeBeneficiaires'] = data.get('santeBeneficiaires')
        elif insurance_type == 'Moto':
            specific_details['motoMarque'] = data.get('motoMarque')
            specific_details['motoModele'] = data.get('motoModele')
            specific_details['motoCylindree'] = data.get('motoCylindree')
        elif insurance_type == 'Voyage':
            specific_details['voyageDestination'] = data.get('voyageDestination')
            specific_details['voyageDureeJours'] = data.get('voyageDureeJours')
        elif insurance_type == 'Retraite':
            specific_details['retraiteTypeProduit'] = data.get('retraiteTypeProduit')
            specific_details['retraiteVersementPeriodique'] = data.get('retraiteVersementPeriodique')

        db = database.get_db()
        try:
            policy_check = db.execute("SELECT id FROM dashboard_user_policies WHERE id = ? AND user_id = ?", (policy_id, user_id)).fetchone()
            if not policy_check:
                return jsonify({"error": "Policy not found or not authorized"}), 404
            db.execute(
                """UPDATE dashboard_user_policies SET
                   insurance_type = ?, insurer = ?, start_date = ?, end_date = ?, amount = ?,
                   payment_frequency = ?, notes = ?, alert_active = ?, specific_details = ?, status = ?, updated_at = ?
                   WHERE id = ? AND user_id = ?""",
                (data['insuranceType'], data['insurer'], data['startDate'], data['endDate'],
                 float(data['amount']), data['paymentFrequency'], data.get('notes'), data.get('alertActive', True),
                 json.dumps(specific_details), data.get('status', 'active'), datetime.utcnow(),
                 policy_id, user_id)
            )
            db.commit()
            updated_policy_row = db.execute("SELECT * FROM dashboard_user_policies WHERE id = ?", (policy_id,)).fetchone()
            return jsonify(serialize_policy(updated_policy_row))
        except sqlite3.Error as e:
            current_app.logger.error(f"Database error updating policy {policy_id}: {e}")
            db.rollback()
            return jsonify({"error": "Database error"}), 500

    @app.route('/api/dashboard/policies/<int:policy_id>', methods=['DELETE'])
    def delete_dashboard_policy(policy_id):
        if 'user_id' not in session:
            return jsonify({"error": "Not authenticated"}), 401
        user_id = session['user_id']
        db = database.get_db()
        try:
            policy_check = db.execute("SELECT id FROM dashboard_user_policies WHERE id = ? AND user_id = ?", (policy_id, user_id)).fetchone()
            if not policy_check:
                return jsonify({"error": "Policy not found or not authorized"}), 404
            db.execute("UPDATE dashboard_user_policies SET status = 'deleted', updated_at = ? WHERE id = ? AND user_id = ?", (datetime.utcnow(), policy_id, user_id))
            db.commit()
            return jsonify({"message": "Policy moved to history"}), 200
        except sqlite3.Error as e:
            current_app.logger.error(f"Database error deleting policy {policy_id}: {e}")
            db.rollback()
            return jsonify({"error": "Database error"}), 500

    @app.route('/api/dashboard/policies/<int:policy_id>/toggle_alert', methods=['PATCH'])
    def toggle_policy_alert(policy_id):
        if 'user_id' not in session:
            return jsonify({"error": "Not authenticated"}), 401
        user_id = session['user_id']
        data = request.json
        alert_active = data.get('alertActive')
        if alert_active is None or not isinstance(alert_active, bool):
            return jsonify({"error": "Invalid value for alertActive"}), 400
        db = database.get_db()
        try:
            policy_check = db.execute("SELECT id FROM dashboard_user_policies WHERE id = ? AND user_id = ?", (policy_id, user_id)).fetchone()
            if not policy_check:
                return jsonify({"error": "Policy not found or not authorized"}), 404
            db.execute("UPDATE dashboard_user_policies SET alert_active = ?, updated_at = ? WHERE id = ? AND user_id = ?", (alert_active, datetime.utcnow(), policy_id, user_id))
            db.commit()
            updated_policy_row = db.execute("SELECT * FROM dashboard_user_policies WHERE id = ?", (policy_id,)).fetchone()
            return jsonify(serialize_policy(updated_policy_row))
        except sqlite3.Error as e:
            current_app.logger.error(f"Database error toggling alert for policy {policy_id}: {e}")
            db.rollback()
            return jsonify({"error": "Database error"}), 500

    # --- Business Leads Section Endpoints ---
    @app.route('/business/login', methods=['POST'])
    def business_login():
        db = database.get_db()
        data = request.json
        username = data.get('username')
        password = data.get('password')
        two_fa_code = data.get('two_fa_code')

        if not username or not password:
            return jsonify({"success": False, "message": "Nom d'utilisateur et mot de passe requis."}), 400

        prof_user = db.execute('SELECT * FROM professional_users WHERE username = ?', (username,)).fetchone()

        if prof_user and check_password_hash(prof_user['password_hash'], password):
            # Check if user has 2FA enabled
            if prof_user['two_fa_code']:
                # 2FA is enabled for this user
                if not two_fa_code:
                    # First step: username and password verified, need 2FA code
                    return jsonify({
                        "success": False,
                        "require_2fa": True,
                        "message": "Veuillez entrer votre code à 6 chiffres."
                    }), 200
                else:
                    # Second step: verify 2FA code
                    if two_fa_code == prof_user['two_fa_code']:
                        # 2FA code is correct, log in the user
                        session['professional_user_id'] = prof_user['id']
                        session['professional_username'] = prof_user['username']
                        session['professional_is_admin'] = prof_user['is_admin']
                        current_app.logger.info(f"Professional user {username} logged in with 2FA. Admin: {prof_user['is_admin']}")
                        return jsonify({"success": True, "username": prof_user['username'], "isAdmin": prof_user['is_admin']})
                    else:
                        current_app.logger.warning(f"Failed 2FA attempt for professional user {username}.")
                        return jsonify({"success": False, "message": "Code à 6 chiffres incorrect."}), 401
            else:
                # No 2FA enabled, log in directly
                session['professional_user_id'] = prof_user['id']
                session['professional_username'] = prof_user['username']
                session['professional_is_admin'] = prof_user['is_admin']
                current_app.logger.info(f"Professional user {username} logged in. Admin: {prof_user['is_admin']}")
                return jsonify({"success": True, "username": prof_user['username'], "isAdmin": prof_user['is_admin']})
        else:
            current_app.logger.warning(f"Failed login attempt for professional user {username}.")
            return jsonify({"success": False, "message": "Nom d'utilisateur ou mot de passe incorrect."}), 401

    @app.route('/business/logout', methods=['POST'])
    def business_logout():
        prof_username = session.get('professional_username', 'Unknown professional')
        session.pop('professional_user_id', None)
        session.pop('professional_username', None)
        session.pop('professional_is_admin', None)
        current_app.logger.info(f"Professional user {prof_username} logged out.")
        return jsonify({"success": True, "message": "Déconnexion réussie."})

    @app.route('/business/auth_status', methods=['GET'])
    def business_auth_status():
        if 'professional_user_id' in session and 'professional_username' in session:
            db = database.get_db()
            prof_user = db.execute('SELECT * FROM professional_users WHERE id = ?', (session['professional_user_id'],)).fetchone()

            return jsonify({
                "isLoggedIn": True,
                "username": session['professional_username'],
                "isAdmin": session.get('professional_is_admin', False),
                "company_name": prof_user['company_name'] if prof_user else None
            })
        else:
            return jsonify({"isLoggedIn": False})

    ASSURANCE_TABLES_CONFIG = {
        "assurance_auto": {"name": "Assurance Auto", "prices": {"quote": 20.0, "estimate": 20.0, "exclusive": 30.0}, "ville_field": "ville", "details_fields": ["marque", "modele", "prix_estime", "valeur_neuf", "carburant", "annee_circulation", "date_mec", "puissance_fiscale", "type_plaque", "immatriculation", "nombre_places", "date_naissance", "date_permis", "assureur_actuel"], "core_unique_fields": ["email", "telephone", "marque", "modele", "date_mec", "immatriculation", "ville"]},
        "assurance_moto": {"name": "Assurance Moto", "prices": {"quote": 10.0, "estimate": 10.0, "exclusive": 20.0}, "ville_field": "ville", "details_fields": ["type_moto", "cylindree"], "core_unique_fields": ["email", "telephone", "type_moto", "cylindree", "ville"]},
        "assurance_habitation": {"name": "Assurance Habitation", "prices": {"quote": 20.0, "estimate": 20.0, "exclusive": 30.0}, "ville_field": "ville", "details_fields": ["type_logement", "surface_habitable"], "core_unique_fields": ["email", "telephone", "type_logement", "surface_habitable", "ville"]},
        "assurance_sante": {"name": "Assurance Santé", "prices": {"quote": 25.0, "estimate": 25.0, "exclusive": 35.0}, "ville_field": "ville", "details_fields": ["besoins", "regime_social"], "core_unique_fields": ["email", "telephone", "besoins", "regime_social", "ville"]},
        "assurance_emprunteur": {"name": "Assurance Emprunteur", "prices": {"quote": 50.0, "estimate": 50.0, "exclusive": 60.0}, "ville_field": "ville", "details_fields": ["type_pret", "montant_emprunt"], "core_unique_fields": ["email", "telephone", "type_pret", "montant_emprunt", "duree_emprunt"]},
        "assurance_voyage": {"name": "Assurance Voyage", "prices": {"quote": 10.0, "estimate": 10.0, "exclusive": 20.0}, "ville_field": "ville", "details_fields": ["destination", "nombre_personnes"], "core_unique_fields": ["email", "telephone", "destination", "date_depart", "date_retour"]},
        "assurance_loisirs": {"name": "Assurance Loisirs", "prices": {"quote": 10.0, "estimate": 10.0, "exclusive": 20.0}, "ville_field": "ville", "details_fields": ["type_loisir", "valeur_bien"], "core_unique_fields": ["email", "telephone", "type_loisir", "valeur_bien", "ville"]},
        "assurance_animaux": {"name": "Assurance Animaux", "prices": {"quote": 10.0, "estimate": 10.0, "exclusive": 20.0}, "ville_field": "ville", "details_fields": ["type_animal", "race_animal"], "core_unique_fields": ["email", "telephone", "type_animal", "race_animal", "age_animal"]},
        "assurance_flotte": {"name": "Assurance Flotte Auto", "prices": {"quote": 50.0, "estimate": 50.0, "exclusive": 100.0}, "ville_field": "ville", "details_fields": ["type_vehicules", "nombre_vehicules"], "core_unique_fields": ["email", "telephone", "type_vehicules", "nombre_vehicules", "secteur_activite"]},
        "assurance_maritime": {"name": "Assurance Maritime", "prices": {"quote": 50.0, "estimate": 50.0, "exclusive": 100.0}, "ville_field": "zone_navigation", "details_fields": ["type_bateau", "usage_bateau"], "core_unique_fields": ["email", "telephone", "type_bateau", "valeur_bateau"]},
        "assurance_marchandise": {"name": "Assurance Marchandise", "prices": {"quote": 50.0, "estimate": 50.0, "exclusive": 100.0}, "ville_field": "destination", "details_fields": ["type_marchandise", "valeur_marchandise"], "core_unique_fields": ["email", "telephone", "type_marchandise", "valeur_marchandise", "mode_transport", "destination"]},
        "assurance_credit": {"name": "Assurance Crédit", "prices": {"quote": 50.0, "estimate": 50.0, "exclusive": 100.0}, "ville_field": "ville", "details_fields": ["type_credit", "montant_credit"], "core_unique_fields": ["email", "telephone", "type_credit", "montant_credit", "duree_remboursement"]},
        "assurance_accident_travail": {"name": "Assurance Accident du Travail", "prices": {"quote": 50.0, "estimate": 50.0, "exclusive": 100.0}, "ville_field": "ville", "details_fields": ["secteur_activite", "nombre_salaries"], "core_unique_fields": ["email", "telephone", "secteur_activite", "nombre_salaries"]},
        "assurance_retraite": {"name": "Assurance Retraite", "prices": {"quote": 30.0, "estimate": 30.0, "exclusive": 40.0}, "ville_field": "ville", "details_fields": ["situation_actuelle", "capacite_epargne"], "core_unique_fields": ["email", "telephone", "situation_actuelle", "revenu_mensuel"]},
        "assurance_patrimoine": {"name": "Assurance Patrimoine", "prices": {"quote": 50.0, "estimate": 50.0, "exclusive": 100.0}, "ville_field": "ville", "details_fields": ["type_patrimoine", "valeur_estimee"], "core_unique_fields": ["email", "telephone", "type_patrimoine", "valeur_estimee"]},
        "assurance_cnops": {"name": "Assurance Santé Complémentaire", "prices": {"quote": 25.0, "estimate": 25.0, "exclusive": 35.0}, "ville_field": "ville", "details_fields": ["type_couverture_cnops", "nom_complet"], "core_unique_fields": ["email", "telephone", "matricule_cnops", "type_couverture_cnops"]},
        "assurance_amc_individuelle": {"name": "Assurance AMC Individuelle", "prices": {"quote": 25.0, "estimate": 25.0, "exclusive": 35.0}, "ville_field": "city", "details_fields": ["firstname", "lastname", "profession", "marital_status", "children_count"], "core_unique_fields": ["email", "telephone", "firstname", "lastname", "city"]},
        # NEW: Configuration for Assurance Stage
        "assurance_stage": {"name": "Assurance Stage", "prices": {"quote": 10.0, "estimate": 10.0, "exclusive": 15.0}, "ville_field": "ville", "details_fields": ["ecole_university_name", "organisme_de_stage", "industry", "periode_de_stage"], "core_unique_fields": ["email", "telephone", "ecole_university_name", "organisme_de_stage", "ville"]},
        # NEW: Configuration for Assurance Ecole
        "assurance_ecole": {"name": "Assurance École", "prices": {"quote": 50.0, "estimate": 50.0, "exclusive": 100.0}, "ville_field": "ville", "details_fields": ["ecole_university_name", "number_of_students"], "core_unique_fields": ["email", "telephone", "ecole_university_name", "number_of_students", "ville"]},
        # NEW: Configuration for Assurance Cybersécurité
        "assurance_cybersecurity": {"name": "Assurance Cybersécurité", "prices": {"quote": 50.0, "estimate": 50.0, "exclusive": 100.0}, "ville_field": "ville", "details_fields": ["secteur_activite", "chiffre_affaires", "nombre_employes", "types_donnees"], "core_unique_fields": ["email", "telephone", "secteur_activite", "chiffre_affaires", "ville"]},
        # NEW: Configuration for Assurance Auto-entrepreneur
        "assurance_autoentrepreneur": {"name": "Assurance Auto-entrepreneur", "prices": {"quote": 30.0, "estimate": 30.0, "exclusive": 50.0}, "ville_field": "ville", "details_fields": ["domaine_activite", "chiffre_affaires", "nombre_clients", "anciennete"], "core_unique_fields": ["email", "telephone", "domaine_activite", "chiffre_affaires", "ville"]},
        # NEW: Configuration for Assurance RC Pro
        "assurance_rc_pro": {"name": "Assurance RC Pro", "prices": {"quote": 50.0, "estimate": 50.0, "exclusive": 100.0}, "ville_field": "ville", "details_fields": ["company_name", "activity", "turnover", "employees", "coverage", "franchise"], "core_unique_fields": ["email", "telephone", "company_name", "activity", "ville"]},
        # NEW: Configuration for Assurance Maladie Complémentaire Groupe
        "assurance_maladie_complementaire_groupe": {"name": "Assurance Maladie Complémentaire Groupe", "prices": {"quote": 50.0, "estimate": 50.0, "exclusive": 100.0}, "ville_field": "ville", "details_fields": ["company_name", "industry", "headcount", "spouses_count", "children_count", "annual_payroll"], "core_unique_fields": ["email", "telephone", "company_name", "industry", "headcount", "ville"]},
    }
    TVA_RATE = 0.20

    def generate_lead_details_string(row_dict, table_name):
        config = ASSURANCE_TABLES_CONFIG.get(table_name)
        if not config or not config.get("details_fields"):
            return "Détails non spécifiés"

        # Custom label mapping for specific tables/fields
        custom_labels = {
            "assurance_stage": {
                "ecole_university_name": "Prénom",
                "organisme_de_stage": "Nom",
                "industry": "Option",
                "periode_de_stage": "Période du stage"
            }
        }

        details_parts = []
        for field_key in config["details_fields"]:
            # Use custom label if available, otherwise generate from field name
            if table_name in custom_labels and field_key in custom_labels[table_name]:
                display_key = custom_labels[table_name][field_key]
            else:
                display_key = field_key.replace("_", " ").capitalize()
            value = row_dict.get(field_key)
            if value is not None:
                details_parts.append(f"{display_key}: {value}")
        return ", ".join(details_parts) if details_parts else "Détails non spécifiés"

    def generate_lead_core_unique_key(lead, table_name):
        config = ASSURANCE_TABLES_CONFIG.get(table_name)
        if not config or not config.get("core_unique_fields"):
            # Fallback if core_unique_fields is not defined for a table
            # Use 'created_at' if available, otherwise 'date_soumission' or a dummy string
            date_part = 'N/A'
            if 'created_at' in lead and lead['created_at']:
                date_part = str(lead['created_at']).split(' ')[0]
            elif 'date_soumission' in lead and lead['date_soumission']:
                date_part = str(lead['date_soumission']).split(' ')[0]

            return f"{table_name}_fallback_{lead.get('user_id')}_{lead.get('email')}_{lead.get('telephone')}_{date_part}"


        key_parts = []
        for field in config["core_unique_fields"]:
            value = lead.get(field)
            if field == "date_soumission" and value:
                value = str(value).split(' ')[0]
            elif field == "created_at" and value:
                value = str(value).split(' ')[0]
            key_parts.append(str(value) if value is not None else "N/A")
        return f"{table_name}_" + "_".join(key_parts)

    def get_user_category_access(prof_username, is_admin):
        """
        Returns a dict mapping category -> access rule.
        Rule format options:
          - {"allowed": [], "blocked": []}  # both empty = all Morocco
          - {"allowed": ["Casablanca"], "blocked": []}  # allow-list
          - {"allowed": [], "blocked": ["Rabat"]}  # block-list
        ENV format (CATEGORY_ACCESS):
          "assurance_stage:*"                   -> all Morocco
          "assurance_stage:Casablanca,Rabat"    -> allow only these
          "assurance_stage:!Rabat,Salé"         -> all except these (block list)
          Multiple rules can be separated by "|".
        Returns None if using old LOCATIONS behavior (backward compatibility).
        """
        if is_admin:
            return {}  # Admin has access to everything

        if not prof_username:
            return None

        category_access = {}

        # Check for category-specific access
        category_access_env = os.environ.get(f'PROF_USER_{prof_username.upper()}_CATEGORY_ACCESS', '')
        if category_access_env:
            # Format: "assurance_stage:*|assurance_ecole:Casablanca,Rabat|assurance_stage:!Rabat,Salé"
            for rule in category_access_env.split('|'):
                rule = rule.strip()
                if ':' not in rule:
                    continue
                category, locations_str = rule.split(':', 1)
                category = category.strip()
                locations_str = locations_str.strip()

                if not category:
                    continue

                # Block-list syntax: starts with "!"
                if locations_str.startswith('!'):
                    blocked = [loc.strip() for loc in locations_str[1:].split(',') if loc.strip()]
                    category_access[category] = {"allowed": [], "blocked": blocked}
                # Wildcard: "*"
                elif locations_str == '*':
                    category_access[category] = {"allowed": [], "blocked": []}  # all Morocco
                else:
                    allowed = [loc.strip() for loc in locations_str.split(',') if loc.strip()]
                    category_access[category] = {"allowed": allowed, "blocked": []}

            # If we have any category rules, return them
            if category_access:
                return category_access

        # Fallback to old LOCATIONS behavior if no category access is defined
        # This maintains backward compatibility
        return None

    @app.route('/api/business/leads', methods=['GET'])
    def api_business_leads():
        if 'professional_user_id' not in session:
            return jsonify({"error": "Not authenticated", "redirectToLogin": True}), 401

        prof_user_id = session['professional_user_id']
        prof_username = session.get('professional_username')
        is_admin = session.get('professional_is_admin', False)
        db = database.get_db()

        # Get category-specific access rules
        category_access = get_user_category_access(prof_username, is_admin)

        # Get old-style LOCATIONS for backward compatibility
        allowed_locations = []
        if prof_username and not is_admin:
            locations_env_var_key = f"PROF_USER_{prof_username.upper()}_LOCATIONS"
            locations_str = os.environ.get(locations_env_var_key, '')
            if locations_str:
                allowed_locations = [loc.strip() for loc in locations_str.split(',')]

        filter_insurance_type_req = request.args.get('insuranceType')
        filter_location_req = request.args.get('location')
        filter_date_req = request.args.get('dateCreated')
        filter_availability_req = request.args.get('availability')
        filter_status_req = request.args.get('status')
        filter_action_type_req = request.args.get('actionType', 'all')

        # Add 15-day filter for performance - only load leads from last 15 days
        fifteen_days_ago = datetime.now() - timedelta(days=15)
        fifteen_days_ago_str = fifteen_days_ago.strftime('%Y-%m-%d')

        all_raw_leads = []
        distinct_locations = set()
        max_claims_per_lead = 3

        for table_name, config in ASSURANCE_TABLES_CONFIG.items():
            if filter_insurance_type_req and config["name"] != filter_insurance_type_req:
                continue

            # Determine available columns for the current table
            cursor = db.execute(f"PRAGMA table_info({table_name})")
            columns_info = cursor.fetchall()
            available_columns = [col[1] for col in columns_info]

            # Dynamically select the date column
            date_column_in_table = None
            if "date_soumission" in available_columns: # Prioritize date_soumission
                date_column_in_table = "date_soumission"
            elif "created_at" in available_columns:
                date_column_in_table = "created_at"


            # Build query_fields dynamically
            query_fields_base = [f"{table_name}.id", f"{table_name}.email", f"{table_name}.user_id"]
            # telephone fallback: use telephone if present else phone as telephone
            if "telephone" in available_columns:
                query_fields_base.append(f"{table_name}.telephone")
            elif "phone" in available_columns:
                query_fields_base.append(f"{table_name}.phone AS telephone")
            else:
                query_fields_base.append(f"'' AS telephone")
            query_fields_base += [f"{table_name}.{f}" for f in config.get("details_fields", [])]

            # For assurance_auto, always include nom and prenom even if not in details_fields
            # (for confidentiality: not shown in market, but shown when lead is taken)
            if table_name == 'assurance_auto':
                if "nom" in available_columns:
                    query_fields_base.append(f"{table_name}.nom")
                if "prenom" in available_columns:
                    query_fields_base.append(f"{table_name}.prenom")

            # Add status and admin_notes if they exist in the current table
            if "status" in available_columns:
                query_fields_base.append(f"{table_name}.status")
            if "admin_notes" in available_columns: # Include admin_notes
                query_fields_base.append(f"{table_name}.admin_notes")
            if "action_type" in available_columns:
                query_fields_base.append(f"{table_name}.action_type")
            if "verified" in available_columns: # Include verified field
                query_fields_base.append(f"{table_name}.verified")

            # Add effective_ville if ville_field is specified in config
            if "ville_field" in config and config["ville_field"] in available_columns:
                query_fields_base.append(f"{table_name}.{config['ville_field']} AS effective_ville")

            select_parts = []
            if filter_availability_req == 'taken_by_me':
                # Use workspace tables for taken leads (much faster than JOINs)
                workspace_table = database.get_workspace_table_name(prof_user_id, table_name)

                if not database.table_exists(db, workspace_table):
                    # No workspace table exists for this user/category, skip
                    continue

                # Build filters for workspace query
                filters = {}
                if filter_date_req:
                    try:
                        datetime.strptime(filter_date_req, '%Y-%m-%d')
                        filters['date_from'] = filter_date_req
                    except ValueError:
                        current_app.logger.warning(f"Invalid date format for filter_date_req: {filter_date_req}")

                if filter_status_req:
                    filters['lead_status'] = filter_status_req

                # Get leads from workspace
                workspace_leads = database.get_workspace_leads(db, prof_user_id, table_name, filters)

                # Convert workspace leads to the expected format
                for lead in workspace_leads:
                    lead_dict = {
                        'id': lead['id'],
                        'email': lead.get('email'),
                        'telephone': lead.get('telephone') or lead.get('phone'),
                        'user_id': lead.get('user_id'),
                        'table_name': table_name,
                        'insuranceTypeDisplayName': config["name"],
                        'dateCreated': lead.get('date_soumission') or lead.get('created_at'),
                        'status': lead.get('status', 'active'),
                        'actionType': lead.get('action_type', 'quote'),
                        'admin_notes': lead.get('admin_notes'),
                        'verified': lead.get('verified', False),  # Include verified status
                        'lead_status': lead.get('lead_status'),
                        'contact_date': lead.get('contact_date'),
                        'lead_quality': lead.get('lead_quality'),
                        'probability': lead.get('probability'),
                        'estimated_value': lead.get('estimated_value'),
                        'next_action': lead.get('next_action'),
                        'comment': lead.get('comment'),
                        'taken_lead_id': lead.get('id'),  # Use workspace lead ID as taken_lead_id
                        'is_exclusive_take': lead.get('is_exclusive_take', False)
                    }

                    # Add detail fields from config
                    for field in config.get("details_fields", []):
                        if field in lead:
                            lead_dict[field] = lead[field]

                    # For taken leads (workspace leads), always include nom and prenom for assurance_auto
                    # even if they're not in details_fields (for confidentiality in market view)
                    if table_name == 'assurance_auto':
                        if 'nom' in lead:
                            lead_dict['nom'] = lead['nom']
                        if 'prenom' in lead:
                            lead_dict['prenom'] = lead['prenom']

                    # Add effective_ville if configured
                    if "ville_field" in config and config["ville_field"] in lead:
                        lead_dict['effective_ville'] = lead[config["ville_field"]]

                    all_raw_leads.append(lead_dict)
                    if 'effective_ville' in lead_dict and lead_dict['effective_ville']:
                        distinct_locations.add(lead_dict['effective_ville'])

                # Skip the standard query processing for taken leads
                continue

            else: # Standard market leads
                # For standard market leads, date_column_in_table should be aliased to date_soumission
                if date_column_in_table:
                    select_parts.append(f"{table_name}.{date_column_in_table} AS date_soumission")

                # Add all other fields
                for field_select in query_fields_base:
                    if date_column_in_table and field_select == f"{table_name}.{date_column_in_table}":
                        continue
                    select_parts.append(field_select)

                query_fields_str = ", ".join(select_parts)

                base_query = f"SELECT {query_fields_str} FROM {table_name} WHERE 1=1"
                params = []

                if "status" in available_columns:
                    if is_admin and filter_status_req:
                        base_query += " AND status = ?"
                        params.append(filter_status_req)
                    elif not is_admin:
                        base_query += " AND status IN ('active', 'exclusive_taken')"

                if filter_date_req and date_column_in_table: # Use date_column_in_table here
                    try:
                        datetime.strptime(filter_date_req, '%Y-%m-%d')
                        base_query += f" AND date({date_column_in_table}) >= ?"
                        params.append(filter_date_req)
                    except ValueError:
                        current_app.logger.warning(f"Invalid date format for filter_date_req: {filter_date_req}")
                elif date_column_in_table and filter_availability_req != 'taken_by_me': # Add 15-day filter for performance if no specific date filter and not viewing taken leads
                    base_query += f" AND date({date_column_in_table}) >= ?"
                    params.append(fifteen_days_ago_str)

                if filter_action_type_req != 'all' and "action_type" in available_columns:
                    base_query += " AND action_type = ?"
                    params.append(filter_action_type_req)

                if date_column_in_table: # Order by the actual column name here
                    base_query += f" ORDER BY {date_column_in_table} DESC"
                else:
                    base_query += f" ORDER BY {table_name}.id DESC" # Fallback if no date column


            try:
                rows = db.execute(base_query, tuple(params)).fetchall()
            except sqlite3.OperationalError as e:
                current_app.logger.error(f"Error querying table {table_name}: {e}. Query: {base_query}")
                continue

            for row_data in rows:
                row_dict = dict(row_data)
                row_dict['table_name'] = table_name
                row_dict['insuranceTypeDisplayName'] = config["name"]

                # date_soumission is now guaranteed to be the key if a date column exists and was aliased
                row_dict['dateCreated'] = row_dict.get('date_soumission') # Ensure this is now correctly named

                # Default status and action_type if not present in the fetched row (for older tables or specific cases)
                row_dict['status'] = row_dict.get('status', 'active')
                row_dict['actionType'] = row_dict.get('action_type', 'quote')
                row_dict['admin_notes'] = row_dict.get('admin_notes', None) # Add admin_notes here
                row_dict['verified'] = row_dict.get('verified', False) # Add verified status


                all_raw_leads.append(row_dict)
                if 'effective_ville' in row_dict and row_dict['effective_ville']:
                    distinct_locations.add(row_dict['effective_ville'])

        quote_core_keys = set()
        for lead in all_raw_leads:
            if lead['actionType'] == 'quote': # Changed from action_type to actionType
                quote_core_keys.add(generate_lead_core_unique_key(lead, lead['table_name']))

        final_filtered_leads = []
        seen_composite_ids = set()

        for lead_data in all_raw_leads:
            table_name = lead_data['table_name']
            lead_original_id = lead_data['id']
            lead_action_type = lead_data.get('actionType', 'quote') # Use actionType consistently
            lead_core_key = generate_lead_core_unique_key(lead_data, table_name)
            composite_id = f"{table_name}_{lead_original_id}"

            if composite_id in seen_composite_ids:
                continue

            include_lead = False
            if filter_action_type_req == 'all':
                if lead_action_type == 'quote':
                    include_lead = True
                elif lead_action_type == 'estimate' and lead_core_key not in quote_core_keys:
                    include_lead = True
            elif filter_action_type_req == 'quote':
                if lead_action_type == 'quote':
                    include_lead = True
            elif filter_action_type_req == 'estimate':
                if lead_action_type == 'estimate' and lead_core_key not in quote_core_keys:
                    include_lead = True

            # If filtering for taken_by_me, override include_lead based on whether it's taken by current user
            if filter_availability_req == 'taken_by_me':
                is_taken_by_current_user_row = db.execute(
                    "SELECT 1 FROM taken_leads WHERE lead_id = ? AND lead_table_name = ? AND professional_user_id = ?",
                    (lead_original_id, table_name, prof_user_id)
                ).fetchone()
                if not is_taken_by_current_user_row:
                    continue # Skip if not taken by current user when filter_availability_req is 'taken_by_me'
                include_lead = True # Include if taken by current user

            if not include_lead and filter_availability_req != 'taken_by_me':
                continue

            lead_status = lead_data.get('status', 'active') # Default status to 'active' for new tables

            exclusive_take_info = db.execute(
                "SELECT professional_user_id FROM taken_leads WHERE lead_id = ? AND lead_table_name = ? AND is_exclusive_take = 1",
                (lead_original_id, table_name)
            ).fetchone()

            is_exclusively_taken_by_anyone = bool(exclusive_take_info)
            exclusively_taken_by_prof_id = exclusive_take_info['professional_user_id'] if exclusive_take_info else None

            # This block should be after we determine if lead is taken by current user for 'taken_by_me' filter
            if filter_availability_req != 'taken_by_me' and is_exclusively_taken_by_anyone and exclusively_taken_by_prof_id != prof_user_id and not is_admin:
                continue

            current_max_claims = 1 if is_exclusively_taken_by_anyone else max_claims_per_lead

            claimed_count_row = db.execute(
                "SELECT COUNT(DISTINCT professional_user_id) as count FROM taken_leads WHERE lead_id = ? AND lead_table_name = ?",
                (lead_original_id, table_name)
            ).fetchone()
            times_claimed = claimed_count_row['count'] if claimed_count_row else 0

            is_taken_by_current_user_row = db.execute(
                "SELECT 1, id AS taken_lead_entry_id FROM taken_leads WHERE lead_id = ? AND lead_table_name = ? AND professional_user_id = ?",
                (lead_original_id, table_name, prof_user_id)
            ).fetchone()
            is_taken_by_current_user = bool(is_taken_by_current_user_row)
            taken_lead_entry_id = is_taken_by_current_user_row['taken_lead_entry_id'] if is_taken_by_current_user_row else None

            contact_info_for_lead = None
            if is_taken_by_current_user :
                contact_info_for_lead = {
                    "email": lead_data.get("email"),
                    "phone": lead_data.get("telephone") or lead_data.get("phone")
                }

            details_str = generate_lead_details_string(lead_data, table_name)
            date_created_str = None
            # The 'dateCreated' key should now reliably exist from the aliased query
            if 'dateCreated' in lead_data and lead_data['dateCreated']:
                if isinstance(lead_data['dateCreated'], str):
                    try:
                        dt_obj = datetime.fromisoformat(lead_data['dateCreated'].replace(' ', 'T'))
                        date_created_str = dt_obj.strftime('%Y-%m-%d')
                    except ValueError:
                         date_created_str = lead_data['dateCreated'].split(" ")[0]
                elif isinstance(lead_data['dateCreated'], (datetime, date)):
                    date_created_str = lead_data['dateCreated'].strftime('%Y-%m-%d')


            price_for_display = ASSURANCE_TABLES_CONFIG[table_name]["prices"].get(lead_action_type, 0.0)
            if is_exclusively_taken_by_anyone and exclusively_taken_by_prof_id == prof_user_id:
                 price_for_display = ASSURANCE_TABLES_CONFIG[table_name]["prices"].get("exclusive", price_for_display)

            lead_location = lead_data.get('effective_ville')

            # Check category-specific access or fall back to old LOCATIONS behavior
            if category_access is None:
                # Old behavior: use allowed_locations for all categories
                is_location_accessible = (
                    is_admin or
                    not allowed_locations or
                    (lead_location and lead_location in allowed_locations)
                )
            else:
                # New behavior: check category-specific access
                if is_admin:
                    is_location_accessible = True
                elif table_name in category_access:
                    # This category has specific rules
                    rule = category_access[table_name]
                    if isinstance(rule, dict):
                        allowed = rule.get("allowed", [])
                        blocked = rule.get("blocked", [])
                        if blocked:
                            is_location_accessible = bool(lead_location) and lead_location not in blocked
                        elif allowed:
                            is_location_accessible = bool(lead_location) and lead_location in allowed
                        else:
                            # Empty allowed/blocked => all Morocco
                            is_location_accessible = True
                    else:
                        # Backward compatibility if rule is still a list
                        category_locations = rule
                        if not category_locations:
                            is_location_accessible = True
                        else:
                            is_location_accessible = (
                                lead_location and lead_location in category_locations
                            )
                else:
                    # No specific rule for this category - check if old LOCATIONS applies
                    # This allows mixing old and new systems
                    if allowed_locations:
                        is_location_accessible = (
                            lead_location and lead_location in allowed_locations
                        )
                    else:
                        # No access defined for this category
                        is_location_accessible = False

            lead_entry = {
                "id": composite_id,
                "original_id": lead_original_id,
                "table_name": table_name,
                "insuranceType": lead_data['insuranceTypeDisplayName'],
                "location": lead_location if lead_location else "N/A",
                "dateCreated": date_created_str, # Use the correctly formatted date
                "details": details_str,
                "timesClaimed": times_claimed,
                "maxClaims": current_max_claims,
                "isTakenByCurrentUser": is_taken_by_current_user,
                "takenLeadEntryId": taken_lead_entry_id,
                "isExclusivelyTaken": is_exclusively_taken_by_anyone,
                "price": price_for_display,
                "exclusive_price": ASSURANCE_TABLES_CONFIG[table_name]["prices"].get("exclusive", 0.0),
                "quote_price": ASSURANCE_TABLES_CONFIG[table_name]["prices"].get("quote", 0.0),
                "estimate_price": ASSURANCE_TABLES_CONFIG[table_name]["prices"].get("estimate", 0.0),
                "contact_details": contact_info_for_lead,
                "email": lead_data.get("email"),
                "phone": lead_data.get("telephone"),
                "status": lead_status,
                "actionType": lead_action_type, # Use actionType consistently
                "adminNotes": lead_data.get("admin_notes"), # Add admin_notes here
                "verified": lead_data.get("verified", False), # Add verified status
                "is_accessible_location": is_location_accessible
            }

            # For assurance_auto, include nom and prenom in lead_entry (for taken leads display)
            # These are not in details_str for confidentiality in market view
            if table_name == 'assurance_auto':
                if 'nom' in lead_data:
                    lead_entry['nom'] = lead_data['nom']
                if 'prenom' in lead_data:
                    lead_entry['prenom'] = lead_data['prenom']

            if filter_availability_req == 'taken_by_me':
                lead_entry['leadStatus'] = lead_data.get('lead_status', 'Nouveau')
                lead_entry['contactDate'] = lead_data.get('contact_date')
                lead_entry['leadQuality'] = lead_data.get('lead_quality', 'medium')
                lead_entry['probability'] = lead_data.get('probability', 0)
                lead_entry['estimatedValue'] = lead_data.get('estimated_value', 0.0)
                lead_entry['nextAction'] = lead_data.get('next_action')
                lead_entry['comment'] = lead_data.get('comment')

            final_filtered_leads.append(lead_entry)
            seen_composite_ids.add(composite_id)

        final_filtered_leads.sort(key=lambda x: (x['dateCreated'] is not None, x['dateCreated']), reverse=True)

        return jsonify({
            "success": True,
            "leads": final_filtered_leads,
            "distinct_locations": sorted(list(loc for loc in distinct_locations if loc))
        })

    @app.route('/api/admin/lead/update_status', methods=['POST'])
    @admin_required
    def admin_update_lead_status():
        data = request.json
        original_lead_id = data.get('original_id')
        lead_table_name = data.get('table_name')
        new_status = data.get('new_status')
        admin_notes = data.get('admin_notes', None)

        if not all([original_lead_id, lead_table_name, new_status]):
            return jsonify({"success": False, "message": "Données manquantes (ID, table, ou nouveau statut)."}), 400

        if lead_table_name not in ASSURANCE_TABLES_CONFIG:
            return jsonify({"success": False, "message": "Type de table de lead invalide."}), 400

        # Check if the table has a 'status' column before attempting to update it
        db = database.get_db()
        cursor = db.execute(f"PRAGMA table_info({lead_table_name})")
        columns = [col[1] for col in cursor.fetchall()]

        if "status" not in columns:
            return jsonify({"success": False, "message": f"La table '{lead_table_name}' ne supporte pas la gestion du statut direct."}), 400

        # Check if 'admin_notes' column exists before trying to update it
        admin_notes_col_exists = "admin_notes" in columns

        valid_statuses = ['active', 'removed_by_admin', 'quality_issue', 'contacted', 'converted', 'archived', 'exclusive_taken']
        if new_status not in valid_statuses:
            return jsonify({"success": False, "message": f"Statut invalide: {new_status}. Doit être l'un de: {', '.join(valid_statuses)}"}), 400


        try:
            if admin_notes_col_exists:
                query = f"UPDATE {lead_table_name} SET status = ?, admin_notes = ? WHERE id = ?"
                cursor = db.execute(query, (new_status, admin_notes, original_lead_id))
            else:
                query = f"UPDATE {lead_table_name} SET status = ? WHERE id = ?"
                cursor = db.execute(query, (new_status, original_lead_id))
            db.commit()

            if cursor.rowcount == 0:
                return jsonify({"success": False, "message": "Lead non trouvé ou aucune modification effectuée."}), 404

            current_app.logger.info(f"Admin {session['professional_username']} updated lead {lead_table_name}_{original_lead_id} to status {new_status}")
            return jsonify({"success": True, "message": f"Statut du lead mis à jour à '{new_status}'."})

        except sqlite3.Error as e:
            db.rollback()
            current_app.logger.error(f"Database error updating lead status: {e}")
            return jsonify({"success": False, "message": "Erreur de base de données lors de la mise à jour du statut."}), 500
        except Exception as e:
            db.rollback()
            current_app.logger.error(f"Unexpected error updating lead status: {e}")
            return jsonify({"success": False, "message": "Une erreur inattendue est survenue."}), 500


    @app.route('/api/business/take_lead', methods=['POST'])
    def api_business_take_lead():
        if 'professional_user_id' not in session:
            return jsonify({"success": False, "message": "Non authentifié.", "redirectToLogin": True}), 401

        prof_user_id = session['professional_user_id']
        is_admin = session.get('professional_is_admin', False)
        data = request.json
        original_lead_id = data.get('original_id')
        lead_table_name = data.get('table_name')
        is_exclusive = data.get('is_exclusive', False)

        if not original_lead_id or not lead_table_name:
            return jsonify({"success": False, "message": "ID de lead ou nom de table manquant."}), 400

        if lead_table_name not in ASSURANCE_TABLES_CONFIG:
             return jsonify({"success": False, "message": "Type de table de lead invalide."}), 400

        db = database.get_db()

        # Fetch lead details, adapting for different column names and checking for existence
        email_col = 'email'

        # Check table columns dynamically
        cursor = db.execute(f"PRAGMA table_info({lead_table_name})")
        columns = [col[1] for col in cursor.fetchall()]

        # Determine phone column name (telephone or phone)
        # Select both if they exist, we'll use whichever has a value
        has_telephone = "telephone" in columns
        has_phone = "phone" in columns

        select_cols = [email_col]
        if has_telephone:
            select_cols.append("telephone")
        if has_phone:
            select_cols.append("phone")
        status_col_exists = "status" in columns
        action_type_col_exists = "action_type" in columns

        if status_col_exists:
            select_cols.append("status")
        if action_type_col_exists:
            select_cols.append("action_type")

        select_cols_str = ", ".join(select_cols)

        lead_details_row = db.execute(
            f"SELECT {select_cols_str} FROM {lead_table_name} WHERE id = ?", (original_lead_id,)
        ).fetchone()

        current_lead_status = lead_details_row['status'] if status_col_exists and lead_details_row else 'active' # Default if no status column
        lead_action_type = lead_details_row['action_type'] if action_type_col_exists and lead_details_row else 'quote' # Default if no action_type column


        if not lead_details_row:
            return jsonify({"success": False, "message": "Lead original non trouvé."}), 404

        exclusive_take_info = db.execute(
            "SELECT professional_user_id FROM taken_leads WHERE lead_id = ? AND lead_table_name = ? AND is_exclusive_take = 1",
            (original_lead_id, lead_table_name)
        ).fetchone()

        if exclusive_take_info and exclusive_take_info['professional_user_id'] != prof_user_id and not is_admin:
            return jsonify({"success": False, "message": "Ce lead a déjà été pris exclusivement par un autre professionnel."}), 403

        # Only check current_lead_status if the table actually has a status column, or if it's an admin bypass
        if status_col_exists and current_lead_status not in ['active', 'exclusive_taken'] and not is_admin:
             return jsonify({"success": False, "message": "Ce lead n'est actuellement pas disponible à la demande."}), 403

        already_taken_by_user = db.execute(
            "SELECT 1, is_exclusive_take FROM taken_leads WHERE lead_id = ? AND lead_table_name = ? AND professional_user_id = ?",
            (original_lead_id, lead_table_name, prof_user_id)
        ).fetchone()

        # Get phone from either telephone or phone column, whichever exists and has a value
        phone_value = None
        if has_telephone:
            try:
                tel_value = lead_details_row['telephone']
                if tel_value:
                    phone_value = tel_value
            except (KeyError, TypeError):
                pass
        if not phone_value and has_phone:
            try:
                phone_val = lead_details_row['phone']
                if phone_val:
                    phone_value = phone_val
            except (KeyError, TypeError):
                pass

        contact_info = {
            "email": lead_details_row[email_col],
            "phone": phone_value
        }

        if already_taken_by_user:
            if already_taken_by_user['is_exclusive_take']:
                return jsonify({
                    "success": True,
                    "message": "Vous avez déjà pris ce lead en exclusivité.",
                    "contact_details": contact_info,
                    "isExclusiveTake": True
                }), 200
            return jsonify({
                "success": True,
                "message": "Vous avez déjà demandé ce lead.",
                "contact_details": contact_info,
                "isExclusiveTake": False
            }), 200

        max_claims_for_check = 1 if is_exclusive else 3

        claimed_count_row = db.execute(
            "SELECT COUNT(DISTINCT professional_user_id) as count FROM taken_leads WHERE lead_id = ? AND lead_table_name = ?",
            (original_lead_id, lead_table_name)
        ).fetchone()
        times_claimed = claimed_count_row['count'] if claimed_count_row else 0

        if times_claimed >= max_claims_for_check and not is_admin:
            return jsonify({"success": False, "message": "Ce lead n'est plus disponible (nombre maximum de demandes atteint ou déjà pris en exclusivité)."}), 403

        try:
            lead_config = ASSURANCE_TABLES_CONFIG.get(lead_table_name)
            # Use the lead_action_type determined earlier
            price_at_claim = lead_config.get("prices", {}).get("exclusive" if is_exclusive else lead_action_type, 0.0)

            # Copy lead to workspace instead of using taken_leads table
            success = database.copy_lead_to_workspace(db, prof_user_id, original_lead_id, lead_table_name, is_exclusive)

            if not success:
                return jsonify({"success": False, "message": "Erreur lors de la copie du lead vers l'espace de travail."}), 500

            # Keep taken_leads for backward compatibility and billing
            db.execute(
                """INSERT INTO taken_leads (professional_user_id, lead_id, lead_table_name, price_at_claim, is_exclusive_take,
                                           lead_status, contact_date, lead_quality, probability, estimated_value, next_action, comment)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (prof_user_id, original_lead_id, lead_table_name, price_at_claim, 1 if is_exclusive else 0,
                 'Nouveau', None, 'medium', 0, 0.0, None, None)
            )

            # Only update status in original table if it has a status column
            if is_exclusive and status_col_exists: # Use status_col_exists
                db.execute(
                    f"UPDATE {lead_table_name} SET status = 'exclusive_taken' WHERE id = ?",
                    (original_lead_id,)
                )
                current_app.logger.info(f"Lead {lead_table_name}_{original_lead_id} marked as 'exclusive_taken' by professional {prof_user_id}.")

            db.commit()
            current_app.logger.info(f"Professional user {prof_user_id} took lead {lead_table_name}_{original_lead_id} (action_type: {lead_action_type}, exclusive: {is_exclusive}) for {price_at_claim}")
            return jsonify({"success": True, "message": "Lead demandé avec succès!", "contact_details": contact_info, "isExclusiveTake": is_exclusive})

        except sqlite3.Error as e:
            db.rollback()
            current_app.logger.error(f"Database error taking lead: {e}")
            return jsonify({"success": False, "message": "Erreur de base de données lors de la demande du lead."}), 500
        except Exception as e:
            db.rollback()
            current_app.logger.error(f"Unexpected error taking lead: {e}")
            return jsonify({"success": False, "message": "Une erreur inattendue est survenue."}), 500

    @app.route('/api/business/update_taken_lead', methods=['POST'])
    def api_business_update_taken_lead():
        if 'professional_user_id' not in session:
            return jsonify({"success": False, "message": "Non authentifié.", "redirectToLogin": True}), 401

        prof_user_id = session['professional_user_id']
        data = request.json
        taken_lead_id = data.get('taken_lead_id')
        lead_status = data.get('lead_status')
        contact_date = data.get('contact_date')
        lead_quality = data.get('lead_quality')
        probability = data.get('probability')
        estimated_value = data.get('estimated_value')
        next_action = data.get('next_action')
        comment = data.get('comment')

        if not taken_lead_id:
            return jsonify({"success": False, "message": "ID du lead ouvert manquant."}), 400

        db = database.get_db()
        try:
            # First, get the lead details from taken_leads to find the workspace table
            check_query = db.execute(
                "SELECT lead_id, lead_table_name FROM taken_leads WHERE id = ? AND professional_user_id = ?",
                (taken_lead_id, prof_user_id)
            ).fetchone()

            if not check_query:
                return jsonify({"success": False, "message": "Lead ouvert non trouvé ou non autorisé."}), 404

            lead_id = check_query['lead_id']
            lead_table_name = check_query['lead_table_name']
            workspace_table = database.get_workspace_table_name(prof_user_id, lead_table_name)

            # Update workspace table
            updates = {
                'lead_status': lead_status,
                'contact_date': contact_date,
                'lead_quality': lead_quality,
                'probability': probability,
                'estimated_value': estimated_value,
                'next_action': next_action,
                'comment': comment
            }

            success = database.update_workspace_lead(db, prof_user_id, workspace_table, lead_id, updates)

            if not success:
                return jsonify({"success": False, "message": "Erreur lors de la mise à jour du lead dans l'espace de travail."}), 500

            # Also update taken_leads for backward compatibility
            db.execute(
                """UPDATE taken_leads SET
                   lead_status = ?, contact_date = ?, lead_quality = ?,
                   probability = ?, estimated_value = ?, next_action = ?, comment = ?
                   WHERE id = ?""",
                (lead_status, contact_date, lead_quality,
                 probability, estimated_value, next_action, comment,
                 taken_lead_id)
            )
            db.commit()
            current_app.logger.info(f"Professional user {prof_user_id} updated taken lead {taken_lead_id}.")
            return jsonify({"success": True, "message": "Lead ouvert mis à jour avec succès."})

        except sqlite3.Error as e:
            db.rollback()
            current_app.logger.error(f"Database error updating taken lead {taken_lead_id}: {e}")
            return jsonify({"success": False, "message": "Erreur de base de données lors de la mise à jour du lead ouvert."}), 500
        except Exception as e:
            db.rollback()
            current_app.logger.error(f"Unexpected error updating taken lead {taken_lead_id}: {e}", exc_info=True)
            return jsonify({"success": False, "message": "Une erreur inattendue est survenue."}), 500


    @app.route('/api/business-tool/workspace-leads', methods=['GET'])
    def api_business_tool_workspace_leads():
        """Get workspace leads for business-tool prospects tab"""
        if 'professional_user_id' not in session:
            return jsonify({"error": "Non autorisé"}), 401

        prof_user_id = session['professional_user_id']
        insurance_category = request.args.get('category', 'assurance_auto')

        try:
            db = database.get_db()

            # Get workspace leads for the specified category
            workspace_leads = database.get_workspace_leads(db, prof_user_id, insurance_category)

            # Debug: Log what we're getting
            current_app.logger.info(f"Found {len(workspace_leads)} workspace leads for user {prof_user_id}, category {insurance_category}")
            if workspace_leads:
                current_app.logger.info(f"Sample lead keys: {list(workspace_leads[0].keys())}")

            # Convert to the format expected by business-tool
            formatted_leads = []
            for lead in workspace_leads:
                # Map the actual workspace data to what the frontend expects
                formatted_lead = {
                    # Core identification
                    'id': lead.get('id'),
                    'user_id': lead.get('user_id', ''),  # Ensure user_id is included

                    # Lead status and workflow
                    'lead_status': lead.get('lead_status', 'Nouveau'),  # Use lead_status consistently
                    'follow_up_date': lead.get('follow_up_date'),
                    'follow_up_completed': bool(lead.get('follow_up_completed', False)),
                    'lead_quality_score': int(lead.get('lead_quality_score', 50)),

                    # Essential missing fields
                    'consentement': lead.get('consentement', ''),
                    'action_type': lead.get('action_type', ''),
                    'code_postal': lead.get('code_postal', ''),
                    'admin_notes': lead.get('admin_notes', ''),

                    # Financial fields
                    'premium_amount': float(lead.get('premium_amount', 0) or 0),
                    'commission_rate': float(lead.get('commission_rate', 0) or 0),
                    'commission_amount': float(lead.get('commission_amount', 0) or 0),
                    'estimated_value': float(lead.get('estimated_value', 0) or 0),
                    'prix_estime': lead.get('prix_estime', ''),

                    # Contact information
                    'email': lead.get('email', ''),
                    'telephone': lead.get('telephone', ''),
                    'ville': lead.get('ville', ''),

                    # Timestamps
                    'date_soumission': lead.get('date_soumission') or lead.get('created_at', ''),
                    'workspace_updated_at': lead.get('workspace_updated_at'),
                    'taken_at': lead.get('taken_at'),

                    # Comment field (essential for editing)
                    'comment': lead.get('comment', ''),

                    # Insurance category-specific fields for assurance_auto
                    'marque': lead.get('marque', ''),
                    'modele': lead.get('modele', ''),
                    'carburant': lead.get('carburant', ''),
                    'annee_circulation': lead.get('annee_circulation', ''),
                    'date_mec': lead.get('date_mec', ''),
                    'puissance_fiscale': lead.get('puissance_fiscale', ''),
                    'type_plaque': lead.get('type_plaque', ''),
                    'immatriculation': lead.get('immatriculation', ''),
                    'nombre_places': lead.get('nombre_places', ''),
                    'prix_estime': lead.get('prix_estime', ''),  # This is valeur_actuelle
                    'valeur_neuf': lead.get('valeur_neuf', ''),
                    'nom': lead.get('nom', ''),
                    'prenom': lead.get('prenom', ''),
                    'date_naissance': lead.get('date_naissance', ''),
                    'date_permis': lead.get('date_permis', ''),
                    'assureur_actuel': lead.get('assureur_actuel', ''),

                    # Insurance category-specific fields for assurance_habitation
                    'type_logement': lead.get('type_logement', ''),
                    'statut_occupation': lead.get('statut_occupation', ''),
                    'residence_principale': lead.get('residence_principale', ''),
                    'surface_habitable': lead.get('surface_habitable', ''),
                    'nombre_pieces': lead.get('nombre_pieces', ''),

                    # Insurance category-specific fields for assurance_sante
                    'besoins': lead.get('besoins', ''),
                    'regime_social': lead.get('regime_social', ''),

                    # Insurance category-specific fields for assurance_voyage
                    'destination': lead.get('destination', ''),
                    'date_depart': lead.get('date_depart', ''),
                    'date_retour': lead.get('date_retour', ''),
                    'nombre_personnes': lead.get('nombre_personnes', ''),

                    # Insurance category-specific fields for assurance_moto
                    'type_moto': lead.get('type_moto', ''),
                    'cylindree': lead.get('cylindree', ''),
                    'usage_moto': lead.get('usage_moto', ''),
                    'mode_stationnement': lead.get('mode_stationnement', ''),

                    # Workspace management fields
                    'next_action': lead.get('next_action', ''),
                    'last_contact_attempt': lead.get('last_contact_attempt'),
                    'contact_date': lead.get('contact_date'),
                    'follow_up_date': lead.get('follow_up_date'),
                    'conversion_date': lead.get('conversion_date'),
                    'lost_reason': lead.get('lost_reason', ''),
                    'probability': lead.get('probability', 0),
                    'is_exclusive_take': lead.get('is_exclusive_take', False),
                    'professional_user_id': lead.get('professional_user_id'),
                    'source_table': lead.get('source_table', ''),

                    # Activity tracking (simplified)
                    'activity': []  # Will be populated separately if needed
                }
                formatted_leads.append(formatted_lead)

            # Debug: Log what we're returning
            current_app.logger.info(f"Returning {len(formatted_leads)} formatted leads")
            if formatted_leads:
                current_app.logger.info(f"Sample formatted lead keys: {list(formatted_leads[0].keys())}")

            return jsonify({"success": True, "leads": formatted_leads})

        except Exception as e:
            current_app.logger.error(f"Error fetching workspace leads: {e}")
            return jsonify({"error": "Erreur lors de la récupération des prospects"}), 500

    @app.route('/api/business-tool/user-categories', methods=['GET'])
    def api_business_tool_user_categories():
        """Get all insurance categories that the user has leads for"""
        if 'professional_user_id' not in session:
            return jsonify({"error": "Non autorisé"}), 401

        prof_user_id = session['professional_user_id']

        try:
            db = database.get_db()
            # Get all tables that match the pattern workspace_{user_id}_*
            cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ?", (f'workspace_{prof_user_id}_%',))
            tables = cursor.fetchall()

            categories = []
            for table in tables:
                table_name = table[0]
                # Extract category name from table name (workspace_{user_id}_{category})
                category = table_name.replace(f'workspace_{prof_user_id}_', '')
                categories.append(category)

            return jsonify({"success": True, "categories": categories})
        except Exception as e:
            current_app.logger.error(f"Error getting user categories: {e}")
            return jsonify({"error": "Erreur lors de la récupération des catégories"}), 500

    @app.route('/api/business-tool/table-schema', methods=['GET'])
    def api_business_tool_table_schema():
        """Get the schema (columns) for a specific workspace table"""
        if 'professional_user_id' not in session:
            return jsonify({"error": "Non autorisé"}), 401

        prof_user_id = session['professional_user_id']
        category = request.args.get('category')

        if not category:
            return jsonify({"error": "Catégorie requise"}), 400

        try:
            db = database.get_db()
            table_name = f'workspace_{prof_user_id}_{category}'

            # Check if table exists, if not create it with default schema
            cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            if not cursor.fetchone():
                # Create table with default schema based on category
                create_workspace_table(db, prof_user_id, category)

            # Get table schema
            cursor = db.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()

            schema = []
            for col in columns:
                schema.append({
                    'name': col[1],
                    'type': col[2],
                    'notnull': bool(col[3]),
                    'default': col[4],
                    'primary_key': bool(col[5])
                })

            return jsonify({"success": True, "schema": schema})
        except Exception as e:
            current_app.logger.error(f"Error getting table schema: {e}")
            return jsonify({"error": "Erreur lors de la récupération du schéma"}), 500

    @app.route('/api/business-tool/columns/<string:category>', methods=['GET'])
    def api_business_tool_columns(category):
        """Get the column names for a specific workspace table, excluding internal fields"""
        if 'professional_user_id' not in session:
            return jsonify({"error": "Non autorisé"}), 401

        prof_user_id = session['professional_user_id']

        try:
            db = database.get_db()
            table_name = f'workspace_{prof_user_id}_{category}'

            # Check if table exists, if not create it with default schema
            cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            if not cursor.fetchone():
                # Create table with default schema based on category
                create_workspace_table(db, prof_user_id, category)

            # Get table schema
            cursor = db.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()

            # Filter out internal fields that shouldn't be displayed in table
            # But keep fields that should be editable in the modal
            excluded_columns = {
                'source_table', 'source_updated_at', 'workspace_updated_at',
                'professional_user_id', 'taken_at', 'is_exclusive_take'
            }

            # Extract column names and filter out excluded ones
            column_names = []
            for col in columns:
                column_name = col[1]
                if column_name not in excluded_columns:
                    column_names.append(column_name)

            return jsonify({
                "success": True,
                "columns": column_names,
                "table_name": table_name
            })
        except Exception as e:
            current_app.logger.error(f"Error getting columns for {category}: {e}")
            return jsonify({"error": "Erreur lors de la récupération des colonnes"}), 500

    def create_workspace_table(db, user_id, category):
        """Create a new workspace table for a user and insurance category"""
        table_name = f'workspace_{user_id}_{category}'

        # Base schema that all workspace tables should have
        base_schema = """
            CREATE TABLE IF NOT EXISTS {} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                workspace_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                workspace_status TEXT DEFAULT 'Nouveau',
                workspace_next_follow_up DATE,
                workspace_follow_up_completed BOOLEAN DEFAULT 0,
                workspace_amount_won REAL DEFAULT 0,
                workspace_commission_percentage REAL DEFAULT 0,
                workspace_lead_score INTEGER DEFAULT 50,
                workspace_notes TEXT,
                workspace_priority TEXT DEFAULT 'Normal',
                workspace_assigned_to TEXT,
                workspace_deadline DATE,
                workspace_tags TEXT,
                workspace_source TEXT,
                workspace_campaign TEXT,
                workspace_budget REAL,
                workspace_probability REAL,
                workspace_stage TEXT,
                workspace_contact_method TEXT,
                workspace_last_contact TIMESTAMP,
                workspace_next_action TEXT,
                workspace_competitor TEXT,
                workspace_objection TEXT,
                workspace_solution TEXT,
                workspace_quote_sent BOOLEAN DEFAULT 0,
                workspace_quote_amount REAL,
                workspace_negotiation_notes TEXT,
                workspace_closing_date DATE,
                workspace_reason_lost TEXT,
                workspace_feedback TEXT,
                workspace_referral_source TEXT
            )
        """.format(table_name)

        # Add category-specific fields
        if category == 'assurance_auto':
            category_schema = """
                , marque TEXT
                , modele TEXT
                , prix_estime REAL
                , valeur_neuf REAL
                , carburant TEXT
                , annee_circulation INTEGER
                , date_mec DATE
                , puissance_fiscale INTEGER
                , type_plaque TEXT
                , immatriculation TEXT
                , nombre_places INTEGER
                , nom TEXT
                , prenom TEXT
                , date_naissance DATE
                , date_permis DATE
                , ville TEXT
                , email TEXT
                , telephone TEXT
                , assureur_actuel TEXT
                , verified BOOLEAN DEFAULT FALSE
                , source TEXT DEFAULT 'Website'
            """
        elif category == 'assurance_moto':
            category_schema = """
                , marque TEXT
                , modele TEXT
                , cylindree INTEGER
                , prix_estime REAL
                , annee_circulation INTEGER
                , ville TEXT
                , email TEXT
                , telephone TEXT
                , source TEXT DEFAULT 'Website'
            """
        elif category == 'assurance_habitation':
            category_schema = """
                , type_logement TEXT
                , statut_occupation TEXT
                , surface_habitable REAL
                , nombre_pieces INTEGER
                , ville TEXT
                , email TEXT
                , telephone TEXT
                , source TEXT DEFAULT 'Website'
            """
        elif category == 'assurance_sante':
            category_schema = """
                , besoins TEXT
                , regime_social TEXT
                , ville TEXT
                , email TEXT
                , telephone TEXT
                , source TEXT DEFAULT 'Website'
            """
        elif category == 'assurance_voyage':
            category_schema = """
                , destination TEXT
                , date_depart DATE
                , date_retour DATE
                , nombre_personnes INTEGER
                , ville TEXT
                , email TEXT
                , telephone TEXT
                , source TEXT DEFAULT 'Website'
            """
        else:
            # Generic schema for unknown categories
            category_schema = """
                , ville TEXT
                , email TEXT
                , telephone TEXT
                , source TEXT DEFAULT 'Website'
            """

        # Combine base and category schemas
        full_schema = base_schema.replace(')', category_schema + ')')

        try:
            db.execute(full_schema)
            db.commit()
            current_app.logger.info(f"Created workspace table: {table_name}")
        except Exception as e:
            current_app.logger.error(f"Error creating workspace table {table_name}: {e}")
            raise

    @app.route('/api/business-tool/update-workspace-lead', methods=['POST'])
    def api_business_tool_update_workspace_lead():
        """Update a workspace lead"""
        if 'professional_user_id' not in session:
            return jsonify({"error": "Non autorisé"}), 401

        prof_user_id = session['professional_user_id']

        try:
            data = request.json
            if not data:
                return jsonify({"error": "Données JSON requises"}), 400

            lead_id = data.get('lead_id')
            insurance_category = data.get('insurance_category')
            updates = data.get('updates', {})

            # Validation
            if not lead_id:
                return jsonify({"error": "ID du prospect requis"}), 400
            if not insurance_category:
                return jsonify({"error": "Catégorie d'assurance requise"}), 400
            if not updates:
                return jsonify({"error": "Aucune mise à jour fournie"}), 400

            # Validate lead_id is numeric
            try:
                lead_id = int(lead_id)
            except (ValueError, TypeError):
                return jsonify({"error": "ID du prospect invalide"}), 400

            # Filter out invalid fields that don't exist in database
            invalid_fields = ['insuranceType', 'source', 'activity', 'insuranceType', 'date_soumission', 'workspace_updated_at', 'taken_at', 'professional_user_id', 'is_exclusive_take', 'source_table', 'user_id', 'admin_notes', 'statut', 'statut_occupation', 'followUpCompleted', 'follow_up_completed', 'leadScore', 'lead_quality_score', 'commissionPercentage']
            filtered_updates = {}

            for key, value in updates.items():
                if key not in invalid_fields:
                    # Map frontend field names to database field names
                    if key == 'status':
                        filtered_updates['lead_status'] = value
                    elif key == 'nextFollowUp':
                        filtered_updates['follow_up_date'] = value
                    elif key == 'leadScore':
                        filtered_updates['lead_quality'] = value  # Map to lead_quality, not lead_quality_score
                    elif key == 'commissionPercentage':
                        filtered_updates['commission_rate'] = value
                    else:
                        filtered_updates[key] = value

            if not filtered_updates:
                return jsonify({"error": "Aucun champ valide à mettre à jour"}), 400

            current_app.logger.info(f"Original updates: {updates}")
            current_app.logger.info(f"Filtered updates: {filtered_updates}")

            updates = filtered_updates

            # Validate financial fields if present
            if 'premium_amount' in updates:
                try:
                    updates['premium_amount'] = float(updates['premium_amount']) if updates['premium_amount'] else 0.0
                except (ValueError, TypeError):
                    return jsonify({"error": "Montant de la prime invalide"}), 400

            if 'commission_rate' in updates:
                try:
                    rate = float(updates['commission_rate']) if updates['commission_rate'] else 0.0
                    if rate < 0 or rate > 100:
                        return jsonify({"error": "Taux de commission doit être entre 0 et 100%"}), 400
                    updates['commission_rate'] = rate
                except (ValueError, TypeError):
                    return jsonify({"error": "Taux de commission invalide"}), 400

            db = database.get_db()

            # Get the workspace table name
            workspace_table = database.get_workspace_table_name(prof_user_id, insurance_category)

            # Check if user is admin
            is_admin = session.get('professional_is_admin', False)

            # Check if lead exists
            # For admin users, check if lead exists in the table (any user)
            # For regular users, check if lead exists and belongs to them
            if is_admin:
                cursor = db.execute(
                    f"SELECT id FROM {workspace_table} WHERE id = ?",
                    (lead_id,)
                )
            else:
                cursor = db.execute(
                    f"SELECT id FROM {workspace_table} WHERE professional_user_id = ? AND id = ?",
                    (prof_user_id, lead_id)
                )

            if not cursor.fetchone():
                return jsonify({"error": "Prospect non trouvé ou accès non autorisé"}), 404

            # Update the workspace lead
            # For admin users, we still need to pass the lead's actual owner for the WHERE clause
            # But we'll modify the function to handle admin updates
            success = database.update_workspace_lead(db, prof_user_id, workspace_table, lead_id, updates, is_admin=is_admin)

            if success:
                # Return updated data for frontend
                # For admin users, get lead by id only; for regular users, check ownership
                try:
                    if is_admin:
                        cursor = db.execute(
                            f"SELECT * FROM {workspace_table} WHERE id = ?",
                            (lead_id,)
                        )
                    else:
                        cursor = db.execute(
                            f"SELECT * FROM {workspace_table} WHERE professional_user_id = ? AND id = ?",
                            (prof_user_id, lead_id)
                        )
                    updated_lead = cursor.fetchone()

                    # Convert Row to dict, handling date conversion issues
                    if updated_lead:
                        lead_dict = {}
                        for key in updated_lead.keys():
                            try:
                                value = updated_lead[key]
                                # Handle date fields that might cause conversion errors
                                if key in ['date_naissance', 'date_permis', 'date_mec'] and value:
                                    if isinstance(value, bytes):
                                        # If it's bytes, decode it
                                        try:
                                            value = value.decode('utf-8')
                                        except:
                                            value = str(value)
                                    lead_dict[key] = str(value)[:10] if len(str(value)) >= 10 else value
                                else:
                                    lead_dict[key] = value
                            except Exception as e:
                                current_app.logger.warning(f"Error converting field {key} for lead {lead_id}: {e}")
                                lead_dict[key] = None
                    else:
                        lead_dict = {}
                except Exception as e:
                    current_app.logger.error(f"Error fetching updated lead data: {e}", exc_info=True)
                    # Still return success since the update worked, just without the updated data
                    lead_dict = {}

                return jsonify({
                    "success": True,
                    "message": "Prospect mis à jour avec succès",
                    "updated_data": lead_dict
                })
            else:
                current_app.logger.error(f"Failed to update lead {lead_id} in workspace {workspace_table} for user {prof_user_id}")
                return jsonify({"error": "Erreur lors de la mise à jour du prospect"}), 500

        except sqlite3.Error as e:
            current_app.logger.error(f"Database error updating workspace lead: {e}", exc_info=True)
            import traceback
            current_app.logger.error(f"Traceback: {traceback.format_exc()}")
            return jsonify({"error": "Erreur de base de données lors de la mise à jour"}), 500
        except Exception as e:
            current_app.logger.error(f"Unexpected error updating workspace lead: {e}", exc_info=True)
            import traceback
            current_app.logger.error(f"Traceback: {traceback.format_exc()}")
            return jsonify({"error": "Erreur interne du serveur"}), 500

    @app.route('/api/business-tool/add-workspace-lead', methods=['POST'])
    def api_business_tool_add_workspace_lead():
        """Add a new lead to workspace"""
        if 'professional_user_id' not in session:
            return jsonify({"error": "Non autorisé"}), 401

        prof_user_id = session['professional_user_id']

        try:
            data = request.json
            if not data:
                return jsonify({"error": "Données JSON requises"}), 400

            insurance_category = data.get('insurance_category')
            lead_data = data.get('lead_data', {})

            # Validation
            if not insurance_category:
                return jsonify({"error": "Catégorie d'assurance requise"}), 400
            if not lead_data:
                return jsonify({"error": "Données du prospect requises"}), 400

            db = database.get_db()

            # Ensure workspace table exists
            workspace_table = database.get_workspace_table_name(prof_user_id, insurance_category)
            if not database.table_exists(db, workspace_table):
                success = database.create_workspace_table(db, prof_user_id, insurance_category)
                if not success:
                    return jsonify({"error": "Erreur lors de la création de la table de workspace"}), 500

            # Get the schema of the workspace table
            cursor = db.execute(f"PRAGMA table_info({workspace_table})")
            columns = [col[1] for col in cursor.fetchall()]

            # Prepare lead data for insertion
            insert_data = {
                'professional_user_id': prof_user_id,
                'lead_status': lead_data.get('lead_status', 'Nouveau'),
                'contact_date': lead_data.get('contact_date'),
                'lead_quality': lead_data.get('lead_quality', 'Moyen'),
                'probability': lead_data.get('probability', 50),
                'estimated_value': float(lead_data.get('estimated_value', 0)),
                'next_action': lead_data.get('next_action'),
                'comment': lead_data.get('comment'),
                'last_contact_attempt': lead_data.get('last_contact_attempt'),
                'follow_up_date': lead_data.get('follow_up_date'),
                'follow_up_completed': lead_data.get('follow_up_completed', False),
                'lead_quality_score': lead_data.get('lead_quality_score', 50),
                'conversion_date': lead_data.get('conversion_date'),
                'lost_reason': lead_data.get('lost_reason'),
                'source_table': 'manual',
                'source_updated_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                'workspace_updated_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                'premium_amount': float(lead_data.get('premium_amount', 0)),
                'commission_rate': float(lead_data.get('commission_rate', 0)),
                'commission_amount': float(lead_data.get('commission_amount', 0)),
                'taken_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                'is_exclusive_take': True,
                # Add missing critical fields for proper table display
                'consentement': lead_data.get('consentement', 'oui'),
                'action_type': lead_data.get('action_type', 'quote'),
                'date_soumission': lead_data.get('date_soumission', datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')),
                'status': 'active',
                'user_id': lead_data.get('user_id', 0),
                'admin_notes': lead_data.get('admin_notes', '')
            }

            # Add category-specific fields
            for key, value in lead_data.items():
                if key in columns and key not in insert_data:
                    insert_data[key] = value

            # Build INSERT query
            columns_to_insert = [col for col in insert_data.keys() if col in columns]
            placeholders = ['?' for _ in columns_to_insert]
            values = [insert_data[col] for col in columns_to_insert]

            # Generate unique numeric ID for user-added leads (starting with 000 for recognition)
            import time
            # Get current timestamp and user ID to create unique numeric ID
            timestamp_part = int(time.time() * 1000) % 1000000  # Last 6 digits of timestamp
            user_part = prof_user_id % 1000  # Last 3 digits of user ID
            # Create ID starting with 000 to make it recognizable as manually added
            user_lead_id = f'000{timestamp_part:06d}{user_part:03d}'

            # Add the custom ID to the insert data
            if 'id' in columns:
                insert_data['id'] = user_lead_id
                columns_to_insert = [col for col in insert_data.keys() if col in columns]
                placeholders = ['?' for _ in columns_to_insert]
                values = [insert_data[col] for col in columns_to_insert]

            insert_sql = f"""
                INSERT INTO {workspace_table} ({', '.join(columns_to_insert)})
                VALUES ({', '.join(placeholders)})
            """

            cursor = db.execute(insert_sql, values)
            lead_id = cursor.lastrowid
            db.commit()

            # Return the created lead
            cursor = db.execute(
                f"SELECT * FROM {workspace_table} WHERE professional_user_id = ? AND id = ?",
                (prof_user_id, lead_id)
            )
            created_lead = cursor.fetchone()

            return jsonify({
                "success": True,
                "message": "Prospect créé avec succès",
                "lead_id": lead_id,
                "lead": dict(created_lead) if created_lead else {}
            })

        except sqlite3.Error as e:
            current_app.logger.error(f"Database error adding workspace lead: {e}")
            return jsonify({"error": "Erreur de base de données lors de la création"}), 500
        except Exception as e:
            current_app.logger.error(f"Unexpected error adding workspace lead: {e}")
            return jsonify({"error": "Erreur interne du serveur"}), 500

    @app.route('/api/business/monthly_invoice', methods=['GET'])
    def api_business_monthly_invoice():
        if 'professional_user_id' not in session:
            return jsonify({"error": "Not authenticated", "redirectToLogin": True}), 401

        prof_user_id = session['professional_user_id']
        db = database.get_db()
        current_month_str = datetime.utcnow().strftime('%Y-%m')
        total_ht = 0.0

        try:
            taken_leads_rows = db.execute(
                """SELECT lead_id, lead_table_name, price_at_claim
                   FROM taken_leads
                   WHERE professional_user_id = ? AND strftime('%Y-%m', taken_at) = ?""",
                (prof_user_id, current_month_str)
            ).fetchall()

            if not taken_leads_rows:
                return jsonify({
                    "total_ht": 0.0,
                    "total_tva": 0.0,
                    "total_ttc": 0.0,
                    "month": current_month_str,
                    "billed_leads_count": 0
                })

            billed_leads_count = 0
            for taken_lead in taken_leads_rows:
                lead_id = taken_lead['lead_id']
                table_name = taken_lead['lead_table_name']
                price_at_claim = taken_lead['price_at_claim']

                if table_name not in ASSURANCE_TABLES_CONFIG:
                    current_app.logger.warning(f"Invalid table_name '{table_name}' found in taken_leads for professional_user_id {prof_user_id}. Skipping.")
                    continue

                # Check if the original table has a 'status' column dynamically
                cursor = db.execute(f"PRAGMA table_info({table_name})")
                columns = [col[1] for col in cursor.fetchall()]
                status_col_exists = "status" in columns

                if not status_col_exists:
                    # For tables without a 'status' column (like the new ones),
                    # we assume they are always billable if taken, unless explicitly
                    # marked as problematic in `taken_leads` (which is not handled by admin_update_lead_status for these tables)
                    total_ht += price_at_claim if price_at_claim is not None else 0.0
                    billed_leads_count += 1
                else:
                    try:
                        original_lead_status_row = db.execute(
                            f"SELECT status FROM {table_name} WHERE id = ?",
                            (lead_id,)
                        ).fetchone()

                        if original_lead_status_row:
                            lead_status = original_lead_status_row['status']
                            if lead_status not in ['removed_by_admin', 'quality_issue']:
                                total_ht += price_at_claim if price_at_claim is not None else 0.0
                                billed_leads_count +=1
                            else:
                                current_app.logger.info(f"Lead {table_name}_{lead_id} for user {prof_user_id} excluded from invoice due to status: {lead_status}")
                        else:
                            current_app.logger.warning(f"Original lead {table_name}_{lead_id} not found for invoice calculation for user {prof_user_id}.")
                    except sqlite3.Error as e_inner:
                        current_app.logger.error(f"DB error checking status for {table_name}_{lead_id} for invoice: {e_inner}")
                        continue


            total_tva = total_ht * TVA_RATE
            total_ttc = total_ht + total_tva

            return jsonify({
                "total_ht": round(total_ht, 2),
                "total_tva": round(total_tva, 2),
                "total_ttc": round(total_ttc, 2),
                "month": current_month_str,
                "billed_leads_count": billed_leads_count
            })
        except sqlite3.Error as e:
            current_app.logger.error(f"Database error fetching monthly invoice for user {prof_user_id}, month {current_month_str}: {e}")
            return jsonify({"error": "Database error while fetching invoice."}), 500
        except Exception as e:
            current_app.logger.error(f"An unexpected error occurred fetching monthly invoice for user {prof_user_id}, month {current_month_str}: {e}", exc_info=True)
            return jsonify({"error": "Une erreur interne est survenue sur le serveur."}), 500


    # --- Blog and Static Page Routes ---
    # NOTE: BLOG_AND_OUTILS_DATA is expected to be managed externally or loaded differently.
    # The routes below will cause an error if BLOG_AND_OUTILS_DATA is not accessible.

    # Using the globally defined BLOG_AND_OUTILS_DATA which is explicitly empty as requested
    # _BLOG_AND_OUTILS_DATA = [] # No need for this local variable anymore, use global.

    @app.route('/blog')
    def blog():
        # Using the global BLOG_AND_OUTILS_DATA directly
        blog_data_for_display = BLOG_AND_OUTILS_DATA
        num_to_sample = min(3, len(blog_data_for_display))
        random_items = []
        if len(blog_data_for_display) > 0 :
             random_items = random.sample(blog_data_for_display, num_to_sample)

        page_title = "Guides d'Achat & Outils Assurance | Conseils & Simulateurs | mesassurances.ma"

        return render_template('blog.html',
                               all_blog_items=blog_data_for_display,
                               random_featured_items=random_items,
                               page_title=page_title)

    @app.route('/blog/<slug>')
    def blog_post_page(slug):
        # Using the global BLOG_AND_OUTILS_DATA directly
        blog_data_for_display = BLOG_AND_OUTILS_DATA
        current_item = next((item for item in blog_data_for_display if item["slug"] == slug and item["category"] == "blog"), None)

        if not current_item:
            current_app.logger.warning(f"Blog post with slug '{slug}' not found.")
            return render_template("404.html"), 404

        all_other_blogs = [
            blog_item for blog_item in blog_data_for_display
            if blog_item["slug"] != slug and blog_item["category"] == "blog"
        ]

        num_related_blogs_to_show = 3
        related_blog_items = []
        if len(all_other_blogs) > 0:
            if len(all_other_blogs) >= num_related_blogs_to_show:
                related_blog_items = random.sample(all_other_blogs, num_related_blogs_to_show)
            else:
                related_blog_items = all_other_blogs

        page_title = current_item.get('title', "Blog")
        template_to_render = current_item.get("template_file")

        if not template_to_render:
            current_app.logger.error(f"No template_file defined for blog slug '{slug}'.")
            return render_template("404.html"), 404

        return render_template(
            template_to_render,
            item=current_item,
            page_title=page_title,
            related_blog_items=related_blog_items
        )

    @app.route('/outils/<slug>')
    def outil_page(slug):
        # Using the global BLOG_AND_OUTILS_DATA directly
        blog_data_for_display = BLOG_AND_OUTILS_DATA
        current_item = next((item for item in blog_data_for_display if item["slug"] == slug and item["category"] == "outils"), None)

        if not current_item:
            current_app.logger.warning(f"Outil with slug '{slug}' not found.")
            return render_template("404.html"), 404

        all_blogs = [
            blog_item for blog_item in blog_data_for_display if blog_item["category"] == "blog"
        ]
        num_related_blogs_to_show = 3
        related_blog_items_for_outil = []
        if len(all_blogs) > 0:
            if len(all_blogs) >= num_related_blogs_to_show:
                related_blog_items_for_outil = random.sample(all_blogs, num_related_blogs_to_show)
            else:
                related_blog_items_for_outil = all_blogs

        page_title = current_item.get('title', "Outil")
        template_to_render = current_item.get("template_file")

        if not template_to_render:
            current_app.logger.error(f"No template_file defined for outil slug '{slug}'.")
            return render_template("404.html"), 404

        return render_template(
            template_to_render,
            item=current_item,
            page_title=page_title,
            related_blog_items=related_blog_items_for_outil
        )

    # --- Other static page routes ---

    @app.route('/comment-ca-marche')
    def comment_ca_marche(): return render_template('comment-ca-marche.html')
    @app.route('/contact')
    def contact(): return render_template('contact.html')
    @app.route('/faq')
    def faq(): return render_template('faq.html')

    @app.route('/business')
    def business():
        return render_template('business.html')

    @app.route('/business-tool')
    def business_tool():
        # Check if user is authenticated for business access
        if 'professional_user_id' not in session:
            return redirect(url_for('business'))
        return render_template('business-tool.html', version=datetime.utcnow().strftime('%Y%m%d%H%M%S'))

    @app.route('/assureurs-et-courtiers')
    def assureurs_et_courtiers(): return render_template('assureurs-et-courtiers.html')

    @app.route('/assureurs-et-courtiers/wafa-assurance')
    def wafa_assurance(): return render_template('wafa-assurance.html')

    @app.route('/assureurs-et-courtiers/sanlam-assurance')
    def sanlam_assurance(): return render_template('sanlam-assurance.html')

    @app.route('/assureurs-et-courtiers/axa-assurance')
    def axa_assurance(): return render_template('axa-assurance.html')

    @app.route('/assureurs-et-courtiers/atlanta-sanad')
    def atlanta_sanad(): return render_template('atlanta-sanad.html')

    @app.route('/assureurs-et-courtiers/rma-assurance')
    def rma_assurance(): return render_template('rma-assurance.html')

    @app.route('/assureurs-et-courtiers/allianz-assurance')
    def allianz_assurance(): return render_template('allianz-assurance.html')

    @app.route('/assureurs-et-courtiers/mamda-et-mcma')
    def mamda_et_mcma(): return render_template('mamda-et-mcma.html')

    @app.route('/assureurs-et-courtiers/smaex')
    def smaex(): return render_template('smaex.html')

    @app.route('/assureurs-et-courtiers/allianz-trade')
    def allianz_trade(): return render_template('allianz-trade.html')

    @app.route('/assureurs-et-courtiers/matu')
    def matu(): return render_template('matu.html')

    @app.route('/assurance-cybersecurite', methods=['GET', 'POST'])
    def cybersecurite():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_cyber')
                user_email_to_use = email_form
                telephone_cyber = request.form.get('telephone_cyber')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                secteur_activite_cyber = request.form.get('secteur_activite_cyber')
                chiffre_affaires_cyber = request.form.get('chiffre_affaires_cyber')
                nombre_employes_cyber = request.form.get('nombre_employes_cyber')
                types_donnees_cyber = request.form.get('types_donnees_cyber')
                ville_cyber = request.form.get('ville_cyber')
                consent_cyber = get_consent_value('consent_cyber')

                db.execute(
                    """INSERT INTO assurance_cybersecurity (user_id, secteur_activite, chiffre_affaires, nombre_employes, types_donnees, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, secteur_activite_cyber, chiffre_affaires_cyber, nombre_employes_cyber, types_donnees_cyber, ville_cyber, user_email_to_use, telephone_cyber, consent_cyber, action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Cybersécurité", ville_cyber)

                # Send confirmation email to user
                send_user_confirmation_email(user_email_to_use, "Cybersécurité", ville_cyber)

                flash_message = 'Votre demande a été traitée.'
                if action_type == 'estimate_cyber':
                    flash_message = 'Votre demande d\'estimation pour une assurance cybersécurité a été enregistrée avec succès!'
                elif action_type == 'quote':
                    flash_message = 'Votre demande de devis pour une assurance cybersécurité a été soumise avec succès!'
                else:
                    flash_message = f'Votre demande de type "{action_type}" pour une assurance cybersécurité a été soumise avec succès!'
                flash(flash_message, 'success')
                return redirect(url_for('cybersecurite'))
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in /cybersecurite POST: {e}")
                db.rollback()
                flash(f'Une erreur de base de données est survenue: {e}', 'danger')
            except Exception as e:
                current_app.logger.error(f"General error in /cybersecurite POST: {e}")
                flash(f'Une erreur est survenue: {e}', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('cybersecurite.html', user_info=user_info)

    @app.route('/ar/assurance-cybersecurite', methods=['GET', 'POST'])
    def cybersecurite_ar():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_cyber')
                user_email_to_use = email_form
                telephone_cyber = request.form.get('telephone_cyber')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                secteur_activite_cyber = request.form.get('secteur_activite_cyber')
                chiffre_affaires_cyber = request.form.get('chiffre_affaires_cyber')
                nombre_employes_cyber = request.form.get('nombre_employes_cyber')
                types_donnees_cyber = request.form.get('types_donnees_cyber')
                ville_cyber = request.form.get('ville_cyber')
                consent_cyber = get_consent_value('consent_cyber')

                db.execute(
                    """INSERT INTO assurance_cybersecurity (user_id, secteur_activite, chiffre_affaires, nombre_employes, types_donnees, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, secteur_activite_cyber, chiffre_affaires_cyber, nombre_employes_cyber, types_donnees_cyber, ville_cyber, user_email_to_use, telephone_cyber, consent_cyber, action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Cybersécurité", ville_cyber)
                send_user_confirmation_email(user_email_to_use, "Cybersécurité", ville_cyber)
                flash('تم إرسال طلبك بنجاح!', 'success')
                return redirect(url_for('cybersecurite_ar'))
            except Exception as e:
                current_app.logger.error(f"Error in /ar/assurance-cybersecurite POST: {e}")
                flash('حدث خطأ أثناء إرسال الطلب', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('cybersecurite-ar.html', user_info=user_info)

    @app.route('/assurance-complementaire-cnss')
    def cnss():
        # REDIRECT: Redirecting to AMC individuelle
        # To disable redirect, comment out the next line and uncomment the code below
        return redirect(url_for('assurance_maladie_complementaire_individuelle'), code=301)

        # ORIGINAL CODE BELOW - Keep for future use
        # return render_template('cnss.html')

    @app.route('/ar/assurance-complementaire-cnss')
    def cnss_ar(): return render_template('cnss-ar.html')

    @app.route('/business-partner')
    def business_partner(): return render_template('business-partner.html')

    @app.route('/assurance-auto-entrepreneur', methods=['GET', 'POST'])
    def autoentrepreneur():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_ae')
                user_email_to_use = email_form
                telephone_ae = request.form.get('telephone_ae')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                domaine_activite_ae = request.form.get('domaine_activite_ae')
                chiffre_affaires_ae = request.form.get('chiffre_affaires_ae')
                nombre_clients_ae = request.form.get('nombre_clients_ae')
                anciennete_ae = request.form.get('anciennete_ae')
                ville_ae = request.form.get('ville_ae')
                consent_ae = get_consent_value('consent_ae')

                db.execute(
                    """INSERT INTO assurance_autoentrepreneur (user_id, domaine_activite, chiffre_affaires, nombre_clients, anciennete, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, domaine_activite_ae, chiffre_affaires_ae, nombre_clients_ae, anciennete_ae, ville_ae, user_email_to_use, telephone_ae, consent_ae, action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Auto-entrepreneur", ville_ae)

                # Send confirmation email to user
                send_user_confirmation_email(user_email_to_use, "Auto-entrepreneur", ville_ae)

                flash_message = 'Votre demande a été traitée.'
                if action_type == 'estimate_ae':
                    flash_message = 'Votre demande d\'estimation pour une assurance auto-entrepreneur a été enregistrée avec succès!'
                elif action_type == 'quote':
                    flash_message = 'Votre demande de devis pour une assurance auto-entrepreneur a été soumise avec succès!'
                else:
                    flash_message = f'Votre demande de type "{action_type}" pour une assurance auto-entrepreneur a été soumise avec succès!'
                flash(flash_message, 'success')
                return redirect(url_for('autoentrepreneur'))
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in /autoentrepreneur POST: {e}")
                db.rollback()
                flash(f'Une erreur de base de données est survenue: {e}', 'danger')
            except Exception as e:
                current_app.logger.error(f"General error in /autoentrepreneur POST: {e}")
                flash(f'Une erreur est survenue: {e}', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('autoentrepreneur.html', user_info=user_info)

    @app.route('/ar/assurance-auto-entrepreneur', methods=['GET', 'POST'])
    def autoentrepreneur_ar():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type')
                current_user_id = get_current_user_id()
                email_form = request.form.get('email_ae')
                user_email_to_use = email_form
                telephone_ae = request.form.get('telephone_ae')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                domaine_activite_ae = request.form.get('domaine_activite_ae')
                chiffre_affaires_ae = request.form.get('chiffre_affaires_ae')
                nombre_clients_ae = request.form.get('nombre_clients_ae')
                anciennete_ae = request.form.get('anciennete_ae')
                ville_ae = request.form.get('ville_ae')
                consent_ae = get_consent_value('consent_ae')

                db.execute(
                    """INSERT INTO assurance_autoentrepreneur (user_id, domaine_activite, chiffre_affaires, nombre_clients, anciennete, ville, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, domaine_activite_ae, chiffre_affaires_ae, nombre_clients_ae, anciennete_ae, ville_ae, user_email_to_use, telephone_ae, consent_ae, action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Auto-entrepreneur", ville_ae)
                send_user_confirmation_email(user_email_to_use, "Auto-entrepreneur", ville_ae)
                flash('تم إرسال طلبك بنجاح!', 'success')
                return redirect(url_for('autoentrepreneur_ar'))
            except Exception as e:
                current_app.logger.error(f"Error in /ar/assurance-auto-entrepreneur POST: {e}")
                flash('حدث خطأ أثناء إرسال الطلب', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('autoentrepreneur-ar.html', user_info=user_info)


    @app.route('/forum')
    def forum(): return render_template('forum.html')
    @app.route('/gestion-cookies')
    def gestion_cookies(): return render_template('gestion-cookies.html')

    @app.route('/mentions-legales')
    def mentions_legales(): return render_template('mentions-legales.html')

    @app.route('/outils')
    def outils():
        # Using the global BLOG_AND_OUTILS_DATA directly
        blog_data_for_display = BLOG_AND_OUTILS_DATA
        outils_items = [item for item in blog_data_for_display if item["category"] == "outils"]
        page_title = "Outils d'Assurance Pratiques | Simulateurs et Calculateurs | mesassurances.ma"
        return render_template('outils.html', outils_items=outils_items, page_title=page_title)

    @app.route('/politique-confidentialite')
    def politique_confidentialite(): return render_template('politique-confidentialite.html')
    @app.route('/qui-sommes-nous')
    def qui_sommes_nous(): return render_template('qui-sommes-nous.html')
    @app.route('/remuneration')
    def remuneration(): return render_template('remuneration.html')

    # Arabic legacy routes → redirect to French versions
    @app.route('/ar/mentions-legales')
    def mentions_legales_ar_redirect():
        return redirect(url_for('mentions_legales'), code=301)

    @app.route('/ar/politique-confidentialite')
    def politique_confidentialite_ar_redirect():
        return redirect(url_for('politique_confidentialite'), code=301)

    @app.route('/ar/contact')
    def contact_ar_redirect():
        return redirect(url_for('contact'), code=301)

    @app.route('/ar/blog')
    def blog_ar_redirect():
        return redirect(url_for('blog'), code=301)

    @app.route('/ar/avis-plateforme')
    def avis_plateforme_ar_redirect():
        return redirect(url_for('avis_plateforme'), code=301)

    @app.route('/ar/avis-assureurs')
    def avis_assureurs_ar_redirect():
        return redirect(url_for('avis_assureurs'), code=301)

    @app.route('/ar/business')
    def business_ar_redirect():
        return redirect(url_for('business'), code=301)

    # The original routes for assurance_ecole and assurance_stage are now handled by the POST methods above
    # and will simply render the template on GET.
    # @app.route('/assurance-ecole')
    # def assurance_ecole(): return render_template('assurance-ecole.html')
    # @app.route('/assurance-stage')
    # def assurance_stage(): return render_template('assurance-stage.html')
    @app.route('/outils/assurances-audit')
    def assurances_audit(): return render_template('assurances-audit.html')


    @app.route('/ask-ai')
    def ask_ai_page():
        return render_template('ask-ai.html')


    @app.route('/ar/assurance-maladie-complementaire-groupe', methods=['GET', 'POST'])
    def assurance_maladie_complementaire_groupe_ar():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type', 'quote')
                current_user_id = get_current_user_id()
                email_form = request.form.get('contact_email')
                user_email_to_use = email_form
                telephone_mg = request.form.get('contact_phone')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                company_name = request.form.get('company_name')
                industry = request.form.get('industry')
                ville = request.form.get('city')
                headcount = request.form.get('headcount')
                spouses_count = request.form.get('spouses_count')
                children_count = request.form.get('children_count')
                annual_payroll = request.form.get('annual_payroll')
                consent_mg = get_consent_value('consent')

                db.execute(
                    """INSERT INTO assurance_maladie_complementaire_groupe (user_id, company_name, industry, ville, headcount, spouses_count, children_count, annual_payroll, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, company_name, industry, ville, headcount, spouses_count, children_count, annual_payroll, user_email_to_use, telephone_mg, consent_mg, action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Maladie Complémentaire Groupe", ville)

                try:
                    send_user_confirmation_email(user_email_to_use, "Maladie Complémentaire Groupe", ville)
                except Exception as email_error:
                    current_app.logger.error(f"Error sending confirmation email for Maladie Complémentaire Groupe (AR): {email_error}")

                flash_message_ar = 'سيتم معالجة طلبك من قبل أحد شركاء MesAssurances.ma الذين سيتواصلون معكم خلال 24 ساعة.'
                # Check if this is an AJAX request (from fetch)
                if request.headers.get('Content-Type') == 'application/x-www-form-urlencoded' or request.headers.get('Accept') == 'application/json':
                    return jsonify({'success': True, 'message': flash_message_ar})
                flash(flash_message_ar, 'success')
                return redirect(url_for('assurance_maladie_complementaire_groupe_ar'))
            except Exception as e:
                current_app.logger.error(f"Error in /ar/assurance-maladie-complementaire-groupe POST: {e}")
                flash('حدث خطأ أثناء إرسال الطلب', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('assurance-maladie-groupe-ar.html', user_info=user_info)

    @app.route('/assurance-maladie-complementaire-groupe', methods=['GET', 'POST'])
    def assurance_maladie_complementaire_groupe():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type', 'quote')
                current_user_id = get_current_user_id()
                email_form = request.form.get('contact_email')
                user_email_to_use = email_form
                telephone_mg = request.form.get('contact_phone')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                company_name = request.form.get('company_name')
                industry = request.form.get('industry')
                ville = request.form.get('city')
                headcount = request.form.get('headcount')
                spouses_count = request.form.get('spouses_count')
                children_count = request.form.get('children_count')
                annual_payroll = request.form.get('annual_payroll')
                consent_mg = get_consent_value('consent')

                db.execute(
                    """INSERT INTO assurance_maladie_complementaire_groupe (user_id, company_name, industry, ville, headcount, spouses_count, children_count, annual_payroll, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, company_name, industry, ville, headcount, spouses_count, children_count, annual_payroll, user_email_to_use, telephone_mg, consent_mg, action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("Maladie Complémentaire Groupe", ville)

                try:
                    send_user_confirmation_email(user_email_to_use, "Maladie Complémentaire Groupe", ville)
                except Exception as email_error:
                    current_app.logger.error(f"Error sending confirmation email for Maladie Complémentaire Groupe: {email_error}")

                flash_message = 'Votre demande sera traitée par l\'un de nos partenaires MesAssurances.ma qui vous recontactera dans les 24 heures.'
                # Check if this is an AJAX request (from fetch)
                if request.headers.get('Content-Type') == 'application/x-www-form-urlencoded' or request.headers.get('Accept') == 'application/json':
                    return jsonify({'success': True, 'message': flash_message})
                flash(flash_message, 'success')
                return redirect(url_for('assurance_maladie_complementaire_groupe'))
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in /assurance-maladie-complementaire-groupe POST: {e}")
                db.rollback()
                flash(f'Une erreur de base de données est survenue: {e}', 'danger')
            except Exception as e:
                current_app.logger.error(f"General error in /assurance-maladie-complementaire-groupe POST: {e}")
                flash(f'Une erreur est survenue: {e}', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('assurance-maladie-groupe.html', user_info=user_info)
    @app.route('/ar/assurance-rc-pro', methods=['GET', 'POST'])
    def assurance_rc_pro_ar():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type', 'quote')
                current_user_id = get_current_user_id()
                email_form = request.form.get('contact_email')
                user_email_to_use = email_form
                telephone_rc = request.form.get('contact_phone')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                company_name = request.form.get('company_name')
                activity = request.form.get('activity')
                ville = request.form.get('city')
                turnover = request.form.get('turnover')
                employees = request.form.get('employees')
                coverage = request.form.get('coverage')
                franchise = request.form.get('franchise')
                projects = request.form.get('projects')
                consent_rc = get_consent_value('consent')

                db.execute(
                    """INSERT INTO assurance_rc_pro (user_id, company_name, activity, ville, turnover, employees, coverage, franchise, projects, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, company_name, activity, ville, turnover, employees, coverage, franchise, projects, user_email_to_use, telephone_rc, consent_rc, action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("RC Pro", ville)

                try:
                    send_user_confirmation_email(user_email_to_use, "RC Pro", ville)
                except Exception as email_error:
                    current_app.logger.error(f"Error sending confirmation email for RC Pro (AR): {email_error}")

                flash_message_ar = 'سيتم معالجة طلبك من قبل أحد شركاء MesAssurances.ma الذين سيتواصلون معكم خلال 24 ساعة.'
                # Check if this is an AJAX request (from fetch)
                if request.headers.get('Content-Type') == 'application/x-www-form-urlencoded' or request.headers.get('Accept') == 'application/json':
                    return jsonify({'success': True, 'message': flash_message_ar})
                flash(flash_message_ar, 'success')
                return redirect(url_for('assurance_rc_pro_ar'))
            except Exception as e:
                current_app.logger.error(f"Error in /ar/assurance-rc-pro POST: {e}")
                flash('حدث خطأ أثناء إرسال الطلب', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('assurance-rc-pro-ar.html', user_info=user_info)

    @app.route('/assurance-rc-pro', methods=['GET', 'POST'])
    def assurance_rc_pro():
        if request.method == 'POST':
            try:
                db = database.get_db()
                action_type = request.form.get('action_type', 'quote')
                current_user_id = get_current_user_id()
                email_form = request.form.get('contact_email')
                user_email_to_use = email_form
                telephone_rc = request.form.get('contact_phone')

                if current_user_id and session.get('user_email'):
                    if not email_form or email_form == session.get('user_email'):
                        user_email_to_use = session.get('user_email')

                company_name = request.form.get('company_name')
                activity = request.form.get('activity')
                ville = request.form.get('city')
                turnover = request.form.get('turnover')
                employees = request.form.get('employees')
                coverage = request.form.get('coverage')
                franchise = request.form.get('franchise')
                projects = request.form.get('projects')
                consent_rc = get_consent_value('consent')

                db.execute(
                    """INSERT INTO assurance_rc_pro (user_id, company_name, activity, ville, turnover, employees, coverage, franchise, projects, email, telephone, consentement, action_type, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (current_user_id, company_name, activity, ville, turnover, employees, coverage, franchise, projects, user_email_to_use, telephone_rc, consent_rc, action_type)
                )
                db.commit()

                if action_type == 'quote':
                    send_notifications_for_new_lead("RC Pro", ville)

                try:
                    send_user_confirmation_email(user_email_to_use, "RC Pro", ville)
                except Exception as email_error:
                    current_app.logger.error(f"Error sending confirmation email for RC Pro: {email_error}")

                flash_message = 'Votre demande sera traitée par l\'un de nos partenaires MesAssurances.ma qui vous recontactera dans les 24 heures.'
                # Check if this is an AJAX request (from fetch)
                if request.headers.get('Content-Type') == 'application/x-www-form-urlencoded' or request.headers.get('Accept') == 'application/json':
                    return jsonify({'success': True, 'message': flash_message})
                flash(flash_message, 'success')
                return redirect(url_for('assurance_rc_pro'))
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error in /assurance-rc-pro POST: {e}")
                db.rollback()
                flash(f'Une erreur de base de données est survenue: {e}', 'danger')
            except Exception as e:
                current_app.logger.error(f"General error in /assurance-rc-pro POST: {e}")
                flash(f'Une erreur est survenue: {e}', 'danger')
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('assurance-rc-pro.html', user_info=user_info)

    @app.route('/assurance-maladie-complementaire-individuelle', methods=['GET'])
    def assurance_maladie_complementaire_individuelle():
        user_info = {"email": session.get('user_email')} if 'user_id' in session else None
        return render_template('assurance-maladie-complementaire-individuelle.html', user_info=user_info)

    @app.route('/assurance-maladie-complementaire-individuelle/submit', methods=['POST'])
    def assurance_maladie_complementaire_individuelle_submit():
        try:
            db = database.get_db()
            data = request.get_json(force=True) if request.is_json else request.form
            current_user_id = get_current_user_id()

            firstname = data.get('firstname')
            lastname = data.get('lastname')
            profession = data.get('profession')
            birthdate = data.get('birthdate')
            marital_status = data.get('marital_status')
            spouse_birthdate = data.get('spouse_birthdate')
            children_count = data.get('children_count') or 0
            city = data.get('city')
            phone = data.get('phone')
            email = data.get('email')
            amo_cnss = data.get('amo_cnss')
            consent = get_consent_value('consent')

            # Collect child birthdates (expecting keys child_1_birthdate, child_2_birthdate, ...)
            child_birthdates = []
            try:
                cnt = int(children_count)
            except Exception:
                cnt = 0
            for i in range(1, cnt + 1):
                cbd = data.get(f'child_{i}_birthdate')
                if cbd:
                    child_birthdates.append(cbd)

            db.execute(
                """INSERT INTO assurance_amc_individuelle
                   (user_id, firstname, lastname, profession, birthdate, marital_status, spouse_birthdate,
                    children_count, child_birthdates, city, phone, email, amo_cnss, consentement, action_type, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'quote', 'active', CURRENT_TIMESTAMP)""",
                (current_user_id, firstname, lastname, profession, birthdate, marital_status, spouse_birthdate,
                 cnt, json.dumps(child_birthdates), city, phone, email, amo_cnss, consent)
            )
            db.commit()

            try:
                send_notifications_for_new_lead("Assurance AMC Individuelle", city)
            except Exception as e:
                current_app.logger.warning(f"Notification failed for AMC Individuelle lead: {e}")

            try:
                send_user_confirmation_email(email, "AMC Individuelle", city)
            except Exception as e:
                current_app.logger.warning(f"User confirmation email failed for AMC Individuelle lead: {e}")

            if request.is_json:
                return jsonify({"success": True})
            else:
                flash("Votre demande a été enregistrée.", "success")
                return redirect(url_for('assurance_maladie_complementaire_individuelle'))
        except Exception as e:
            current_app.logger.error(f"Error in AMC Individuelle submit: {e}", exc_info=True)
            if request.is_json:
                return jsonify({"error": "submit_failed"}), 400
            flash("Une erreur est survenue lors de l'enregistrement de votre demande.", "danger")
            return redirect(url_for('assurance_maladie_complementaire_individuelle'))

    @app.route('/assurance-maladie-complementaire-individuelle/email-pdf', methods=['POST'])
    def assurance_maladie_complementaire_individuelle_email_pdf():
        """Receive AMC individuelle PDF (base64) and email it to the user with custom next steps."""
        try:
            data = request.get_json(force=True) or {}
            blocked_cities = {"rabat", "salé", "sale", "temara", "skhirat"}
            user_email = data.get('email')
            pdf_b64 = data.get('pdf_base64')
            filename = data.get('filename') or 'Devis-AMC-Individuelle.pdf'
            firstname = data.get('firstname') or ''
            lastname = data.get('lastname') or ''
            city = data.get('city') or ''
            phone = data.get('phone') or ''
            profession = data.get('profession') or ''

            city_normalized = city.strip().lower()
            if city_normalized in blocked_cities:
                current_app.logger.info(f"Skipping AMC PDF email for blocked city: {city_normalized}")
                return jsonify({"success": False, "message": "Zone non couverte pour l'envoi du devis."}), 200

            if not user_email or not pdf_b64:
                return jsonify({"error": "missing_parameters"}), 400

            # Decode PDF
            try:
                # Accept data URI or raw base64
                if ',' in pdf_b64:
                    pdf_b64 = pdf_b64.split(',', 1)[1]
                pdf_bytes = base64.b64decode(pdf_b64)
            except Exception:
                return jsonify({"error": "invalid_pdf"}), 400

            subject = "Votre devis AMC individuelle"
            next_steps = "Pour finaliser votre offre, contactez AGECAP Assurances. Il vous sera demandé de remplir un questionnaire médical."

            user_display_name = f"{firstname} {lastname}".strip() or "Client"
            whatsapp_number = "212666590994"
            whatsapp_url = f"https://wa.me/{whatsapp_number}"

            html_body = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Votre devis AMC individuelle</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f5f5f5;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f5f5f5;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); padding: 30px; text-align: center; border-radius: 8px 8px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700;">Merci d'avoir utilisé MesAssurances.ma</h1>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            <p style="margin: 0 0 20px 0; color: #1e293b; font-size: 16px; line-height: 1.6;">
                                Bonjour {user_display_name},
                            </p>

                            <p style="margin: 0 0 20px 0; color: #1e293b; font-size: 16px; line-height: 1.6;">
                                Nous vous remercions d'avoir utilisé <strong>MesAssurances.ma</strong> pour votre demande d'assurance AMC individuelle.
                            </p>

                            <p style="margin: 0 0 20px 0; color: #1e293b; font-size: 16px; line-height: 1.6;">
                                Votre devis, de notre partenaire AGECAP, est disponible en pièce jointe de cet email. Vous pouvez le télécharger et le consulter à tout moment.
                            </p>

                            <!-- Info Box -->
                            <div style="background-color: #eff6ff; border-left: 4px solid #2563eb; padding: 20px; margin: 30px 0; border-radius: 4px;">
                                <p style="margin: 0 0 10px 0; color: #1e40af; font-size: 16px; font-weight: 600;">
                                    📋 Prochaines étapes
                                </p>
                                <p style="margin: 0; color: #1e293b; font-size: 15px; line-height: 1.6;">
                                    Pour finaliser votre offre, remplissez le questionnaire en pièce jointe et contactez <strong>AGECAP Assurances</strong>.
                                </p>
                            </div>

                            <!-- WhatsApp Button -->
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="margin: 30px 0;">
                                <tr>
                                    <td align="center">
                                        <a href="{whatsapp_url}" style="display: inline-block; background-color: #25D366; color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 6px; font-weight: 600; font-size: 16px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                            <span style="display: inline-block; margin-right: 8px;">💬</span>
                                            Contacter AGECAP sur WhatsApp
                                        </a>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 20px 0 0 0; color: #64748b; font-size: 14px; line-height: 1.6; text-align: center;">
                                Ou contactez-les directement au <strong>{whatsapp_number}</strong>
                            </p>

                            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">

                            <p style="margin: 0 0 10px 0; color: #64748b; font-size: 14px; line-height: 1.6;">
                                <strong>Rappel :</strong> MesAssurances.ma agit uniquement en tant que plateforme de mise en relation technique.
                                AGECAP Assurances est responsable de la finalisation de votre contrat d'assurance.
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8fafc; padding: 20px 30px; text-align: center; border-radius: 0 0 8px 8px; border-top: 1px solid #e5e7eb;">
                            <p style="margin: 0 0 10px 0; color: #64748b; font-size: 12px;">
                                <strong>MesAssurances.ma</strong><br>
                                Plateforme d'éducation et mise en relation technique
                            </p>
                            <p style="margin: 0; color: #94a3b8; font-size: 11px;">
                                Cet email a été envoyé à {user_email}
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
            """

            text_body = f"""
Merci d'avoir utilisé MesAssurances.ma

Bonjour {user_display_name},

Nous vous remercions d'avoir utilisé MesAssurances.ma pour votre demande d'assurance AMC individuelle.
Votre devis, de notre partenaire AGECAP, est disponible en pièce jointe.

Prochaines étapes:
- Pour finaliser votre offre, remplissez le questionnaire en pièce jointe et contactez AGECAP Assurances.

Contacter AGECAP sur WhatsApp : {whatsapp_url}
Ou directement au {whatsapp_number}

Rappel : MesAssurances.ma agit uniquement en tant que plateforme de mise en relation technique.
AGECAP Assurances est responsable de la finalisation de votre contrat d'assurance.
"""

            msg = Message(
                subject,
                sender="notification@mesassurances.ma",
                recipients=[user_email],
                cc=["elmahdi.boutiyeb@agecap.ma"]
            )
            msg.body = text_body
            msg.html = html_body
            msg.attach(filename, 'application/pdf', pdf_bytes)

            mail.send(msg)
            return jsonify({"success": True})
        except Exception as e:
            current_app.logger.error(f"Error emailing AMC Individuelle PDF: {e}", exc_info=True)
            return jsonify({"error": "email_failed"}), 500

    @app.route('/api/amc/calculate', methods=['POST'])
    def api_amc_calculate():
        """Server-side AMC individuelle premium calculation to avoid exposing formulas in the frontend."""
        try:
            payload = request.get_json(force=True) or {}
            birthdate = payload.get('birthdate')
            marital_status = (payload.get('marital_status') or '').lower()
            spouse_birthdate = payload.get('spouse_birthdate')
            children_birthdates = payload.get('child_birthdates') or []

            def parse_age(date_str):
                if not date_str:
                    return None
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d").date()
                except Exception:
                    return None
                today = date.today()
                age = today.year - dt.year - ((today.month, today.day) < (dt.month, dt.day))
                return age

            def find_row_index(age, role=None):
                if age is None:
                    return None
                for idx, bracket in enumerate(AMC_AGE_BRACKETS):
                    # Skip "10-26" bracket (index 1) for adults (assuré/conjoint)
                    # Only children (enfants) can use the "10-26" bracket
                    if idx == 1 and role != 'enfants':
                        continue
                    if bracket["min"] <= age <= bracket["max"]:
                        return idx
                return None

            # Prepare row counters per age bracket
            row_counts = {idx: {"assure": 0, "conjoint": 0, "enfants": 0} for idx in range(len(AMC_AGE_BRACKETS))}

            def add_person(role, date_str):
                age = parse_age(date_str)
                row_idx = find_row_index(age, role)
                if row_idx is None:
                    return
                if role == 'enfants':
                    row_counts[row_idx]["enfants"] += 1
                elif role == 'conjoint':
                    row_counts[row_idx]["conjoint"] = 1
                else:
                    row_counts[row_idx]["assure"] = 1

            # Assuré
            add_person('assure', birthdate)
            # Conjoint
            if marital_status == 'marie' and spouse_birthdate:
                add_person('conjoint', spouse_birthdate)
            # Enfants
            for child_bd in children_birthdates:
                add_person('enfants', child_bd)

            # Compute annual totals
            annual_totals = {k: 0.0 for k in AMC_PLAN_KEYS}
            for idx, counts in row_counts.items():
                data_row = AMC_INSURANCE_DATA[idx]
                multiplier = counts["assure"] + counts["conjoint"] + counts["enfants"]
                if multiplier <= 0:
                    continue
                deces_component = counts["assure"] * data_row.get("deces", 0.0)
                for key in AMC_PLAN_KEYS:
                    base_price = data_row.get(key, 0.0)
                    annual_totals[key] += (base_price * multiplier) + deces_component

            def apply_factor(totals, factor_map):
                return {k: totals[k] * factor_map.get(k, 0.0) for k in AMC_PLAN_KEYS}

            sem_totals = apply_factor(annual_totals, AMC_SEM_FACTORS)
            tri_totals = apply_factor(annual_totals, AMC_TRI_FACTORS)
            mens_totals = apply_factor(annual_totals, AMC_MENS_FACTORS)

            response = {
                "totals": {
                    "annuel": annual_totals,
                    "semestrielle": sem_totals,
                    "trimestrielle": tri_totals,
                    "mensuelle": mens_totals,
                },
                "child_dates": children_birthdates,
            }
            return jsonify(response)
        except Exception as e:
            current_app.logger.error(f"Error in /api/amc/calculate: {e}")
            return jsonify({"error": "calculation_failed"}), 400

    @app.errorhandler(404)
    def page_not_found(e):
        # Using the global BLOG_AND_OUTILS_DATA directly
        blog_data_for_display = BLOG_AND_OUTILS_DATA
        all_blog_items_for_404 = [item for item in blog_data_for_display if item["category"] == "blog"]
        num_to_sample = min(4, len(all_blog_items_for_404))
        suggested_items = []
        if len(all_blog_items_for_404) > 0:
            suggested_items = random.sample(all_blog_items_for_404, num_to_sample)

        return render_template('404.html', suggested_items=suggested_items), 404

    @app.errorhandler(500)
    def internal_error(error):
        """Global 500 error handler that logs all exceptions with full traceback"""
        import traceback
        error_traceback = traceback.format_exc()
        error_message = str(error)

        # Log to Flask logger (which goes to file and console/stderr)
        current_app.logger.error(
            f"500 Internal Server Error: {error_message}\n"
            f"Traceback:\n{error_traceback}",
            exc_info=True
        )

        # Also log to security logger
        from security_config import log_security_event
        log_security_event("INTERNAL_ERROR", f"500 error: {error_message}")

        # Return user-friendly error page
        return render_template('404.html', suggested_items=[]), 500

    @app.errorhandler(Exception)
    def handle_exception(e):
        """Global exception handler for unhandled exceptions (excluding HTTP exceptions)"""
        from werkzeug.exceptions import HTTPException

        # Let Flask handle HTTP exceptions (404, 403, etc.) normally
        if isinstance(e, HTTPException):
            return e

        import traceback
        error_traceback = traceback.format_exc()
        error_message = str(e)

        # Log to Flask logger with full traceback
        current_app.logger.error(
            f"Unhandled Exception: {type(e).__name__}: {error_message}\n"
            f"Traceback:\n{error_traceback}",
            exc_info=True
        )

        # Also log to security logger
        from security_config import log_security_event
        log_security_event("UNHANDLED_EXCEPTION", f"{type(e).__name__}: {error_message}")

        # Return 500 error
        return render_template('404.html', suggested_items=[]), 500


    @app.route('/api/ask-ai-proxy', methods=['POST'])
    def ask_ai_proxy():
        # Extract client information
        client_ip, user_agent, referer = get_client_info(request)

        # STEP 1: Detect bots FIRST (before any processing)
        is_bot, bot_reason = detect_bot(user_agent, client_ip, referer)
        if is_bot:
            current_app.logger.warning(
                f"Bot detected and blocked - IP: {client_ip}, Reason: {bot_reason}, "
                f"UA: {user_agent[:50] if user_agent else 'None'}"
            )
            return jsonify({
                "error": "Accès refusé. Les bots et scripts automatisés ne sont pas autorisés."
            }), 403

        # STEP 2: Check global rate limit (12 req/min for free plan - keeps us under Gemini's 15 RPM)
        if not global_rate_limiter.is_allowed():
            remaining = global_rate_limiter.get_remaining_requests()
            current_app.logger.warning(
                f"Global rate limit exceeded. Remaining requests: {remaining}"
            )
            return jsonify({
                "error": "Le service est temporairement surchargé. Veuillez patienter quelques instants avant de réessayer."
            }), 429

        # STEP 3: Check per-IP rate limit (5 req/min - permissive for legitimate users)
        if not ip_rate_limiter.is_allowed(client_ip):
            remaining = ip_rate_limiter.get_remaining_requests(client_ip)
            current_app.logger.warning(
                f"Rate limit exceeded for IP {client_ip}. Remaining requests: {remaining}"
            )
            return jsonify({
                "error": "Trop de requêtes depuis votre adresse. Veuillez patienter quelques instants avant de réessayer."
            }), 429

        try:
            data = request.get_json()
            if not data or 'chat_history' not in data:
                current_app.logger.error("Missing chat_history in request to /api/ask-ai-proxy")
                return jsonify({"error": "Historique de chat manquant."}), 400

            chat_history = data['chat_history']
            api_key = current_app.config.get('GEMINI_API_KEY')
            if not api_key:
                current_app.logger.error("GEMINI_API_KEY is missing from app config.")
                return jsonify({"error": "La clé API du service IA n'est pas configurée sur le serveur."}), 500

            # Use gemini-2.5-flash-lite (free tier: 1,500 RPD / 30 RPM)
            gemini_api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={api_key}"
            system_instruction = {
                "parts": [{
                    "text": "Réponds en trois phrases maximum. Réponds uniquement et strictement si en relation l'assurance au maroc. MesAssurances ou Equivalent lié au site www.mesassurances.ma est une plateforme de mise en relation avec des courtiers agréés uniquement, les utilisateurs souscrive directement leur assurances avec les courtiers. MesAssurances n'est ni assureur ni courtier. Pour être assureur ou courtier il faut des agrements du régulateur ACAPS."
                }]
            }
            payload = {
                "contents": chat_history,
                "systemInstruction": system_instruction
            }

            # Make single API call - no retries (user can try again if it fails)
            try:
                response = requests.post(
                    gemini_api_url,
                    json=payload,
                    timeout=30,
                    headers={'Content-Type': 'application/json'}
                )

                # Handle 429 Too Many Requests
                if response.status_code == 429:
                    current_app.logger.warning(
                        f"Rate limit hit (429) from Gemini API for IP {client_ip}"
                    )
                    return jsonify({
                        "error": "Le service IA est temporairement surchargé. Veuillez réessayer dans quelques instants."
                    }), 429

                # Check for other HTTP errors
                if response.status_code != 200:
                    current_app.logger.error(
                        f"Gemini API returned status {response.status_code} for IP {client_ip}: {response.text[:200]}"
                    )
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('error', {}).get('message', f"Erreur API (status {response.status_code})")
                    except:
                        error_msg = f"Erreur API (status {response.status_code}): {response.text[:200]}"
                    return jsonify({"error": f"Erreur du service IA: {error_msg}"}), response.status_code

                # Success - parse response
                response.raise_for_status()
                gemini_response_data = response.json()

                ai_text_response = "Désolé, je n'ai pas pu obtenir de réponse."

                if (gemini_response_data.get('candidates') and
                    len(gemini_response_data['candidates']) > 0 and
                    gemini_response_data['candidates'][0].get('content') and
                    gemini_response_data['candidates'][0]['content'].get('parts') and
                    len(gemini_response_data['candidates'][0]['content']['parts']) > 0 and
                    gemini_response_data['candidates'][0]['content']['parts'][0].get('text')):
                    ai_text_response = gemini_response_data['candidates'][0]['content']['parts'][0]['text']
                elif gemini_response_data.get('promptFeedback') and gemini_response_data['promptFeedback'].get('blockReason'):
                    block_reason = gemini_response_data['promptFeedback']['blockReason']
                    ai_text_response = f"Votre demande a été bloquée par le service IA ({block_reason}). Veuillez reformuler."
                    current_app.logger.warning(f"Gemini API prompt blocked: {block_reason}")
                else:
                    current_app.logger.warning(f"Unexpected Gemini API response structure: {gemini_response_data}")

                return jsonify({"response": ai_text_response})

            except requests.exceptions.Timeout:
                current_app.logger.error(f"Timeout calling Gemini API for IP {client_ip}")
                return jsonify({
                    "error": "Le service IA a mis trop de temps à répondre. Veuillez réessayer."
                }), 504

            except requests.exceptions.RequestException as e:
                # Handle 429 in exception
                if hasattr(e, 'response') and e.response is not None and e.response.status_code == 429:
                    current_app.logger.warning(f"Rate limit (429) from Gemini API for IP {client_ip}")
                    return jsonify({
                        "error": "Le service IA est temporairement surchargé. Veuillez réessayer dans quelques instants."
                    }), 429

                # Other RequestException - log and return error
                current_app.logger.error(
                    f"RequestException in /api/ask-ai-proxy for IP {client_ip}: {e}",
                    exc_info=True
                )
                error_detail = "Erreur de communication avec le service IA."
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_json = e.response.json()
                        if error_json.get('error') and error_json['error'].get('message'):
                            error_detail = f"Erreur du service IA: {error_json['error']['message']}"
                    except (ValueError, AttributeError):
                        error_detail = f"Erreur du service IA (status {e.response.status_code}): {e.response.text[:200] if hasattr(e.response, 'text') else 'Unknown error'}"
                return jsonify({"error": error_detail}), 502

            except Exception as e:
                current_app.logger.error(
                    f"Unexpected error in /api/ask-ai-proxy for IP {client_ip}: {e}",
                    exc_info=True
                )
                return jsonify({
                    "error": "Une erreur interne est survenue sur le serveur."
                }), 500

        except Exception as e:
            current_app.logger.error(
                f"Unexpected error in /api/ask-ai-proxy for IP {client_ip}: {e}",
                exc_info=True
            )
            return jsonify({
                "error": "Une erreur interne est survenue sur le serveur."
            }), 500


    @app.route('/test_db')
    def test_db_connection():
        try:
            db = database.get_db()
            cursor = db.execute("SELECT COUNT(*) FROM professional_users")
            count = cursor.fetchone()[0]
            return f"Database connection successful. Found {count} rows in professional_users table."
        except Exception as e:
            current_app.logger.error(f"Error in /test_db: {e}")
            return f"Error connecting to or querying database: {e}", 500

    return app

if __name__ == '__main__':
    # This block is for local development only and will NOT run on a WSGI server.
    # It attempts to load environment variables from a .env file for convenience during local development.
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("Loaded .env file for local development.")
    except ImportError:
        print("python-dotenv not installed. Environment variables must be set manually for local development.")
    except Exception as e:
        print(f"Error loading .env file: {e}")

    app = create_app()
    try:
        port = int(os.environ.get("PORT", 5000))
    except ValueError:
        port = 5000
    print(f"Running Flask app locally on http://127.0.0.1:{port}")
    app.run(debug=True, host='127.0.0.1', port=port)
