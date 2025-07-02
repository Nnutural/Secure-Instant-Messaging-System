// 全局变量
let currentContactId = null;
let appData = null;
let backend = null;  // 后端对象

// 动态加载 qwebchannel.js
function loadQWebChannelScript(callback) {
    const script = document.createElement('script');
    script.src = 'qwebchannel.js'; // 确保 qwebchannel.js 路径正确
    script.onload = callback;
    script.onerror = () => {
        console.error('加载 qwebchannel.js 失败');
    };
    document.head.appendChild(script);
}

// 初始化 QWebChannel 和绑定 backend 对象
function initWebChannel() {
    if (typeof QWebChannel === 'undefined') {
        console.error('QWebChannel 未定义');
        return;
    }
    new QWebChannel(qt.webChannelTransport, function(channel) {
        backend = channel.objects.backend;
        console.log('QWebChannel 初始化完成，backend 可用');
    });
}

// DOM 加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    loadQWebChannelScript(() => {
        initWebChannel();
    });
    loadData();
    bindEvents();
});

// 载入 data.json，初始化联系人列表
function loadData() {
    fetch('data.json')
    .then(response => {
        if (!response.ok) throw new Error('网络响应失败');
        return response.json();
    })
    .then(json => {
        appData = json;
        renderContacts(appData.contacts);
        if (appData.contacts.length > 0) {
            selectContact(appData.contacts[0].id);
        }
    })
    .catch(err => {
        alert('加载数据失败，请检查 data.json 文件是否存在或格式是否正确');
        console.error(err);
    });
}

// 绑定各种事件
function bindEvents() {
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-btn');
    const searchInput = document.getElementById('search-contacts');
    const themeToggle = document.getElementById('theme-toggle');

    messageInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = this.scrollHeight + 'px';
        sendButton.disabled = !this.value.trim();
    });

    sendButton.addEventListener('click', sendMessage);

    messageInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    themeToggle.addEventListener('click', function() {
        document.body.classList.toggle('light');
    });

    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        document.querySelectorAll('.contact-item').forEach(contact => {
            const name = contact.querySelector('.contact-name').textContent.toLowerCase();
            contact.style.display = name.includes(searchTerm) ? 'flex' : 'none';
        });
    });

    setupWindowControls();
}

// 渲染联系人列表
function renderContacts(contacts) {
    const contactList = document.getElementById('contact-list');
    contactList.innerHTML = '';

    const recentHeader = document.createElement('div');
    recentHeader.className = 'contact-header';
    recentHeader.textContent = '最近聊天';
    contactList.appendChild(recentHeader);

    contacts.forEach(contact => {
        const contactItem = document.createElement('div');
        contactItem.className = 'contact-item';
        contactItem.dataset.id = contact.id;

        contactItem.innerHTML = `
            <div class="contact-avatar">
                <span>${contact.avatar}</span>
                <div class="contact-status ${contact.status === 'offline' ? 'status-offline' : ''}"></div>
            </div>
            <div class="contact-details">
                <div class="contact-name">${contact.name}</div>
                <div class="contact-preview">${contact.preview}</div>
            </div>
            <div class="contact-time">${contact.time || ''}</div>
        `;

        contactItem.addEventListener('click', () => {
            selectContact(contact.id);
        });

        contactList.appendChild(contactItem);
    });
}

// 选中联系人
function selectContact(contactId) {
    currentContactId = contactId;

    document.querySelectorAll('.contact-item').forEach(item => {
        item.classList.toggle('active', item.dataset.id == contactId);
    });

    const contact = getContactById(contactId);
    if (contact) {
        document.getElementById('current-contact-avatar').textContent = contact.avatar;
        document.getElementById('current-contact-name').textContent = contact.name;
        document.getElementById('current-contact-status').textContent =
            contact.status === 'online' ? '在线' : '离线';
    }

    loadMessages(contactId);
}

function getContactById(contactId) {
    return appData.contacts.find(contact => contact.id == contactId);
}

// 载入消息
function loadMessages(contactId) {
    const messages = appData.messages[contactId] || [];
    renderMessages(messages);
}

