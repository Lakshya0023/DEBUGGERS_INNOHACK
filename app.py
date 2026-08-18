#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BhoomiSeva - Digital Land Record Management & Grievance Redressal System
Startup entry point. Run: python app.py
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.server import app
from backend.db import init_db

if __name__ == '__main__':
    print("\n" + "="*50)
    print("  BhoomiSeva - Digital Land Record Management System")
    print("="*50)
    
    # Initialize database
    init_db()
    
    print("\n✅ Database ready")
    print("\n🌐 Starting server...")
    print("   URL: http://localhost:5000")
    print("\n👤 Demo Credentials:")
    print("   Admin:   admin@landrecords.gov.in / admin123")
    print("   Citizen: ramesh@email.com         / citizen123")
    print("\n📄 Pages:")
    print("   Home:      http://localhost:5000/")
    print("   Map:       http://localhost:5000/map.html")
    print("   Records:   http://localhost:5000/records.html")
    print("   Grievance: http://localhost:5000/grievance.html")
    print("   Admin:     http://localhost:5000/admin.html")
    print("\n🔌 API Base: http://localhost:5000/api/")
    print("="*50 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
