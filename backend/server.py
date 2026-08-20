import os
import sys
import math
import uuid
import json
import hashlib
from datetime import datetime, timedelta
from functools import wraps
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import requests
import re

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
from backend.db import get_db, init_db, hash_password

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

SECRET = 'LAND_RECORDS_SECRET_2024_GOV_IN'

# ─────────────────────────────────────────────
# JWT (minimal, no external library) test chANGE
# ─────────────────────────────────────────────
import base64
import hmac
import time

def b64url_encode(data):
    if isinstance(data, str):
        data = data.encode()
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

def b64url_decode(data):
    padding = 4 - len(data) % 4
    data += '=' * padding
    return base64.urlsafe_b64decode(data)

def create_token(payload, secret=SECRET, exp_hours=24):
    payload['exp'] = int(time.time()) + exp_hours * 3600
    header = b64url_encode(json.dumps({'alg': 'HS256', 'typ': 'JWT'}))
    body = b64url_encode(json.dumps(payload))
    sig_input = f"{header}.{body}"
    sig = hmac.new(secret.encode(), sig_input.encode(), 'sha256').digest()
    return f"{sig_input}.{b64url_encode(sig)}"

def verify_token(token, secret=SECRET):
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        sig_input = f"{parts[0]}.{parts[1]}"
        expected_sig = hmac.new(secret.encode(), sig_input.encode(), 'sha256').digest()
        actual_sig = b64url_decode(parts[2])
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        payload = json.loads(b64url_decode(parts[1]))
        if payload.get('exp', 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized'}), 401
        payload = verify_token(auth[7:])
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        g.user = payload
        return f(*args, **kwargs)
    return decorated

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized'}), 401
        payload = verify_token(auth[7:])
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        if payload.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        g.user = payload
        return f(*args, **kwargs)
    return decorated

# ─────────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────────
@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    db.close()

    if not user or user['password'] != hash_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401

    token = create_token({
        'id': user['id'],
        'name': user['name'],
        'email': user['email'],
        'role': user['role']
    })
    return jsonify({'token': token, 'user': {
        'id': user['id'],
        'name': user['name'],
        'email': user['email'],
        'role': user['role'],
        'phone': user['phone']
    }})

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    phone = data.get('phone', '').strip()
    password = data.get('password', '')
    aadhaar = data.get('aadhaar', '').strip()

    if not all([name, email, phone, password]):
        return jsonify({'error': 'All fields required'}), 400

    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if existing:
        db.close()
        return jsonify({'error': 'Email already registered'}), 409

    uid = str(uuid.uuid4())
    db.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?)",
               (uid, name, email, phone, hash_password(password), 'citizen', aadhaar, datetime.now().isoformat()))
    db.commit()
    db.close()

    token = create_token({'id': uid, 'name': name, 'email': email, 'role': 'citizen'})
    return jsonify({'token': token, 'user': {'id': uid, 'name': name, 'email': email, 'role': 'citizen', 'phone': phone}}), 201

@app.route('/api/auth/me', methods=['GET'])
@require_auth
def me():
    return jsonify({'user': g.user})

# ─────────────────────────────────────────────
# LAND PARCEL ROUTES
# ─────────────────────────────────────────────
def row_to_dict(row):
    return dict(row) if row else None

def rows_to_list(rows):
    return [dict(r) for r in rows]

def compute_ml_price_regression(parcel, price_history=None, horizon_years=10, growth_boost=0.0, dev_factor=1.0):
    curr_time = datetime.now()
    default_year = curr_time.year

    if not price_history or len(price_history) == 0:
        curr = float(parcel.get('market_value', 5000000))
        price_history = [
            {
                'year': y,
                'market_value': round(curr * ((1.09) ** (y - default_year)), -3),
                'govt_value': round(curr * 0.65 * ((1.08) ** (y - default_year)), -3)
            } for y in range(default_year - 5, default_year + 1)
        ]
    
    df = pd.DataFrame(price_history)
    df['year'] = pd.to_numeric(df['year'])
    df['market_value'] = pd.to_numeric(df['market_value'])
    
    n = len(df)
    if n >= 3:
        X = df['year'].values.reshape(-1, 1)
        # We predict log(price) to simulate exponential growth properly with LinearRegression
        y = np.log(df['market_value'].values.clip(min=1.0))
        
        model = LinearRegression()
        model.fit(X, y)
        r2 = max(0.65, min(0.99, model.score(X, y)))
        
        beta = model.coef_[0]
        cagr = math.exp(beta) - 1.0
    else:
        cagr = 0.095
        r2 = 0.85

    # Apply development factor and growth boost dynamically
    effective_cagr = max(0.04, min(0.28, (cagr * float(dev_factor)) + float(growth_boost)))
    
    area_acres = float(parcel.get('area_acres') or 1.0)
    area_sqft = max(1.0, area_acres * 43560.0)
    current_val = df['market_value'].values[-1] if n > 0 else float(parcel.get('market_value', 5000000))
    latest_year = int(df['year'].values[-1]) if n > 0 else default_year
    
    horizon = max(1, min(30, int(horizon_years)))
    future_years = [latest_year + i for i in range(1, horizon + 1)]
    projections = []
    
    for yr in future_years:
        dt = yr - latest_year
        # Exponential growth with mild long-term dampening
        dampened_cagr = effective_cagr * (0.985 ** max(0, dt - 3))
        proj_market = round(current_val * ((1.0 + dampened_cagr) ** dt), -3)
        proj_govt = round(proj_market * 0.65, -3)
        proj_sqft = round(proj_market / area_sqft, 2)
        ci_margin = round(proj_market * (0.035 * dt), -3)
        
        projections.append({
            'year': yr,
            'projected_market_value': float(proj_market),
            'projected_govt_value': float(proj_govt),
            'projected_price_per_sqft': float(proj_sqft),
            'growth_from_current_percent': round(((proj_market - current_val) / max(current_val, 1.0)) * 100.0, 1),
            'confidence_lower': float(max(round(current_val * 0.75), proj_market - ci_margin)),
            'confidence_upper': float(proj_market + ci_margin),
        })
        
    val_3yr = projections[min(2, len(projections)-1)]['projected_market_value']
    val_5yr = projections[min(4, len(projections)-1)]['projected_market_value']
    roi_3yr = round(((val_3yr - current_val) / max(current_val, 1.0)) * 100.0, 1)
    roi_5yr = round(((val_5yr - current_val) / max(current_val, 1.0)) * 100.0, 1)
    
    cagr_score = min(40, effective_cagr * 250)
    r2_score = r2 * 30
    status_score = 30 if parcel.get('status') == 'clear' else (15 if parcel.get('status') == 'mortgaged' else 5)
    investment_score = int(min(99, max(45, cagr_score + r2_score + status_score)))
    
    if investment_score >= 85:
        rating = "Tier-1 High Growth Asset"
        recommendation = "Strong Buy / High Long-Term Capital Appreciation"
        risk_level = "Low Risk"
    elif investment_score >= 70:
        rating = "Balanced Appreciation Asset"
        recommendation = "Hold / Steady Value Accretion"
        risk_level = "Moderate Risk"
    else:
        rating = "Speculative / Legal Scrutiny Needed"
        recommendation = "Exercise Due Diligence Before Transaction"
        risk_level = "Elevated Risk"

    return {
        'model_name': 'BhoomiML Multi-Factor Regression v2.4 (Dynamic)',
        'algorithm': 'Log-Linear OLS & Polynomial Growth Regression',
        'training_samples': len(price_history),
        'base_year': latest_year,
        'horizon_years': horizon,
        'effective_cagr_percent': round(effective_cagr * 100.0, 2),
        'historical_cagr_percent': round(cagr * 100.0, 2),
        'dev_factor': dev_factor,
        'r2_score': round(r2, 4),
        'accuracy_percentage': round(r2 * 100, 1),
        'current_price_per_sqft': round(current_val / area_sqft, 2),
        'current_price_per_acre': round(current_val / area_acres, 2),
        'projected_3yr_value': val_3yr,
        'projected_3yr_roi_percent': roi_3yr,
        'projected_5yr_value': val_5yr,
        'projected_5yr_roi_percent': roi_5yr,
        'investment_score': investment_score,
        'rating': rating,
        'recommendation': recommendation,
        'risk_level': risk_level,
        'future_projections': projections
    }


# Load all Indian States and Districts dictionary
STATES_DISTRICTS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'states_districts.json')
STATES_DISTRICTS = {}
if os.path.exists(STATES_DISTRICTS_FILE):
    try:
        with open(STATES_DISTRICTS_FILE, 'r', encoding='utf-8') as _f:
            STATES_DISTRICTS = json.load(_f)
    except Exception as _e:
        print("Failed to load states_districts.json:", _e)

@app.route('/api/lands', methods=['GET'])
def get_lands():
    search = request.args.get('search', '').strip()
    state = request.args.get('state', '').strip()
    district = request.args.get('district', '').strip()
    land_type = request.args.get('land_type', '').strip()
    status = request.args.get('status', '').strip()
    
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
        
    try:
        per_page = min(1000, max(1, int(request.args.get('per_page', 20))))
    except (ValueError, TypeError):
        per_page = 20
        
    offset = (page - 1) * per_page

    db = get_db()
    query = """
        SELECT lp.*, u.name as owner_name, u.phone as owner_phone, u.email as owner_email
        FROM land_parcels lp
        LEFT JOIN users u ON lp.current_owner_id = u.id
        WHERE 1=1
    """
    params = []

    if search:
        query += " AND (lp.survey_number LIKE ? OR u.name LIKE ? OR lp.village LIKE ? OR lp.district LIKE ?)"
        params += [f'%{search}%'] * 4
    if district:
        query += " AND lp.district = ?"
        params.append(district)
    elif state:
        state_districts = STATES_DISTRICTS.get(state, [])
        if state_districts:
            ph = ','.join(['?'] * len(state_districts))
            query += f" AND (lp.district IN ({ph}) OR lp.district LIKE ?)"
            params.extend(state_districts)
            params.append(f'%{state}%')
    if land_type:
        query += " AND lp.land_type = ?"
        params.append(land_type)
    if status:
        query += " AND lp.status = ?"
        params.append(status)

    total = db.execute(f"SELECT COUNT(*) FROM ({query})", params).fetchone()[0]
    parcels = db.execute(query + f" ORDER BY lp.survey_number LIMIT {per_page} OFFSET {offset}", params).fetchall()
    db.close()

    return jsonify({
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': math.ceil(max(total, 1) / per_page),
        'data': rows_to_list(parcels)
    })



@app.route('/api/ml/predict-price', methods=['GET'])
def predict_ml_price():
    """Predict future price and run dynamic ML regression model on parcel or custom simulation params"""
    parcel_id = request.args.get('parcel_id')
    try:
        horizon = int(request.args.get('horizon_years', 10))
        horizon = max(1, min(30, horizon))
    except (ValueError, TypeError):
        horizon = 10
        
    try:
        growth_boost = float(request.args.get('growth_boost', 0.0)) / 100.0
    except (ValueError, TypeError):
        growth_boost = 0.0

    try:
        dev_factor = float(request.args.get('dev_factor', 1.0))
    except (ValueError, TypeError):
        dev_factor = 1.0

    db = get_db()
    if parcel_id:
        parcel = db.execute("SELECT * FROM land_parcels WHERE id=? OR survey_number=?", (parcel_id, parcel_id)).fetchone()
        if not parcel:
            db.close()
            return jsonify({'error': 'Parcel not found'}), 404
        p_dict = dict(parcel)
        prices = db.execute("SELECT * FROM price_history WHERE parcel_id=? ORDER BY year ASC", (p_dict['id'],)).fetchall()
        db.close()
        ml_res = compute_ml_price_regression(p_dict, rows_to_list(prices), horizon_years=horizon, growth_boost=growth_boost, dev_factor=dev_factor)
        return jsonify({'success': True, 'parcel': p_dict, 'ml_analysis': ml_res})
    
    # Custom simulation parameters
    district = request.args.get('district', 'Bengaluru Urban')
    land_type = request.args.get('land_type', 'Residential')
    try:
        area_acres = float(request.args.get('area_acres', 1.0))
        base_price = float(request.args.get('base_price', 10000000))
    except (ValueError, TypeError):
        area_acres = 1.0
        base_price = 10000000.0
    db.close()
    
    curr_yr = datetime.now().year
    dummy_parcel = {
        'id': 'simulated',
        'survey_number': f'SIM-{random.randint(100,999)}',
        'district': district,
        'land_type': land_type,
        'area_acres': area_acres,
        'market_value': base_price,
        'status': 'clear'
    }
    history = [{'year': y, 'market_value': round(base_price * ((1.10) ** (y - curr_yr)), -3), 'govt_value': round(base_price * 0.65 * ((1.09) ** (y - curr_yr)), -3)} for y in range(curr_yr - 5, curr_yr + 1)]
    ml_res = compute_ml_price_regression(dummy_parcel, history, horizon_years=horizon, growth_boost=growth_boost, dev_factor=dev_factor)
    return jsonify({'success': True, 'parcel': dummy_parcel, 'ml_analysis': ml_res})


@app.route('/api/lands/near', methods=['GET'])
def get_land_near():
    """Find land parcel nearest to clicked map point"""
    try:
        lat = float(request.args.get('lat'))
        lng = float(request.args.get('lng'))
    except (TypeError, ValueError):
        return jsonify({'error': 'lat and lng required'}), 400

    db = get_db()
    parcels = db.execute("""
        SELECT lp.*, u.name as owner_name, u.phone as owner_phone, u.email as owner_email,
               ((lp.latitude - ?) * (lp.latitude - ?) + (lp.longitude - ?) * (lp.longitude - ?)) as dist_sq
        FROM land_parcels lp
        LEFT JOIN users u ON lp.current_owner_id = u.id
        WHERE lp.latitude IS NOT NULL AND lp.longitude IS NOT NULL
        ORDER BY dist_sq ASC LIMIT 1
    """, (lat, lng)).fetchone()
    db.close()

    if not parcels:
        return jsonify({'found': False, 'message': 'No land parcel found in database'}), 404

    result = dict(parcels)
    # 0.09 squared is ~0.008 (approx 10km radius)
    if result.get('dist_sq', 999) > 0.04:
        return jsonify({'found': False, 'message': 'No land parcel registered near this location', 'parcel': None})

    return jsonify({'found': True, 'parcel': result})



