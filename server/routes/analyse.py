# server/routes/analyse.py
# AI analysis endpoint
from flask import Blueprint, current_app, request, jsonify
from flask_jwt_extended import jwt_required
from services.openai_svc import OpenAIService


def _normalise_people_names(raw: str) -> str:
    if not raw:
        return ""

    blocked = {
        "hopefully",
        "maybe",
        "someone",
        "somebody",
        "everyone",
        "everybody",
        "nobody",
        "anyone",
        "anybody",
        "person",
        "people",
        "friend",
        "friends",
        "unknown",
        "none",
        "na",
        "n/a",
    }

    cleaned = []
    for token in str(raw).split(","):
        candidate = token.strip()
        if not candidate:
            continue

        lower = candidate.lower()
        if lower in blocked:
            continue

        if not all(ch.isalpha() or ch in " -'" for ch in candidate):
            continue

        if len(candidate) < 2:
            continue

        cleaned.append(candidate)

    # Preserve ordering, drop duplicates.
    seen = set()
    ordered = []
    for item in cleaned:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)

    return ",".join(ordered)

analyse_bp = Blueprint('analyse', __name__)
ANALYSE_TEXT_MAX_LENGTH = 10000

@analyse_bp.route('/analyse', methods=['POST'])
@jwt_required()
def analyse_text():
    """Analyse text using OpenAI and return structured insights."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Request body must be a JSON object'}), 400

    mode = data.get('mode', 'daily')  # 'daily' or 'dream'
    text = data.get('text', '')

    if mode not in ['daily', 'dream']:
        return jsonify({'error': 'Invalid mode. Use "daily" or "dream"'}), 400

    if not isinstance(text, str):
        return jsonify({'error': 'Text must be a string'}), 400

    text = text.strip()
    if not text:
        return jsonify({'error': 'Text is required'}), 400

    if len(text) > ANALYSE_TEXT_MAX_LENGTH:
        return jsonify({'error': f'Text exceeds maximum length of {ANALYSE_TEXT_MAX_LENGTH} characters'}), 400
    
    try:
        ai_service = OpenAIService()
        
        if mode == 'daily':
            result = ai_service.analyse_daily_entry(text)
            return jsonify({
                'ai_response': result['ai_response'],
                'tags': result['tags'],
                'daily_people_names': _normalise_people_names(result.get('people_names', '')),
                'daily_places': result['places']
            }), 200
        else:  # dream mode
            result = ai_service.analyse_dream_entry(text)
            return jsonify({
                'summary': result['summary'],
                'interpretation': result['interpretation'],
                'image_prompt': result['image_prompt'],
                'tags': result['tags'],
                'dream_people_names': _normalise_people_names(result.get('people_names', '')),
                'dream_places': result['places']
            }), 200
            
    except Exception:
        current_app.logger.exception('Analysis failed')
        return jsonify({'error': 'Analysis failed'}), 500