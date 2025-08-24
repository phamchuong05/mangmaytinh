import os, threading, time
from datetime import datetime, timedelta, timezone

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit, join_room, leave_room

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "app.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev_secret")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

HOLD_TTL = 120  # seconds

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    rating = db.Column(db.String(10))

class Show(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey("movie.id"), nullable=False)
    room = db.Column(db.String(50), nullable=False)
    start_time = db.Column(db.String(30), nullable=False)
    rows = db.Column(db.Integer, nullable=False)
    cols = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    movie = db.relationship("Movie", backref="shows")

class Seat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    show_id = db.Column(db.Integer, db.ForeignKey("show.id"), nullable=False, index=True)
    seat_id = db.Column(db.String(10), nullable=False)  # e.g., A1
    status = db.Column(db.String(1), nullable=False, default="A")  # A=Available, H=Held, S=Sold
    held_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    hold_expires_at = db.Column(db.DateTime(timezone=True))
    show = db.relationship("Show", backref="seats")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def utcnow():
    return datetime.now(timezone.utc)

def cleanup_thread():
    while True:
        time.sleep(1)
        now = utcnow()
        expired = Seat.query.filter(Seat.status=="H", Seat.hold_expires_at!=None, Seat.hold_expires_at<=now).all()
        if expired:
            for s in expired:
                s.status = "A"; s.held_by = None; s.hold_expires_at = None
                # notify clients in room for this show
                socketio.emit("seat_released", {"show_code": s.show.code, "seat": s.seat_id}, room=f"show_{s.show.code}")
            db.session.commit()

def seed_data():
    if Movie.query.first():
        return
    m1 = Movie(code="M1", title="The Quantum Heist", rating="13+")
    m2 = Movie(code="M2", title="Lost in Saigon", rating="P")
    db.session.add_all([m1,m2]); db.session.commit()
    s1 = Show(code="S1", movie_id=m1.id, room="Room A", start_time="2025-08-25 19:00", rows=5, cols=7, price=85000)
    s2 = Show(code="S2", movie_id=m1.id, room="Room A", start_time="2025-08-25 21:30", rows=5, cols=7, price=85000)
    s3 = Show(code="S3", movie_id=m2.id, room="Room B", start_time="2025-08-25 20:00", rows=6, cols=8, price=75000)
    db.session.add_all([s1,s2,s3]); db.session.commit()
    for show in [s1,s2,s3]:
        for r in range(show.rows):
            row_label = chr(65+r)
            for c in range(1, show.cols+1):
                db.session.add(Seat(show_id=show.id, seat_id=f"{row_label}{c}", status="A"))
    db.session.commit()

# Routes
@app.route("/")
def index():
    movies = Movie.query.all()
    return render_template("index.html", movies=movies)

@app.route("/movie/<code>")
def movie_view(code):
    movie = Movie.query.filter_by(code=code).first_or_404()
    return render_template("movie.html", movie=movie, shows=movie.shows)

@app.route("/show/<code>")
def show_view(code):
    show = Show.query.filter_by(code=code).first_or_404()
    seats = Seat.query.filter_by(show_id=show.id).all()
    seat_map = {s.seat_id: s.status for s in seats}
    rows = []
    for r in range(show.rows):
        row_label = chr(65+r)
        rows.append((row_label, [f"{row_label}{c}" for c in range(1, show.cols+1)]))
    return render_template("seats.html", show=show, seat_map=seat_map, rows=rows)

# Auth
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        u = request.form.get("username","").strip(); p = request.form.get("password","").strip()
        if not u or not p:
            flash("Vui lòng nhập đủ thông tin","error"); return redirect(url_for("register"))
        if User.query.filter_by(username=u).first():
            flash("Tên đăng nhập đã tồn tại","error"); return redirect(url_for("register"))
        user = User(username=u); user.set_password(p)
        db.session.add(user); db.session.commit()
        flash("Đăng ký thành công. Vui lòng đăng nhập.","success"); return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u = request.form.get("username","").strip(); p = request.form.get("password","").strip()
        user = User.query.filter_by(username=u).first()
        if user and user.check_password(p):
            login_user(user); flash("Đăng nhập thành công","success"); return redirect(url_for("index"))
        flash("Tên đăng nhập hoặc mật khẩu sai","error")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user(); flash("Đã đăng xuất","success"); return redirect(url_for("index"))

