const socket = io();

const authUi = document.getElementById('auth-ui');
const lobbyUi = document.getElementById('lobby-ui');
const chatUi = document.getElementById('chat-ui');

const authUsernameInput = document.getElementById('auth-username');
const authPasswordInput = document.getElementById('auth-password');
const avatarSection = document.getElementById('avatar-section');
const avatarFileInput = document.getElementById('avatar-file-input');
const avatarPreview = document.getElementById('avatar-preview');
const authButton = document.getElementById('auth-button');
const authToggle = document.getElementById('toggle-auth');
const authStatus = document.getElementById('auth-status');

const roomList = document.getElementById('room-list');
const refreshRoomsBtn = document.getElementById('refresh-rooms');
const roomInput = document.getElementById('room-input');
const joinRoomForm = document.getElementById('join-room-form');

const roomTitle = document.getElementById('room-title');
const backToLobbyBtn = document.querySelector('.back-to-lobby');
const form = document.getElementById('form');
const input = document.getElementById('input');
const messages = document.getElementById('messages');

let isRegisterMode = false;
let myUsername = '';
let currentRoom = '';

function showAuthUI() {
  authUi.style.display = 'flex';
  lobbyUi.style.display = 'none';
  chatUi.style.display = 'none';
}

function showLobbyUI() {
  authUi.style.display = 'none';
  lobbyUi.style.display = 'flex';
  chatUi.style.display = 'none';
}

function showChatUI() {
  authUi.style.display = 'none';
  lobbyUi.style.display = 'none';
  chatUi.style.display = 'flex';
}

function scrollToBottom() {
  messages.scrollTop = messages.scrollHeight;
}

function appendMessage(data) {
  const item = document.createElement('li');
  
  if (data.type === 'status') {
    item.classList.add('status');
    item.textContent = data.text;
  } else {
    // Tin nhắn bình thường
    const isMyMessage = (data.sender === myUsername);
    if (isMyMessage) {
      item.classList.add('self');
    } else {
      item.classList.add('other');
    }
    
    const avatar = document.createElement('img');
    avatar.src = data.avatar;
    avatar.classList.add('avatar');
    item.appendChild(avatar);

    const messageContent = document.createElement('div');
    messageContent.classList.add('message-content');
    
    const senderInfo = document.createElement('span');
    senderInfo.classList.add('message-info');
    senderInfo.textContent = data.sender;
    messageContent.appendChild(senderInfo);

    const bubble = document.createElement('div');
    bubble.classList.add('message-bubble');
    bubble.classList.add(isMyMessage ? 'self' : 'other');
    bubble.textContent = data.text;
    messageContent.appendChild(bubble);

    item.appendChild(messageContent);
  }
  
  messages.appendChild(item);
  scrollToBottom();
}

// Xử lý sự kiện Auth
authToggle.addEventListener('click', () => {
  isRegisterMode = !isRegisterMode;
  authStatus.textContent = '';
  if (isRegisterMode) {
    document.querySelector('#auth-ui h2').textContent = 'Đăng ký';
    authButton.textContent = 'Đăng ký';
    authToggle.textContent = 'Đăng nhập';
    avatarSection.classList.remove('hidden');
    authStatus.classList.remove('error');
    authStatus.classList.remove('success');
    authStatus.textContent = "Bạn có thể chọn ảnh đại diện hoặc để trống để sử dụng ảnh mặc định.";
  } else {
    document.querySelector('#auth-ui h2').textContent = 'Đăng nhập';
    authButton.textContent = 'Đăng nhập';
    authToggle.textContent = 'Đăng ký';
    avatarSection.classList.add('hidden');
    authStatus.textContent = '';
  }
});

avatarFileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            avatarPreview.src = e.target.result;
            avatarPreview.style.display = 'block';
        };
        reader.readAsDataURL(file);
    } else {
        avatarPreview.src = '';
        avatarPreview.style.display = 'none';
    }
});

authButton.addEventListener('click', () => {
  const username = authUsernameInput.value;
  const password = authPasswordInput.value;
  if (!username || !password) {
      authStatus.textContent = 'Vui lòng nhập tên tài khoản và mật khẩu.';
      authStatus.classList.add('error');
      return;
  }

  if (isRegisterMode) {
      const file = avatarFileInput.files[0];
      if (file) {
          const reader = new FileReader();
          reader.onload = (e) => {
              const avatarData = e.target.result.split(',')[1];
              socket.emit('register', {
                  username,
                  password,
                  avatarFile: avatarData,
                  fileName: file.name
              });
          };
          reader.readAsDataURL(file);
      } else {
          // Đăng ký không có file
          socket.emit('register', { username, password });
      }
  } else {
      socket.emit('login', { username, password });
  }
});

socket.on('register_status', (data) => {
  authStatus.textContent = data.message;
  authStatus.classList.toggle('success', data.success);
  authStatus.classList.toggle('error', !data.success);
  if (data.success) {
    isRegisterMode = false;
    authToggle.click();
  }
});

socket.on('login_status', (data) => {
  if (data.success) {
    myUsername = data.username;
    showLobbyUI();
  } else {
    authStatus.textContent = data.message;
    authStatus.classList.add('error');
  }
});

// Xử lý sự kiện Lobby
socket.on('room_list', (rooms) => {
  roomList.innerHTML = '';
  rooms.forEach((room) => {
    const li = document.createElement('li');
    li.classList.add('room-item');
    li.textContent = room;
    li.addEventListener('click', () => {
      socket.emit('join_room', room);
    });
    roomList.appendChild(li);
  });
});

refreshRoomsBtn.addEventListener('click', () => {
  socket.emit('room_list', null);
});

joinRoomForm.addEventListener('submit', (e) => {
  e.preventDefault();
  const roomName = roomInput.value.trim();
  if (roomName) {
    socket.emit('join_room', roomName);
    roomInput.value = '';
  }
});

// Xử lý sự kiện Chat
socket.on('room_joined', (data) => {
  currentRoom = data.roomName;
  roomTitle.textContent = data.roomName;
  messages.innerHTML = '';
  
  data.history.forEach(appendMessage);
  
  showChatUI();
  scrollToBottom();
});

backToLobbyBtn.addEventListener('click', () => {
  socket.emit('join_room', null);
  showLobbyUI();
});

form.addEventListener('submit', (e) => {
  e.preventDefault();
  if (input.value) {
    socket.emit('chat message', input.value);
    input.value = '';
  }
});

socket.on('chat message', (data) => {
  appendMessage(data);
  scrollToBottom();
});


// Bắt đầu ứng dụng
showAuthUI();