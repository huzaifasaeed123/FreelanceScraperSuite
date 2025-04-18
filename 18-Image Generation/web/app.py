from flask import Flask, send_from_directory
from flask_cors import CORS
import os
from api.routes import api_bp

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Register blueprints
app.register_blueprint(api_bp, url_prefix='/api')

# Serve static files (generated images)
@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory('static/generated_profiles', filename)

if __name__ == '__main__':
    # Ensure the images directory exists
    os.makedirs('static/generated_profiles', exist_ok=True)
    app.run(debug=True, port=5000)