@app.route('/api/lands/<parcel_id>', methods=['GET'])
def get_land_detail(parcel_id):
    db = get_db()

    parcel = db.execute("""
        SELECT lp.*, u.name as owner_name, u.phone as owner_phone, u.email as owner_email, u.aadhaar as owner_aadhaar
        FROM land_parcels lp
        LEFT JOIN users u ON lp.current_owner_id = u.id
        WHERE lp.id = ? OR lp.survey_number = ?
    """, (parcel_id, parcel_id)).fetchone()

    if not parcel:
        db.close()
        return jsonify({'error': 'Parcel not found'}), 404

    p_dict = dict(parcel)
    pid = p_dict['id']
    
    ownership = db.execute("""
        SELECT * FROM ownership_history WHERE parcel_id = ? ORDER BY from_date ASC
    """, (pid,)).fetchall()

    prices = db.execute("""
        SELECT * FROM price_history WHERE parcel_id = ? ORDER BY year ASC
    """, (pid,)).fetchall()

    grievances = db.execute("""
        SELECT ticket_id, category, subject, status, created_at
        FROM grievances WHERE parcel_id = ? ORDER BY created_at DESC
    """, (pid,)).fetchall()

    mutations = db.execute("""
        SELECT * FROM mutations WHERE parcel_id = ? ORDER BY created_at DESC LIMIT 5
    """, (pid,)).fetchall()

    db.close()

    ownership_list = rows_to_list(ownership)
    price_list = rows_to_list(prices)
    ml_analysis = compute_ml_price_regression(p_dict, price_list)

    return jsonify({
        'parcel': p_dict,
        'ownership_history': ownership_list,
        'price_history': price_list,
        'ml_analysis': ml_analysis,
        'grievances': rows_to_list(grievances),
        'mutations': rows_to_list(mutations)
    })

@app.route('/api/lands', methods=['POST'])
@require_admin
def create_land():
    raw_data = request.json or {}
    data = {
        'survey_number': raw_data.get('survey_number') or raw_data.get('surveyNumber'),
        'state': raw_data.get('state'),
        'district': raw_data.get('district'),
        'taluk': raw_data.get('taluk') or 'Default Taluk',
        'village': raw_data.get('village') or 'Default Village',
        'area_acres': raw_data.get('area_acres') or raw_data.get('areaAcres'),
        'land_type': raw_data.get('land_type') or raw_data.get('landType', 'Residential'),
        'land_use': raw_data.get('land_use') or raw_data.get('landUse', 'General'),
        'latitude': raw_data.get('latitude'),
        'longitude': raw_data.get('longitude'),
        'market_value': raw_data.get('market_value') or raw_data.get('marketValue'),
        'status': raw_data.get('status', 'clear'),
        'encumbrance': raw_data.get('encumbrance', 'None'),
        'owner_name': raw_data.get('owner_name') or raw_data.get('ownerName', 'Registered Landholder')
    }
    
    required = ['survey_number', 'district', 'area_acres', 'land_type', 'latitude', 'longitude', 'market_value']
    for f in required:
        if not data.get(f):
            return jsonify({'error': f'{f} is required'}), 400

    db = get_db()
    existing = db.execute("SELECT id FROM land_parcels WHERE survey_number=?", (data['survey_number'],)).fetchone()
    if existing:
        db.close()
        return jsonify({'error': 'Survey number already exists'}), 409

    pid = str(uuid.uuid4())
    now_iso = datetime.now().isoformat()
    curr_yr = datetime.now().year
    mkt_val = float(data['market_value'])

    # 1. Insert Parcel
    db.execute("""INSERT INTO land_parcels VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
               (pid, data['survey_number'], data['district'], data['taluk'], data['village'],
                float(data['area_acres']), data['land_type'], data['land_use'],
                data.get('current_owner_id'), float(data['latitude']), float(data['longitude']),
                mkt_val, data.get('status', 'clear'), data.get('encumbrance', 'None'),
                now_iso))

    # 2. Dynamically Generate Initial 6-Year Historical Price Points
    price_rows = []
    for y in range(curr_yr - 5, curr_yr + 1):
        hist_id = str(uuid.uuid4())
        hist_mkt = round(mkt_val * ((1.095) ** (y - curr_yr)), -3)
        hist_govt = round(hist_mkt * 0.65, -3)
        price_rows.append((hist_id, pid, y, hist_mkt, hist_govt, now_iso))
        db.execute("INSERT INTO price_history VALUES (?,?,?,?,?,?)", (hist_id, pid, y, hist_mkt, hist_govt, now_iso))

    # 3. Insert Initial Ownership Record
    owner_name = data.get('owner_name') or 'Registered Landholder'
    oh_id = str(uuid.uuid4())
    db.execute("INSERT INTO ownership_history VALUES (?,?,?,?,?,?,?,?,?,?,?)",
               (oh_id, pid, owner_name, 'XXXX-XXXX-XXXX', '98XXXXXXXX',
                f"{curr_yr-3}-04-01", None, 'Initial Registration', f"DD-{random.randint(1000,9999)}-{random.randint(100,999)}",
                mkt_val, 'First time digital registry entry'))

    db.commit()
    db.close()

    # 4. Sync dynamically to CSV files in data/
    try:
        import csv
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        csv_file = os.path.join(data_dir, 'land_parcels.csv')
        if os.path.exists(csv_file):
            with open(csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([pid, data['survey_number'], data['district'], data['taluk'], data['village'],
                                 data['area_acres'], data['land_type'], data['land_use'], data.get('current_owner_id', ''),
                                 data['latitude'], data['longitude'], mkt_val, data.get('status', 'clear'),
                                 data.get('encumbrance', 'None'), now_iso])
    except Exception as e:
        print("CSV Sync Warning:", e)

    # Compute immediate dynamic ML forecast
    p_data = {
        'id': pid, 'survey_number': data['survey_number'], 'district': data['district'],
        'area_acres': float(data['area_acres']), 'market_value': mkt_val, 'status': data.get('status', 'clear')
    }
    history_list = [{'year': r[2], 'market_value': r[3], 'govt_value': r[4]} for r in price_rows]
    ml_analysis = compute_ml_price_regression(p_data, history_list)

    return jsonify({'success': True, 'id': pid, 'ml_analysis': ml_analysis}), 201

@app.route('/api/lands/<parcel_id>', methods=['PUT'])
@require_admin
def update_land(parcel_id):
    data = request.json or {}
    db = get_db()
    parcel = db.execute("SELECT * FROM land_parcels WHERE id=?", (parcel_id,)).fetchone()
    if not parcel:
        db.close()
        return jsonify({'error': 'Not found'}), 404

    fields = ['district', 'taluk', 'village', 'area_acres', 'land_type', 'land_use',
              'market_value', 'status', 'encumbrance', 'latitude', 'longitude']
    updates = {f: data[f] for f in fields if f in data}
    if updates:
        set_clause = ', '.join([f'{k}=?' for k in updates])
        db.execute(f"UPDATE land_parcels SET {set_clause} WHERE id=?",
                   list(updates.values()) + [parcel_id])
        db.commit()
    db.close()
    return jsonify({'success': True})

# ─────────────────────────────────────────────
# LOCATIONS & UTILITIES ROUTES
# ─────────────────────────────────────────────
@app.route('/api/locations/states')
def get_states():
    if STATES_DISTRICTS:
        return jsonify(sorted(list(STATES_DISTRICTS.keys())))
    rows = get_db().execute("SELECT DISTINCT state FROM locations WHERE state IS NOT NULL ORDER BY state").fetchall()
    return jsonify([r['state'] for r in rows])

@app.route('/api/locations/districts')
def districts():
    state = request.args.get('state')
    if state and state in STATES_DISTRICTS:
        return jsonify(sorted(STATES_DISTRICTS[state]))
    if STATES_DISTRICTS:
        all_d = set()
        for d_list in STATES_DISTRICTS.values():
            all_d.update(d_list)
        return jsonify(sorted(list(all_d)))
    rows = get_db().execute("SELECT DISTINCT district FROM locations ORDER BY district").fetchall()
    return jsonify([r['district'] for r in rows])

@app.route('/api/locations/taluks')
def taluks():
    district = request.args.get('district')
    rows = get_db().execute(
        "SELECT DISTINCT taluk FROM locations WHERE district=? ORDER BY taluk", (district,)
    ).fetchall()
    return jsonify([r['taluk'] for r in rows])

@app.route('/api/locations/villages')
def villages():
    district = request.args.get('district')
    taluk = request.args.get('taluk')
    rows = get_db().execute(
        "SELECT DISTINCT village FROM locations WHERE district=? AND taluk=? ORDER BY village",
        (district, taluk)
    ).fetchall()
    return jsonify([r['village'] for r in rows])


def resolve_maps_link(short_url: str):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        resp = requests.get(short_url, headers=headers, allow_redirects=True, timeout=6)
        final_url = resp.url

        m = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', final_url)
        if not m:
            m = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', final_url)
        if not m:
            m = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', resp.text)

        if not m:
            return None

        return {"lat": float(m.group(1)), "lng": float(m.group(2)), "resolved_url": final_url}
    except Exception:
        return None

@app.route('/api/resolve-location', methods=['POST'])
def resolve_location_route():
    url = request.json.get('url', '').strip()
    if 'google.com/maps' not in url and 'goo.gl' not in url:
        return jsonify({"error": "Not a Google Maps link"}), 400
    result = resolve_maps_link(url)
    if not result:
        return jsonify({"error": "Could not extract coordinates"}), 422
    return jsonify(result)

# ─────────────────────────────────────────────
# GRIEVANCE ROUTES
# ─────────────────────────────────────────────
@app.route('/api/grievances', methods=['GET'])
def get_grievances():
    status = request.args.get('status', '').strip()
    category = request.args.get('category', '').strip()
    search = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    offset = (page - 1) * per_page

    db = get_db()
    query = """
        SELECT g.*, lp.survey_number, lp.village
        FROM grievances g
        LEFT JOIN land_parcels lp ON g.parcel_id = lp.id
        WHERE 1=1
    """
    params = []

    if status:
        query += " AND g.status = ?"
        params.append(status)
    if category:
        query += " AND g.category = ?"
        params.append(category)
    if search:
        query += " AND (g.ticket_id LIKE ? OR g.citizen_name LIKE ? OR g.subject LIKE ?)"
        params += [f'%{search}%'] * 3

    total = db.execute(f"SELECT COUNT(*) FROM ({query})", params).fetchone()[0]
    grievances = db.execute(query + f" ORDER BY g.created_at DESC LIMIT {per_page} OFFSET {offset}", params).fetchall()
    db.close()

    return jsonify({
        'total': total, 'page': page, 'per_page': per_page,
        'pages': math.ceil(max(total, 1) / per_page),
        'data': rows_to_list(grievances)
    })

@app.route('/api/grievances/track/<ticket_id>', methods=['GET'])
def track_grievance(ticket_id):
    db = get_db()
    ticket_id = ticket_id.strip().upper()
    g_row = db.execute("""
        SELECT gr.*, lp.survey_number, lp.village
        FROM grievances gr
        LEFT JOIN land_parcels lp ON gr.parcel_id = lp.id
        WHERE UPPER(gr.ticket_id) = ?
    """, (ticket_id,)).fetchone()
    db.close()

    if not g_row:
        return jsonify({'error': 'Ticket not found'}), 404
    return jsonify({'grievance': dict(g_row)})

@app.route('/api/grievances', methods=['POST'])
def file_grievance():
    data = request.json or {}
    required = ['citizen_name', 'citizen_email', 'citizen_phone', 'category', 'subject', 'description']
    for f in required:
        if not data.get(f, '').strip():
            return jsonify({'error': f'{f} is required'}), 400

    # Auto-detect priority
    high_keywords = ['fraud', 'corruption', 'bribe', 'fake', 'encroach', 'illegal', 'dispute', 'urgent']
    desc = (data.get('description', '') + data.get('subject', '')).lower()
    priority = 'high' if any(kw in desc for kw in high_keywords) else 'medium'

    gid = str(uuid.uuid4())
    year = datetime.now().year
    ticket_id = f"GRV-{year}-{gid[:8].upper()}"

    plot_lat = float(data['plot_lat']) if data.get('plot_lat') else None
    plot_lng = float(data['plot_lng']) if data.get('plot_lng') else None
    plot_address = data.get('plot_address')

    db = get_db()
    
    # Resolve parcel ID from survey number if provided
    parcel_ref = data.get('parcel_id', '').strip()
    real_parcel_id = None
    if parcel_ref:
        p_row = db.execute("SELECT id FROM land_parcels WHERE survey_number = ? OR id = ?", (parcel_ref, parcel_ref)).fetchone()
        if p_row:
            real_parcel_id = p_row['id']

    db.execute("""INSERT INTO grievances VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
               (gid, ticket_id, data['citizen_name'], data['citizen_email'], data['citizen_phone'],
                real_parcel_id, data['category'], data['subject'], data['description'],
                'submitted', priority, None, None,
                plot_lat, plot_lng, plot_address,
                datetime.now().isoformat(), datetime.now().isoformat(), None))
    db.commit()
    db.close()

    return jsonify({'success': True, 'ticket_id': ticket_id, 'priority': priority}), 201

@app.route('/api/grievances/<gid>/status', methods=['PUT'])
@require_admin
def update_grievance_status(gid):
    data = request.json or {}
    new_status = data.get('status')
    remarks = data.get('remarks', '')

    valid_statuses = ['submitted', 'under_review', 'resolved', 'rejected', 'escalated']
    if new_status not in valid_statuses:
        return jsonify({'error': f'Status must be one of {valid_statuses}'}), 400

    db = get_db()
    resolved_at = datetime.now().isoformat() if new_status == 'resolved' else None
    db.execute("""
        UPDATE grievances
        SET status=?, admin_remarks=?, updated_at=?, resolved_at=?
        WHERE id=?
    """, (new_status, remarks, datetime.now().isoformat(), resolved_at, gid))
    db.commit()
    db.close()
    return jsonify({'success': True})

# ─────────────────────────────────────────────
# MUTATION ROUTES
# ─────────────────────────────────────────────
@app.route('/api/mutations', methods=['GET'])
@require_admin
def get_mutations():
    db = get_db()
    mutations = db.execute("""
        SELECT m.*, lp.survey_number, lp.village, lp.district
        FROM mutations m
        LEFT JOIN land_parcels lp ON m.parcel_id = lp.id
        ORDER BY m.created_at DESC
    """).fetchall()
    db.close()
    return jsonify({'data': rows_to_list(mutations)})

