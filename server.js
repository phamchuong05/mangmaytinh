const express = require('express');
const http = require('http');
const path = require('path');
const { Server } = require('socket.io');
const fs = require('fs');
const bcrypt = require('bcrypt');
const multer = require('multer');

const app = express();
const server = http.createServer(app);
const io = new Server(server);

// Configure multer for file uploads
const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        cb(null, 'public/uploads/');
    },
    filename: (req, file, cb) => {
        cb(null, Date.now() + path.extname(file.originalname));
    }
});
const upload = multer({ storage: storage });

app.use(express.static(path.join(__dirname, 'public')));
app.use(express.json());

const usersFilePath = path.join(__dirname, 'users.json');
const rooms = {}; // Object để lưu trữ các phòng và lịch sử tin nhắn

// Hàm để tải dữ liệu người dùng
const loadUsers = () => {
    if (fs.existsSync(usersFilePath)) {
        const data = fs.readFileSync(usersFilePath, 'utf8');
        return JSON.parse(data);
    }
    return {};
};

// Hàm để lưu dữ liệu người dùng
const saveUsers = (users) => {
    fs.writeFileSync(usersFilePath, JSON.stringify(users, null, 2), 'utf8');
};

let users = loadUsers();

io.on('connection', (socket) => {
    console.log(`User connected: ${socket.id}`);

    // Xử lý đăng ký
    socket.on('register', async (data) => {
        const { username, password, avatarFile, fileName } = data;
        if (users[username]) {
            socket.emit('register_status', { success: false, message: 'Tên tài khoản đã tồn tại.' });
            return;
        }

        try {
            const hashedPassword = await bcrypt.hash(password, 10);
            let avatarPath = '/images/default-avatar.png'; // Ảnh đại diện mặc định
            
            if (avatarFile) {
                const uploadsDir = path.join(__dirname, 'public/uploads');
                if (!fs.existsSync(uploadsDir)) {
                    fs.mkdirSync(uploadsDir);
                }
                const avatarFileName = Date.now() + path.extname(fileName);
                const buffer = Buffer.from(avatarFile, 'base64');
                fs.writeFileSync(path.join(uploadsDir, avatarFileName), buffer);
                avatarPath = `/uploads/${avatarFileName}`;
            }

            users[username] = { password: hashedPassword, avatar: avatarPath };
            saveUsers(users);
            socket.emit('register_status', { success: true, message: 'Đăng ký thành công!' });
        } catch (error) {
            console.error('Lỗi khi đăng ký:', error);
            socket.emit('register_status', { success: false, message: 'Lỗi khi đăng ký.' });
        }
    });

    // Xử lý đăng nhập
    socket.on('login', async (data) => {
        const { username, password } = data;
        const user = users[username];
        if (user && await bcrypt.compare(password, user.password)) {
            socket.username = username;
            socket.avatar = user.avatar;
            socket.emit('login_status', { success: true, username });
            io.emit('room_list', Object.keys(rooms));
        } else {
            socket.emit('login_status', { success: false, message: 'Sai tên tài khoản hoặc mật khẩu.' });
        }
    });

    // Xử lý yêu cầu danh sách phòng
    socket.on('room_list', () => {
        socket.emit('room_list', Object.keys(rooms));
    });

    // Xử lý tham gia phòng chat
    socket.on('join_room', (roomName) => {
        if (socket.currentRoom) {
            socket.leave(socket.currentRoom);
            io.to(socket.currentRoom).emit('chat message', { type: 'status', text: `${socket.username} đã rời phòng.` });
        }
        
        if (roomName) {
            socket.join(roomName);
            socket.currentRoom = roomName;
            
            if (!rooms[roomName]) {
                rooms[roomName] = [];
            }
            
            socket.emit('room_joined', { roomName, history: rooms[roomName] });
            io.to(roomName).emit('chat message', { type: 'status', text: `${socket.username} đã tham gia phòng chat!` });
            console.log(`${socket.username} joined room: ${roomName}`);
        }
    });

    // Xử lý tin nhắn chat
    socket.on('chat message', (msg) => {
        const messageData = {
            sender: socket.username,
            text: msg,
            avatar: socket.avatar,
            type: 'chat'
        };
        io.to(socket.currentRoom).emit('chat message', messageData);
        rooms[socket.currentRoom].push(messageData);
    });

    // Xử lý khi người dùng ngắt kết nối
    socket.on('disconnect', () => {
        console.log(`User disconnected: ${socket.id}`);
        if (socket.currentRoom) {
            io.to(socket.currentRoom).emit('chat message', { type: 'status', text: `${socket.username} đã rời phòng.` });
        }
    });
});

server.listen(3000, () => {
    console.log('Server listening on *:3000');
});

// Tạo thư mục public và uploads nếu chúng chưa tồn tại
if (!fs.existsSync('public')) {
    fs.mkdirSync('public');
}
if (!fs.existsSync('public/uploads')) {
    fs.mkdirSync('public/uploads');
}

// LƯU Ý: Bạn cần cài đặt các gói Node.js sau:
// npm install express socket.io bcrypt multer