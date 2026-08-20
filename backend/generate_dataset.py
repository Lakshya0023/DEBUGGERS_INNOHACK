import os
import sys
import csv
import json
import uuid
import math
import random
import sqlite3
from datetime import datetime, timedelta

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, 'data')
DB_PATH = os.path.join(ROOT_DIR, 'backend', 'land_records.db')

os.makedirs(DATA_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────
#  DISTRICTS & CITY CONFIGURATION (14 Major Districts across India)
# ─────────────────────────────────────────────────────────────
DISTRICTS = {
    "Bengaluru Urban": {
        "state": "Karnataka", "base_lat": 12.9716, "base_lng": 77.5946, "spread": 0.18,
        "price_base": 8_000_000, "price_max": 80_000_000,
        "taluks": ["Bengaluru North", "Bengaluru South", "Bengaluru East", "Yelahanka", "Anekal"],
        "localities": ["Koramangala","Indiranagar","Whitefield","Jayanagar","JP Nagar","HSR Layout","BTM Layout","Marathahalli","Electronic City","Sarjapur","Hebbal","Yelahanka","Bannerghatta","Rajajinagar","Malleswaram"],
        "survey_prefix": "BLR"
    },
    "Bengaluru Rural": {
        "state": "Karnataka", "base_lat": 13.2330, "base_lng": 77.5670, "spread": 0.20,
        "price_base": 3_500_000, "price_max": 30_000_000,
        "taluks": ["Devanahalli", "Doddaballapura", "Hoskote", "Nelamangala"],
        "localities": ["Devanahalli Town","Hoskote Industrial","Doddaballapur Cross","Nelamangala Highway","Bagalur","Budigere Cross","Vijayapura"],
        "survey_prefix": "BLRR"
    },
    "Delhi": {
        "state": "Delhi", "base_lat": 28.6139, "base_lng": 77.2090, "spread": 0.20,
        "price_base": 10_000_000, "price_max": 120_000_000,
        "taluks": ["New Delhi", "North Delhi", "South Delhi", "East Delhi", "West Delhi", "Dwarka"],
        "localities": ["Connaught Place","Lajpat Nagar","Saket","Dwarka","Rohini","Janakpuri","Pitampura","Hauz Khas","Karol Bagh","Vasant Kunj","Greater Kailash","Defence Colony","Mehrauli","Najafgarh","Narela"],
        "survey_prefix": "DLH"
    },
    "Chennai": {
        "state": "Tamil Nadu", "base_lat": 13.0400, "base_lng": 80.1800, "spread": 0.06,
        "price_base": 6_000_000, "price_max": 60_000_000,
        "taluks": ["Chennai North", "Chennai South", "Tambaram", "Sholinganallur", "Ambattur"],
        "localities": ["T Nagar","Adyar","Anna Nagar","Velachery","Tambaram","Porur","Chromepet","Perambur","Royapettah","Mylapore","Guindy","Sholinganallur","Perungudi","Ambattur","Avadi"],
        "survey_prefix": "CHN"
    },
    "Mumbai": {
        "state": "Maharashtra", "base_lat": 19.1000, "base_lng": 72.9000, "spread": 0.05,
        "price_base": 15_000_000, "price_max": 200_000_000,
        "taluks": ["Mumbai City", "Mumbai Suburban", "Andheri", "Borivali", "Kurla"],
        "localities": ["Andheri","Bandra","Borivali","Dadar","Goregaon","Malad","Kandivali","Kurla","Ghatkopar","Mulund","Thane","Powai","Vikhroli","Chembur","Sion","Worli","Lower Parel","Prabhadevi"],
        "survey_prefix": "MUM"
    },
    "Vellore": {
        "state": "Tamil Nadu", "base_lat": 12.9165, "base_lng": 79.1325, "spread": 0.20,
        "price_base": 1_800_000, "price_max": 18_000_000,
        "taluks": ["Vellore", "Katpadi", "Anaicut", "Arcot", "Gudiyatham"],
        "localities": ["Katpadi","Sathuvachari","Gandhi Nagar","Bagayam","Kosapet","Melvisharam","Arcot","Ranipet","Wallajah","Sholingur","Gudiyatham","Ambur","Vaniyambadi"],
        "survey_prefix": "VLR"
    },
    "Hyderabad": {
        "state": "Telangana", "base_lat": 17.3850, "base_lng": 78.4867, "spread": 0.18,
        "price_base": 5_000_000, "price_max": 70_000_000,
        "taluks": ["Hyderabad", "Secunderabad", "Rangareddy", "Medchal", "Shamshabad"],
        "localities": ["Banjara Hills","Jubilee Hills","Hitech City","Gachibowli","Kondapur","Madhapur","Manikonda","Kukatpally","Ameerpet","Begumpet","Secunderabad","Uppal","LB Nagar"],
        "survey_prefix": "HYD"
    },
    "Pune": {
        "state": "Maharashtra", "base_lat": 18.5204, "base_lng": 73.8567, "spread": 0.18,
        "price_base": 4_000_000, "price_max": 50_000_000,
        "taluks": ["Pune City", "Haveli", "Khed", "Shirur", "Mulshi"],
        "localities": ["Kothrud","Wakad","Baner","Aundh","Hinjewadi","Viman Nagar","Koregaon Park","Kalyani Nagar","Hadapsar","Magarpatta","Kondhwa","Katraj","Bavdhan","Balewadi"],
        "survey_prefix": "PNE"
    },
    "Kolkata": {
        "state": "West Bengal", "base_lat": 22.5726, "base_lng": 88.3639, "spread": 0.15,
        "price_base": 3_000_000, "price_max": 40_000_000,
        "taluks": ["Kolkata North", "Kolkata South", "Salt Lake", "Howrah", "Barasat"],
        "localities": ["Salt Lake","New Town","Rajarhat","Dum Dum","Behala","Jadavpur","Tollygunge","Ballygunge","Park Street","Alipore","Howrah","Shibpur","Barasat"],
        "survey_prefix": "KOL"
    },
    "Ahmedabad": {
        "state": "Gujarat", "base_lat": 23.0225, "base_lng": 72.5714, "spread": 0.16,
        "price_base": 3_500_000, "price_max": 45_000_000,
        "taluks": ["Ahmedabad City", "Daskroi", "Sanand", "Dholka"],
        "localities": ["SG Highway","Bopal","Satellite","Navrangpura","Prahlad Nagar","Bodakdev","Vastrapur","Maninagar","Sanand Industrial","Ghatlodia","Thaltej"],
        "survey_prefix": "AMD"
    },
    "Jaipur": {
        "state": "Rajasthan", "base_lat": 26.9124, "base_lng": 75.7873, "spread": 0.18,
        "price_base": 2_500_000, "price_max": 35_000_000,
        "taluks": ["Jaipur", "Sanganer", "Amer", "Chaksu"],
        "localities": ["Malviya Nagar","Vaishali Nagar","Mansarovar","C Scheme","Jagatpura","Tonk Road","Ajmer Road","Sanganer","Amer Road","Bani Park"],
        "survey_prefix": "JPR"
    },
    "Lucknow": {
        "state": "Uttar Pradesh", "base_lat": 26.8467, "base_lng": 80.9462, "spread": 0.16,
        "price_base": 2_800_000, "price_max": 32_000_000,
        "taluks": ["Lucknow", "Bakshi Ka Talab", "Mohanlalganj", "Sarojini Nagar"],
        "localities": ["Gomti Nagar","Hazratganj","Aliganj","Indira Nagar","Vikas Nagar","Mahanagar","Ashiyana","Janki Puram","Shaheed Path","Chinhat"],
        "survey_prefix": "LKO"
    },
    "Patna": {
        "state": "Bihar", "base_lat": 25.5941, "base_lng": 85.1376, "spread": 0.15,
        "price_base": 2_200_000, "price_max": 28_000_000,
        "taluks": ["Patna Sadar", "Danapur", "Phulwari", "Fatwah"],
        "localities": ["Boring Road","Kankarbagh","Bailey Road","Patliputra","Danapur","Rajendra Nagar","Anisabad","Ashiana Nagar","Phulwari Sharif","Digha"],
        "survey_prefix": "PAT"
    },
    "Visakhapatnam": {
        "state": "Andhra Pradesh", "base_lat": 17.7200, "base_lng": 83.2200, "spread": 0.06,
        "price_base": 2_500_000, "price_max": 35_000_000,
        "taluks": ["Visakhapatnam Urban", "Visakhapatnam Rural", "Gajuwaka", "Anakapalle"],
        "localities": ["MVP Colony","Siripuram","Madhurawada","Gajuwaka","Rushikonda","Seethammadhara","Dwaraka Nagar","Pendurthi","Bheemunipatnam"],
        "survey_prefix": "VSKP"
    }
}

LAND_TYPES = ["Residential", "Commercial", "Agricultural", "Industrial"]
LAND_USES  = {
    "Residential":  ["Housing", "Apartment", "Villa", "Duplex", "Row House"],
    "Commercial":   ["Office", "Retail Shop", "Mall", "Showroom", "Warehouse"],
    "Agricultural": ["Farming", "Horticulture", "Plantation", "Orchard", "Grazing"],
    "Industrial":   ["Factory", "Workshop", "Logistics", "Manufacturing", "IT Park"]
}

INDIAN_NAMES = [
    "Ramesh Kumar Sharma","Priya Devi Nair","Suresh Babu Reddy","Anita Kumari Singh",
    "Mohammad Arif Khan","Lakshmi Venkatesh","Vijay Prakash Rao","Geeta Mahesh Patel",
    "Deepika Mehta","Santosh Kumar","Rekha Nair","Arun Prakash","Sunita Verma",
    "Harish Chandra","Kavitha Rao","Ravi Shankar","Meena Devi","Rajesh Gupta",
    "Sushma Swarup","Naresh Kumar","Asha Bhosale","Dinesh Patil","Pooja Sharma",
    "Mahesh Babu","Sridevi Kapoor","Ajay Singh","Smita Patil","Ranjit Kumar",
    "Seema Malhotra","Prakash Raj","Divya Menon","Anil Kapoor","Nandini Reddy",
    "Sunil Shetty","Rani Mukherjee","Vinod Khanna","Jyoti Prasad","Rohit Sharma",
    "Sonia Verma","Girish Kumar","Uma Shankar","Nitin Gadkari","Lalitha Kumari",
    "Balu Mahendra","Revathy Nair","Ganesh Patel","Saritha Devi","Mohan Das"
]

def hash_pass(p):
    import hashlib
    return hashlib.sha256(p.encode()).hexdigest()

def rand_date(years_ago_min, years_ago_max):
    days = random.randint(years_ago_min * 365, years_ago_max * 365)
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

def generate_csv_and_sqlite():
    print("=" * 60)
    print("Generating CSV datasets & building SQLite database...")
    print("=" * 60)

    rng = random.Random(42)

    # 1. Users
    users = [
        {"id": str(uuid.uuid4()), "name": "Admin Officer", "email": "admin@landrecords.gov.in", "phone": "9800000001", "password": hash_pass("admin123"), "role": "admin", "aadhaar": None, "created_at": datetime.now().isoformat()},
        {"id": str(uuid.uuid4()), "name": "Ramesh Kumar Sharma", "email": "ramesh@email.com", "phone": "9876543210", "password": hash_pass("citizen123"), "role": "citizen", "aadhaar": "1234-5678-9012", "created_at": datetime.now().isoformat()},
        {"id": str(uuid.uuid4()), "name": "Priya Devi Nair", "email": "priya@email.com", "phone": "9876543211", "password": hash_pass("citizen123"), "role": "citizen", "aadhaar": "2345-6789-0123", "created_at": datetime.now().isoformat()},
        {"id": str(uuid.uuid4()), "name": "Suresh Babu Reddy", "email": "suresh@email.com", "phone": "9876543212", "password": hash_pass("citizen123"), "role": "citizen", "aadhaar": "3456-7890-1234", "created_at": datetime.now().isoformat()},
        {"id": str(uuid.uuid4()), "name": "Anita Kumari Singh", "email": "anita@email.com", "phone": "9876543213", "password": hash_pass("citizen123"), "role": "citizen", "aadhaar": "4567-8901-2345", "created_at": datetime.now().isoformat()},
        {"id": str(uuid.uuid4()), "name": "Mohammad Arif Khan", "email": "arif@email.com", "phone": "9876543214", "password": hash_pass("citizen123"), "role": "citizen", "aadhaar": "5678-9012-3456", "created_at": datetime.now().isoformat()},
        {"id": str(uuid.uuid4()), "name": "Lakshmi Venkatesh", "email": "lakshmi@email.com", "phone": "9876543215", "password": hash_pass("citizen123"), "role": "citizen", "aadhaar": "6789-0123-4567", "created_at": datetime.now().isoformat()},
        {"id": str(uuid.uuid4()), "name": "Vijay Prakash Rao", "email": "vijay@email.com", "phone": "9876543216", "password": hash_pass("citizen123"), "role": "citizen", "aadhaar": "7890-1234-5678", "created_at": datetime.now().isoformat()},
        {"id": str(uuid.uuid4()), "name": "Geeta Mahesh Patel", "email": "geeta@email.com", "phone": "9876543217", "password": hash_pass("citizen123"), "role": "citizen", "aadhaar": "8901-2345-6789", "created_at": datetime.now().isoformat()},
    ]
    citizen_ids = [u["id"] for u in users if u["role"] == "citizen"]

    # 2. Land Parcels & Price History
    parcels = []
    ownership = []
    price_histories = []

    for city_name, city in DISTRICTS.items():
        counter = 1
        for ltype in LAND_TYPES:
            for k in range(15):
                pid = str(uuid.uuid4())
                prefix = city["survey_prefix"]
                sub = rng.choice(["A","B","C","1","2","3","P","Q"])
                survey = f"{prefix}-{counter:03d}/{sub}-{pid[:4].upper()}"
                counter += 1

                locality = rng.choice(city["localities"])
                taluk = rng.choice(city["taluks"])
                luse = rng.choice(LAND_USES[ltype])

                if k % 5 == 3:
                    status = "disputed"
                    enc = "Court Order"
                elif k % 5 == 4:
                    status = "mortgaged"
                    enc = "Bank Mortgage"
                else:
                    status = "clear"
                    enc = "None"

                if ltype == "Residential":
                    area = round(rng.uniform(0.06, 0.80), 2)
                elif ltype == "Commercial":
                    area = round(rng.uniform(0.20, 2.50), 2)
                elif ltype == "Agricultural":
                    area = round(rng.uniform(1.50, 15.00), 2)
                else:
                    area = round(rng.uniform(1.00, 8.00), 2)

                lat = city["base_lat"] + rng.uniform(-city["spread"], city["spread"])
                lng = city["base_lng"] + rng.uniform(-city["spread"], city["spread"])

                type_mult = {"Residential": 1.4, "Commercial": 2.2, "Agricultural": 0.35, "Industrial": 1.1}[ltype]
                base = city["price_base"] * type_mult
                maxv = city["price_max"] * type_mult
                price = round(rng.uniform(base, maxv) * (area / 1.5), -3)
                price = max(price, base * 0.4)

                owner_id = rng.choice(citizen_ids)

                parcels.append({
                    "id": pid, "survey_number": survey, "district": city_name,
                    "taluk": taluk, "village": locality, "area_acres": area,
                    "land_type": ltype, "land_use": luse, "current_owner_id": owner_id,
                    "latitude": round(lat, 6), "longitude": round(lng, 6),
                    "market_value": price, "status": status, "encumbrance": enc,
                    "created_at": datetime.now().isoformat(),
                    "location_url": None
                })

                # Ownership history
                n_owners = rng.randint(2, 4)
                dates = sorted([rand_date(2, 30) for _ in range(n_owners - 1)])
                prev_val = price * rng.uniform(0.2, 0.5)

                for j in range(n_owners):
                    from_d = dates[j-1] if j > 0 else rand_date(25, 40)
                    to_d = dates[j] if j < n_owners - 1 else None
                    ttype = rng.choice(["Sale", "Inheritance", "Gift", "Partition", "Court Decree"])
                    deed = f"DD-{rng.randint(1000,9999)}-{rng.randint(100,999)}"
                    amt = 0 if ttype == "Inheritance" else round(prev_val * rng.uniform(0.85, 1.25), -3)
                    prev_val = amt if amt > 0 else prev_val
                    owner_name = rng.choice(INDIAN_NAMES)

                    ownership.append({
                        "id": str(uuid.uuid4()), "parcel_id": pid, "owner_name": owner_name,
                        "owner_aadhaar": f"{rng.randint(1000,9999)}-{rng.randint(1000,9999)}-{rng.randint(1000,9999)}",
                        "owner_phone": f"9{rng.randint(100000000,999999999)}",
                        "from_date": from_d, "to_date": to_d, "transfer_type": ttype,
                        "deed_number": deed, "consideration_amount": amt, "remarks": None
                    })

                # Price history (2020 to 2025)
                annual_cagr = rng.uniform(1.07, 1.15)
                p2020 = price / (annual_cagr ** 5)
                curr_p = p2020
                for yr in range(2020, 2026):
                    noise = rng.uniform(0.97, 1.03)
                    mkt = round(curr_p * noise, -3)
                    govt = round(mkt * rng.uniform(0.60, 0.72), -3)
                    price_histories.append({
                        "id": str(uuid.uuid4()), "parcel_id": pid, "year": yr,
                        "market_value": mkt, "govt_value": govt,
                        "recorded_on": datetime.now().isoformat()
                    })
                    curr_p *= annual_cagr

    # 3. Grievances
    grievances = [
        {
            "id": str(uuid.uuid4()), "ticket_id": f"GRV-2026-T7A89001",
            "citizen_name": "Ramesh Kumar Sharma", "citizen_email": "ramesh@email.com",
            "citizen_phone": "9876543210", "parcel_id": parcels[0]["id"],
            "category": "Title Dispute", "subject": "Encroachment on boundary line",
            "description": "Neighbor constructed a temporary fence 2 feet inside my registered parcel.",
            "status": "under_review", "priority": "high", "assigned_to": users[0]["id"],
            "admin_remarks": "Surveyor assigned for boundary demarcation inspection.",
            "plot_lat": parcels[0]["latitude"], "plot_lng": parcels[0]["longitude"],
            "plot_address": f"{parcels[0]['village']}, {parcels[0]['district']}",
            "created_at": (datetime.now() - timedelta(days=5)).isoformat(),
            "updated_at": (datetime.now() - timedelta(days=2)).isoformat(),
            "resolved_at": None
        },
        {
            "id": str(uuid.uuid4()), "ticket_id": f"GRV-2026-M4B11234",
            "citizen_name": "Priya Devi Nair", "citizen_email": "priya@email.com",
            "citizen_phone": "9876543211", "parcel_id": parcels[10]["id"],
            "category": "Record Correction", "subject": "Spelling mistake in ownership ledger",
            "description": "Owner name misspelled in RTC register. Requesting correction.",
            "status": "resolved", "priority": "medium", "assigned_to": users[0]["id"],
            "admin_remarks": "Verified Aadhaar and updated revenue ledger name spelling.",
            "plot_lat": parcels[10]["latitude"], "plot_lng": parcels[10]["longitude"],
            "plot_address": f"{parcels[10]['village']}, {parcels[10]['district']}",
            "created_at": (datetime.now() - timedelta(days=12)).isoformat(),
            "updated_at": (datetime.now() - timedelta(days=3)).isoformat(),
            "resolved_at": (datetime.now() - timedelta(days=3)).isoformat()
        }
    ]

    # Save to CSV Files in data/
    def save_csv(filename, data_list):
        if not data_list: return
        filepath = os.path.join(DATA_DIR, filename)
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=data_list[0].keys())
            writer.writeheader()
            writer.writerows(data_list)
        print(f"  [CSV] Saved {len(data_list)} rows to: {filepath}")

    save_csv('users.csv', users)
    save_csv('land_parcels.csv', parcels)
    save_csv('ownership_history.csv', ownership)
    save_csv('price_history.csv', price_histories)
    save_csv('grievances.csv', grievances)

    # Save to SQLite Database
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")
    c = conn.cursor()

    # Recreate tables cleanly
    c.execute("DROP TABLE IF EXISTS price_history")
    c.execute("DROP TABLE IF EXISTS ownership_history")
    c.execute("DROP TABLE IF EXISTS mutations")
    c.execute("DROP TABLE IF EXISTS grievances")
    c.execute("DROP TABLE IF EXISTS land_parcels")
    c.execute("DROP TABLE IF EXISTS users")

    c.execute('''CREATE TABLE users (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
        phone TEXT, password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'citizen',
        aadhaar TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE land_parcels (
        id TEXT PRIMARY KEY, survey_number TEXT UNIQUE NOT NULL,
        district TEXT NOT NULL, taluk TEXT NOT NULL, village TEXT NOT NULL,
        area_acres REAL NOT NULL, land_type TEXT NOT NULL, land_use TEXT NOT NULL,
        current_owner_id TEXT, latitude REAL NOT NULL, longitude REAL NOT NULL,
        market_value REAL NOT NULL, status TEXT DEFAULT 'clear',
        encumbrance TEXT DEFAULT 'None', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        location_url TEXT,
        FOREIGN KEY(current_owner_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE ownership_history (
        id TEXT PRIMARY KEY, parcel_id TEXT NOT NULL, owner_name TEXT NOT NULL,
        owner_aadhaar TEXT, owner_phone TEXT, from_date TEXT NOT NULL,
        to_date TEXT, transfer_type TEXT NOT NULL, deed_number TEXT,
        consideration_amount REAL, remarks TEXT,
        FOREIGN KEY(parcel_id) REFERENCES land_parcels(id)
    )''')

    c.execute('''CREATE TABLE price_history (
        id TEXT PRIMARY KEY, parcel_id TEXT NOT NULL, year INTEGER NOT NULL,
        market_value REAL NOT NULL, govt_value REAL NOT NULL,
        recorded_on TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(parcel_id) REFERENCES land_parcels(id)
    )''')

    c.execute('''CREATE TABLE grievances (
        id TEXT PRIMARY KEY, ticket_id TEXT UNIQUE NOT NULL,
        citizen_name TEXT NOT NULL, citizen_email TEXT NOT NULL,
        citizen_phone TEXT NOT NULL, parcel_id TEXT, category TEXT NOT NULL,
        subject TEXT NOT NULL, description TEXT NOT NULL,
        status TEXT DEFAULT 'submitted', priority TEXT DEFAULT 'medium',
        assigned_to TEXT, admin_remarks TEXT,
        plot_lat REAL, plot_lng REAL, plot_address TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP, resolved_at TEXT,
        FOREIGN KEY(parcel_id) REFERENCES land_parcels(id)
    )''')

    c.execute('''CREATE TABLE mutations (
        id TEXT PRIMARY KEY, parcel_id TEXT NOT NULL, requested_by TEXT NOT NULL,
        new_owner_name TEXT NOT NULL, new_owner_aadhaar TEXT, new_owner_phone TEXT,
        transfer_type TEXT NOT NULL, consideration_amount REAL, deed_number TEXT,
        status TEXT DEFAULT 'pending', admin_remarks TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP, approved_at TEXT,
        FOREIGN KEY(parcel_id) REFERENCES land_parcels(id)
    )''')

    # Bulk insert
    for u in users:
        c.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?)", list(u.values()))
    for p in parcels:
        c.execute("INSERT INTO land_parcels VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", list(p.values()))
    for o in ownership:
        c.execute("INSERT INTO ownership_history VALUES (?,?,?,?,?,?,?,?,?,?,?)", list(o.values()))
    for ph in price_histories:
        c.execute("INSERT INTO price_history VALUES (?,?,?,?,?,?)", list(ph.values()))
    for g in grievances:
        c.execute("INSERT INTO grievances VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", list(g.values()))

    conn.commit()
    conn.execute("PRAGMA foreign_keys=ON")
    conn.close()

    print(f"\n[SUCCESS] Seeded {len(parcels)} land parcels ({len(DISTRICTS)} districts x 60 parcels each)")
    print(f"  Guaranteed: 15 Residential, 15 Commercial, 15 Agricultural, 15 Industrial in EVERY district!")
    print(f"  Total price records: {len(price_histories)}")
    print(f"  Total ownership records: {len(ownership)}")
    print(f"  SQLite DB: {DB_PATH}")

if __name__ == '__main__':
    generate_csv_and_sqlite()
