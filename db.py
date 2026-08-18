import sqlite3, json, os, hashlib, uuid, random
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), 'land_records.db')

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn

def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
        phone TEXT, password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'citizen',
        aadhaar TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS land_parcels (
        id TEXT PRIMARY KEY, survey_number TEXT UNIQUE NOT NULL,
        district TEXT NOT NULL, taluk TEXT NOT NULL, village TEXT NOT NULL,
        area_acres REAL NOT NULL, land_type TEXT NOT NULL, land_use TEXT NOT NULL,
        current_owner_id TEXT, latitude REAL NOT NULL, longitude REAL NOT NULL,
        market_value REAL NOT NULL, status TEXT DEFAULT 'clear',
        encumbrance TEXT DEFAULT 'None', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(current_owner_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS ownership_history (
        id TEXT PRIMARY KEY, parcel_id TEXT NOT NULL, owner_name TEXT NOT NULL,
        owner_aadhaar TEXT, owner_phone TEXT, from_date TEXT NOT NULL,
        to_date TEXT, transfer_type TEXT NOT NULL, deed_number TEXT,
        consideration_amount REAL, remarks TEXT,
        FOREIGN KEY(parcel_id) REFERENCES land_parcels(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS price_history (
        id TEXT PRIMARY KEY, parcel_id TEXT NOT NULL, year INTEGER NOT NULL,
        market_value REAL NOT NULL, govt_value REAL NOT NULL,
        recorded_on TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(parcel_id) REFERENCES land_parcels(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS grievances (
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

    c.execute('''CREATE TABLE IF NOT EXISTS mutations (
        id TEXT PRIMARY KEY, parcel_id TEXT NOT NULL, requested_by TEXT NOT NULL,
        new_owner_name TEXT NOT NULL, new_owner_aadhaar TEXT, new_owner_phone TEXT,
        transfer_type TEXT NOT NULL, consideration_amount REAL, deed_number TEXT,
        status TEXT DEFAULT 'pending', admin_remarks TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP, approved_at TEXT,
        FOREIGN KEY(parcel_id) REFERENCES land_parcels(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        district TEXT NOT NULL,
        taluk TEXT NOT NULL,
        village TEXT NOT NULL,
        UNIQUE(district, taluk, village)
    )''')

    conn.commit()

    existing = c.execute("SELECT COUNT(*) FROM land_parcels").fetchone()[0]
    if existing < 500:
        data_csv = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'land_parcels.csv')
        if os.path.exists(data_csv):
            load_from_csv(conn)
        else:
            seed_data(conn, c)

    conn.close()

def load_from_csv(conn):
    """Loads dataset from CSV files into SQLite database tables."""
    import csv
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    c = conn.cursor()
    print("Loading SQLite database from CSV datasets in data/ ...")

    tables = [
        ('users.csv', 'users', 8),
        ('land_parcels.csv', 'land_parcels', 15),
        ('ownership_history.csv', 'ownership_history', 11),
        ('price_history.csv', 'price_history', 6),
        ('grievances.csv', 'grievances', 19),
    ]

    for filename, table, col_count in tables:
        filepath = os.path.join(data_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = [list(r.values()) for r in reader]
                if rows:
                    c.execute(f"DELETE FROM {table}")
                    placeholders = ','.join(['?'] * col_count)
                    c.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)
            print(f"  Loaded {len(rows)} records into table '{table}' from {filename}")
    conn.commit()

# ─────────────────────────────────────────────────────────────
#  EXPANDED CITY & DISTRICT DATA — All States 
# ─────────────────────────────────────────────────────────────
CITIES = {
    "Bengaluru Urban": {
        "state": "Karnataka",
        "base_lat": 12.9716, "base_lng": 77.5946, "spread": 0.18,
        "price_base": 8_000_000, "price_max": 80_000_000,
        "taluks": ["Bengaluru North", "Bengaluru South", "Bengaluru East", "Yelahanka", "Anekal"],
        "localities": ["Koramangala","Indiranagar","Whitefield","Jayanagar","JP Nagar","HSR Layout","BTM Layout","Marathahalli","Electronic City","Sarjapur","Hebbal","Yelahanka","Bannerghatta","Rajajinagar","Malleswaram"],
        "survey_prefix": "BLR"
    },
    "Bengaluru Rural": {
        "state": "Karnataka",
        "base_lat": 13.2330, "base_lng": 77.5670, "spread": 0.20,
        "price_base": 3_500_000, "price_max": 30_000_000,
        "taluks": ["Devanahalli", "Doddaballapura", "Hoskote", "Nelamangala"],
        "localities": ["Devanahalli Town","Hoskote Industrial","Doddaballapur Cross","Nelamangala Highway","Bagalur","Budigere Cross","Vijayapura"],
        "survey_prefix": "BLRR"
    },
    "Delhi": {
        "state": "Delhi",
        "base_lat": 28.6139, "base_lng": 77.2090, "spread": 0.20,
        "price_base": 10_000_000, "price_max": 120_000_000,
        "taluks": ["New Delhi", "North Delhi", "South Delhi", "East Delhi", "West Delhi", "Dwarka"],
        "localities": ["Connaught Place","Lajpat Nagar","Saket","Dwarka","Rohini","Janakpuri","Pitampura","Hauz Khas","Karol Bagh","Vasant Kunj","Greater Kailash","Defence Colony","Mehrauli","Najafgarh","Narela"],
        "survey_prefix": "DLH"
    },
    "Chennai": {
        "state": "Tamil Nadu",
        "base_lat": 13.0827, "base_lng": 80.2707, "spread": 0.15,
        "price_base": 6_000_000, "price_max": 60_000_000,
        "taluks": ["Chennai North", "Chennai South", "Tambaram", "Sholinganallur", "Ambattur"],
        "localities": ["T Nagar","Adyar","Anna Nagar","Velachery","Tambaram","Porur","Chromepet","Perambur","Royapettah","Mylapore","Guindy","Sholinganallur","Perungudi","Ambattur","Avadi"],
        "survey_prefix": "CHN"
    },
    "Mumbai": {
        "state": "Maharashtra",
        "base_lat": 19.0760, "base_lng": 72.8777, "spread": 0.12,
        "price_base": 15_000_000, "price_max": 200_000_000,
        "taluks": ["Mumbai City", "Mumbai Suburban", "Andheri", "Borivali", "Kurla"],
        "localities": ["Andheri","Bandra","Borivali","Dadar","Goregaon","Malad","Kandivali","Kurla","Ghatkopar","Mulund","Thane","Powai","Vikhroli","Chembur","Sion","Worli","Lower Parel","Prabhadevi"],
        "survey_prefix": "MUM"
    },
    "Vellore": {
        "state": "Tamil Nadu",
        "base_lat": 12.9165, "base_lng": 79.1325, "spread": 0.20,
        "price_base": 1_800_000, "price_max": 18_000_000,
        "taluks": ["Vellore", "Katpadi", "Anaicut", "Arcot", "Gudiyatham"],
        "localities": ["Katpadi","Sathuvachari","Gandhi Nagar","Bagayam","Kosapet","Melvisharam","Arcot","Ranipet","Wallajah","Sholingur","Gudiyatham","Ambur","Vaniyambadi"],
        "survey_prefix": "VLR"
    },
    "Hyderabad": {
        "state": "Telangana",
        "base_lat": 17.3850, "base_lng": 78.4867, "spread": 0.18,
        "price_base": 5_000_000, "price_max": 70_000_000,
        "taluks": ["Hyderabad", "Secunderabad", "Rangareddy", "Medchal", "Shamshabad"],
        "localities": ["Banjara Hills","Jubilee Hills","Hitech City","Gachibowli","Kondapur","Madhapur","Manikonda","Kukatpally","Ameerpet","Begumpet","Secunderabad","Uppal","LB Nagar"],
        "survey_prefix": "HYD"
    },
    "Pune": {
        "state": "Maharashtra",
        "base_lat": 18.5204, "base_lng": 73.8567, "spread": 0.18,
        "price_base": 4_000_000, "price_max": 50_000_000,
        "taluks": ["Pune City", "Haveli", "Khed", "Shirur", "Mulshi"],
        "localities": ["Kothrud","Wakad","Baner","Aundh","Hinjewadi","Viman Nagar","Koregaon Park","Kalyani Nagar","Hadapsar","Magarpatta","Kondhwa","Katraj","Bavdhan","Balewadi"],
        "survey_prefix": "PNE"
    },
    "Kolkata": {
        "state": "West Bengal",
        "base_lat": 22.5726, "base_lng": 88.3639, "spread": 0.15,
        "price_base": 3_000_000, "price_max": 40_000_000,
        "taluks": ["Kolkata North", "Kolkata South", "Salt Lake", "Howrah", "Barasat"],
        "localities": ["Salt Lake","New Town","Rajarhat","Dum Dum","Behala","Jadavpur","Tollygunge","Ballygunge","Park Street","Alipore","Howrah","Shibpur","Barasat"],
        "survey_prefix": "KOL"
    },
    "Ahmedabad": {
        "state": "Gujarat",
        "base_lat": 23.0225, "base_lng": 72.5714, "spread": 0.16,
        "price_base": 3_500_000, "price_max": 45_000_000,
        "taluks": ["Ahmedabad City", "Daskroi", "Sanand", "Dholka"],
        "localities": ["SG Highway","Bopal","Satellite","Navrangpura","Prahlad Nagar","Bodakdev","Vastrapur","Maninagar","Sanand Industrial","Ghatlodia","Thaltej"],
        "survey_prefix": "AMD"
    },
    "Jaipur": {
        "state": "Rajasthan",
        "base_lat": 26.9124, "base_lng": 75.7873, "spread": 0.18,
        "price_base": 2_500_000, "price_max": 35_000_000,
        "taluks": ["Jaipur", "Sanganer", "Amer", "Chaksu"],
        "localities": ["Malviya Nagar","Vaishali Nagar","Mansarovar","C Scheme","Jagatpura","Tonk Road","Ajmer Road","Sanganer","Amer Road","Bani Park"],
        "survey_prefix": "JPR"
    },
    "Lucknow": {
        "state": "Uttar Pradesh",
        "base_lat": 26.8467, "base_lng": 80.9462, "spread": 0.16,
        "price_base": 2_800_000, "price_max": 32_000_000,
        "taluks": ["Lucknow", "Bakshi Ka Talab", "Mohanlalganj", "Sarojini Nagar"],
        "localities": ["Gomti Nagar","Hazratganj","Aliganj","Indira Nagar","Vikas Nagar","Mahanagar","Ashiyana","Janki Puram","Shaheed Path","Chinhat"],
        "survey_prefix": "LKO"
    },
    "Patna": {
        "state": "Bihar",
        "base_lat": 25.5941, "base_lng": 85.1376, "spread": 0.15,
        "price_base": 2_200_000, "price_max": 28_000_000,
        "taluks": ["Patna Sadar", "Danapur", "Phulwari", "Fatwah"],
        "localities": ["Boring Road","Kankarbagh","Bailey Road","Patliputra","Danapur","Rajendra Nagar","Anisabad","Ashiana Nagar","Phulwari Sharif","Digha"],
        "survey_prefix": "PAT"
    },
    "Visakhapatnam": {
        "state": "Andhra Pradesh",
        "base_lat": 17.6868, "base_lng": 83.2185, "spread": 0.16,
        "price_base": 2_500_000, "price_max": 35_000_000,
        "taluks": ["Visakhapatnam Urban", "Visakhapatnam Rural", "Gajuwaka", "Anakapalle"],
        "localities": ["MVP Colony","Siripuram","Madhurawada","Gajuwaka","Rushikonda","Seethammadhara","Dwaraka Nagar","Pendurthi","Bheemunipatnam"],
        "survey_prefix": "VSKP"
    }
}

LOCATION_SEED = {
    "Bengaluru Urban": {
        "Bengaluru North": ["Yelahanka", "Hebbal", "Jakkur"],
        "Bengaluru South": ["Jayanagar", "JP Nagar", "Bommanahalli"],
        "Bengaluru East": ["Whitefield", "KR Puram", "Mahadevapura"],
    },
    "Chennai": {
        "Egmore": ["Kilpauk", "Chetpet", "Nungambakkam"],
        "Mylapore": ["Alwarpet", "Adyar", "Besant Nagar"],
    },
    "Vellore": {
        "Vellore": ["Katpadi", "Gandhi Nagar", "Sathuvachari"],
        "Gudiyatham": ["Melvisharam", "Pallikonda"],
    },
    "Delhi": {
        "New Delhi": ["Connaught Place", "Chanakyapuri"],
        "South Delhi": ["Saket", "Hauz Khas", "Mehrauli"],
        "Dwarka": ["Sector 12", "Sector 21"],
    },
    "Mumbai": {
        "Andheri": ["Andheri East", "Andheri West"],
        "Borivali": ["Borivali West", "Kandivali"],
    },
    "Hyderabad": {
        "Hyderabad": ["Banjara Hills", "Jubilee Hills"],
        "Rangareddy": ["Hitech City", "Gachibowli"],
    },
    "Pune": {
        "Pune City": ["Kothrud", "Aundh", "Baner"],
        "Haveli": ["Hinjewadi", "Wakad"],
    },
    "Ahmedabad": {
        "Ahmedabad City": ["SG Highway", "Navrangpura"],
        "Daskroi": ["Bopal", "Satellite"],
    },
    "Kolkata": {
        "Salt Lake": ["Sector V", "New Town"],
        "Kolkata South": ["Ballygunge", "Tollygunge"],
    },
    "Jaipur": {
        "Jaipur": ["Malviya Nagar", "C Scheme"],
        "Sanganer": ["Mansarovar", "Jagatpura"],
    },
    "Lucknow": {
        "Lucknow": ["Gomti Nagar", "Hazratganj"],
        "Bakshi Ka Talab": ["Aliganj", "Vikas Nagar"],
    },
    "Patna": {
        "Patna Sadar": ["Boring Road", "Kankarbagh"],
        "Danapur": ["Bailey Road", "Patliputra"],
    },
    "Visakhapatnam": {
        "Visakhapatnam Urban": ["MVP Colony", "Siripuram"],
        "Gajuwaka": ["Madhurawada", "Rushikonda"],
    },
    "Bengaluru Rural": {
        "Devanahalli": ["Devanahalli Town", "Bagalur"],
        "Hoskote": ["Hoskote Industrial", "Budigere Cross"],
    }
}

def seed_locations(conn):
    for district, taluks in LOCATION_SEED.items():
        for taluk, villages in taluks.items():
            for village in villages:
                conn.execute(
                    "INSERT OR IGNORE INTO locations (district, taluk, village) VALUES (?,?,?)",
                    (district, taluk, village)
                )
    conn.commit()

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
    "Balu Mahendra","Revathy Nair","Ganesh Patel","Saritha Devi","Mohan Das",
    "Chandrika Sinha","Ashok Kumar","Padmavathi Reddy","Gopal Krishnan","Swarna Latha",
    "Venkat Rao","Bhavana Menon","Srinivas Murthy","Sumitra Devi","Ramu Naik",
    "Kamal Hassan","Jayashree Rao","Balakrishnan","Suganya Devi","Muthu Swamy",
    "Thiruvengadam","Nalini Jayaram","Selvam","Kamala Devi","Arumugam",
    "Balachandran","Radhika Apte","Sundaram","Vimala Devi","Krishnamurthy",
    "Palaniswamy","Malathi Rao","Duraiswamy","Punitha Devi","Senthilkumar",
    "Meenakshi Sundaram","Prabhu Deva","Saranya","Thiagarajan","Pushpa Lata",
    "Nazim Khan","Fatima Begum","Salman Sheikh","Ayesha Siddiqui","Irfan Patel",
    "Zubair Ahmed","Hina Malik","Farhan Akhtar","Shabana Azmi","Javed Akhtar",
    "Parineeti Chopra","Siddharth Malhotra","Shraddha Kapoor","Varun Dhawan",
    "Alia Bhatt","Ranbir Kapoor","Katrina Kaif","Akshay Kumar","Deepika Padukone"
]

LAND_TYPES = ["Residential", "Commercial", "Agricultural", "Industrial"]
LAND_USES  = {
    "Residential":  ["Housing", "Apartment", "Villa", "Duplex", "Row House"],
    "Commercial":   ["Office", "Retail Shop", "Mall", "Showroom", "Warehouse"],
    "Agricultural": ["Farming", "Horticulture", "Plantation", "Orchard", "Grazing"],
    "Industrial":   ["Factory", "Workshop", "Logistics", "Manufacturing", "IT Park"]
}
STATUSES_DIST    = ["clear", "clear", "clear", "clear", "mortgaged", "disputed"]
ENCUMBRANCES     = ["None", "None", "None", "Bank Mortgage", "Court Order", "Loan Pending", "Family Dispute"]
TRANSFER_TYPES   = ["Sale", "Inheritance", "Gift", "Partition", "Court Decree", "Exchange"]
GRIEVANCE_CATS   = ["Title Dispute","Encroachment","Record Correction","Document Issue",
                    "Mutation Delay","Corruption Complaint","Boundary Dispute","Other"]
GRIEVANCE_STATUS = ["submitted","under_review","resolved","rejected","escalated"]


def rand_date(years_ago_min, years_ago_max):
    days = random.randint(years_ago_min * 365, years_ago_max * 365)
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

def rand_phone():
    return "9" + str(random.randint(100000000, 999999999))

def rand_aadhaar():
    return f"{random.randint(1000,9999)}-{random.randint(1000,9999)}-{random.randint(1000,9999)}"

def seed_data(conn, c):
    print("Seeding database with 840+ balanced land records across 14 districts...")
    rng = random.Random(42)  # reproducible

    # Clear old data if re-seeding
    c.execute("DELETE FROM price_history")
    c.execute("DELETE FROM ownership_history")
    c.execute("DELETE FROM mutations")
    c.execute("DELETE FROM grievances")
    c.execute("DELETE FROM land_parcels")
    c.execute("DELETE FROM users")

    # ── USERS ──────────────────────────────────────────────────
    admin_id = str(uuid.uuid4())
    c.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?)",
              (admin_id,'Admin Officer','admin@landrecords.gov.in','9800000001',
               hash_password('admin123'),'admin',None,datetime.now().isoformat()))

    base_citizens = [
        ('Ramesh Kumar Sharma','ramesh@email.com','9876543210','1234-5678-9012'),
        ('Priya Devi Nair','priya@email.com','9876543211','2345-6789-0123'),
        ('Suresh Babu Reddy','suresh@email.com','9876543212','3456-7890-1234'),
        ('Anita Kumari Singh','anita@email.com','9876543213','4567-8901-2345'),
        ('Mohammad Arif Khan','arif@email.com','9876543214','5678-9012-3456'),
        ('Lakshmi Venkatesh','lakshmi@email.com','9876543215','6789-0123-4567'),
        ('Vijay Prakash Rao','vijay@email.com','9876543216','7890-1234-5678'),
        ('Geeta Mahesh Patel','geeta@email.com','9876543217','8901-2345-6789'),
    ]
    citizen_ids = []
    for name, email, phone, aadhaar in base_citizens:
        uid = str(uuid.uuid4())
        citizen_ids.append(uid)
        c.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?)",
                  (uid,name,email,phone,hash_password('citizen123'),'citizen',aadhaar,datetime.now().isoformat()))

    # ── LAND PARCELS (Guaranteed 15 of EACH Land Type per District) ──
    all_parcel_ids = []
    parcel_counter = {}

    for city_name, city in CITIES.items():
        parcel_counter[city_name] = 0
        counter = 1

        # 15 Residential, 15 Commercial, 15 Agricultural, 15 Industrial = 60 per district
        for ltype in LAND_TYPES:
            for k in range(15):
                pid    = str(uuid.uuid4())
                prefix = city["survey_prefix"]
                num    = counter
                counter += 1
                sub    = rng.choice(["A","B","C","1","2","3","P","Q"])
                survey = f"{prefix}-{num:03d}/{sub}-{pid[:4].upper()}"

                locality = rng.choice(city["localities"])
                taluk    = rng.choice(city["taluks"])
                luse     = rng.choice(LAND_USES[ltype])
                
                # Ensure each status (clear, disputed, mortgaged) is represented
                if k % 5 == 3:
                    status = "disputed"
                    enc = "Court Order"
                elif k % 5 == 4:
                    status = "mortgaged"
                    enc = "Bank Mortgage"
                else:
                    status = "clear"
                    enc = "None"

                # Area based on land type
                if ltype == "Residential":
                    area = round(rng.uniform(0.05, 0.75), 2)
                elif ltype == "Commercial":
                    area = round(rng.uniform(0.20, 2.50), 2)
                elif ltype == "Agricultural":
                    area = round(rng.uniform(1.50, 15.00), 2)
                else: # Industrial
                    area = round(rng.uniform(1.00, 8.00), 2)

                # Realistic scatter
                lat = city["base_lat"] + rng.uniform(-city["spread"], city["spread"])
                lng = city["base_lng"] + rng.uniform(-city["spread"], city["spread"])

                # Pricing calculation with land type multiplier
                type_mult = {"Residential": 1.4, "Commercial": 2.2, "Agricultural": 0.35, "Industrial": 1.1}[ltype]
                base  = city["price_base"] * type_mult
                maxv  = city["price_max"] * type_mult
                price = round(rng.uniform(base, maxv) * (area / 1.5), -3)
                price = max(price, base * 0.4)

                owner_id = rng.choice(citizen_ids)

                c.execute("""INSERT INTO land_parcels VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                          (pid, survey, city_name, taluk, locality, area, ltype, luse,
                           owner_id, round(lat,6), round(lng,6), price, status, enc,
                           datetime.now().isoformat()))

                # ── Ownership history (2–4 owners) ─────────────────
                n_owners   = rng.randint(2, 4)
                dates      = sorted([rand_date(2, 30) for _ in range(n_owners - 1)])
                prev_value = price * rng.uniform(0.2, 0.5)

                for j in range(n_owners):
                    from_d  = dates[j-1] if j > 0 else rand_date(25, 40)
                    to_d    = dates[j] if j < n_owners - 1 else None
                    ttype   = rng.choice(TRANSFER_TYPES)
                    deed    = f"DD-{rng.randint(1000,9999)}-{rng.randint(100,999)}"
                    amt     = 0 if ttype == "Inheritance" else round(prev_value * rng.uniform(0.85,1.25), -3)
                    prev_value = amt if amt > 0 else prev_value
                    owner_name = rng.choice(INDIAN_NAMES)
                    c.execute("INSERT INTO ownership_history VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                              (str(uuid.uuid4()), pid, owner_name, rand_aadhaar(), rand_phone(),
                               from_d, to_d, ttype, deed, amt, None))

                # ── Price history (2020–2025) ───────────────────────
                # Realistic historical growth for ML regression
                annual_cagr = rng.uniform(1.07, 1.15)
                # Compute base price in 2020 that leads to current price in 2025
                p2020 = price / (annual_cagr ** 5)
                current_p = p2020
                for yr in range(2020, 2026):
                    noise = rng.uniform(0.97, 1.03)
                    mkt   = round(current_p * noise, -3)
                    govt  = round(mkt * rng.uniform(0.60, 0.72), -3)
                    c.execute("INSERT INTO price_history VALUES (?,?,?,?,?,?)",
                              (str(uuid.uuid4()), pid, yr, mkt, govt, datetime.now().isoformat()))
                    current_p *= annual_cagr

                all_parcel_ids.append(pid)
                parcel_counter[city_name] += 1

    conn.commit()

    # ── GRIEVANCES (30 across all cities) ─────────────────────
    grievance_subjects = [
        ("Title Dispute",        "Encroachment on registered plot by neighbor"),
        ("Record Correction",    "Name misspelled in land ownership record"),
        ("Document Issue",       "Original sale deed not received after registration"),
        ("Mutation Delay",       "Mutation pending for over 6 months after purchase"),
        ("Boundary Dispute",     "Survey markers removed by adjacent land owner"),
        ("Corruption Complaint", "Bribe demanded by local tahsildar for NOC"),
        ("Encroachment",         "Unauthorized construction on government land"),
        ("Title Dispute",        "Fraudulent transfer of land without consent"),
        ("Record Correction",    "Area mentioned in records does not match actual"),
        ("Document Issue",       "Pahani certificate showing wrong owner name"),
        ("Mutation Delay",       "Property transfer stuck in tehsil for 8 months"),
        ("Other",                "Land classified wrongly as agricultural instead of residential"),
        ("Boundary Dispute",     "Fence erected beyond boundary by neighbour"),
        ("Title Dispute",        "Duplicate sale deed issued by fraudulent agent"),
        ("Encroachment",         "Encroachment on highway setback land"),
        ("Record Correction",    "Survey number mismatch between state and central records"),
        ("Corruption Complaint", "Officer demanding payment for registration appointment"),
        ("Mutation Delay",       "Legal heir mutation pending for over 1 year"),
        ("Document Issue",       "Encumbrance certificate not issued despite application"),
        ("Boundary Dispute",     "Wall construction crossing into my registered plot"),
        ("Title Dispute",        "Court-disputed land sold without disclosure"),
        ("Other",                "Agricultural land converted to residential without approval"),
        ("Encroachment",         "Road widening affecting 2 cents of private plot"),
        ("Record Correction",    "Wrong khata number linked to my property"),
        ("Mutation Delay",       "Purchased plot 4 months ago, mutation not done"),
        ("Corruption Complaint", "Sub-registrar office delaying registration for bribe"),
        ("Boundary Dispute",     "Land boundary unclear after old survey stones removed"),
        ("Document Issue",       "Property tax receipt shows different owner"),
        ("Title Dispute",        "Two separate parties claiming ownership of same survey number"),
        ("Record Correction",    "Village changed in record from Katpadi to Vellore incorrectly"),
    ]
    descriptions = [
        "I purchased this land legally with all documents in order. The neighbor has illegally encroached upon 10 feet of my registered boundary and constructed a compound wall. Despite repeated verbal requests, the encroachment has not been removed. I am filing this complaint seeking immediate action and removal of illegal structure.",
        "The land records show my name as 'Rahmesh' instead of 'Ramesh'. This error has caused multiple rejections in bank loan applications. I request immediate correction of my name in all government records including RTC, mutation register, and revenue records.",
        "I registered my property on 15 March 2024 and paid all applicable duties. However, I have not received the original sale deed documents from the sub-registrar office. Multiple visits have yielded no result. This is causing me difficulty in obtaining a housing loan.",
        "I purchased this agricultural land through a registered sale deed dated November 2023. The mutation has been pending for 7 months despite submission of all required documents including sale deed, identity proof, and Encumbrance Certificate.",
        "Survey markers on my registered boundary have been physically removed by the adjacent land owner. This is causing confusion about the exact boundary location. I am requesting a fresh survey and restoration of boundary markers.",
        "The local tahsildar has demanded a payment of Rs. 15,000 for issuing an NOC for my land. This is a case of corruption and I am formally reporting this along with supporting evidence including recorded phone calls.",
        "Unauthorized construction has been taking place on government land adjacent to my plot. I have reported this multiple times to local authorities but no action has been taken. The encroachers have built permanent structures.",
        "I have discovered that my land was fraudulently transferred to a third party without my knowledge or consent. My digital signature was forged in the registration documents. I am seeking immediate cancellation of fraudulent transfer.",
    ]

    statuses_list = ["submitted","under_review","resolved","submitted","under_review","escalated"]
    priorities_list = ["high","high","medium","low","medium","high"]

    for i, (cat, subj) in enumerate(grievance_subjects):
        gid     = str(uuid.uuid4())
        year    = 2024 + (i % 2)
        code    = uuid.uuid4().hex[:8].upper()
        ticket  = f"GRV-{year}-{code}"
        parcel  = rng.choice(all_parcel_ids) if rng.random() > 0.3 else None
        status  = statuses_list[i % len(statuses_list)]
        priority= priorities_list[i % len(priorities_list)]
        name    = rng.choice(INDIAN_NAMES)
        desc    = descriptions[i % len(descriptions)]
        remarks = "Under investigation by district revenue officer." if status == "under_review" else (
                  "Issue resolved. Records corrected." if status == "resolved" else None)
        created = rand_date(0, 1)
        resolved= rand_date(0, 0) if status == "resolved" else None

        c.execute("""INSERT INTO grievances VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (gid, ticket, name, f"{name.lower().replace(' ','.')}@email.com",
                   rand_phone(), parcel, cat, subj, desc, status, priority,
                   admin_id, remarks, created, created, resolved))

    conn.commit()

    conn.commit()

    seed_locations(conn)

    total = sum(parcel_counter.values())
    print(f"\n✅ Database seeded successfully!")
    print(f"   Total parcels: {total}")
    for city, count in parcel_counter.items():
        print(f"   {city}: {count} records")
    print(f"   Grievances: {len(grievance_subjects)}")

