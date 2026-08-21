<<<<<<< HEAD
# BhoomiSeva — Digital Land Record Management System
## भूमि सेवा पोर्टल

A secure, transparent full-stack web platform for **land record management** and **citizen grievance redressal**. Built for the Hackathon — Digital India Initiative.

---

##  Quick Start

### Requirements
- Python 3.8+ (already installed)

### Run the server

**Option 1: Double-click** `start.bat`

**Option 2: Command line**
```bash
python app.py
```

Open your browser at: **http://localhost:5000**

---

##  Demo Login Credentials

| Role | Email | Password |
|---|---|---|
| Admin | admin@landrecords.gov.in | admin123 |
| Citizen | ramesh@email.com | citizen123 |
| Citizen | priya@email.com | citizen123 |

---

##  Pages

| Page | URL | Description |
|---|---|---|
| Home | `/` | Landing page with stats |
| Map Explorer | `/map.html` | Interactive map — click to see land details |
| Land Records | `/records.html` | Search/filter all land parcels |
| Grievance Portal | `/grievance.html` | File & track complaints |
| Admin Dashboard | `/admin.html` | Admin analytics & management |

---

##  API Endpoints

### Auth
- `POST /api/auth/login` — Login
- `POST /api/auth/register` — Register

### Land Records
- `GET /api/lands` — List parcels (search, filter, paginate)
- `GET /api/lands/near?lat=&lng=` — Find parcel near map click
- `GET /api/lands/all_markers` — All map markers (lightweight)
- `GET /api/lands/:id` — Full detail (ownership history, price history)
- `POST /api/lands` — Create parcel (admin)
- `PUT /api/lands/:id` — Update parcel (admin)

### Grievances
- `GET /api/grievances` — List grievances
- `POST /api/grievances` — File new grievance
- `GET /api/grievances/track/:ticket_id` — Track by ticket ID
- `PUT /api/grievances/:id/status` — Update status (admin)

### Analytics
- `GET /api/analytics/summary` — Dashboard KPIs and charts data

---

## 🗂️ Project Structure

```
hac/
├── app.py              # Entry point — run this!
├── start.bat           # Windows double-click launcher
├── backend/
│   ├── server.py       # Flask REST API
│   ├── db.py           # SQLite setup + seed data
│   └── land_records.db # Auto-created SQLite database
└── frontend/
    ├── index.html      # Landing page
    ├── map.html        # Interactive Leaflet.js map
    ├── records.html    # Land records search
    ├── grievance.html  # Grievance portal
    ├── admin.html      # Admin dashboard
    └── css/
        └── style.css   # Full design system
```

---

##  Map Features

- **20 land parcels** seeded across Bengaluru and surrounding areas
- Click any colored marker to see:
  - Survey number, area, village, district
  - **Current owner** details
  - **Ownership history** (2-3 previous owners per parcel)
  - **Price trend chart** (2020–2025, market vs govt value)
  - Deed numbers, transfer types, consideration amounts
- Color-coded markers:
  - 🔵 Blue = Residential
  - 🟣 Purple = Commercial
  - 🟢 Green = Agricultural
  - 🟠 Orange = Industrial
  - 🔴 Red (pulsing) = Disputed

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3 + Flask |
| Database | SQLite (zero setup) |
| Map | Leaflet.js + OpenStreetMap |
| Charts | Chart.js |
| Auth | JWT (HMAC-SHA256, no external library) |
| Frontend | Pure HTML + CSS + Vanilla JS |
| Design | UI/UX Pro Max Skill (government accessible style) |

---

##  Design System

- **Font**: Atkinson Hyperlegible (WCAG/dyslexia-friendly)
- **Style**: Accessible & Ethical (government grade) + Dark OLED
- **Colors**: Professional Blue `#1E40AF` + Service Green `#16A34A`
- **Components**: Glassmorphism cards, animated KPI widgets, timeline, stepper

---

*Built with  for the Hackathon — Digital Land Record Management & Grievance Redressal System*
=======
# DEBUGGERS_INNOHACK
LAND MANAGEMENT SYSTEM
>>>>>>> lakshya/main
