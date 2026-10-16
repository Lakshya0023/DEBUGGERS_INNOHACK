<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6,12,20&height=270&section=header&text=BHOOMISEVA&fontSize=80&fontColor=ffffff&animation=fadeIn&fontAlignY=38&desc=Digital%20Land%20Record%20Management%20System&descAlignY=60&descSize=22" alt="BhoomiSeva banner" width="100%"/>

<img src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=600&size=21&duration=2800&pause=900&color=22C55E&center=true&vCenter=true&width=950&lines=%E0%A4%AD%E0%A5%82%E0%A4%AE%E0%A4%BF+%E0%A4%B8%E0%A5%87%E0%A4%B5%E0%A4%BE+%E0%A4%AA%E0%A5%8B%E0%A4%B0%E0%A5%8D%E0%A4%9F%E0%A4%B2;Explore+Land+on+an+Interactive+Map;Verify+Ownership+and+Price+History;File+and+Track+Grievances;Transparent+Land+Governance" alt="BhoomiSeva typing animation"/>

<br/>

**A secure, transparent full-stack web platform for land record management and citizen grievance redressal. Built for the Digital India Initiative at InnoHack.**

<br/>

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-REST_API-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![SQLite](https://img.shields.io/badge/SQLite-Zero_Setup-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Leaflet](https://img.shields.io/badge/Leaflet.js-Interactive_Map-199900?style=for-the-badge&logo=leaflet&logoColor=white)](https://leafletjs.com/)
[![Chart.js](https://img.shields.io/badge/Chart.js-Analytics-FF6384?style=for-the-badge&logo=chartdotjs&logoColor=white)](https://www.chartjs.org/)
[![Vercel](https://img.shields.io/badge/Vercel-Deployed-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://debuggers-innohack.vercel.app)

<br/>

[![Live Demo](https://img.shields.io/badge/%E2%9C%A6%20LIVE%20DEMO-Open%20App-22C55E?style=for-the-badge&labelColor=0B1220)](https://debuggers-innohack.vercel.app)
[![Source Code](https://img.shields.io/badge/%E2%9C%A6%20SOURCE-GitHub-8B5CF6?style=for-the-badge&labelColor=0B1220&logo=github)](https://github.com/Lakshya0023/DEBUGGERS_INNOHACK)

<br/>

<a href="#-overview">Overview</a> &nbsp;·&nbsp;
<a href="#-features">Features</a> &nbsp;·&nbsp;
<a href="#-architecture">Architecture</a> &nbsp;·&nbsp;
<a href="#-map-explorer">Map</a> &nbsp;·&nbsp;
<a href="#-api-reference">API</a> &nbsp;·&nbsp;
<a href="#-quick-start">Quick Start</a> &nbsp;·&nbsp;
<a href="#-demo-credentials">Demo Login</a> &nbsp;·&nbsp;
<a href="#-roadmap">Roadmap</a>

</div>

<br/>

```text
 ____  _   _  ___   ___  __  __ ___   ____  _______     ___
| __ )| | | |/ _ \ / _ \|  \/  |_ _| / ___|| ____\ \   / / \
|  _ \| |_| | | | | | | | |\/| || |  \___ \|  _|  \ \ / / _ \
| |_) |  _  | |_| | |_| | |  | || |   ___) | |___  \ V / ___ \
|____/|_| |_|\___/ \___/|_|  |_|___| |____/|_____|  \_/_/   \_\
```

> **BhoomiSeva** (भूमि सेवा, "land service") puts land records in front of citizens. Anyone can click a parcel on the map and see who owns it, who owned it before, and how its price has moved. When something goes wrong, they can file a grievance and track it by ticket ID.

<br/>

## ✦ At a Glance

<div align="center">

| 🗺️ **20** | 🏷️ **5** | 📄 **5** | 🌐 **13** | 🔐 **2** |
|:---:|:---:|:---:|:---:|:---:|
| Seeded land parcels | Land-type colour codes | Web pages | API endpoints | User roles |

</div>

<br/>

## ✦ Overview

Land records are often hard to reach, hard to verify and slow to correct. BhoomiSeva brings three things into one portal:

<div align="center">

| 🗺️ Explore | 📜 Verify | 📣 Resolve |
|:---:|:---:|:---:|
| Click any parcel on a live map | Ownership and price history in one view | File and track complaints by ticket ID |

</div>

```mermaid
flowchart LR
    C(["🧑 Citizen"]) --> W["🌐 Web Portal<br/>HTML · CSS · JS"]
    A(["🏛️ Admin"]) --> W
    W -->|"REST + JWT"| API{{"🐍 Flask API"}}
    API --> DB[("🗄️ SQLite<br/>Land Records")]
    W --> MAP["🗺️ Leaflet +<br/>OpenStreetMap"]
    W --> CH["📊 Chart.js"]

    classDef user fill:#FEF3C7,stroke:#F59E0B,color:#0B1220
    classDef web fill:#DBEAFE,stroke:#3B82F6,color:#0B1220
    classDef api fill:#22C55E,stroke:#166534,color:#fff,stroke-width:2px
    classDef store fill:#0F172A,stroke:#38BDF8,color:#E2E8F0
    class C,A user
    class W,MAP,CH web
    class API api
    class DB store
```

<br/>

## ✦ Features

<div align="center">

| 🗺️ Land Records | 📣 Grievance Redressal | 🏛️ Administration |
|:---|:---|:---|
| Interactive map with colour-coded parcels | File a grievance online | Admin analytics dashboard |
| Survey number, area, village and district | Get a unique ticket ID | Create and update land parcels |
| Current owner details | Track status by ticket ID | Update grievance status |
| Ownership history per parcel | Status updates managed by admin | KPI widgets and charts |
| Price trend chart, market vs govt value | | Search, filter and paginate records |
| Deed numbers, transfer types, amounts | | JWT-secured admin access |

</div>

<br/>

## ✦ Architecture

```mermaid
flowchart TD
    subgraph FE["🎨 Frontend · Vanilla HTML / CSS / JS"]
        H["index.html<br/>Landing"]
        M["map.html<br/>Map Explorer"]
        R["records.html<br/>Land Records"]
        G["grievance.html<br/>Grievance Portal"]
        D["admin.html<br/>Admin Dashboard"]
    end

    subgraph BE["⚙️ Backend · Flask"]
        S["server.py<br/>REST API + JWT"]
        DBM["db.py<br/>SQLite setup + seed data"]
    end

    DB[("🗄️ land_records.db")]

    H --> S
    M --> S
    R --> S
    G --> S
    D --> S
    S --> DBM --> DB

    classDef fe fill:#DBEAFE,stroke:#3B82F6,color:#0B1220
    classDef be fill:#22C55E,stroke:#166534,color:#fff
    classDef st fill:#0F172A,stroke:#38BDF8,color:#E2E8F0
    class H,M,R,G,D fe
    class S,DBM be
    class DB st
```

<div align="center">

| Layer | Technology | Notes |
|:---|:---|:---|
| 🐍 **Backend** | Python 3 + Flask | REST API |
| 🗄️ **Database** | SQLite | Zero setup, auto-created with seed data |
| 🗺️ **Map** | Leaflet.js + OpenStreetMap | Interactive parcel explorer |
| 📊 **Charts** | Chart.js | Price trends and admin analytics |
| 🔐 **Auth** | JWT (HMAC-SHA256) | No external library needed |
| 🎨 **Frontend** | Pure HTML + CSS + Vanilla JS | No build step |
| ☁️ **Hosting** | Vercel | Live at `debuggers-innohack.vercel.app` |

</div>

<br/>

## ✦ Pages

<div align="center">

| Page | URL | Description |
|:---|:---|:---|
| 🏠 Home | `/` | Landing page with stats |
| 🗺️ Map Explorer | `/map.html` | Interactive map: click to see land details |
| 📜 Land Records | `/records.html` | Search and filter all land parcels |
| 📣 Grievance Portal | `/grievance.html` | File and track complaints |
| 📊 Admin Dashboard | `/admin.html` | Admin analytics and management |

</div>

<br/>

## ✦ Map Explorer

The map is seeded with **20 land parcels across Bengaluru and surrounding areas**. Click any marker to open the parcel's full record:

<div align="center">

| 📍 Parcel Info | 👤 Ownership | 📈 Pricing |
|:---|:---|:---|
| Survey number | Current owner details | Price trend chart, 2020 to 2025 |
| Area | Ownership history (2–3 previous owners per parcel) | Market value vs govt value |
| Village and district | Deed numbers, transfer types, consideration amounts | |

</div>

### Marker colours

<div align="center">

| Marker | Land type |
|:---:|:---|
| 🔵 | Residential |
| 🟣 | Commercial |
| 🟢 | Agricultural |
| 🟠 | Industrial |
| 🔴 *(pulsing)* | **Disputed** |

</div>

<br/>

## ✦ How a Grievance Flows

```mermaid
sequenceDiagram
    autonumber
    actor C as 🧑 Citizen
    participant UI as 🌐 Grievance Portal
    participant API as 🐍 Flask API
    participant DB as 🗄️ SQLite
    actor A as 🏛️ Admin

    C->>UI: Fill in grievance form
    UI->>API: POST /api/grievances
    API->>DB: Store grievance
    API-->>UI: Ticket ID
    UI-->>C: Show ticket ID
    A->>API: PUT /api/grievances/:id/status
    API->>DB: Update status
    C->>UI: Enter ticket ID
    UI->>API: GET /api/grievances/track/:ticket_id
    API-->>UI: Current status
```

<br/>

## ✦ API Reference

<div align="center">

| Method | Endpoint | Description | Access |
|:---:|:---|:---|:---:|
| ![POST](https://img.shields.io/badge/POST-3B82F6?style=flat-square) | `/api/auth/login` | Login | Public |
| ![POST](https://img.shields.io/badge/POST-3B82F6?style=flat-square) | `/api/auth/register` | Register | Public |
| ![GET](https://img.shields.io/badge/GET-22C55E?style=flat-square) | `/api/lands` | List parcels (search, filter, paginate) | Public |
| ![GET](https://img.shields.io/badge/GET-22C55E?style=flat-square) | `/api/lands/near?lat=&lng=` | Find the parcel nearest a map click | Public |
| ![GET](https://img.shields.io/badge/GET-22C55E?style=flat-square) | `/api/lands/all_markers` | All map markers (lightweight) | Public |
| ![GET](https://img.shields.io/badge/GET-22C55E?style=flat-square) | `/api/lands/:id` | Full detail with ownership and price history | Public |
| ![POST](https://img.shields.io/badge/POST-F59E0B?style=flat-square) | `/api/lands` | Create parcel | Admin |
| ![PUT](https://img.shields.io/badge/PUT-F59E0B?style=flat-square) | `/api/lands/:id` | Update parcel | Admin |
| ![GET](https://img.shields.io/badge/GET-22C55E?style=flat-square) | `/api/grievances` | List grievances | Auth |
| ![POST](https://img.shields.io/badge/POST-3B82F6?style=flat-square) | `/api/grievances` | File a new grievance | Auth |
| ![GET](https://img.shields.io/badge/GET-22C55E?style=flat-square) | `/api/grievances/track/:ticket_id` | Track a grievance by ticket ID | Public |
| ![PUT](https://img.shields.io/badge/PUT-F59E0B?style=flat-square) | `/api/grievances/:id/status` | Update grievance status | Admin |
| ![GET](https://img.shields.io/badge/GET-22C55E?style=flat-square) | `/api/analytics/summary` | Dashboard KPIs and chart data | Admin |

</div>

<sub>The Access column is a guide based on each endpoint's purpose. Adjust it to match your actual auth rules.</sub>

<br/>

## ✦ Quick Start

<details open>
<summary><b>1 · Clone the repository</b></summary>

<br/>

```bash
git clone https://github.com/Lakshya0023/DEBUGGERS_INNOHACK.git
cd DEBUGGERS_INNOHACK
```

</details>

<details open>
<summary><b>2 · Install dependencies</b></summary>

<br/>

Requires **Python 3.8+**.

```bash
pip install -r requirements.txt
```

</details>

<details open>
<summary><b>3 · Run the server</b></summary>

<br/>

**Option 1:** double-click `start.bat` (Windows)

**Option 2:** command line

```bash
python app.py
```

Then open **http://localhost:5000**.

The SQLite database and seed data are created automatically on first run.

</details>

<br/>

## ✦ Demo Credentials

<div align="center">

| Role | Email | Password |
|:---:|:---|:---|
| 🏛️ **Admin** | `admin@landrecords.gov.in` | `admin123` |
| 🧑 **Citizen** | `ramesh@email.com` | `citizen123` |
| 🧑 **Citizen** | `priya@email.com` | `citizen123` |

</div>

> ⚠️ These are demo accounts for the hackathon build. Change or remove them before any real deployment.

<br/>

## ✦ Project Structure

```text
DEBUGGERS_INNOHACK/
│
├── app.py                  # Entry point: run this
├── start.bat               # Windows double-click launcher
├── requirements.txt        # Python dependencies
├── package.json
├── vercel.json             # Vercel deployment config
├── .vercelignore
├── test_api_script.py      # API test script
├── states_districts.js     # State / district data
│
├── api/                    # Vercel API entry
├── data/                   # Data files
│
├── backend/
│   ├── server.py           # Flask REST API
│   ├── db.py               # SQLite setup + seed data
│   └── land_records.db     # Auto-created SQLite database
│
└── frontend/
    ├── index.html          # Landing page
    ├── map.html            # Interactive Leaflet.js map
    ├── records.html        # Land records search
    ├── grievance.html      # Grievance portal
    ├── admin.html          # Admin dashboard
    └── css/
        └── style.css       # Full design system
```

<br/>

## ✦ Design System

Built to be accessible first, in the spirit of government-grade digital services.

<div align="center">

| 🔤 Typography | 🎨 Palette | 🧩 Components |
|:---|:---|:---|
| **Atkinson Hyperlegible**, a WCAG and dyslexia-friendly typeface | Professional Blue `#1E40AF` | Glassmorphism cards |
| Accessible and ethical style | Service Green `#16A34A` | Animated KPI widgets |
| Dark OLED-friendly theme | | Timeline and stepper |

</div>

<br/>

## ✦ Testing

Run the API test script with the server running:

```bash
python test_api_script.py
```

<br/>

## ✦ Roadmap

```mermaid
timeline
    title BhoomiSeva Roadmap
    section Current
        Records : 20 seeded parcels : Ownership and price history : Interactive map
        Citizen services : Grievance filing and tracking : Admin dashboard
    section Next
        Data : Live land-registry data : Document upload for grievances
        Access : Hindi and regional language UI : SMS and email status alerts
    section Later
        Trust : Tamper-proof record trail : Digital sale-deed verification
        Scale : Multi-state coverage : Production database
```

<br/>

## ✦ Author

<div align="center">

**Team DEBUGGERS** · InnoHack

[![GitHub](https://img.shields.io/badge/GitHub-Lakshya0023-181717?style=for-the-badge&logo=github)](https://github.com/Lakshya0023)

</div>

<br/>

<div align="center">

```text
EXPLORE  →  VERIFY  →  FILE  →  TRACK  →  RESOLVE
```

### Transparent land records for every citizen

**Built with Python · Flask · SQLite · Leaflet.js · Chart.js**

<br/>

[Live Demo](https://debuggers-innohack.vercel.app) &nbsp;·&nbsp; [Source Code](https://github.com/Lakshya0023/DEBUGGERS_INNOHACK)

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6,12,20&height=120&section=footer" alt="footer" width="100%"/>

</div>
