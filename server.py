
import socket
import threading
import json
import time
from pathlib import Path

HOST = "0.0.0.0"
PORT = 5050
DATA_FILE = Path(__file__).with_name("data.json")

# Seat states
AVAILABLE = "A"
HELD = "H"
SOLD = "S"

HOLD_TTL = 120  # seconds that a hold lasts

class ShowState:
    def __init__(self, show, rows, cols):
        self.show = show
        self.rows = rows
        self.cols = cols
        # seats dict: "A1" -> state
        self.seats = {}
        for r in range(rows):
            row_label = chr(ord("A") + r)
            for c in range(1, cols + 1):
                self.seats[f"{row_label}{c}"] = AVAILABLE
        # holds: seat -> (client_id, expire_ts)
        self.holds = {}
        self.lock = threading.RLock()

    def to_public(self):
        with self.lock:
            return {
                "show_id": self.show["id"],
                "room": self.show["room"],
                "start": self.show["start"],
                "price": self.show["price"],
                "rows": self.rows,
                "cols": self.cols,
                "seats": self.seats.copy()
            }

    def cleanup_holds(self):
        now = time.time()
        expired = []
        with self.lock:
            for seat, (cid, exp) in list(self.holds.items()):
                if exp <= now and self.seats.get(seat) == HELD:
                    self.seats[seat] = AVAILABLE
                    expired.append(seat)
                    del self.holds[seat]
        return expired

    def hold(self, client_id, seat_ids):
        now = time.time()
        ok = []
        fail = []
        with self.lock:
            for seat in seat_ids:
                state = self.seats.get(seat)
                if state != AVAILABLE:
                    fail.append({"seat": seat, "reason": f"not available ({state})"})
                    continue
                self.seats[seat] = HELD
                self.holds[seat] = (client_id, now + HOLD_TTL)
                ok.append(seat)
        return ok, fail

    def release(self, client_id, seat_ids):
        released = []
        with self.lock:
            for seat in seat_ids:
                owner = self.holds.get(seat, (None,))[0]
                if self.seats.get(seat) == HELD and owner == client_id:
                    self.seats[seat] = AVAILABLE
                    del self.holds[seat]
                    released.append(seat)
        return released

    def confirm(self, client_id, seat_ids):
        confirmed = []
        fail = []
        with self.lock:
            for seat in seat_ids:
                owner = self.holds.get(seat, (None,))[0]
                if self.seats.get(seat) == HELD and owner == client_id:
                    self.seats[seat] = SOLD
                    del self.holds[seat]
                    confirmed.append(seat)
                else:
                    fail.append({"seat": seat, "reason": "not held by you"})
        return confirmed, fail

class BookingServer:
    def __init__(self, host, port, data_file):
        self.host = host
        self.port = port
        self.data_file = data_file
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.clients = set()
        self.clients_lock = threading.Lock()

        with open(data_file, "r", encoding="utf-8") as f:
            db = json.load(f)
        self.movies = db["movies"]
        self.shows = {s["id"]: s for s in db["shows"]}

        # per-show state
        self.states = {}
        for s in db["shows"]:
            self.states[s["id"]] = ShowState(s, s["rows"], s["cols"])

        self.running = True
        self.gc_thread = threading.Thread(target=self.gc_loop, daemon=True)
        self.gc_thread.start()

    def gc_loop(self):
        while self.running:
            for st in self.states.values():
                expired = st.cleanup_holds()
                if expired:
                    # Optionally log
                    pass
            time.sleep(1)

    def start(self):
        self.server.bind((self.host, self.port))
        self.server.listen(16)
        print(f"Server listening on {self.host}:{self.port}")
        try:
            while self.running:
                conn, addr = self.server.accept()
                with self.clients_lock:
                    self.clients.add(conn)
                threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()
        finally:
            self.server.close()

    def handle_client(self, conn, addr):
        file = conn.makefile("rwb")
        try:
            self.send_json(file, {"type": "WELCOME", "message": "Cinema Booking Server", "protocol": "jsonl"})
            while True:
                line = file.readline()
                if not line:
                    break
                try:
                    req = json.loads(line.decode("utf-8").strip() or "{}")
                except json.JSONDecodeError:
                    self.send_json(file, {"type": "ERROR", "error": "invalid json"})
                    continue
                typ = req.get("type")

                if typ == "PING":
                    self.send_json(file, {"type": "PONG"})
                elif typ == "LIST_MOVIES":
                    self.send_json(file, {"type": "MOVIES", "data": self.movies})
                elif typ == "LIST_SHOWS":
                    movie_id = req.get("movie_id")
                    shows = [s for s in self.shows.values() if (movie_id is None or s["movie_id"] == movie_id)]
                    self.send_json(file, {"type": "SHOWS", "data": shows})
                elif typ == "GET_SEATS":
                    show_id = req.get("show_id")
                    st = self.states.get(show_id)
                    if not st:
                        self.send_json(file, {"type": "ERROR", "error": "invalid show_id"})
                    else:
                        self.send_json(file, {"type": "SEATS", "data": st.to_public()})
                elif typ == "HOLD_SEATS":
                    show_id = req.get("show_id")
                    seats = req.get("seats", [])
                    client_id = req.get("client_id")
                    st = self.states.get(show_id)
                    if not st:
                        self.send_json(file, {"type": "ERROR", "error": "invalid show_id"})
                    else:
                        ok, fail = st.hold(client_id, seats)
                        self.send_json(file, {"type": "HOLD_RESULT", "ok": ok, "fail": fail, "ttl": HOLD_TTL})
                elif typ == "RELEASE_SEATS":
                    show_id = req.get("show_id")
                    seats = req.get("seats", [])
                    client_id = req.get("client_id")
                    st = self.states.get(show_id)
                    if not st:
                        self.send_json(file, {"type": "ERROR", "error": "invalid show_id"})
                    else:
                        released = st.release(client_id, seats)
                        self.send_json(file, {"type": "RELEASE_RESULT", "released": released})
                elif typ == "CONFIRM_SEATS":
                    show_id = req.get("show_id")
                    seats = req.get("seats", [])
                    client_id = req.get("client_id")
                    st = self.states.get(show_id)
                    if not st:
                        self.send_json(file, {"type": "ERROR", "error": "invalid show_id"})
                    else:
                        ok, fail = st.confirm(client_id, seats)
                        total = len(ok) * st.show["price"]
                        self.send_json(file, {"type": "CONFIRM_RESULT", "ok": ok, "fail": fail, "total": total})
                elif typ == "QUIT":
                    self.send_json(file, {"type": "BYE"})
                    break
                else:
                    self.send_json(file, {"type": "ERROR", "error": "unknown command"})
        finally:
            with self.clients_lock:
                if conn in self.clients:
                    self.clients.remove(conn)
            conn.close()

    def send_json(self, file, obj):
        data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        file.write(data)
        file.flush()

if __name__ == "__main__":
    BookingServer(HOST, PORT, DATA_FILE).start()
