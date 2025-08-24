
import socket
import json
import sys
import uuid

HOST = "127.0.0.1"
PORT = 5050

def send(sock, obj):
    sock.sendall((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))

def recv(sock):
    buf = b""
    while True:
        ch = sock.recv(1)
        if not ch:
            return None
        buf += ch
        if ch == b"\n":
            break
    return json.loads(buf.decode("utf-8"))

def print_seat_map(seat_info):
    rows = seat_info["rows"]
    cols = seat_info["cols"]
    seats = seat_info["seats"]
    print(f'Room: {seat_info["room"]} | Start: {seat_info["start"]} | Price: {seat_info["price"]}')
    print("Legend: A=Available, H=Held, S=Sold")
    # header
    header = "   " + " ".join([f"{c:>2}" for c in range(1, cols+1)])
    print(header)
    for r in range(rows):
        row_label = chr(ord("A")+r)
        row_cells = []
        for c in range(1, cols+1):
            seat_id = f"{row_label}{c}"
            row_cells.append(seats.get(seat_id, "?"))
        print(f"{row_label}: " + " ".join([f"{x:>2}" for x in row_cells]))

def choose(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        return ""

def main():
    client_id = str(uuid.uuid4())[:8]
    print("Connecting to server...")
    sock = socket.create_connection((HOST, PORT))
    print("Connected.")
    msg = recv(sock)
    if msg:
        print(msg.get("message", ""), "| Protocol:", msg.get("protocol", ""))

    while True:
        print("\n=== MENU ===")
        print("1. Liệt kê phim")
        print("2. Liệt kê suất chiếu theo phim")
        print("3. Xem sơ đồ ghế của suất chiếu")
        print("4. Giữ ghế (hold)")
        print("5. Hủy giữ ghế (release)")
        print("6. Xác nhận mua ghế")
        print("7. Thoát")
        choice = choose("Chọn (1-7): ")
        if choice == "1":
            send(sock, {"type": "LIST_MOVIES"})
            resp = recv(sock)
            for m in resp.get("data", []):
                print(f'{m["id"]}: {m["title"]} (Rated {m.get("rating","")})')
        elif choice == "2":
            movie_id = choose("Nhập mã phim (vd: M1): ")
            send(sock, {"type": "LIST_SHOWS", "movie_id": movie_id})
            resp = recv(sock)
            for s in resp.get("data", []):
                print(f'{s["id"]}: {s["room"]} | {s["start"]} | price {s["price"]}')
        elif choice == "3":
            show_id = choose("Nhập mã suất chiếu (vd: S1): ")
            send(sock, {"type": "GET_SEATS", "show_id": show_id})
            resp = recv(sock)
            if resp.get("type") == "SEATS":
                print_seat_map(resp["data"])
            else:
                print("Lỗi:", resp.get("error"))
        elif choice == "4":
            show_id = choose("Mã suất chiếu: ")
            seats = choose("Danh sách ghế, cách nhau bởi dấu phẩy (vd: A1,A2): ")
            seat_list = [s.strip().upper() for s in seats.split(",") if s.strip()]
            send(sock, {"type": "HOLD_SEATS", "show_id": show_id, "seats": seat_list, "client_id": client_id})
            resp = recv(sock)
            print("Giữ thành công:", resp.get("ok"))
            fail = resp.get("fail", [])
            if fail:
                print("Không giữ được:", fail)
            print(f'Ghế được giữ trong {resp.get("ttl",0)} giây.')
        elif choice == "5":
            show_id = choose("Mã suất chiếu: ")
            seats = choose("Danh sách ghế (vd: A1,A2): ")
            seat_list = [s.strip().upper() for s in seats.split(",") if s.strip()]
            send(sock, {"type": "RELEASE_SEATS", "show_id": show_id, "seats": seat_list, "client_id": client_id})
            resp = recv(sock)
            print("Đã hủy giữ các ghế:", resp.get("released"))
        elif choice == "6":
            show_id = choose("Mã suất chiếu: ")
            seats = choose("Danh sách ghế (vd: A1,A2): ")
            seat_list = [s.strip().upper() for s in seats.split(",") if s.strip()]
            send(sock, {"type": "CONFIRM_SEATS", "show_id": show_id, "seats": seat_list, "client_id": client_id})
            resp = recv(sock)
            print("Mua thành công:", resp.get("ok"))
            if resp.get("fail"):
                print("Không mua được:", resp.get("fail"))
            print("Tổng tiền:", resp.get("total"))
        elif choice == "7":
            send(sock, {"type": "QUIT"})
            print("Tạm biệt.")
            break
        else:
            print("Không hợp lệ.")

    sock.close()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nĐã thoát.")