# AJAX endpoints
@app.post("/api/hold")
@login_required
def api_hold():
    code = request.form.get("show_code")
    seats = request.form.getlist("seats[]") or request.form.getlist("seats")
    show = Show.query.filter_by(code=code).first_or_404()
    now = utcnow()
    ok, fail = [], []
    for seat_id in seats:
        seat = Seat.query.filter_by(show_id=show.id, seat_id=seat_id).with_for_update().first()
        if not seat:
            fail.append({"seat": seat_id, "reason":"invalid"}); continue
        if seat.status == "A":
            seat.status = "H"; seat.held_by = current_user.id; seat.hold_expires_at = now + timedelta(seconds=HOLD_TTL)
            ok.append(seat_id)
            socketio.emit("seat_held", {"show_code": code, "seat": seat_id, "by": current_user.username}, room=f"show_{code}")
        else:
            fail.append({"seat": seat_id, "reason": seat.status})
    db.session.commit()
    return jsonify({"ok": ok, "fail": fail, "ttl": HOLD_TTL})

@app.post("/api/release")
@login_required
def api_release():
    code = request.form.get("show_code")
    seats = request.form.getlist("seats[]") or request.form.getlist("seats")
    show = Show.query.filter_by(code=code).first_or_404()
    released = []
    for seat_id in seats:
        seat = Seat.query.filter_by(show_id=show.id, seat_id=seat_id).first()
        if seat and seat.status=="H" and seat.held_by==current_user.id:
            seat.status="A"; seat.held_by=None; seat.hold_expires_at=None; released.append(seat_id)
            socketio.emit("seat_released", {"show_code": code, "seat": seat_id}, room=f"show_{code}")
    db.session.commit()
    return jsonify({"released": released})

@app.post("/api/confirm")
@login_required
def api_confirm():
    code = request.form.get("show_code")
    seats = request.form.getlist("seats[]") or request.form.getlist("seats")
    show = Show.query.filter_by(code=code).first_or_404()
    ok, fail = [], []
    for seat_id in seats:
        seat = Seat.query.filter_by(show_id=show.id, seat_id=seat_id).first()
        if seat and seat.status=="H" and seat.held_by==current_user.id:
            seat.status="S"; seat.held_by=None; seat.hold_expires_at=None; ok.append(seat_id)
            socketio.emit("seat_sold", {"show_code": code, "seat": seat_id}, room=f"show_{code}")
        else:
            fail.append({"seat": seat_id, "reason":"not-held-by-you"})
    db.session.commit()
    total = len(ok)*show.price
    return jsonify({"ok": ok, "fail": fail, "total": total})

@app.get("/checkout/<code>")
@login_required
def checkout(code):
    show = Show.query.filter_by(code=code).first_or_404()
    held = Seat.query.filter_by(show_id=show.id, status="H", held_by=current_user.id).all()
    total = len(held)*show.price
    return render_template("checkout.html", show=show, seats=[s.seat_id for s in held], total=total)

@app.post("/api/pay")
@login_required
def api_pay():
    code = request.form.get("show_code")
    show = Show.query.filter_by(code=code).first_or_404()
    held = Seat.query.filter_by(show_id=show.id, status="H", held_by=current_user.id).all()
    for seat in held:
        seat.status="S"; seat.held_by=None; seat.hold_expires_at=None
        socketio.emit("seat_sold", {"show_code": code, "seat": seat.seat_id}, room=f"show_{code}")
    db.session.commit()
    return jsonify({"status":"paid", "confirmed":[s.seat_id for s in held]})

# SocketIO events
@socketio.on("join_show")
def on_join(data):
    code = data.get("show_code")
    join_room(f"show_{code}")

@socketio.on("leave_show")
def on_leave(data):
    code = data.get("show_code")
    leave_room(f"show_{code}")

# App init
with app.app_context():
    db.create_all()
    seed_data()

# Start cleanup thread
threading.Thread(target=cleanup_thread, daemon=True).start()

if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
