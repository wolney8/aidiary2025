# server/routes/analyse.py
# AI analysis endpoint
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from services.openai_svc import OpenAIService

analyse_bp = Blueprint('analyse', __name__)

@analyse_bp.route('/analyse', methods=['POST'])
@jwt_required()
def analyse_text():
    """Analyse text using OpenAI and return structured insights."""
    data = request.get_json()
    mode = data.get('mode', 'daily')  # 'daily' or 'dream'
    text = data.get('text', '')
    
    if not text:
        return jsonify({'error': 'Text is required'}), 400
    
    if mode not in ['daily', 'dream']:
        return jsonify({'error': 'Invalid mode. Use "daily" or "dream"'}), 400
    
    try:
        ai_service = OpenAIService()
        
        if mode == 'daily':
            result = ai_service.analyse_daily_entry(text)
            return jsonify({
                'ai_response': result['ai_response'],
                'tags': result['tags'],
                'daily_people_names': result['people_names'],
                'daily_places': result['places']
            }), 200
        else:  # dream mode
            result = ai_service.analyse_dream_entry(text)
            return jsonify({
                'summary': result['summary'],
                'interpretation': result['interpretation'],
                'image_prompt': result['image_prompt'],
                'tags': result['tags'],
                'dream_people_names': result['people_names'],
                'dream_places': result['places']
            }), 200
            
    except Exception as e:
        print(f"Analysis error: {str(e)}")
        return jsonify({'error': 'Analysis failed'}), 500