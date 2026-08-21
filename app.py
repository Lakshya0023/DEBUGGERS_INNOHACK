#!/ usr/bin/env python
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

import socket

def is_port_available(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return True
        except OSError:
            return False

def get_available_port(default=5000):
    if 'PORT' in os.environ:
        return int(os.environ['PORT'])
    for p in [default, 5001, 5002, 8000, 8080, 8081]:
        if is_port_available(p):
            return p
    return default


if __name__ == '__main__':
    port = get_available_port(5000)
    print("\n" + "="*50)
    print("  BhoomiSeva - Digital Land Record Management System")
    print("="*50)
    
    # Initialize database
    init_db()
    
    print("\n✅ Database ready")
    print(f"\n🌐 Starting server...")
    print(f"   URL: http://localhost:{port}")
    print("\n👤 Demo Credentials:")
    print("   Admin:   admin@landrecords.gov.in / admin123")
    print("   Citizen: ramesh@email.com         / citizen123")
    print("\n📄 Pages:")
    print(f"   Home:      http://localhost:{port}/")
    print(f"   Map:       http://localhost:{port}/map.html")
    print(f"   Records:   http://localhost:{port}/records.html")
    print(f"   Grievance: http://localhost:{port}/grievance.html")
    print(f"   Admin:     http://localhost:{port}/admin.html")
    print(f"\n🔌 API Base: http://localhost:{port}/api/")
    print("="*50 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)

