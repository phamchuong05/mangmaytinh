const express = require('express');
const http = require('http');
const socketio = require('socket.io');

const app = express();
const server = http.createServer(app);
const io = socketio(server);

// Cơ sở dữ liệu người dùng giả
const users = {};
// Lưu danh sách các phòng chat
const rooms = new Set();
// Lưu trữ lịch sử tin nhắn cho mỗi phòng
const chatHistory = {};

app.use(express.static('public'));

io.on('connection', (socket) => {
  console.log('Một người dùng đã kết nối.');

  // Gửi danh sách phòng chat hiện tại tới người dùng mới
  socket.emit('room_list', Array.from(rooms));

  // Xử lý sự kiện đăng ký
  socket.on('register', ({ username, password }) => {
    if (users[username]) {
      socket.emit('register_status', { success: false, message: 'Tên tài khoản đã tồn tại.' });
    } else {
      users[username] = { password: password };
      console.log(`Người dùng mới đã đăng ký: ${username}`);
      socket.emit('register_status', { success: true, message: 'Đăng ký thành công! Vui lòng đăng nhập.' });
    }
  });

  // Xử lý sự kiện đăng nhập
  socket.on('login', ({ username, password }) => {
    if (users[username] && users[username].password === password) {
      console.log(`Người dùng đã đăng nhập: ${username}`);
      socket.username = username;
      socket.emit('login_status', { success: true, username: username });
      socket.emit('room_list', Array.from(rooms));
    } else {
      socket.emit('login_status', { success: false, message: 'Tên tài khoản hoặc mật khẩu không đúng.' });
    }
  });

  // Xử lý sự kiện tạo phòng mới hoặc tham gia phòng đã có
  socket.on('join_room', (roomName) => {
    if (!roomName) return;

    if (socket.currentRoom) {
      socket.leave(socket.currentRoom);
      console.log(`${socket.username} đã rời phòng ${socket.currentRoom}`);
    }

    socket.join(roomName);
    socket.currentRoom = roomName;
    rooms.add(roomName);
    
    // Nếu phòng chưa có lịch sử, tạo mới một mảng rỗng
    if (!chatHistory[roomName]) {
        chatHistory[roomName] = [];
    }
    
    console.log(`${socket.username} đã tham gia phòng ${roomName}`);
    // Gửi lịch sử tin nhắn của phòng đó cho người dùng mới
    socket.emit('room_joined', { roomName, history: chatHistory[roomName] });

    // Thông báo cho tất cả người dùng trong phòng
    io.to(roomName).emit('chat message', {
      type: 'status',
      text: `${socket.username} đã tham gia phòng chat.`,
    });

    // Cập nhật danh sách phòng cho tất cả mọi người
    io.emit('room_list', Array.from(rooms));
  });

  // Xử lý tin nhắn
  socket.on('chat message', (msg) => {
    if (socket.username && socket.currentRoom) {
      const messageData = {
        type: 'message',
        text: msg,
        sender: socket.username,
      };
      // Lưu tin nhắn vào lịch sử của phòng
      chatHistory[socket.currentRoom].push(messageData);
      // Gửi tin nhắn đến tất cả mọi người trong phòng
      io.to(socket.currentRoom).emit('chat message', messageData);
    }
  });

  // Xử lý ngắt kết nối
  socket.on('disconnect', () => {
    console.log('Một người dùng đã ngắt kết nối.');
    if (socket.username && socket.currentRoom) {
      socket.broadcast.to(socket.currentRoom).emit('chat message', {
        type: 'status',
        text: `${socket.username} đã thoát phòng chat.`,
      });
    }
  });
});

server.listen(3000, () => {
  console.log('Server đang chạy tại http://localhost:3000');
});