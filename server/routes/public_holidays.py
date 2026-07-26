from __future__ import annotations

from datetime import datetime

import httpx
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from services.public_holidays import (
    get_public_holidays,
    list_available_countries,
    list_fallback_countries,
)
from services.sql_compat import adapt_placeholders

public_holidays_bp = Blueprint('public_holidays', __name__)


def get_db():
    return current_app.config['DATABASE_ADAPTER'].connect(timeout=30)


def _database_provider() -> str:
    return current_app.config.get('DATABASE_PROVIDER', 'sqlite')


def _sql(statement: str) -> str:
    return adapt_placeholders(statement, _database_provider())


@public_holidays_bp.route('/public-holidays/countries', methods=['GET'])
@jwt_required()
def get_public_holiday_countries():
    try:
        countries = list_available_countries()
    except httpx.HTTPError as exc:
        current_app.logger.warning(
            'Public holiday countries fetch failed, using fallback list: %s',
            exc,
        )
        countries = list_fallback_countries()

    return jsonify(countries), 200


@public_holidays_bp.route('/public-holidays', methods=['GET'])
@jwt_required()
def get_public_holiday_feed():
    user_id = int(get_jwt_identity())
    year_param = request.args.get('year', '').strip()

    try:
        year = int(year_param)
    except ValueError:
        year = datetime.now().year

    if year < 1900 or year > 2100:
        return jsonify({'error': 'Year is out of range'}), 400

    country_code = ''
    try:
        with get_db() as conn:
            profile_row = conn.execute(
                _sql(
                    """
                    SELECT holiday_country_code, show_public_holidays
                    FROM users
                    WHERE id = ?
                    """
                ),
                (user_id,),
            ).fetchone()

            if not profile_row:
                return jsonify({'error': 'User not found'}), 404

            country_code = str(profile_row['holiday_country_code'] or '').strip().upper()
            show_public_holidays = bool(profile_row['show_public_holidays'])

            if not show_public_holidays or not country_code:
                return jsonify(
                    {
                        'countryCode': country_code,
                        'enabled': show_public_holidays,
                        'year': year,
                        'holidays': [],
                    }
                ), 200

            holidays = get_public_holidays(
                conn,
                country_code=country_code,
                year=year,
                provider=_database_provider(),
            )
    except httpx.HTTPError as exc:
        current_app.logger.error('Public holiday fetch failed for %s %s: %s', country_code, year, exc)
        return jsonify({'error': 'Unable to load public holidays'}), 502

    return jsonify(
        {
            'countryCode': country_code,
            'enabled': show_public_holidays,
            'year': year,
            'holidays': holidays,
        }
    ), 200
