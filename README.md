
# Hệ thống đặt vé xem phim — Multi Client/Server (Python Socket)

## Cấu trúc
- `server.py`: Server TCP đa luồng, giao thức JSON Lines.
- `client.py`: Ứng dụng CLI cho nhiều client đồng thời.
- `data.json`: Dữ liệu mẫu (phim, suất chiếu, cấu hình phòng).
- Mô hình: nhiều client -> 1 server; seat hold TTL, lock theo suất chiếu.

## Yêu cầu
- Python 3.9+ (đã kiểm thử với 3.10+)
- Chạy nội bộ (localhost) hoặc LAN.

## Cách chạy
Mở **2 cửa sổ** terminal:

**Terminal 1 (Server):**
```bash
cd socket_cinema_booking
python server.py
```

**Terminal 2 (Client — có thể mở nhiều cái):**
```bash
cd socket_cinema_booking
python client.py
```

## Tính năng chính
- Liệt kê phim, suất chiếu
- Xem sơ đồ ghế (A=trống, H=đang giữ, S=đã bán)
- Giữ ghế (hold) theo `client_id` trong 120s (tự hết hạn)
- Hủy giữ ghế
- Xác nhận mua, tính tổng tiền
- An toàn đồng thời: lock theo suất chiếu + luồng dọn dẹp hold

## Giao thức (tóm tắt)
- Mỗi request/response là một JSON theo dòng (`\n` kết thúc).
- `LIST_MOVIES` -> `{type:"MOVIES", data:[...]}`
- `LIST_SHOWS`, `GET_SEATS`
- `HOLD_SEATS`, `RELEASE_SEATS`, `CONFIRM_SEATS`
- `QUIT`

## Gợi ý mở rộng
- Đăng nhập người dùng, hoá đơn
- Thanh toán (giả lập/QR)
- Ghi log đặt vé vào file/DB
- Tối ưu seat map (WebSocket/GUI), sharding theo phòng

Chúc bạn học tốt!