// 渲染消息
function renderMessages(messageData) {
    const messageHistory = document.getElementById('message-history');
    const newMessages = document.getElementById('new-messages');

    messageHistory.innerHTML = '';
    newMessages.innerHTML = '';

    if (!messageData || messageData.length === 0) {
        const noMessages = document.createElement('div');
        noMessages.className = 'message-day';
        noMessages.textContent = '无历史消息';
        messageHistory.appendChild(noMessages);
        return;
    }

    messageData.forEach(day => {
        const dayElement = document.createElement('div');
        dayElement.className = 'message-day';
        dayElement.textContent = day.date;
        messageHistory.appendChild(dayElement);

        day.messages.forEach(msg => {
            const messageElement = document.createElement('div');
            messageElement.className = `message-bubble message-${msg.sender === 'user' ? 'sent' : 'receive'}`;
            messageElement.innerHTML = `
                ${msg.content}
                <div class="message-time">${msg.time}</div>
            `;
            messageHistory.appendChild(messageElement);
        });
    });

    scrollToBottom();
}

// 发送消息，保存到后端
function sendMessage() {
    const messageInput = document.getElementById('message-input');
    const messageText = messageInput.value.trim();

    if (!messageText || !currentContactId) return;

    const now = new Date();
    const timeString = `${now.getHours()}:${now.getMinutes().toString().padStart(2, '0')}`;
    const todayDate = now.toLocaleDateString();

    // 1. 本地保存
    if (!appData.messages[currentContactId]) {
        appData.messages[currentContactId] = [];
    }

    let dayEntry = appData.messages[currentContactId].find(day => day.date === todayDate);
    if (!dayEntry) {
        dayEntry = { date: todayDate, messages: [] };
        appData.messages[currentContactId].push(dayEntry);
    }

    dayEntry.messages.push({
        sender: 'user',
        content: messageText,
        time: timeString
    });

    // 2. 界面更新
    const messageElement = document.createElement('div');
    messageElement.className = 'message-bubble message-sent';
    messageElement.innerHTML = `
        ${messageText}
        <div class="message-time">${timeString}</div>
    `;
    document.getElementById('new-messages').appendChild(messageElement);

    messageInput.value = '';
    messageInput.style.height = 'auto';
    document.getElementById('send-btn').disabled = true;
    scrollToBottom();

    // 3. 调用后端保存
    if (backend && backend.saveMessage) {
        backend.saveMessage(currentContactId, 'user', messageText, timeString, todayDate);
        console.log('调用后端保存消息');
    } else {
        console.warn('后端未连接，消息未保存');
    }

    // 4. 模拟对方回复（可删）
    setTimeout(simulateReply, 1000 + Math.random() * 2000);
}

// 模拟对方回复
function simulateReply() {
    if (!currentContactId) return;

    const replies = [
        '好的，收到',
        '谢谢你的建议',
        '我会准时到',
        '需要我带些什么吗？',
        '很高兴听到这个消息',
        '期待见面！',
        '那地方停车方便吗？'
    ];

    const randomReply = replies[Math.floor(Math.random() * replies.length)];
    const now = new Date();
    const timeString = `${now.getHours()}:${now.getMinutes().toString().padStart(2, '0')}`;

    const replyElement = document.createElement('div');
    replyElement.className = 'message-bubble message-receive';
    replyElement.innerHTML = `
        ${randomReply}
        <div class="message-time">${timeString}</div>
    `;

    document.getElementById('new-messages').appendChild(replyElement);
    scrollToBottom();
}

function scrollToBottom() {
    const messageArea = document.querySelector('.messages-container');
    messageArea.scrollTop = messageArea.scrollHeight;
}

function setupWindowControls() {
    const minimizeBtn = document.querySelector('.minimize');
    const maximizeBtn = document.querySelector('.maximize');
    const closeBtn = document.querySelector('.close');

    minimizeBtn.addEventListener('click', function() {
        this.style.opacity = '0.7';
        setTimeout(() => this.style.opacity = '1', 300);
    });

    maximizeBtn.addEventListener('click', function() {
        document.querySelector('.desktop-app').classList.toggle('fullscreen');
        const icon = this.querySelector('i');
        if (icon.classList.contains('fa-square')) {
            icon.classList.replace('fa-square', 'fa-clone');
            icon.classList.add('fas');
            icon.style.transform = 'rotate(180deg)';
        } else {
            icon.classList.replace('fa-clone', 'fa-square');
            icon.classList.remove('fas');
            icon.classList.add('far');
            icon.style.transform = '';
        }
    });

    closeBtn.addEventListener('click', function() {
        this.style.opacity = '0.7';
        setTimeout(() => {
            const app = document.querySelector('.desktop-app');
            app.style.transform = 'scale(0.9)';
            app.style.opacity = '0';
            setTimeout(() => alert('应用程序已关闭 - 此提示仅用于演示'), 300);
        }, 300);
    });
}
