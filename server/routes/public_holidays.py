from __future__ import annotations

import sqlite3
from datetime import datetime

import httpx
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from services.public_holidays import (
    get_public_holidays,
    list_available_countries,
    list_fallback_countries,
)

public_holidays_bp = Blueprint('public_holidays', __name__)


def get_db():
    db_path = current_app.config['DATABASE_PATH']
    current_app.logger.debug('Public holidays get_db connecting to %s', db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


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

    conn = get_db()
    profile_row = conn.execute(
        """
        SELECT holiday_country_code, show_public_holidays
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()

    if not profile_row:
        conn.close()
        return jsonify({'error': 'User not found'}), 404

    country_code = str(profile_row['holiday_country_code'] or '').strip().upper()
    show_public_holidays = bool(profile_row['show_public_holidays'])

    if not show_public_holidays or not country_code:
        conn.close()
        return jsonify(
            {
                'countryCode': country_code,
                'enabled': show_public_holidays,
                'year': year,
                'holidays': [],
            }
        ), 200

    try:
        holidays = get_public_holidays(
            conn,
            country_code=country_code,
            year=year,
        )
    except httpx.HTTPError as exc:
        current_app.logger.error('Public holiday fetch failed for %s %s: %s', country_code, year, exc)
        conn.close()
        return jsonify({'error': 'Unable to load public holidays'}), 502

    conn.close()
    return jsonify(
        {
            'countryCode': country_code,
            'enabled': show_public_holidays,
            'year': year,
            'holidays': holidays,
        }
    ), 200
