Cinema Fullstack (Flask + SQLAlchemy + SocketIO)
Features:
- User auth (register/login)
- Real-time seat updates with SocketIO
- Hold TTL (120s) cleanup thread
- Mock payment (QR + 'Mark as paid')
- SQLite database seeded on first run

Run:
python -m venv .venv
# activate venv
pip install -r requirements.txt
python app.py
Open http://127.0.0.1:5000