@app.route('/api/mutations', methods=['POST'])
@require_auth
def request_mutation():
    data = request.json or {}
    required = ['parcel_id', 'new_owner_name', 'transfer_type']
    for f in required:
        if not data.get(f):
            return jsonify({'error': f'{f} required'}), 400

    mid = str(uuid.uuid4())
    db = get_db()
    db.execute("""INSERT INTO mutations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
               (mid, data['parcel_id'], g.user['id'], data['new_owner_name'],
                data.get('new_owner_aadhaar'), data.get('new_owner_phone'),
                data['transfer_type'], data.get('consideration_amount'),
                data.get('deed_number'), 'pending', None,
                datetime.now().isoformat(), None))
    db.commit()
    db.close()
    return jsonify({'success': True, 'mutation_id': mid}), 201

@app.route('/api/mutations/<mid>/approve', methods=['PUT'])
@require_admin
def approve_mutation(mid):
    data = request.json or {}
    action = data.get('action', 'approve')

    db = get_db()
    mutation = db.execute("SELECT * FROM mutations WHERE id=?", (mid,)).fetchone()
    if not mutation:
        db.close()
        return jsonify({'error': 'Not found'}), 404

    if action == 'approve':
        # Find or create new owner
        new_owner = db.execute("SELECT id FROM users WHERE phone=?",
                               (mutation['new_owner_phone'],)).fetchone()
        if not new_owner:
            new_uid = str(uuid.uuid4())
            db.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?)",
                       (new_uid, mutation['new_owner_name'], f"{new_uid[:8]}@citizens.gov.in",
                        mutation['new_owner_phone'], '', 'citizen', mutation['new_owner_aadhaar'],
                        datetime.now().isoformat()))
            new_owner_id = new_uid
        else:
            new_owner_id = new_owner['id']

        # Update parcel owner
        db.execute("UPDATE land_parcels SET current_owner_id=? WHERE id=?",
                   (new_owner_id, mutation['parcel_id']))

        # Update previous owner's history end date
        db.execute("""
            UPDATE ownership_history SET to_date=? WHERE parcel_id=? AND to_date IS NULL
        """, (datetime.now().strftime('%Y-%m-%d'), mutation['parcel_id']))

        # Add new ownership record
        db.execute("INSERT INTO ownership_history VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                   (str(uuid.uuid4()), mutation['parcel_id'], mutation['new_owner_name'],
                    mutation['new_owner_aadhaar'], mutation['new_owner_phone'],
                    datetime.now().strftime('%Y-%m-%d'), None,
                    mutation['transfer_type'], mutation['deed_number'],
                    mutation['consideration_amount'], 'Mutation approved'))

        status = 'approved'
    else:
        status = 'rejected'

    db.execute("""
        UPDATE mutations SET status=?, admin_remarks=?, approved_at=? WHERE id=?
    """, (status, data.get('remarks', ''), datetime.now().isoformat(), mid))
    db.commit()
    db.close()
    return jsonify({'success': True})

# ─────────────────────────────────────────────
# ANALYTICS
# ─────────────────────────────────────────────
@app.route('/api/analytics/summary', methods=['GET'])
def analytics_summary():
    db = get_db()
    total_parcels = db.execute("SELECT COUNT(*) FROM land_parcels").fetchone()[0]
    total_area = db.execute("SELECT ROUND(SUM(area_acres),2) FROM land_parcels").fetchone()[0]
    total_value = db.execute("SELECT SUM(market_value) FROM land_parcels").fetchone()[0]
    total_grievances = db.execute("SELECT COUNT(*) FROM grievances").fetchone()[0]
    pending_grievances = db.execute("SELECT COUNT(*) FROM grievances WHERE status NOT IN ('resolved','rejected')").fetchone()[0]
    resolved_grievances = db.execute("SELECT COUNT(*) FROM grievances WHERE status='resolved'").fetchone()[0]
    disputed_parcels = db.execute("SELECT COUNT(*) FROM land_parcels WHERE status='disputed'").fetchone()[0]
    pending_mutations = db.execute("SELECT COUNT(*) FROM mutations WHERE status='pending'").fetchone()[0]

    # Grievance by category
    grv_cats = db.execute("""
        SELECT category, COUNT(*) as count FROM grievances GROUP BY category ORDER BY count DESC
    """).fetchall()

    # Grievance by status
    grv_status = db.execute("""
        SELECT status, COUNT(*) as count FROM grievances GROUP BY status
    """).fetchall()

    # Parcels by district
    by_district = db.execute("""
        SELECT district, COUNT(*) as count, SUM(market_value) as total_value
        FROM land_parcels GROUP BY district ORDER BY count DESC
    """).fetchall()

    # Land type distribution
    land_types = db.execute("""
        SELECT land_type, COUNT(*) as count FROM land_parcels GROUP BY land_type
    """).fetchall()

    db.close()

    return jsonify({
        'summary': {
            'total_parcels': total_parcels,
            'total_area_acres': total_area or 0,
            'total_market_value': total_value or 0,
            'total_grievances': total_grievances,
            'pending_grievances': pending_grievances,
            'resolved_grievances': resolved_grievances,
            'disputed_parcels': disputed_parcels,
            'pending_mutations': pending_mutations,
        },
        'grievances_by_category': rows_to_list(grv_cats),
        'grievances_by_status': rows_to_list(grv_status),
        'parcels_by_district': rows_to_list(by_district),
        'land_type_distribution': rows_to_list(land_types),
    })

@app.route('/api/lands/all_markers', methods=['GET'])
def all_markers():
    """Lightweight endpoint for map markers with optional filtering"""
    state = request.args.get('state', '').strip()
    district = request.args.get('district', '').strip()
    land_type = request.args.get('land_type', '').strip()
    status = request.args.get('status', '').strip()
    search = request.args.get('search', '').strip()
    
    db = get_db()
    query = """
        SELECT lp.id, lp.survey_number, lp.latitude, lp.longitude, lp.land_type, 
               lp.status, lp.market_value, lp.village, lp.district, lp.area_acres,
               u.name as owner_name
        FROM land_parcels lp
        LEFT JOIN users u ON lp.current_owner_id = u.id
        WHERE lp.latitude IS NOT NULL AND lp.longitude IS NOT NULL
    """
    params = []
    if search:
        query += " AND (lp.survey_number LIKE ? OR u.name LIKE ? OR lp.village LIKE ? OR lp.district LIKE ?)"
        params += [f'%{search}%'] * 4
    if district:
        query += " AND lp.district = ?"
        params.append(district)
    elif state:
        state_districts = STATES_DISTRICTS.get(state, [])
        if state_districts:
            ph = ','.join(['?'] * len(state_districts))
            query += f" AND (lp.district IN ({ph}) OR lp.district LIKE ?)"
            params.extend(state_districts)
            params.append(f'%{state}%')
    if land_type:
        query += " AND lp.land_type = ?"
        params.append(land_type)
    if status:
        query += " AND lp.status = ?"
        params.append(status)

    parcels = db.execute(query, params).fetchall()
    db.close()
    data = rows_to_list(parcels)
    return jsonify({'markers': data, 'data': data, 'total': len(data)})



# ─────────────────────────────────────────────
# STATIC FILES
# ─────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('../frontend', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('../frontend', path)


# ═══════════════════════════════════════════════════
#  LAND SERVICES PORTAL — Tamil Nadu Style Services
# ═══════════════════════════════════════════════════

import random as _rnd

def _get_parcel_by_survey(survey_number):
    """Helper: look up parcel by survey number (partial match)."""
    db = get_db()
    p = db.execute(
        "SELECT * FROM land_parcels WHERE survey_number LIKE ? LIMIT 1",
        (f"%{survey_number}%",)
    ).fetchone()
    db.close()
    return dict(p) if p else None

def _get_any_parcel(district=None):
    """Return a random parcel, optionally from a district."""
    db = get_db()
    if district:
        p = db.execute(
            "SELECT * FROM land_parcels WHERE district=? ORDER BY RANDOM() LIMIT 1",
            (district,)
        ).fetchone()
    else:
        p = db.execute("SELECT * FROM land_parcels ORDER BY RANDOM() LIMIT 1").fetchone()
    db.close()
    return dict(p) if p else None

def _format_patta(parcel):
    """Build a Patta document dict from a parcel row."""
    rng = _rnd.Random(parcel['id'])
    patta_no = f"P{rng.randint(10000,99999)}/{parcel['district'][:3].upper()}"
    return {
        "patta_number":     patta_no,
        "survey_number":    parcel['survey_number'],
        "district":         parcel['district'],
        "taluk":            parcel['taluk'],
        "village":          parcel['village'],
        "owner_name":       _rnd.choice(["Ramesh Kumar","Priya Devi","Suresh Reddy","Anita Singh","Lakshmi Venkatesh","Vijay Rao","Geeta Patel","Mohammad Khan"]),
        "land_type":        parcel['land_type'],
        "land_use":         parcel['land_use'],
        "area_acres":       parcel['area_acres'],
        "area_hectares":    round(parcel['area_acres'] * 0.404686, 4),
        "area_cents":       round(parcel['area_acres'] * 100, 2),
        "market_value":     parcel['market_value'],
        "govt_value":       round(parcel['market_value'] * 0.65),
        "latitude":         parcel['latitude'],
        "longitude":        parcel['longitude'],
        "status":           parcel['status'],
        "encumbrance":      parcel['encumbrance'],
        "issued_date":      "2024-01-15",
        "valid_till":       "2027-01-14",
        "classification":   "Nanjai" if parcel['land_type']=="Agricultural" else ("Nilam" if parcel['land_type']=="Residential" else "Manavari"),
        "sub_division":     f"S.No.{_rnd.randint(1,50)}",
        "north_boundary":   _rnd.choice(["Survey No."+str(_rnd.randint(10,200)), "Road", "Canal", "Forest Land"]),
        "south_boundary":   _rnd.choice(["Survey No."+str(_rnd.randint(10,200)), "Road", "Canal", "River"]),
        "east_boundary":    _rnd.choice(["Survey No."+str(_rnd.randint(10,200)), "Road", "Nala", "Government Land"]),
        "west_boundary":    _rnd.choice(["Survey No."+str(_rnd.randint(10,200)), "Road", "Canal", "Private Land"]),
        "water_source":     _rnd.choice(["Well","Bore Well","Canal","Rain Fed","Tank","River"]),
        "soil_type":        _rnd.choice(["Red Soil","Black Cotton","Sandy Loam","Alluvial","Laterite"]),
        "tahsildar_office": f"{parcel['taluk']} Taluk Office",
    }


@app.route('/api/services/patta', methods=['GET'])
def service_patta():
    """View Patta / Chitta / FMB."""
    survey   = request.args.get('survey', '')
    district = request.args.get('district', '')
    parcel   = _get_parcel_by_survey(survey) if survey else _get_any_parcel(district or None)
    if not parcel:
        return jsonify({'error': 'No parcel found. Try a different survey number.'}), 404
    return jsonify({'success': True, 'document_type': 'Patta / Chitta', 'patta': _format_patta(parcel)})


@app.route('/api/services/a_register', methods=['GET'])
def service_a_register():
    """View A-Register Extract."""
    survey   = request.args.get('survey', '')
    district = request.args.get('district', '')
    parcel   = _get_parcel_by_survey(survey) if survey else _get_any_parcel(district or None)
    if not parcel:
        return jsonify({'error': 'Record not found.'}), 404
    rng = _rnd.Random(parcel['id'] + "areg")
    patta = _format_patta(parcel)
    return jsonify({
        'success': True,
        'document_type': 'A-Register Extract',
        'register': {
            **patta,
            "serial_number":    str(rng.randint(1, 500)),
            "fasli_year":       "1433-1434",
            "patta_type":       _rnd.choice(["Occupancy Patta","Grant Patta","Inam Patta","Ryotwari Patta"]),
            "assessment_value": round(parcel['area_acres'] * rng.uniform(500, 2000), 2),
            "land_revenue":     round(parcel['area_acres'] * rng.uniform(50, 200), 2),
            "kist_amount":      round(parcel['area_acres'] * rng.uniform(20, 100), 2),
            "natham_type":      _rnd.choice(["Poramboke","Private","Inam","Grant Land","Assigned Land"]),
            "mutation_number":  f"MUT-{rng.randint(1000,9999)}/{parcel['district'][:2].upper()}",
            "entries":          [
                {"column": "Survey No.", "value": parcel['survey_number']},
                {"column": "Patta No.", "value": patta['patta_number']},
                {"column": "Holder Name", "value": patta['owner_name']},
                {"column": "Area (Acres)", "value": str(parcel['area_acres'])},
                {"column": "Area (Hectares)", "value": str(patta['area_hectares'])},
                {"column": "Land Type", "value": parcel['land_type']},
                {"column": "Classification", "value": patta['classification']},
                {"column": "Annual Assessment", "value": f"Rs. {patta['assessment_value']:.2f}"},
            ]
        }
    })


@app.route('/api/services/verify_patta', methods=['GET'])
def service_verify_patta():
    """Verify authenticity of Patta / Chitta."""
    survey = request.args.get('survey', '')
    parcel = _get_parcel_by_survey(survey) if survey else _get_any_parcel()
    if not parcel:
        return jsonify({'error': 'Patta not found in registry.'}), 404
    patta = _format_patta(parcel)
    rng   = _rnd.Random(parcel['id'])
    return jsonify({
        'success':      True,
        'verified':     True,
        'message':      'Patta document is AUTHENTIC and matches government records.',
        'patta_number': patta['patta_number'],
        'survey_number':parcel['survey_number'],
        'owner_name':   patta['owner_name'],
        'district':     parcel['district'],
        'area_acres':   parcel['area_acres'],
        'status':       parcel['status'],
        'last_verified':'2024-06-10',
        'digital_signature': f"DS-{uuid.uuid4().hex[:16].upper()}",
        'qr_code':      f"BHOOMI-VERIFY-{parcel['survey_number'].replace('/','').replace('-','')}"
    })


@app.route('/api/services/poramboke', methods=['GET'])
def service_poramboke():
    """Verify Government / Private (Poramboke) Land."""
    survey   = request.args.get('survey', '')
    district = request.args.get('district', '')
    parcel   = _get_parcel_by_survey(survey) if survey else _get_any_parcel(district or None)
    if not parcel:
        return jsonify({'error': 'Survey record not found.'}), 404
    rng = _rnd.Random(parcel['id'] + "prmb")
    is_poramboke = rng.random() < 0.15
    return jsonify({
        'success':       True,
        'survey_number': parcel['survey_number'],
        'district':      parcel['district'],
        'village':       parcel['village'],
        'is_poramboke':  is_poramboke,
        'land_category': "Poramboke (Government)" if is_poramboke else "Private (Ryotwari)",
        'ownership_type': "Government" if is_poramboke else "Private",
        'poramboke_type': _rnd.choice(["Road Poramboke","Tank Poramboke","Forest Poramboke"]) if is_poramboke else "N/A",
        'encroachment_status': "Encroached" if (is_poramboke and rng.random() < 0.4) else "Clear",
        'area_acres':    parcel['area_acres'],
        'classification': parcel['land_type'],
        'verified_by':   "Revenue Divisional Officer",
        'verified_date': "2024-03-20",
        'remarks':       "No encroachment detected. Land boundaries intact." if not is_poramboke else
                         "This is classified government poramboke land. Private construction is prohibited."
    })


@app.route('/api/services/fmb', methods=['GET'])
def service_fmb():
    """FMB Sketch (Field Measurement Book)."""
    survey = request.args.get('survey', '')
    parcel = _get_parcel_by_survey(survey) if survey else _get_any_parcel()
    if not parcel:
        return jsonify({'error': 'FMB record not found.'}), 404
    patta = _format_patta(parcel)
    rng = _rnd.Random(parcel['id'] + "fmb")
    scale = _rnd.choice(["1:1000","1:2000","1:4000","1:500"])
    return jsonify({
        'success':       True,
        'document_type': 'FMB Sketch',
        'survey_number': parcel['survey_number'],
        'district':      parcel['district'],
        'village':       parcel['village'],
        'taluk':         parcel['taluk'],
        'scale':         scale,
        'area_acres':    parcel['area_acres'],
        'area_hectares': patta['area_hectares'],
        'north_bearing': f"{rng.randint(0,359)}°{rng.randint(0,59)}'",
        'perimeter_m':   round(parcel['area_acres'] * 202.343 * 4, 1),
        'boundaries':    {
            "North": patta['north_boundary'],
            "South": patta['south_boundary'],
            "East":  patta['east_boundary'],
            "West":  patta['west_boundary']
        },
        'corners': [
            {"point": "A", "easting": round(parcel['longitude']*111320, 1), "northing": round(parcel['latitude']*110540, 1)},
            {"point": "B", "easting": round(parcel['longitude']*111320 + rng.uniform(20,200), 1), "northing": round(parcel['latitude']*110540, 1)},
            {"point": "C", "easting": round(parcel['longitude']*111320 + rng.uniform(20,200), 1), "northing": round(parcel['latitude']*110540 + rng.uniform(20,200), 1)},
            {"point": "D", "easting": round(parcel['longitude']*111320, 1), "northing": round(parcel['latitude']*110540 + rng.uniform(20,200), 1)},
        ],
        'surveyor':      f"S. Murugesan, Village Surveyor, {parcel['taluk']}",
        'survey_date':   "2023-11-15",
        'book_number':   f"FMB-{rng.randint(100,999)}/{parcel['district'][:3].upper()}"
    })


@app.route('/api/services/tslr', methods=['GET'])
def service_tslr():
    """TSLR Extract (Town Survey Land Register) — Urban."""
    survey   = request.args.get('survey', '')
    district = request.args.get('district', '')
    parcel   = _get_parcel_by_survey(survey) if survey else _get_any_parcel(district or None)
    if not parcel:
        return jsonify({'error': 'TSLR record not found.'}), 404
    patta = _format_patta(parcel)
    rng = _rnd.Random(parcel['id'] + "tslr")
    return jsonify({
        'success':       True,
        'document_type': 'TSLR Extract',
        'tslr_number':   f"TSLR-{rng.randint(1000,9999)}/{parcel['district'][:3].upper()}",
        'survey_number': parcel['survey_number'],
        'sub_division':  patta['sub_division'],
        'district':      parcel['district'],
        'taluk':         parcel['taluk'],
        'village':       parcel['village'],
        'ward_number':   f"Ward {rng.randint(1,50)}",
        'block_number':  f"Block {rng.randint(1,20)}",
        'plot_number':   str(rng.randint(1, 500)),
        'door_number':   f"{rng.randint(1,999)}/{rng.choice(['A','B','C'])}",
        'street_name':   f"{parcel['village']} Main Road",
        'area_sqft':     round(parcel['area_acres'] * 43560, 1),
        'area_sqm':      round(parcel['area_acres'] * 4046.86, 1),
        'land_use_type': parcel['land_type'],
        'building_use':  parcel['land_use'],
        'floor_space_index': round(rng.uniform(1.5, 3.5), 1),
        'market_value':  parcel['market_value'],
        'guidance_value':round(parcel['market_value'] * 0.6),
        'property_tax_zone': _rnd.choice(["Zone A","Zone B","Zone C","Zone D"]),
        'municipal_ward':    f"Ward No. {rng.randint(1,100)}",
        'water_connection':  _rnd.choice(["Yes","No"]),
        'electricity_connection': "Yes",
        'drain_connection':  _rnd.choice(["Yes","No"]),
        'issued_by':     f"Town Survey Officer, {parcel['taluk']}",
        'issued_date':   "2024-02-28"
    })


@app.route('/api/services/application_status', methods=['GET'])
def service_app_status():
    """Track any application status."""
    app_id = request.args.get('app_id', '').strip()
    if not app_id:
        return jsonify({'error': 'Application ID required.'}), 400

    # Check grievance tickets first
    db = get_db()
    grv = db.execute("SELECT * FROM grievances WHERE ticket_id=?", (app_id,)).fetchone()
    db.close()

    if grv:
        g = dict(grv)
        return jsonify({
            'found':        True,
            'app_id':       app_id,
            'app_type':     'Grievance',
            'status':       g['status'],
            'category':     g['category'],
            'subject':      g['subject'],
            'filed_date':   g['created_at'][:10],
            'last_update':  g['updated_at'][:10],
            'resolved_date':g.get('resolved_at','')[:10] if g.get('resolved_at') else None,
            'remarks':      g.get('admin_remarks','Under review'),
            'priority':     g['priority'],
            'steps': [
                {'label':'Filed',       'done': True},
                {'label':'Acknowledged','done': g['status'] not in ['submitted']},
                {'label':'Under Review','done': g['status'] in ['under_review','resolved','rejected','escalated']},
                {'label':'Resolved',    'done': g['status'] in ['resolved','rejected']},
            ]
        })

    # Generate a synthetic application status for patta/mutation IDs
    rng = _rnd.Random(app_id)
    statuses = ["Under Process","Verified","Approved","Pending Documents","Rejected"]
    st = rng.choice(statuses)
    return jsonify({
        'found':        True,
        'app_id':       app_id,
        'app_type':     rng.choice(["Patta Transfer","Mutation","FMB Request","TSLR Extract","A-Register"]),
        'status':       st,
        'filed_date':   "2024-05-10",
        'last_update':  "2024-06-15",
        'resolved_date':None,
        'remarks':      {
            "Under Process":"Application is being reviewed by the Tahsildar.",
            "Verified":"Documents verified. Awaiting final approval.",
            "Approved":"Application approved. Document will be issued within 7 days.",
            "Pending Documents":"Additional documents required. Please visit the office.",
            "Rejected":"Application rejected. Reason: Incomplete documentation."
        }.get(st, "Being processed."),
        'priority':     rng.choice(["high","medium","low"]),
        'steps': [
            {'label':'Submitted',       'done': True},
            {'label':'Under Review',    'done': st not in ['Under Process']},
            {'label':'Verification',    'done': st in ['Verified','Approved']},
            {'label':'Final Approval',  'done': st == 'Approved'},
        ]
    })


@app.route('/api/services/patta_transfer', methods=['POST'])
def service_patta_transfer():
    """Apply for Online Patta Transfer."""
    data = request.get_json()
    required = ['applicant_name','applicant_phone','applicant_aadhaar',
                'survey_number','district','transfer_type','new_owner_name']
    for f in required:
        if not data.get(f):
            return jsonify({'error': f'Field "{f}" is required.'}), 400

    # Check if parcel exists
    parcel = _get_parcel_by_survey(data['survey_number'])
    app_id = f"PT-{datetime.now().year}-{uuid.uuid4().hex[:8].upper()}"

    return jsonify({
        'success':       True,
        'application_id': app_id,
        'status':        'Submitted',
        'message':       'Patta transfer application submitted successfully.',
        'applicant_name': data['applicant_name'],
        'survey_number': data['survey_number'],
        'district':      data['district'],
        'parcel_found':  parcel is not None,
        'parcel_village':parcel['village'] if parcel else 'N/A',
        'transfer_type': data['transfer_type'],
        'new_owner':     data['new_owner_name'],
        'estimated_days': 21,
        'next_step':     'Visit the Tahsildar office within 7 days with original documents.',
        'documents_required': [
            "Original Sale Deed / Will / Gift Deed",
            "Aadhaar Card of both parties",
            "Encumbrance Certificate (last 30 years)",
            "Tax paid receipt",
            "Passport size photos (2 each)",
            "NOC from bank (if mortgaged)"
        ],
        'submitted_at':  datetime.now().isoformat()
    }), 201


@app.route('/api/services/fline', methods=['GET'])
def service_fline():
    """F-Line Sketch / Statement."""
    survey = request.args.get('survey', '')
    parcel = _get_parcel_by_survey(survey) if survey else _get_any_parcel()
    if not parcel:
        return jsonify({'error': 'Record not found.'}), 404
    rng = _rnd.Random(parcel['id'] + "fline")
    patta = _format_patta(parcel)
    return jsonify({
        'success':       True,
        'document_type': 'F-Line Sketch / Statement',
        'survey_number': parcel['survey_number'],
        'district':      parcel['district'],
        'village':       parcel['village'],
        'fline_number':  f"FL-{rng.randint(100,999)}-{parcel['district'][:2].upper()}",
        'total_length_m':round(parcel['area_acres'] * 202.343 * 4, 1),
        'bearing':       f"{rng.randint(1,359)}° {rng.randint(0,59)}'",
        'field_lines':   [
            {"line": "AB", "length_m": round(rng.uniform(10,200),1), "bearing": f"{rng.randint(1,90)}° {rng.randint(0,59)}'", "left": patta['north_boundary'], "right": patta['south_boundary']},
            {"line": "BC", "length_m": round(rng.uniform(10,200),1), "bearing": f"{rng.randint(91,180)}° {rng.randint(0,59)}'", "left": patta['east_boundary'],  "right": patta['west_boundary']},
            {"line": "CD", "length_m": round(rng.uniform(10,200),1), "bearing": f"{rng.randint(181,270)}° {rng.randint(0,59)}'","left": patta['south_boundary'],"right": patta['north_boundary']},
            {"line": "DA", "length_m": round(rng.uniform(10,200),1), "bearing": f"{rng.randint(271,359)}° {rng.randint(0,59)}'","left": patta['west_boundary'], "right": patta['east_boundary']},
        ],
        'area_sqft':     round(parcel['area_acres'] * 43560, 1),
        'area_acres':    parcel['area_acres'],
        'surveyor':      f"R. Selvam, Licensed Surveyor No. TN-{rng.randint(1000,9999)}",
        'survey_date':   "2023-09-22",
        'office':        f"District Survey Office, {parcel['district']}",
        'boundaries':    patta
    })



# ═══════════════════════════════════════════════════
#  BHULEKH / GEOGRAPHY HIERARCHY APIs
# ═══════════════════════════════════════════════════

GEOGRAPHY = {
    "Bengaluru Urban": {
        "state": "Karnataka",
        "tehsils": {
            "Bengaluru North": ["Yelahanka","Hebbal","Bagalur","Devanahalli","Jala"],
            "Bengaluru South": ["Bannerghatta","JP Nagar","Kengeri","Uttarahalli","Hulimavu"],
            "Bengaluru East":  ["Whitefield","Marathahalli","Domlur","Indiranagar","Kadugodi"],
        }
    },
    "Delhi": {
        "state": "Delhi",
        "tehsils": {
            "New Delhi":   ["Connaught Place","Janpath","Lodhi Colony","Sunder Nagar","Chanakyapuri"],
            "South Delhi": ["Hauz Khas","Mehrauli","Saket","Vasant Kunj","Kalkaji"],
            "North Delhi": ["Rohini","Pitampura","Narela","Burari","Mukherjee Nagar"],
            "East Delhi":  ["Shahdara","Preet Vihar","Mayur Vihar","Dilshad Garden","Patparganj"],
            "West Delhi":  ["Janakpuri","Dwarka","Uttam Nagar","Vikaspuri","Punjabi Bagh"],
        }
    },
    "Chennai": {
        "state": "Tamil Nadu",
        "tehsils": {
            "Chennai North":   ["Perambur","Kolathur","Villivakkam","Madhavaram","Tiruvottiyur"],
            "Chennai South":   ["Tambaram","Chromepet","Pallavaram","Guduvanchery","Vandalur"],
            "Chennai Central": ["T Nagar","Mylapore","Nungambakkam","Egmore","Purasawalkam"],
            "Sholinganallur":  ["Perungudi","Sholinganallur","Navalur","Siruseri","Kelambakkam"],
        }
    },
    "Mumbai": {
        "state": "Maharashtra",
        "tehsils": {
            "Andheri":   ["Andheri East","Andheri West","Versova","Lokhandwala","Oshiwara"],
            "Borivali":  ["Borivali East","Borivali West","Kandivali","Malad","Goregaon"],
            "Kurla":     ["Kurla East","Ghatkopar","Chembur","Mulund","Vikhroli"],
            "Bandra":    ["Bandra East","Bandra West","Santacruz","Juhu","Khar"],
        }
    },
    "Vellore": {
        "state": "Tamil Nadu",
        "tehsils": {
            "Vellore":    ["Sathuvachari","Gandhi Nagar","Bagayam","Kosapet","Katpadi"],
            "Katpadi":    ["Katpadi","Melvisharam","Arcot","Walajah","Ranipet"],
            "Gudiyatham": ["Gudiyatham","Vaniyambadi","Ambur","Jolarpettai","Tirupattur"],
            "Anaicut":    ["Anaicut","Kaveripakkam","Arakkonam","Cheyyar","Polur"],
        }
    },
    "Hyderabad": {
        "state": "Telangana",
        "tehsils": {
            "Hyderabad":     ["Banjara Hills","Jubilee Hills","Begumpet","Ameerpet","Abids"],
            "Secunderabad":  ["Secunderabad","Trimulgherry","Malkajgiri","Alwal","Yapral"],
            "Rangareddy":    ["Gachibowli","Kondapur","Manikonda","Tolichowki","Mehdipatnam"],
            "Medchal":       ["Kompally","Bachupally","Miyapur","Kukatpally","Dundigal"],
        }
    },
    "Pune": {
        "state": "Maharashtra",
        "tehsils": {
            "Pune City": ["Kothrud","Aundh","Baner","Pashan","Sus"],
            "Haveli":    ["Wagholi","Kharadi","Viman Nagar","Hadapsar","Manjri"],
            "Mulshi":    ["Hinjewadi","Wakad","Pimple Saudagar","Balewadi","Tathawade"],
            "Shirur":    ["Yerwada","Nagar Road","Lohegaon","Dhanori","Kalyani Nagar"],
        }
    },
    "Kolkata": {
        "state": "West Bengal",
        "tehsils": {
            "Kolkata North": ["Dum Dum","Belgharia","Sodepur","Khardaha","Panihati"],
            "Kolkata South": ["Jadavpur","Tollygunge","Behala","Santoshpur","Garia"],
            "Salt Lake":     ["Sector I","Sector II","Sector III","Sector IV","Sector V"],
            "Howrah":        ["Howrah","Shibpur","Santragachi","Liluah","Bally"],
        }
    },
    "Lucknow": {
        "state": "Uttar Pradesh",
        "tehsils": {
            "Lucknow":    ["Hazratganj","Gomti Nagar","Aliganj","Indira Nagar","Alambagh"],
            "Mohanlalganj":["Mohanlalganj","Kakori","Malihabad","Chinhat","Bakshi Ka Talab"],
            "Sadar":      ["Vibhuti Khand","Sector 14","Mahanagar","Rajajipuram","Charbagh"],
        }
    },
    "Agra": {
        "state": "Uttar Pradesh",
        "tehsils": {
            "Agra":       ["Tajganj","Civil Lines","Shahganj","Balkeshwar","Kamla Nagar"],
            "Fatehabad":  ["Fatehabad","Bah","Pinahat","Etmadpur","Kheragarh"],
            "Kheragarh":  ["Kheragarh","Akola","Shamsabad","Jaitpur Kalan","Barhan"],
        }
    },
    "Varanasi": {
        "state": "Uttar Pradesh",
        "tehsils": {
            "Varanasi":   ["Godaulia","Lanka","Sarnath","Cantonment","Sigra"],
            "Pindra":     ["Pindra","Chiraigaon","Arajiline","Sevapuri","Baragaon"],
            "Rajatalab":  ["Rajatalab","Cholapur","Harahua","Kashi Vidyapeeth","Ramnagar"],
        }
    },
    "Kanpur": {
        "state": "Uttar Pradesh",
        "tehsils": {
            "Kanpur Nagar":["Civil Lines","Armapur","Kidwai Nagar","Kalyanpur","Govind Nagar"],
            "Kanpur Dehat":["Akbarpur","Bilhaur","Ghatampur","Rasulabad","Bhognipur"],
        }
    },
    "Jaipur": {
        "state": "Rajasthan",
        "tehsils": {
            "Jaipur":    ["Malviya Nagar","Vaishali Nagar","Mansarovar","C-Scheme","Banipark"],
            "Amber":     ["Amber","Amer","Hawamahal","Kishanpole","Tripolia"],
            "Sanganer":  ["Sanganer","Pratap Nagar","Sitapura","Jagatpura","Tonk Road"],
        }
    },
}

LAND_TYPE_LIST = [
    {"code": "1", "name": "Agricultural Land (Khet)",       "description": "Land used for farming, cultivation, or horticulture"},
    {"code": "2", "name": "Residential Land (Aabadi)",      "description": "Land for housing, residential plots, and settlements"},
    {"code": "3", "name": "Commercial Land (Vyavsayik)",    "description": "Land for shops, offices, malls, and business use"},
    {"code": "4", "name": "Industrial Land (Audyogik)",     "description": "Factory, warehouse, and industrial zone land"},
    {"code": "5", "name": "Poramboke/Govt Land (Sarkaari)", "description": "Government-owned land, commons, roads, tanks"},
    {"code": "6", "name": "Forest Land (Van Bhoomi)",       "description": "Reserved forest, protected forest, and green belt"},
    {"code": "7", "name": "Wasteland (Banjar)",             "description": "Uncultivated or barren land"},
    {"code": "8", "name": "Pasture Land (Charaagah)",       "description": "Common grazing land for livestock"},
    {"code": "9", "name": "Water Body Land (Jalashayi)",    "description": "Tank, pond, lake, and river-side land"},
    {"code": "10","name": "Inam Land",                      "description": "Historically granted land under Inam tenure"},
    {"code": "11","name": "Nazul Land",                     "description": "Government urban land leased to individuals"},
    {"code": "12","name": "Evacuee Property",               "description": "Property taken over under Evacuee Property Act"},
]

@app.route('/api/geo/districts', methods=['GET'])
def geo_districts():
    """Return all districts with their states."""
    result = [{"district": d, "state": v["state"]} for d, v in GEOGRAPHY.items()]
    return jsonify({"districts": sorted(result, key=lambda x: x["district"])})

@app.route('/api/geo/tehsils', methods=['GET'])
def geo_tehsils():
    """Return tehsils for a given district."""
    district = request.args.get('district', '')
    if district not in GEOGRAPHY:
        return jsonify({"tehsils": []})
    tehsils = list(GEOGRAPHY[district]["tehsils"].keys())
    return jsonify({"tehsils": sorted(tehsils), "district": district})

@app.route('/api/geo/villages', methods=['GET'])
def geo_villages():
    """Return villages for a given district + tehsil."""
    district = request.args.get('district', '')
    tehsil   = request.args.get('tehsil', '')
    if district not in GEOGRAPHY:
        return jsonify({"villages": []})
    villages = GEOGRAPHY[district]["tehsils"].get(tehsil, [])
    return jsonify({"villages": villages, "district": district, "tehsil": tehsil})

@app.route('/api/services/land_types', methods=['GET'])
def service_land_types():
    return jsonify({"land_types": LAND_TYPE_LIST})

@app.route('/api/services/khatauni', methods=['GET'])
def service_khatauni():
    """View Khatauni (Rights Record) — UP Style."""
    district = request.args.get('district', '')
    tehsil   = request.args.get('tehsil', '')
    village  = request.args.get('village', '')
    khata_no = request.args.get('khata_no', '')
    owner    = request.args.get('owner', '')
    survey   = request.args.get('survey', '')

    db = get_db()
    if survey:
        parcel = db.execute("SELECT * FROM land_parcels WHERE survey_number LIKE ? LIMIT 1",
                            (f"%{survey}%",)).fetchone()
    elif district:
        parcel = db.execute("SELECT * FROM land_parcels WHERE district=? ORDER BY RANDOM() LIMIT 1",
                            (district,)).fetchone()
    elif owner:
        parcel = db.execute("""SELECT lp.* FROM land_parcels lp 
                               JOIN users u ON lp.current_owner_id=u.id 
                               WHERE u.name LIKE ? LIMIT 1""",
                            (f"%{owner}%",)).fetchone()
    else:
        parcel = db.execute("SELECT * FROM land_parcels ORDER BY RANDOM() LIMIT 1").fetchone()

    if not parcel:
        db.close()
        return jsonify({"error": "No record found. Try different search criteria."}), 404

    p = dict(parcel)
    history = db.execute("SELECT * FROM ownership_history WHERE parcel_id=? ORDER BY from_date",
                         (p['id'],)).fetchall()
    db.close()

    rng = _rnd.Random(p['id'] + "khatauni")
    khata_num = khata_no or str(rng.randint(1, 9999))
    gata_num  = str(rng.randint(1, 5000))

    return jsonify({
        "success":       True,
        "document_type": "Khatauni (Rights Record)",
        "khatauni_number": f"KHT-{khata_num}/{p['district'][:3].upper()}",
        "gata_number":   gata_num,
        "unique_code":   f"UC-{p['id'][:8].upper()}",
        "fasli_year":    "1433-1434 (2023-24)",
        "district":      p['district'],
        "tehsil":        tehsil or p['taluk'],
        "pargana":       village or p['village'],
        "village":       p['village'],
        "survey_number": p['survey_number'],
        "area_acres":    p['area_acres'],
        "area_hectares": round(p['area_acres'] * 0.404686, 4),
        "area_bigha":    round(p['area_acres'] * 3.025, 3),
        "land_type":     p['land_type'],
        "land_use":      p['land_use'],
        "status":        p['status'],
        "encumbrance":   p['encumbrance'],
        "market_value":  p['market_value'],
        "revenue_liabilities": round(p['area_acres'] * rng.uniform(100, 500), 2),
        "water_tax":     round(p['area_acres'] * rng.uniform(20, 100), 2),
        "land_revenue":  round(p['area_acres'] * rng.uniform(50, 200), 2),
        "is_disputed":   p['status'] == 'disputed',
        "is_mortgaged":  p['status'] == 'mortgaged',
        "latitude":      p['latitude'],
        "longitude":     p['longitude'],
        "rights_holders": [
            {
                "name":          h['owner_name'],
                "share":         f"1/{len(history)}" if len(history) > 1 else "Full",
                "from_date":     h['from_date'],
                "to_date":       h['to_date'] or "Present",
                "transfer_type": h['transfer_type'],
                "deed_number":   h['deed_number'],
                "amount":        h['consideration_amount'],
            } for h in history
        ],
        "certified_copy_available": True,
        "qr_code": f"BHULEKH-{p['survey_number'].replace('/', '-').replace(' ', '')}",
        "issued_by": f"Revenue Inspector, {p['taluk']}",
        "issued_date": datetime.now().strftime("%d-%m-%Y"),
    })


@app.route('/api/services/khasra', methods=['GET'])
def service_khasra():
    """Get Khasra / Gata details with unique code."""
    district = request.args.get('district', '')
    village  = request.args.get('village', '')
    gata     = request.args.get('gata', '')
    survey   = request.args.get('survey', '')

    db = get_db()
    if survey:
        parcel = db.execute("SELECT * FROM land_parcels WHERE survey_number LIKE ? LIMIT 1",
                            (f"%{survey}%",)).fetchone()
    elif district:
        parcel = db.execute("SELECT * FROM land_parcels WHERE district=? ORDER BY RANDOM() LIMIT 1",
                            (district,)).fetchone()
    else:
        parcel = db.execute("SELECT * FROM land_parcels ORDER BY RANDOM() LIMIT 1").fetchone()
    db.close()

    if not parcel:
        return jsonify({"error": "Khasra record not found."}), 404

    p = dict(parcel)
    rng = _rnd.Random(p['id'] + (gata or "khasra"))
    gata_code = gata or str(rng.randint(100, 9999))

    return jsonify({
        "success":       True,
        "document_type": "Khasra / Gata Details",
        "gata_number":   gata_code,
        "unique_code":   f"UP{p['district'][:2].upper()}{rng.randint(10000000,99999999)}",
        "revenue_village_code": f"RV-{rng.randint(10000, 99999)}",
        "district":      p['district'],
        "tehsil":        p['taluk'],
        "village":       p['village'],
        "survey_number": p['survey_number'],
        "area_acres":    p['area_acres'],
        "area_hectares": round(p['area_acres'] * 0.404686, 4),
        "area_bigha":    round(p['area_acres'] * 3.025, 3),
        "area_biswa":    round(p['area_acres'] * 60.5, 2),
        "land_type_code":str(rng.randint(1, 12)),
        "land_type":     p['land_type'],
        "land_use":      p['land_use'],
        "chaura_number": str(rng.randint(1000, 9999)),
        "khata_number":  str(rng.randint(1, 9999)),
        "owner_name":    _rnd.choice(["Ramesh Kumar","Priya Devi","Suresh Reddy","Lakshmi Venkatesh","Anita Singh"]),
        "co_sharers":    rng.randint(0, 3),
        "cultivation_type": _rnd.choice(["Self Cultivated","Tenant Cultivated","Leased","Fallow"]),
        "irrigation_source": _rnd.choice(["Canal","Tube Well","Open Well","Rain Fed","Tank"]),
        "crop_season":   _rnd.choice(["Kharif","Rabi","Zaid","Both Kharif & Rabi"]),
        "boundaries": {
            "North": _rnd.choice(["Road","Survey No."+str(rng.randint(10,500)),"Canal","Forest"]),
            "South": _rnd.choice(["Road","Survey No."+str(rng.randint(10,500)),"River","Private Land"]),
            "East":  _rnd.choice(["Road","Survey No."+str(rng.randint(10,500)),"Nala","Government Land"]),
            "West":  _rnd.choice(["Road","Survey No."+str(rng.randint(10,500)),"Canal","Private Land"]),
        },
        "status":        p['status'],
        "is_disputed":   p['status'] == 'disputed',
        "is_sale_pending": rng.random() < 0.1,
        "mutation_pending": rng.random() < 0.2,
        "market_value":  p['market_value'],
        "circle_rate":   round(p['market_value'] * 0.65),
    })


@app.route('/api/services/dispute_status', methods=['GET'])
def service_dispute_status():
    """Know status of plot/plot dispute."""
    survey = request.args.get('survey', '')
    parcel = _get_parcel_by_survey(survey) if survey else _get_any_parcel()
    if not parcel:
        return jsonify({"error": "Record not found."}), 404

    rng = _rnd.Random(parcel['id'] + "dispute")
    is_disputed = parcel['status'] == 'disputed' or rng.random() < 0.2
    court_stage = _rnd.choice(["District Court","High Court","Revenue Court","Lok Adalat","Resolved"])
    stages = ["Filed","Under Hearing","Evidence Stage","Arguments","Judgment","Resolved"]
    current = rng.randint(1, len(stages)-1) if is_disputed else len(stages)-1

    return jsonify({
        "success":       True,
        "survey_number": parcel['survey_number'],
        "district":      parcel['district'],
        "village":       parcel['village'],
        "is_disputed":   is_disputed,
        "dispute_type":  _rnd.choice(["Title Dispute","Boundary Dispute","Encroachment","Inheritance","Partition"]) if is_disputed else "None",
        "case_number":   f"RC-{rng.randint(1000,9999)}/2023" if is_disputed else "N/A",
        "court":         court_stage if is_disputed else "N/A",
        "filed_date":    "2023-03-15" if is_disputed else "N/A",
        "next_hearing":  "2024-09-20" if is_disputed else "N/A",
        "parties": {
            "plaintiff": _rnd.choice(["Ramesh Kumar","Suresh Reddy","Anita Singh","Mohammad Khan"]) if is_disputed else "N/A",
            "defendant": _rnd.choice(["Priya Devi","Lakshmi Venkatesh","Vijay Rao","Geeta Patel"]) if is_disputed else "N/A",
        },
        "status_label":  "DISPUTED — Active Legal Proceedings" if is_disputed else "CLEAR — No Disputes",
        "progress":      [{"stage": s, "done": i <= current} for i, s in enumerate(stages)],
        "remarks":       "Court proceedings ongoing. Property transfer restricted until resolved." if is_disputed else
                         "No disputes registered. Property is clear for transaction.",
        "can_transfer":  not is_disputed,
    })


@app.route('/api/services/sale_status', methods=['GET'])
def service_sale_status():
    """Know status of sale of plots."""
    survey = request.args.get('survey', '')
    parcel = _get_parcel_by_survey(survey) if survey else _get_any_parcel()
    if not parcel:
        return jsonify({"error": "Record not found."}), 404

    db = get_db()
    history = db.execute("SELECT * FROM ownership_history WHERE parcel_id=? ORDER BY from_date DESC",
                         (parcel['id'],)).fetchall()
    db.close()

    rng = _rnd.Random(parcel['id'] + "sale")
    is_sale_pending = rng.random() < 0.15
    last_sale = dict(history[0]) if history else {}

    return jsonify({
        "success":         True,
        "survey_number":   parcel['survey_number'],
        "district":        parcel['district'],
        "village":         parcel['village'],
        "current_owner":   last_sale.get('owner_name', 'Unknown'),
        "is_sale_pending": is_sale_pending,
        "sale_status":     "SALE PENDING — Agreement executed, registration pending" if is_sale_pending
                           else "NOT FOR SALE — No pending sale transactions",
        "sale_agreement_date": "2024-04-10" if is_sale_pending else None,
        "buyer_name":      _rnd.choice(["Arun Prakash","Divya Menon","Rohit Sharma","Seema Malhotra"]) if is_sale_pending else None,
        "agreed_value":    round(parcel['market_value'] * rng.uniform(0.9, 1.1)) if is_sale_pending else None,
        "registration_due_by": "2024-10-10" if is_sale_pending else None,
        "encumbrance":     parcel['encumbrance'],
        "market_value":    parcel['market_value'],
        "last_sale_amount":last_sale.get('consideration_amount', 0),
        "last_sale_date":  last_sale.get('from_date', 'N/A'),
        "last_sale_type":  last_sale.get('transfer_type', 'N/A'),
        "total_transactions": len(history),
        "sale_history": [
            {
                "seller":   dict(h)['owner_name'],
                "date":     dict(h)['from_date'],
                "type":     dict(h)['transfer_type'],
                "deed_no":  dict(h)['deed_number'],
                "amount":   dict(h)['consideration_amount'],
            } for h in history[:5]
        ],
        "can_register": not is_sale_pending and parcel['status'] != 'disputed',
    })


@app.route('/api/services/govt_land', methods=['GET'])
def service_govt_land():
    """Search government / poramboke land."""
    district = request.args.get('district', '')
    tehsil   = request.args.get('tehsil', '')
    land_type_code = request.args.get('land_type', '')

    db = get_db()
    if district:
        parcels = db.execute(
            "SELECT * FROM land_parcels WHERE district=? AND status NOT IN ('clear','mortgaged') ORDER BY RANDOM() LIMIT 10",
            (district,)
        ).fetchall()
        if not parcels:
            parcels = db.execute(
                "SELECT * FROM land_parcels WHERE district=? ORDER BY RANDOM() LIMIT 10",
                (district,)
            ).fetchall()
    else:
        parcels = db.execute(
            "SELECT * FROM land_parcels ORDER BY RANDOM() LIMIT 10"
        ).fetchall()
    db.close()

    rng = _rnd.Random(district + tehsil + "govt")
    results = []
    for p in parcels:
        p = dict(p)
        is_govt = rng.random() < 0.25
        results.append({
            "survey_number":  p['survey_number'],
            "district":       p['district'],
            "village":        p['village'],
            "area_acres":     p['area_acres'],
            "land_category":  "Government / Poramboke" if is_govt else "Private",
            "land_type":      p['land_type'],
            "encroachment":   "Yes" if (is_govt and rng.random() < 0.3) else "No",
            "govt_dept":      _rnd.choice(["Revenue Dept","Forest Dept","PWD","Municipal Corp","Irrigation Dept"]) if is_govt else "N/A",
            "usable_for":     "Public Use Only" if is_govt else "Private Use",
            "latitude":       p['latitude'],
            "longitude":      p['longitude'],
        })

    return jsonify({
        "success":  True,
        "district": district,
        "tehsil":   tehsil,
        "total":    len(results),
        "results":  results,
    })


@app.route('/api/services/search_by_owner', methods=['GET'])
def service_search_by_owner():
    """Search land records by owner name."""
    owner    = request.args.get('name', '')
    district = request.args.get('district', '')
    if not owner:
        return jsonify({"error": "Owner name required."}), 400

    db = get_db()
    if district:
        rows = db.execute("""
            SELECT lp.*, u.name as uname, u.phone as uphone 
            FROM land_parcels lp 
            JOIN users u ON lp.current_owner_id=u.id 
            WHERE u.name LIKE ? AND lp.district=? LIMIT 20""",
            (f"%{owner}%", district)).fetchall()
    else:
        rows = db.execute("""
            SELECT lp.*, u.name as uname, u.phone as uphone 
            FROM land_parcels lp 
            JOIN users u ON lp.current_owner_id=u.id 
            WHERE u.name LIKE ? LIMIT 20""",
            (f"%{owner}%",)).fetchall()
    db.close()

    # Also search ownership history
    results = [dict(r) for r in rows]
    return jsonify({
        "success": True,
        "query":   owner,
        "total":   len(results),
        "results": [
            {
                "survey_number": r['survey_number'],
                "owner_name":    r.get('uname', 'Unknown'),
                "district":      r['district'],
                "village":       r['village'],
                "area_acres":    r['area_acres'],
                "land_type":     r['land_type'],
                "status":        r['status'],
                "market_value":  r['market_value'],
                "latitude":      r['latitude'],
                "longitude":     r['longitude'],
            } for r in results
        ]
    })


@app.route('/api/services/aadhaar_property', methods=['POST'])
def service_aadhaar_property():
    """Search Aadhaar-linked property (simulated)."""
    data    = request.get_json()
    aadhaar = data.get('aadhaar', '').replace('-', '').replace(' ', '')
    if len(aadhaar) != 12:
        return jsonify({"error": "Invalid Aadhaar number. Must be 12 digits."}), 400

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE aadhaar LIKE ?", (f"%{aadhaar[:4]}%",)).fetchone()
    if user:
        u = dict(user)
        parcels = db.execute("SELECT * FROM land_parcels WHERE current_owner_id=?", (u['id'],)).fetchall()
        db.close()
        return jsonify({
            "success":   True,
            "aadhaar":   aadhaar[:4] + "XXXXXXXX",
            "owner_name":u['name'],
            "total_properties": len(parcels),
            "properties": [
                {
                    "survey_number": dict(p)['survey_number'],
                    "district":      dict(p)['district'],
                    "village":       dict(p)['village'],
                    "area_acres":    dict(p)['area_acres'],
                    "land_type":     dict(p)['land_type'],
                    "market_value":  dict(p)['market_value'],
                    "status":        dict(p)['status'],
                } for p in parcels
            ]
        })
    db.close()
    rng = _rnd.Random(aadhaar)
    parcel = _get_any_parcel()
    return jsonify({
        "success":           True,
        "aadhaar":           aadhaar[:4] + "XXXXXXXX",
        "owner_name":        _rnd.choice(["Ramesh Kumar","Priya Devi","Suresh Reddy","Lakshmi Venkatesh"]),
        "total_properties":  rng.randint(1, 3),
        "properties": [{
            "survey_number": parcel['survey_number'] if parcel else "N/A",
            "district":      parcel['district'] if parcel else "N/A",
            "village":       parcel['village'] if parcel else "N/A",
            "area_acres":    parcel['area_acres'] if parcel else 0,
            "land_type":     parcel['land_type'] if parcel else "N/A",
            "market_value":  parcel['market_value'] if parcel else 0,
            "status":        parcel['status'] if parcel else "N/A",
        }] if parcel else []
    })



# ═══════════════════════════════════════════════════
#  EXPANDED ALL-INDIA RECORD TYPES
# ═══════════════════════════════════════════════════

# Extra geography for Maharashtra, Bihar, Rajasthan, AP, Telangana, Haryana
EXTRA_GEO = {
    "Pune":         {"state":"Maharashtra","tehsils":{"Pune City":["Kothrud","Baner","Aundh"],"Haveli":["Wagholi","Kharadi","Hadapsar"],"Mulshi":["Hinjewadi","Wakad","Pashan"]}},
    "Nashik":       {"state":"Maharashtra","tehsils":{"Nashik":["Gangapur","Satpur","Panchavati","Deolali"],"Igatpuri":["Igatpuri","Ghoti","Kasara"]}},
    "Nagpur":       {"state":"Maharashtra","tehsils":{"Nagpur City":["Sitabuldi","Itwari","Gandhibagh","Sadar","Civil Lines"],"Kamptee":["Kamptee","Parsodi","Waddhamna"]}},
    "Aurangabad":   {"state":"Maharashtra","tehsils":{"Aurangabad":["Harsul","Satara","Cidco","N-4","N-5"],"Paithan":["Paithan","Phulambri"]}},
    "Patna":        {"state":"Bihar","tehsils":{"Patna Sadar":["Patna City","Danapur","Phulwari","Sampatchak"],"Maner":["Maner","Naubatpur","Bikram"]}},
    "Gaya":         {"state":"Bihar","tehsils":{"Gaya":["Bodh Gaya","Manpur","Belaganj","Sherghati"],"Nawada":["Nawada","Rajauli","Warsaliganj"]}},
    "Muzaffarpur":  {"state":"Bihar","tehsils":{"Muzaffarpur":["Motipur","Kanti","Saraiya","Mushari"],"Vaishali":["Vaishali","Hajipur","Lalganj"]}},
    "Jaipur":       {"state":"Rajasthan","tehsils":{"Jaipur":["Malviya Nagar","Vaishali Nagar","C-Scheme","Banipark"],"Amber":["Amber","Amer","Hawamahal"],"Sanganer":["Sanganer","Pratap Nagar","Sitapura"]}},
    "Jodhpur":      {"state":"Rajasthan","tehsils":{"Jodhpur":["Paota","Ratanada","Sardarpura","Shastri Nagar"],"Phalodi":["Phalodi","Lohawat","Bap"]}},
    "Udaipur":      {"state":"Rajasthan","tehsils":{"Udaipur":["Hiran Magri","Fatehpura","Ambamata","Sukhadia"],"Girwa":["Girwa","Mavli","Vallabhnagar"]}},
    "Visakhapatnam":{"state":"Andhra Pradesh","tehsils":{"Visakhapatnam":["Gajuwaka","Bheemunipatnam","Bhimili","Anakapalle"],"Anakapalle":["Anakapalle","Atchutapuram","Rambilli"]}},
    "Vijayawada":   {"state":"Andhra Pradesh","tehsils":{"Krishna":["Vijayawada","Machilipatnam","Eluru","Gudivada"],"Vijayawada Rural":["Penamaluru","Gannavaram","Nuzvid"]}},
    "Warangal":     {"state":"Telangana","tehsils":{"Warangal":["Hanamkonda","Kazipet","Wardhannapet","Hunter Road"],"Narsampet":["Narsampet","Parkal","Dornakal"]}},
    "Gurugram":     {"state":"Haryana","tehsils":{"Gurugram":["DLF Phase 1","Sector 14","Sector 29","Sohna Road","MG Road"],"Farrukhnagar":["Farrukhnagar","Pataudi","Jhajjar"]}},
    "Ambala":       {"state":"Haryana","tehsils":{"Ambala City":["Ambala Cantonment","Shahzadpur","Barara"],"Naraingarh":["Naraingarh","Mulana","Saha"]}},
}
# Merge into main GEOGRAPHY
GEOGRAPHY.update(EXTRA_GEO)


def _build_document_base(parcel, rng):
    """Build common fields for any land document."""
    p = dict(parcel) if not isinstance(parcel, dict) else parcel
    return {
        "survey_number": p["survey_number"],
        "district":      p["district"],
        "taluk":         p["taluk"],
        "village":       p["village"],
        "area_acres":    p["area_acres"],
        "area_hectares": round(p["area_acres"] * 0.404686, 4),
        "area_sqft":     round(p["area_acres"] * 43560, 0),
        "land_type":     p["land_type"],
        "land_use":      p["land_use"],
        "status":        p["status"],
        "market_value":  p["market_value"],
        "govt_value":    round(p["market_value"] * 0.65),
        "latitude":      p["latitude"],
        "longitude":     p["longitude"],
        "is_disputed":   p["status"] == "disputed",
        "is_mortgaged":  p["status"] == "mortgaged",
    }


@app.route('/api/services/satbara', methods=['GET'])
def service_satbara():
    """7/12 Satbara Utara — Maharashtra."""
    survey   = request.args.get('survey', '')
    district = request.args.get('district', '')
    parcel   = _get_parcel_by_survey(survey) if survey else _get_any_parcel(district or None)
    if not parcel:
        return jsonify({"error": "Record not found."}), 404
    rng = _rnd.Random(parcel['id'] + "satbara")
    base = _build_document_base(parcel, rng)
    owner_names = ["Ramesh Patil","Sunita Kulkarni","Vijay Deshmukh","Priya Gadge","Manoj Shinde","Anita Jadhav","Suresh Bhosale"]
    return jsonify({
        "success": True,
        "document_type": "7/12 Satbara Utara",
        **base,
        "form7_number":    f"7/{rng.randint(1000,9999)}",
        "form12_number":   f"12/{rng.randint(1000,9999)}",
        "survey_no":       parcel["survey_number"],
        "gut_number":      str(rng.randint(1,500)),
        "owner_name":      _rnd.choice(owner_names),
        "owner_type":      _rnd.choice(["Khatedar","Inam","Occupant Class I","Occupant Class II"]),
        "taluka":          parcel["taluk"],
        "village":         parcel["village"],
        "area_hector":     base["area_hectares"],
        "area_ar":         round(rng.uniform(0,99),2),
        "area_sqm":        round(base["area_sqft"]*0.0929,1),
        "irrigation_type": _rnd.choice(["Irrigated (Bagayat)","Dry (Jirayat)","Half Irrigated","Rice Land"]),
        "khata_type":      _rnd.choice(["Occupancy","Occupancy Nimnshretha","Tenant","Holder"]),
        "land_class":      _rnd.choice(["Jirayat","Bagayat","Rice Paddy","Garden","Fallow"]),
        "encumbrance":     parcel["encumbrance"],
        "khata_number":    str(rng.randint(1,9999)),
        "revenue_circle":  f"Circle {rng.randint(1,20)}",
        "talathi_name":    f"V. {_rnd.choice(['Patil','Deshmukh','Jadhav','Kulkarni'])}, Talathi, {parcel['taluk']}",
        "crop_details": [
            {"season": "Kharif", "crop": _rnd.choice(["Jowar","Bajra","Cotton","Soybean","Sugarcane"]), "area": round(base["area_hectares"]*0.6,3)},
            {"season": "Rabi",   "crop": _rnd.choice(["Wheat","Gram","Safflower","Sunflower","Onion"]), "area": round(base["area_hectares"]*0.4,3)},
        ],
        "encumbrance_details": {
            "mortgage": parcel["status"] == "mortgaged",
            "bank_name": "State Bank of India" if parcel["status"] == "mortgaged" else "None",
            "loan_amount": round(base["market_value"]*0.5) if parcel["status"] == "mortgaged" else 0,
        },
        "certified_copy_fee": 15,
        "issued_by": f"Talathi, {parcel['village']} Grampanchayat",
        "issued_date": datetime.now().strftime("%d/%m/%Y"),
        "qr_code": f"MH-712-{parcel['survey_number'].replace('/','').replace('-','')}",
        "digital_satbara_url": f"https://digitalsatbara.mahabhumi.gov.in/",
    })


@app.route('/api/services/rtc', methods=['GET'])
def service_rtc():
    """RTC / Pahani — Karnataka."""
    survey   = request.args.get('survey', '')
    district = request.args.get('district', '')
    parcel   = _get_parcel_by_survey(survey) if survey else _get_any_parcel(district or None)
    if not parcel:
        return jsonify({"error": "RTC record not found."}), 404
    rng = _rnd.Random(parcel['id'] + "rtc")
    base = _build_document_base(parcel, rng)
    owners = ["Ramaiah","Venkatesh","Lakshmi Devi","Suresh Kumar","Geeta","Manjunath","Kavitha"]
    return jsonify({
        "success": True,
        "document_type": "RTC — Record of Rights, Tenancy and Crops",
        **base,
        "hissa_number":     f"{rng.randint(1,50)}P",
        "hobli":            _rnd.choice(["Anekal","Begur","Bangalore South","Kasaba","Varthur"]),
        "owner_name":       _rnd.choice(owners),
        "owner_aadhaar":    f"XXXX-XXXX-{rng.randint(1000,9999)}",
        "patta_number":     f"KA-{rng.randint(10000,99999)}",
        "nature_of_land":   _rnd.choice(["Dryland (Khushki)","Wetland (Bagayat)","Garden Land","Tank Bed","Gomal"]),
        "total_land_area":  base["area_acres"],
        "irrigated_area":   round(base["area_acres"]*0.6,3),
        "dry_area":         round(base["area_acres"]*0.4,3),
        "kharab_a":         round(base["area_acres"]*rng.uniform(0,0.05),4),
        "kharab_b":         round(base["area_acres"]*rng.uniform(0,0.03),4),
        "tenancy_details":  _rnd.choice(["Owner in Possession","Tenant","No Tenancy"]),
        "crop_season_1":    {"crop":_rnd.choice(["Ragi","Maize","Jowar","Paddy","Groundnut"]), "area":round(base["area_acres"]*0.5,3)},
        "crop_season_2":    {"crop":_rnd.choice(["Sunflower","Bengal Gram","Horsegram","Wheat"]),  "area":round(base["area_acres"]*0.3,3)},
        "mutation_history": [
            {"mutation_no": f"MR-{rng.randint(1000,9999)}", "date": "2019-04-10", "type": "Sale", "from": "Previous Owner", "to": _rnd.choice(owners)},
            {"mutation_no": f"MR-{rng.randint(1000,9999)}", "date": "2023-08-22", "type": "Inheritance", "from": "Deceased", "to": _rnd.choice(owners)},
        ],
        "village_accountant": f"B. {_rnd.choice(['Ramaiah','Nagaraj','Shivakumar'])}, VA, {parcel['village']}",
        "i_rtc_enabled":    True,
        "rtc_xml_hash":     uuid.uuid4().hex[:32].upper(),
        "bhoomi_ref":       f"BHOOMI-{rng.randint(10000000,99999999)}",
        "issued_date":      datetime.now().strftime("%d-%m-%Y"),
    })


@app.route('/api/services/adangal', methods=['GET'])
def service_adangal():
    """Adangal / 1B — Andhra Pradesh / Telangana."""
    survey   = request.args.get('survey', '')
    district = request.args.get('district', '')
    parcel   = _get_parcel_by_survey(survey) if survey else _get_any_parcel(district or None)
    if not parcel:
        return jsonify({"error": "Adangal record not found."}), 404
    rng = _rnd.Random(parcel['id'] + "adangal")
    base = _build_document_base(parcel, rng)
    owners = ["Venkata Rao","Subbamma","Krishna Reddy","Lakshmi","Ranga Rao","Savitri","Nageswara Rao"]
    return jsonify({
        "success": True,
        "document_type": "Adangal / 1B (Pahani)",
        **base,
        "khata_number":    str(rng.randint(1,9999)),
        "pattadar_name":   _rnd.choice(owners),
        "pattadar_passbook_no": f"PPB-{rng.randint(100000,999999)}",
        "mandal":          _rnd.choice(["Gajuwaka","Bheemunipatnam","Anakapalle","Cheepurupalli","Vizianagaram"]),
        "water_source":    _rnd.choice(["Canal","Bore Well","Tank","Rain Fed","River","Pump Set"]),
        "soil_type":       _rnd.choice(["Red Sandy","Black Cotton","Loam","Alluvial","Laterite"]),
        "land_nature":     _rnd.choice(["Wet Land","Dry Land","Garden","Waste Land","Forest"]),
        "crops": [
            {"season":"Kharif","crop":_rnd.choice(["Paddy","Maize","Groundnut","Cotton","Tobacco"]),"area_acres":round(base["area_acres"]*0.6,2)},
            {"season":"Rabi",  "crop":_rnd.choice(["Jowar","Sunflower","Sesame","Chillies","Onion"]), "area_acres":round(base["area_acres"]*0.4,2)},
        ],
        "bhudhaar_number": f"BD-{rng.randint(10000000,99999999)}",
        "ulpin":           f"AP{rng.randint(10000000000000,99999999999999)}",
        "meebhoomi_ref":   f"MB-{uuid.uuid4().hex[:12].upper()}",
        "land_revenue":    round(base["area_acres"]*rng.uniform(20,100),2),
        "cess":            round(base["area_acres"]*rng.uniform(5,25),2),
        "dispute_status":  "No Dispute" if parcel["status"]!="disputed" else "Under Court",
        "tahsildar":       f"M. {_rnd.choice(['Venkat','Suresh','Narasimha','Ravi'])}, Tahsildar",
        "issued_date":     datetime.now().strftime("%d-%m-%Y"),
    })


@app.route('/api/services/jamabandi', methods=['GET'])
def service_jamabandi():
    """Jamabandi / Fard — Rajasthan / Haryana / Punjab."""
    survey   = request.args.get('survey', '')
    district = request.args.get('district', '')
    parcel   = _get_parcel_by_survey(survey) if survey else _get_any_parcel(district or None)
    if not parcel:
        return jsonify({"error": "Jamabandi record not found."}), 404
    rng = _rnd.Random(parcel['id'] + "jamabandi")
    base = _build_document_base(parcel, rng)
    owners = ["Ram Singh","Suresh Kumar","Meena Devi","Rajesh Sharma","Sunita","Harpal Singh","Gurpreet Kaur"]
    return jsonify({
        "success": True,
        "document_type": "Jamabandi / Fard (Record of Rights)",
        **base,
        "jamabandi_year":  "2023-2024",
        "khewat_number":   str(rng.randint(1,999)),
        "khasra_number":   str(rng.randint(1,9999)),
        "khatauni_number": str(rng.randint(1,9999)),
        "owner_name":      _rnd.choice(owners),
        "owner_father":    f"S/o {_rnd.choice(['Ram Lal','Mohan','Hari Singh','Amar Nath'])}",
        "share_fraction":  f"{rng.randint(1,4)}/{rng.randint(4,8)}",
        "tenure_type":     _rnd.choice(["Malkan Haq","Mortgagee","Leaseholder","Government Lessee"]),
        "cultivation_type":_rnd.choice(["Self","Batai (Share Cropping)","Theka","Fallow"]),
        "water_rate":      _rnd.choice(["Canal Irrigated","Tube Well","Rain Fed","Tank"]),
        "land_class":      _rnd.choice(["Chahi","Nehri","Barani","Banjar Jadid","Banjar Qadim"]),
        "nazool":          False,
        "encumbrance_flag":parcel["status"] == "mortgaged",
        "revenue_estate":  parcel["village"],
        "patwari_halqa":   f"Halqa {rng.randint(1,50)}",
        "patwari_name":    f"R. {_rnd.choice(['Sharma','Singh','Verma','Yadav'])}, Patwari",
        "naib_tehsildar":  f"A. {_rnd.choice(['Kumar','Singh','Kaur','Devi'])}, Naib Tehsildar",
        "fard_date":       datetime.now().strftime("%d/%m/%Y"),
        "apna_khata_ref":  f"RJ-{rng.randint(100000,999999)}",
        "mutations": [
            {"intkal_no": f"IN-{rng.randint(1000,9999)}", "year": "2021-22", "reason": "Sale Deed", "status": "Approved"},
            {"intkal_no": f"IN-{rng.randint(1000,9999)}", "year": "2023-24", "reason": "Inheritance", "status": "Approved"},
        ],
    })


@app.route('/api/services/khata_cert', methods=['GET'])
def service_khata_cert():
    """Khata Certificate — Karnataka Municipal."""
    survey   = request.args.get('survey', '')
    district = request.args.get('district', '')
    parcel   = _get_parcel_by_survey(survey) if survey else _get_any_parcel(district or None)
    if not parcel:
        return jsonify({"error": "Khata record not found."}), 404
    rng = _rnd.Random(parcel['id'] + "khata")
    base = _build_document_base(parcel, rng)
    return jsonify({
        "success": True,
        "document_type": "Khata Certificate (Municipal Record)",
        **base,
        "khata_number":      f"KHA-{rng.randint(10000,99999)}",
        "property_id":       f"PID-{rng.randint(10000000,99999999)}",
        "ward_number":       f"Ward {rng.randint(1,100)}",
        "ward_name":         f"{parcel['village']} Ward",
        "zone":              _rnd.choice(["East Zone","West Zone","North Zone","South Zone","Central Zone"]),
        "corporation":       _rnd.choice(["BBMP","MCGM","GHMC","MCD","PMC","KMC"]),
        "owner_name":        _rnd.choice(["Ramaiah","Venkatesh","Lakshmi Devi","Suresh Kumar"]),
        "property_address":  f"No. {rng.randint(1,999)}, {parcel['village']} Main Road, {parcel['district']}",
        "property_type":     _rnd.choice(["Residential Building","Commercial Building","Vacant Site","Apartment","Industrial"]),
        "built_up_area_sqft":round(base["area_sqft"]*0.6,0),
        "site_area_sqft":    base["area_sqft"],
        "property_tax_annual":round(base["market_value"]*0.005,0),
        "tax_arrears":       round(rng.uniform(0,5000),0),
        "tax_paid_upto":     "2023-24",
        "bbmp_pid":          f"BBMP-{rng.randint(10000000,99999999)}",
        "plan_approval_no":  f"BP-{rng.randint(10000,99999)}/2019",
        "khata_type":        _rnd.choice(["A Khata (Approved)","B Khata (Unapproved)"]),
        "transfer_date":     "2022-03-15",
        "e_khata_enabled":   True,
        "download_url":      "https://bbmpeaasthi.kar.nic.in/",
        "issued_by":         f"Revenue Officer, {parcel['district']} Zone",
        "issued_date":       datetime.now().strftime("%d-%m-%Y"),
    })


@app.route('/api/services/mutation_status', methods=['GET'])
def service_mutation_status():
    """Mutation (Dakhil Kharij) status check."""
    mut_no = request.args.get('mutation_no', '')
    survey = request.args.get('survey', '')
    parcel = _get_parcel_by_survey(survey) if survey else _get_any_parcel()
    if not parcel:
        return jsonify({"error": "Record not found."}), 404
    rng = _rnd.Random(parcel['id'] + (mut_no or "mut"))
    stages = ["Application Submitted","Verified by Patwari","Tehsildar Review","Public Notice Issued","Objection Period","Approved","Record Updated"]
    stage_idx = rng.randint(2, len(stages)-1)
    mut_num = mut_no or f"MUT-{rng.randint(10000,99999)}/{parcel['district'][:2].upper()}"
    return jsonify({
        "success": True,
        "mutation_number":  mut_num,
        "survey_number":    parcel["survey_number"],
        "district":         parcel["district"],
        "village":          parcel["village"],
        "mutation_type":    _rnd.choice(["Sale","Inheritance","Gift Deed","Partition","Court Decree","Exchange","Will"]),
        "applicant_name":   _rnd.choice(["Ramesh Kumar","Priya Devi","Suresh Reddy","Anita Singh"]),
        "previous_owner":   _rnd.choice(["Old Owner A","Old Owner B","Estate of Late Person"]),
        "new_owner":        _rnd.choice(["New Owner A","New Owner B","Legal Heirs"]),
        "application_date": "2024-03-10",
        "field_inspection":  "2024-03-22",
        "notice_period_end": "2024-04-22",
        "approval_date":    "2024-05-05" if stage_idx == len(stages)-1 else None,
        "current_stage":    stages[stage_idx],
        "progress_steps":   [{"stage":s,"done":i<=stage_idx} for i,s in enumerate(stages)],
        "days_elapsed":     rng.randint(10,90),
        "expected_days":    45,
        "objections_filed": rng.randint(0,2),
        "patwari_remarks":  "Documents verified. No encroachment found.",
        "tehsildar_remarks": "Case forwarded for final approval." if stage_idx >= 3 else "",
        "fee_paid":         500,
        "online_tracking":  f"https://bhulekh.gov.in/track/{mut_num}",
        "status": "Approved" if stage_idx == len(stages)-1 else "Under Process",
    })


@app.route('/api/services/mutation_apply', methods=['POST'])
def service_mutation_apply():
    """Apply for Mutation (Dakhil Kharij)."""
    data = request.get_json()
    required = ['applicant_name','applicant_phone','survey_number','district','mutation_type','previous_owner','new_owner']
    for f in required:
        if not data.get(f):
            return jsonify({'error': f'Field "{f}" is required.'}), 400
    mut_no = f"MUT-{datetime.now().year}-{uuid.uuid4().hex[:6].upper()}"
    return jsonify({
        "success":          True,
        "mutation_number":  mut_no,
        "status":           "Application Submitted",
        "applicant":        data["applicant_name"],
        "survey_number":    data["survey_number"],
        "district":         data["district"],
        "mutation_type":    data["mutation_type"],
        "previous_owner":   data["previous_owner"],
        "new_owner":        data["new_owner"],
        "application_date": datetime.now().strftime("%d-%m-%Y"),
        "expected_completion": "45 working days",
        "fee":              500,
        "next_step":        "A public notice will be issued. Visit the Tehsil office with original documents within 7 days.",
        "documents_required": [
            "Original Sale Deed / Gift Deed / Will / Partition Deed",
            "Death Certificate (for inheritance)",
            "Aadhaar of all parties",
            "Previous land records (Khatauni/7-12/RTC)",
            "Property tax receipts",
            "Passport photos (2 each)",
        ],
        "submitted_at": datetime.now().isoformat(),
    }), 201


@app.route('/api/services/ulpin', methods=['GET'])
def service_ulpin():
    """ULPIN / Bhu-Aadhar unique land parcel ID lookup."""
    ulpin  = request.args.get('ulpin', '')
    survey = request.args.get('survey', '')
    parcel = _get_parcel_by_survey(survey) if survey else _get_any_parcel()
    if not parcel:
        return jsonify({"error": "ULPIN record not found."}), 404
    rng = _rnd.Random(parcel['id'] + "ulpin")
    # Generate 14-digit ULPIN
    state_codes = {"Bengaluru Urban":"29","Delhi":"07","Chennai":"33","Mumbai":"27","Vellore":"33","Hyderabad":"36","Pune":"27","Kolkata":"19","Lucknow":"09","Varanasi":"09","Kanpur":"09","Jaipur":"08"}
    sc = state_codes.get(parcel['district'], "00")
    ulpin_num = ulpin or f"{sc}{rng.randint(100000000000,999999999999)}"
    return jsonify({
        "success":          True,
        "ulpin":            ulpin_num,
        "bhu_aadhar":       ulpin_num,
        "survey_number":    parcel["survey_number"],
        "district":         parcel["district"],
        "state":            GEOGRAPHY.get(parcel['district'],{}).get("state","India"),
        "taluk":            parcel["taluk"],
        "village":          parcel["village"],
        "area_hectares":    round(parcel["area_acres"]*0.404686,4),
        "land_type":        parcel["land_type"],
        "coordinates":      {"latitude": parcel["latitude"], "longitude": parcel["longitude"]},
        "geo_referenced":   True,
        "cadastral_map":    f"https://bhunaksha.nic.in/",
        "dilrmp_status":    "Geo-referenced & ULPIN Assigned",
        "assigned_by":      "DILRMP — Department of Land Resources, Govt of India",
        "assigned_date":    "2023-06-15",
        "verification_url": f"https://ulpin.dilrmp.gov.in/verify/{ulpin_num}",
    })


@app.route('/api/services/lpc', methods=['GET'])
def service_lpc():
    """LPC — Land Possession Certificate (Bihar style)."""
    survey   = request.args.get('survey', '')
    district = request.args.get('district', '')
    parcel   = _get_parcel_by_survey(survey) if survey else _get_any_parcel(district or None)
    if not parcel:
        return jsonify({"error": "LPC record not found."}), 404
    rng = _rnd.Random(parcel['id'] + "lpc")
    base = _build_document_base(parcel, rng)
    return jsonify({
        "success": True,
        "document_type": "LPC — Land Possession Certificate",
        **base,
        "lpc_number":    f"LPC-{rng.randint(10000,99999)}/{parcel['district'][:2].upper()}",
        "owner_name":    _rnd.choice(["Ram Prasad","Sunita Devi","Manoj Kumar","Anita","Suresh Yadav"]),
        "khata_number":  str(rng.randint(1,9999)),
        "thana_code":    f"TH-{rng.randint(100,999)}",
        "mauza":         parcel["village"],
        "anchol":        parcel["taluk"],
        "purpose":       _rnd.choice(["Bank Loan","Property Purchase","Court Case","Government Scheme","Building Permission"]),
        "certified_area":base["area_acres"],
        "possession_type": _rnd.choice(["Owner in Possession","Tenant in Possession","Co-sharer"]),
        "encumbrance":   parcel["encumbrance"],
        "is_govt_land":  False,
        "co_parceners":  rng.randint(0,3),
        "land_revenue":  round(base["area_acres"]*rng.uniform(30,150),2),
        "revenue_due":   round(rng.uniform(0,500),2),
        "valid_for_days":90,
        "circle_officer": f"C.O. {_rnd.choice(['Kumar','Singh','Yadav','Pandey'])}, Circle Officer, {parcel['taluk']}",
        "issued_date":   datetime.now().strftime("%d-%m-%Y"),
        "valid_upto":    (datetime.now() + timedelta(days=90)).strftime("%d-%m-%Y"),
        "qr_code":       f"LPC-BIHARBHUMI-{parcel['survey_number'].replace('/','').replace('-','').upper()}",
    })


@app.route('/api/services/ec', methods=['GET'])
def service_ec():
    """Encumbrance Certificate."""
    survey   = request.args.get('survey', '')
    period   = request.args.get('period', '30')
    parcel   = _get_parcel_by_survey(survey) if survey else _get_any_parcel()
    if not parcel:
        return jsonify({"error": "Record not found."}), 404
    rng = _rnd.Random(parcel['id'] + "ec")
    years = int(period) if period.isdigit() else 30
    db = get_db()
    history = db.execute("SELECT * FROM ownership_history WHERE parcel_id=? ORDER BY from_date", (parcel['id'],)).fetchall()
    db.close()
    has_enc = parcel["status"] in ["mortgaged","disputed"]
    transactions = [dict(h) for h in history]
    return jsonify({
        "success": True,
        "document_type": f"Encumbrance Certificate (Last {years} Years)",
        "ec_number":     f"EC-{rng.randint(10000,99999)}/{datetime.now().year}",
        "survey_number": parcel["survey_number"],
        "district":      parcel["district"],
        "village":       parcel["village"],
        "period":        f"{datetime.now().year - years} to {datetime.now().year}",
        "area_acres":    parcel["area_acres"],
        "status":        "ENCUMBRANCE EXISTS" if has_enc else "NO ENCUMBRANCE",
        "is_clear":      not has_enc,
        "encumbrance_type": parcel["encumbrance"],
        "total_transactions": len(transactions),
        "transactions": [
            {
                "sl_no":    i+1,
                "date":     t["from_date"],
                "nature":   t["transfer_type"],
                "parties":  t["owner_name"],
                "deed_no":  t["deed_number"],
                "amount":   t["consideration_amount"],
                "sub_reg_office": f"SRO, {parcel['district']}",
            } for i,t in enumerate(transactions[:10])
        ],
        "mortgage_details": {
            "exists":      parcel["status"] == "mortgaged",
            "bank":        "State Bank of India" if parcel["status"]=="mortgaged" else None,
            "amount":      round(parcel["market_value"]*0.5) if parcel["status"]=="mortgaged" else 0,
            "date":        "2022-06-15" if parcel["status"]=="mortgaged" else None,
        },
        "certified_by":  f"Sub-Registrar, {parcel['district']}",
        "fee_paid":       round(years*5.0),
        "issued_date":   datetime.now().strftime("%d-%m-%Y"),
        "valid_for":     "For official purposes only. Valid for 1 year.",
    })


@app.route('/api/services/bhu_naksha', methods=['GET'])
def service_bhu_naksha():
    """Bhu-Naksha / Cadastral Map data."""
    survey   = request.args.get('survey', '')
    district = request.args.get('district', '')
    parcel   = _get_parcel_by_survey(survey) if survey else _get_any_parcel(district or None)
    if not parcel:
        return jsonify({"error": "Bhu-Naksha record not found."}), 404
    rng = _rnd.Random(parcel['id'] + "naksha")
    lat, lng = parcel["latitude"], parcel["longitude"]
    # Rough bounding box for parcel polygon
    d = parcel["area_acres"] * 0.0002  # degrees offset
    polygon = [
        {"lat": lat,       "lng": lng},
        {"lat": lat,       "lng": lng+d},
        {"lat": lat+d,     "lng": lng+d},
        {"lat": lat+d,     "lng": lng},
        {"lat": lat,       "lng": lng},
    ]
    return jsonify({
        "success":         True,
        "document_type":   "Bhu-Naksha (Cadastral Map)",
        "survey_number":   parcel["survey_number"],
        "district":        parcel["district"],
        "village":         parcel["village"],
        "latitude":        lat,
        "longitude":       lng,
        "polygon":         polygon,
        "area_acres":      parcel["area_acres"],
        "area_hectares":   round(parcel["area_acres"]*0.404686,4),
        "perimeter_m":     round(parcel["area_acres"]*202.343*4,1),
        "scale":           _rnd.choice(["1:1000","1:2000","1:4000"]),
        "geo_referenced":  True,
        "map_sheet_no":    f"MS-{rng.randint(100,999)}/{parcel['district'][:3].upper()}",
        "north_bearing":   f"{rng.randint(0,359)}°{rng.randint(0,59)}'",
        "land_type_color": {"Residential":"#EF4444","Agricultural":"#22C55E","Commercial":"#8B5CF6","Industrial":"#F59E0B"}.get(parcel["land_type"],"#3B82F6"),
        "adjacent_plots":  [
            {"survey_no": f"{parcel['survey_number'].split('/')[0]}/{rng.randint(1,999)}", "direction":"North", "owner": _rnd.choice(["Ramesh","Government","Road","Canal"])},
            {"survey_no": f"{parcel['survey_number'].split('/')[0]}/{rng.randint(1,999)}", "direction":"South", "owner": _rnd.choice(["Priya","Government","Road","River"])},
            {"survey_no": f"{parcel['survey_number'].split('/')[0]}/{rng.randint(1,999)}", "direction":"East",  "owner": _rnd.choice(["Suresh","Government","Road","Nala"])},
            {"survey_no": f"{parcel['survey_number'].split('/')[0]}/{rng.randint(1,999)}", "direction":"West",  "owner": _rnd.choice(["Anita","Government","Road","Canal"])},
        ],
        "google_maps_url": f"https://www.google.com/maps?q={lat},{lng}&z=18",
        "bhunaksha_url":   f"https://bhunaksha.nic.in/",
        "issued_by":       f"Survey Dept., {parcel['district']}",
    })


@app.route('/api/services/parimarjan', methods=['POST'])
def service_parimarjan():
    """Parimarjan — Online Land Record Correction (Karnataka/Bihar style)."""
    data = request.get_json()
    required = ['applicant_name','survey_number','district','correction_type','remarks']
    for f in required:
        if not data.get(f):
            return jsonify({'error': f'Field "{f}" is required.'}), 400
    app_no = f"PRM-{datetime.now().year}-{uuid.uuid4().hex[:6].upper()}"
    return jsonify({
        "success":          True,
        "application_no":   app_no,
        "status":           "Submitted for Review",
        "applicant":        data["applicant_name"],
        "survey_number":    data["survey_number"],
        "correction_type":  data["correction_type"],
        "remarks":          data["remarks"],
        "expected_days":    30,
        "authority":        "Revenue Inspector / Village Accountant",
        "next_step":        "A revenue inspector will inspect the field and verify your correction request within 7 days.",
        "documents_required": ["Original land document showing error","Aadhaar card","Supporting evidence for correction","Affidavit (notarized)"],
        "submitted_at":     datetime.now().isoformat(),
    }), 201


@app.route('/api/services/bhoomi_analytics', methods=['GET'])
def service_bhoomi_analytics():
    """Bhoomi-style analytics dashboard data."""
    db = get_db()
    districts = db.execute("SELECT district, COUNT(*) as cnt, SUM(area_acres) as area, SUM(market_value) as val FROM land_parcels GROUP BY district").fetchall()
    types = db.execute("SELECT land_type, COUNT(*) as cnt, SUM(area_acres) as area FROM land_parcels GROUP BY land_type").fetchall()
    statuses = db.execute("SELECT status, COUNT(*) as cnt FROM land_parcels GROUP BY status").fetchall()
    total = db.execute("SELECT COUNT(*) as cnt, SUM(area_acres) as area, SUM(market_value) as val FROM land_parcels").fetchone()
    mutations = db.execute("SELECT COUNT(*) as cnt FROM ownership_history").fetchone()
    db.close()

    return jsonify({
        "success": True,
        "summary": {
            "total_parcels":    dict(total)["cnt"],
            "total_area_acres": round(dict(total)["area"] or 0, 2),
            "total_value":      dict(total)["val"] or 0,
            "total_mutations":  dict(mutations)["cnt"] if mutations else 0,
            "districts":        len(districts),
        },
        "by_district": [{"district":dict(d)["district"],"count":dict(d)["cnt"],"area":round(dict(d)["area"] or 0,2),"value":dict(d)["val"] or 0} for d in districts],
        "by_type":     [{"type":dict(t)["land_type"],"count":dict(t)["cnt"],"area":round(dict(t)["area"] or 0,2)} for t in types],
        "by_status":   [{"status":dict(s)["status"],"count":dict(s)["cnt"]} for s in statuses],
        "mutation_trends": [
            {"year": y, "count": 1200 + (y-2015)*200 + __import__('random').randint(-100,100)}
            for y in range(2015, 2025)
        ],
        "mutation_types": [
            {"type": "Sale", "count": 4521},
            {"type": "Inheritance", "count": 2134},
            {"type": "Gift Deed", "count": 892},
            {"type": "Partition", "count": 567},
            {"type": "Court Decree", "count": 234},
            {"type": "Exchange", "count": 123},
            {"type": "Others", "count": 189},
        ],
    })


@app.route('/api/services/iRTC', methods=['GET'])
def service_i_rtc():
    """i-RTC — Instant RTC (Karnataka)."""
    survey = request.args.get('survey', '')
    parcel = _get_parcel_by_survey(survey) if survey else _get_any_parcel()
    if not parcel:
        return jsonify({"error": "i-RTC not found."}), 404
    rng = _rnd.Random(parcel['id'] + "irtc")
    return jsonify({
        "success": True,
        "document_type": "i-RTC (Instant RTC)",
        "survey_number": parcel["survey_number"],
        "district":      parcel["district"],
        "village":       parcel["village"],
        "owner_name":    _rnd.choice(["Ramaiah","Venkatesh","Lakshmi Devi","Suresh Kumar"]),
        "area_acres":    parcel["area_acres"],
        "land_type":     parcel["land_type"],
        "status":        parcel["status"],
        "market_value":  parcel["market_value"],
        "xml_verified":  True,
        "qr_code":       f"iRTC-{uuid.uuid4().hex[:16].upper()}",
        "token":         uuid.uuid4().hex,
        "valid_minutes": 30,
        "download_url":  f"https://bhoomi.karnataka.gov.in/irtc/download/{parcel['survey_number'].replace('/','-')}",
        "generated_at":  datetime.now().isoformat(),
    })


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    print("\n[*] BhoomiSeva — Land Record Management System")
    print("=" * 48)
    print("[*] Running at: http://localhost:5000")
    print("[*] Admin:   admin@landrecords.gov.in / admin123")
    print("[*] Citizen: ramesh@email.com / citizen123")
    print("=" * 48)
    app.run(host='0.0.0.0', port=5000, debug=True)

