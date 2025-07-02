let currentTab = 'private';
let currentGroupId = null;
let currentPrivateUserId = null;
let lastMessageId = 0;
let pollingInterval = null;
let justOpenedModal = false;
let currentUpload = null;
let displayedMessageIds = new Set();
let isFetching = false;
let currentUserId = null;
let currentMessageId = null;
let currentIsSender = null;

gsap.from(".chat-window, .chat-item", { duration: 0.6, y: 20, opacity: 0, stagger: 0.05, ease: "power2.out" });

function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
}

function getCurrentUserId() {
    return currentUserId;
}

function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.className = `notification p-3 rounded-lg text-white glass-effect ${type === 'error' ? 'bg-red-600' : type === 'info' ? 'bg-blue-600' : 'bg-green-600'}`;
    notification.textContent = message;
    document.getElementById('notifications').appendChild(notification);
    gsap.from(notification, { duration: 0.3, y: -10, opacity: 0, ease: "power2.out" });
    setTimeout(() => notification.remove(), 3000);
}

function saveUserData(data) {
    localStorage.setItem('chat_user', JSON.stringify({
        user_id: data.user_id,
        username: data.username,
        display_name: data.display_name,
        profile_image: data.profile_image
    }));
}

function clearUserData() {
    localStorage.removeItem('chat_user');
}

function loadUserData() {
    return JSON.parse(localStorage.getItem('chat_user') || '{}');
}

function checkStoredUser() {
    const userData = loadUserData();
    if (userData.user_id) {
        fetch('/api/users/current/', {
            headers: { 'X-CSRFToken': getCsrfToken() }
        })
            .then(response => {
                if (!response.ok) throw new Error('کاربر معتبر نیست');
                return response.json();
            })
            .then(data => {
                currentUserId = data.user_id;
                document.getElementById('display-name').textContent = data.display_name || data.username;
                document.getElementById('username').textContent = data.username;
                document.getElementById('profile-image').src = data.profile_image || '/static/profiles/ICON_PROF.jpg';
                document.getElementById('login-modal').classList.add('hidden');
                fetchChats();
                startPolling();
                startOnlineStatusPolling();
            })
            .catch(error => {
                clearUserData();
                document.getElementById('login-modal').classList.remove('hidden');
                setTimeout(() => document.getElementById('login-modal').querySelector('.modal-content').classList.add('show'), 10);
            });
    } else {
        document.getElementById('login-modal').classList.remove('hidden');
        setTimeout(() => document.getElementById('login-modal').querySelector('.modal-content').classList.add('show'), 10);
    }
}

// اصلاح تابع startOnlineStatusPolling
function startOnlineStatusPolling() {
  if (!currentPrivateUserId) return;
  
  const checkStatus = () => {
    fetch(`/api/users/${currentPrivateUserId}/`, {
      headers: { 'X-CSRFToken': getCsrfToken() }
    })
    .then(response => {
      if (!response.ok) return;
      return response.json();
    })
    .then(data => {
      if (!data) return;
      const statusIndicator = document.querySelector(`[data-user-id="${currentPrivateUserId}"] .rounded-full`);
      if (statusIndicator) {
        // اگر endpoint وضعیت وجود ندارد، از یک مقدار پیش‌فرض استفاده کنید
        statusIndicator.className = `w-3 h-3 rounded-full bg-gray-500`;
      }
    })
    .catch(() => {});
  };

  checkStatus();
  setInterval(checkStatus, 10000);
}
function saveMessages() {
    if (!currentTab || (!currentGroupId && !currentPrivateUserId)) return;
    const messages = [];
    document.querySelectorAll('#chat-messages .message:not(.uploading)').forEach(msg => {
        const messageId = msg.dataset.messageId;
        if (messageId) {
            messages.push({
                id: messageId,
                content: msg.querySelector('.message-content')?.textContent || '',
                timestamp: msg.querySelector('.text-xs')?.textContent || '',
                files: Array.from(msg.querySelectorAll('img, video, audio, a')).map(el => ({
                    type: el.tagName.toLowerCase(),
                    src: el.src || el.href
                })),
                sender: {
                    id: msg.classList.contains('justify-end') ? getCurrentUserId() : null,
                    display_name: msg.querySelector('.message-sender')?.textContent || ''
                }
            });
        }
    });
    const storageKey = `chat_${currentTab}_${currentTab === 'group' ? currentGroupId : currentPrivateUserId}`;
    localStorage.setItem(storageKey, JSON.stringify(messages));
}

function loadMessages() {
    const storageKey = `chat_${currentTab}_${currentTab === 'group' ? currentGroupId : currentPrivateUserId}`;
    const storedMessages = JSON.parse(localStorage.getItem(storageKey) || '[]');
    const chatMessages = document.getElementById('chat-messages');
    storedMessages.forEach(msg => {
        if (!displayedMessageIds.has(parseInt(msg.id))) {
            displayedMessageIds.add(parseInt(msg.id));
            if (parseInt(msg.id) > lastMessageId) lastMessageId = parseInt(msg.id);
            const messageElement = document.createElement('div');
            const isSender = msg.sender?.id === getCurrentUserId();
            messageElement.className = `message flex ${isSender ? 'justify-end' : 'justify-start'}`;
            messageElement.dataset.messageId = msg.id;
            let filesHtml = msg.files.map(file => {
                if (file.type === 'img') return `<img src="${file.src}" alt="File" class="max-w-full rounded-lg mt-2">`;
                if (file.type === 'video') return `<video src="${file.src}" controls class="max-w-full rounded-lg mt-2"></video>`;
                if (file.type === 'audio') return `<audio src="${file.src}" controls class="w-full mt-2"></audio>`;
                return `<a href="${file.src}" class="text-blue-400 underline mt-2 block">دانلود فایل</a>`;
            }).join('');
            messageElement.innerHTML = `
                <div class="message-bubble ${isSender ? 'sent' : 'received'}">
                    <p class="message-sender">${msg.sender.display_name}</p>
                    <p class="message-content">${msg.content}</p>
                    ${filesHtml}
                    <p class="text-xs">${msg.timestamp}</p>
                    ${isSender ? '<span class="message-ticks read"></span>' : ''}
                </div>
            `;
            chatMessages.appendChild(messageElement);
            messageElement.addEventListener('contextmenu', e => showContextMenu(e, msg.id, isSender));
            gsap.from(messageElement, { duration: 0.3, y: 10, opacity: 0, ease: "power2.out" });
        }
    });
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function clearMessages() {
    document.getElementById('chat-messages').innerHTML = '';
    displayedMessageIds.clear();
    lastMessageId = 0;
    const storageKey = `chat_${currentTab}_${currentTab === 'group' ? currentGroupId : currentPrivateUserId}`;
    localStorage.removeItem(storageKey);
}

function showContextMenu(event, messageId, isSender, isUploading = false) {
    event.preventDefault();
    event.stopPropagation();
    currentMessageId = messageId;
    currentIsSender = isSender;
    const contextMenu = document.getElementById('context-menu');
    contextMenu.innerHTML = '';
    
    const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
    const hasMedia = messageElement?.querySelector('img, video, audio, a');
    
    if (isUploading) {
        contextMenu.innerHTML = `<div onclick="cancelUpload()"><i class="bi bi-x-circle"></i> لغو ارسال</div>`;
    } else {
        if (isSender) {
            contextMenu.innerHTML += `
                <div onclick="contextAction('edit')"><i class="bi bi-pencil"></i> ویرایش</div>
                <div onclick="contextAction('delete')"><i class="bi bi-trash"></i> حذف</div>
            `;
        }
        
        if (!hasMedia) {
            contextMenu.innerHTML += `
                <div onclick="contextAction('reply')"><i class="bi bi-reply"></i> پاسخ</div>
                <div onclick="contextAction('forward')"><i class="bi bi-forward"></i> ارسال به دیگری</div>
                <div onclick="contextAction('copy')"><i class="bi bi-copy"></i> کپی متن پیام</div>
            `;
        } else {
            contextMenu.innerHTML += `
                <div onclick="contextAction('download')"><i class="bi bi-download"></i> دانلود فایل</div>
                <div onclick="contextAction('forward')"><i class="bi bi-forward"></i> ارسال به دیگری</div>
            `;
        }
        
        contextMenu.innerHTML += `<div onclick="copySelectedText()"><i class="bi bi-text-paragraph"></i> کپی متن انتخاب شده</div>`;
    }
    
    contextMenu.style.display = 'block';
    contextMenu.style.top = `${event.clientY}px`;
    contextMenu.style.left = `${event.clientX}px`;
}





function hideContextMenu() {
    document.getElementById('context-menu').style.display = 'none';
    currentMessageId = null;
    currentIsSender = null;
}

function contextAction(action) {
    if (!currentMessageId) return;
    switch(action) {
        case 'edit':
            if (currentIsSender) editMessage(currentMessageId);
            break;
        case 'delete':
            if (currentIsSender) deleteMessage(currentMessageId);
            break;
        case 'reply':
            replyToMessage(currentMessageId);
            break;
        case 'forward':
            forwardMessage(currentMessageId);
            break;
        case 'download':
            downloadMessageFiles(currentMessageId);
            break;
        case 'copy':
            copyMessageText(currentMessageId);
            break;
    }
    hideContextMenu();
}

function copyMessageText(messageId) {
    const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
    const content = messageElement.querySelector('.message-content')?.textContent || '';
    navigator.clipboard.writeText(content)
        .then(() => showNotification('متن پیام کپی شد', 'success'))
        .catch(() => showNotification('خطا در کپی متن', 'error'));
}

function copySelectedText() {
    const selectedText = window.getSelection().toString().trim();
    if (selectedText) {
        navigator.clipboard.writeText(selectedText)
            .then(() => showNotification('متن انتخاب شده کپی شد', 'success'))
            .catch(() => showNotification('خطا در کپی متن', 'error'));
    } else {
        showNotification('هیچ متنی انتخاب نشده است', 'error');
    }
}

function downloadMessageFiles(messageId) {
    const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
    const files = messageElement.querySelectorAll('img[src], video[src], audio[src], a[href]');
    
    if (files.length === 0) {
        showNotification('هیچ فایلی برای دانلود وجود ندارد', 'error');
        return;
    }

    files.forEach(file => {
        const downloadLink = document.createElement('a');
        downloadLink.href = file.src || file.href;
        downloadLink.download = file.src ? file.src.split('/').pop() : file.href.split('/').pop();
        downloadLink.style.display = 'none';
        document.body.appendChild(downloadLink);
        downloadLink.click();
        document.body.removeChild(downloadLink);
    });
}

function cancelUpload() {
    if (currentUpload) {
        currentUpload.abort();
        const tempMessage = document.querySelector('.message.uploading');
        if (tempMessage) tempMessage.remove();
        currentUpload = null;
        showNotification('ارسال فایل لغو شد', 'info');
    }
}

function editMessage(messageId) {
    const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
    const content = messageElement.querySelector('.message-content')?.textContent || '';
    const newContent = prompt('پیام جدید را وارد کنید:', content);
    if (newContent && newContent.trim()) {
        fetch(`/api/messages/${messageId}/`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({ content: newContent.trim() })
        })
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (data.status === 'error') throw new Error(data.message);
                messageElement.querySelector('.message-content').textContent = newContent.trim();
                saveMessages();
                showNotification('پیام ویرایش شد', 'success');
            })
            .catch(error => {
                showNotification(`خطا در ویرایش پیام: ${error.message}`, 'error');
            });
    }
}

function deleteMessage(messageId) {
    if (confirm('آیا مطمئن هستید که می‌خواهید این پیام را حذف کنید؟')) {
        fetch(`/api/messages/${messageId}/`, {
            method: 'DELETE',
            headers: { 'X-CSRFToken': getCsrfToken() }
        })
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (data.status === 'error') throw new Error(data.message);
                const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
                if (messageElement) messageElement.remove();
                displayedMessageIds.delete(messageId);
                saveMessages();
                showNotification('پیام حذف شد', 'success');
            })
            .catch(error => {
                showNotification(`خطا در حذف پیام: ${error.message}`, 'error');
            });
    }
}

function replyToMessage(messageId) {
    const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
    const content = messageElement.querySelector('.message-content')?.textContent || '';
    const replyContent = prompt('پاسخ خود را وارد کنید:', `پاسخ به: ${content}`);
    if (replyContent && replyContent.trim()) {
        sendMessageWithFiles([], replyContent);
    }
}
async function forwardMessage(messageId) {
    const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
    const content = messageElement.querySelector('.message-content')?.textContent || '';
    const files = Array.from(messageElement.querySelectorAll('img, video, audio, a')).map(el => ({
        type: el.tagName.toLowerCase(),
        src: el.src || el.href
    }));
    
    const recipient = prompt('نام کاربری دریافت‌کننده را وارد کنید:');
    if (!recipient?.trim()) return;

    try {
        const userResponse = await fetch('/api/users/?search=' + encodeURIComponent(recipient), {
            headers: { 'X-CSRFToken': getCsrfToken() }
        });
        const userData = await userResponse.json();

        if (userData.users.length === 0) {
            showNotification('کاربر یافت نشد', 'error');
            return;
        }

        currentPrivateUserId = userData.users[0].id;
        
        // اگر فایلی وجود ندارد، فقط متن را ارسال کنید
        if (files.length === 0) {
            await sendMessageWithFiles([], content);
            showNotification('پیام ارسال شد', 'success');
            return;
        }

        // ارسال فایل‌ها به صورت مستقیم
        const fileIds = [];
        for (const file of files) {
            const response = await fetch(file.src);
            const blob = await response.blob();
            const formData = new FormData();
            formData.append('files', blob, file.src.split('/').pop());
            
            const uploadResponse = await fetch('/api/upload/', {
                method: 'POST',
                headers: { 'X-CSRFToken': getCsrfToken() },
                body: formData
            });
            
            const uploadData = await uploadResponse.json();
            if (uploadData.status === 'error') {
                throw new Error(uploadData.message);
            }
            
            fileIds.push(...uploadData.file_ids);
        }

        await sendMessageWithFiles(fileIds, content);
        showNotification('پیام ارسال شد', 'success');
    } catch (error) {
        showNotification(`خطا در ارسال پیام: ${error.message}`, 'error');
    }
}



function getMessageContentType(messageElement) {
    if (messageElement.querySelector('img')) return 'image';
    if (messageElement.querySelector('video')) return 'video';
    if (messageElement.querySelector('audio')) return 'audio';
    if (messageElement.querySelector('a[href]')) return 'file';
    return 'text';
}
function showUserProfile() {
    fetch('/api/users/current/', {
        headers: { 'X-CSRFToken': getCsrfToken() }
    })
        .then(response => {
            if (!response.ok) throw new Error('کاربر وارد نشده است');
            return response.json();
        })
        .then(data => {
            justOpenedModal = true;
            document.getElementById('profile-modal-image').src = data.profile_image || '/static/profiles/ICON_PROF.jpg';
            document.getElementById('profile-modal-title').textContent = data.display_name || data.username;
            document.getElementById('profile-modal-username').textContent = `نام کاربری: ${data.username}`;
            document.getElementById('profile-modal-description').textContent = data.description || '';
            document.getElementById('profile-modal-edit').classList.remove('hidden');
            const modal = document.getElementById('profile-modal');
            modal.classList.remove('hidden');
            setTimeout(() => modal.querySelector('.modal-content').classList.add('show'), 10);
        })
        .catch(error => {
            showNotification(`خطا در دریافت اطلاعات پروفایل: ${error.message}`, 'error');
        });
}

function showChatProfile() {
    if (currentTab === 'private' && currentPrivateUserId) {
        fetch(`/api/users/${currentPrivateUserId}/`, {
            headers: { 'X-CSRFToken': getCsrfToken() }
        })
            .then(response => {
                if (!response.ok) throw new Error('کاربر یافت نشد');
                return response.json();
            })
            .then(data => {
                justOpenedModal = true;
                document.getElementById('profile-modal-image').src = data.profile_image || '/static/profiles/ICON_PROF.jpg';
                document.getElementById('profile-modal-title').textContent = data.display_name || data.username;
                document.getElementById('profile-modal-username').textContent = `نام کاربری: ${data.username}`;
                document.getElementById('profile-modal-description').textContent = data.description || '';
                document.getElementById('profile-modal-edit').classList.add('hidden');
                const modal = document.getElementById('profile-modal');
                modal.classList.remove('hidden');
                setTimeout(() => modal.querySelector('.modal-content').classList.add('show'), 10);
            })
            .catch(error => {
                showNotification(`خطا در دریافت اطلاعات پروفایل: ${error.message}`, 'error');
            });
    } else if (currentTab === 'group' && currentGroupId) {
        fetch(`/api/groups/${currentGroupId}/`, {
            headers: { 'X-CSRFToken': getCsrfToken() }
        })
            .then(response => {
                if (!response.ok) throw new Error('گروه یافت نشد');
                return response.json();
            })
            .then(data => {
                justOpenedModal = true;
                document.getElementById('profile-modal-image').src = data.image || '/static/profiles/ICON_GROUP.jpg';
                document.getElementById('profile-modal-title').textContent = data.name;
                document.getElementById('profile-modal-username').textContent = '';
                document.getElementById('profile-modal-description').textContent = data.description || '';
                document.getElementById('profile-modal-edit').classList.add('hidden');
                const modal = document.getElementById('profile-modal');
                modal.classList.remove('hidden');
                setTimeout(() => modal.querySelector('.modal-content').classList.add('show'), 10);
            })
            .catch(error => {
                showNotification(`خطا در دریافت اطلاعات گروه: ${error.message}`, 'error');
            });
    } else {
        showNotification('لطفاً یک چت خصوصی یا گروهی انتخاب کنید', 'error');
    }
}

function handleFileSelect(e) {
    const files = e.target.files;
    if (!files.length) return;

    const maxSize = 20 * 1024 * 1024 * 1024;
    for (let file of files) {
        if (file.size > maxSize) {
            showNotification(`فایل ${file.name} بیش از 20 گیگابایت است`, 'error');
            return;
        }
        if (file.size > 1024 * 1024 * 1024) {
            showNotification(`آپلود فایل ${file.name} ممکن است زمان‌بر باشد`, 'info');
        }
    }

    const chatMessages = document.getElementById('chat-messages');
    const tempMessage = document.createElement('div');
    tempMessage.className = 'message flex justify-end uploading';
    tempMessage.innerHTML = `
        <div class="message-bubble sent relative">
            <p class="message-content">در حال ارسال فایل...</p>
            <div class="progress-circle"></div>
            <span class="progress-text">0% - ${(files[0].size / (1024 * 1024)).toFixed(2)} MB</span>
        </div>
    `;
    chatMessages.appendChild(tempMessage);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    tempMessage.addEventListener('contextmenu', e => showContextMenu(e, null, true, true));

    const formData = new FormData();
    Array.from(files).forEach(file => formData.append('files', file));

    const xhr = new XMLHttpRequest();
    currentUpload = xhr;
    xhr.open('POST', '/api/upload/', true);
    xhr.setRequestHeader('X-CSRFToken', getCsrfToken());

    xhr.upload.onprogress = function(event) {
        if (event.lengthComputable) {
            const percentComplete = Math.round((event.loaded / event.total) * 100);
            const loadedSize = (event.loaded / (1024 * 1024)).toFixed(2);
            const totalSize = (event.total / (1024 * 1024)).toFixed(2);
            tempMessage.querySelector('.progress-text').textContent = `${percentComplete}% - ${loadedSize} MB از ${totalSize} MB`;
        }
    };

    xhr.onload = function() {
        if (xhr.status === 200) {
            const data = JSON.parse(xhr.responseText);
            if (data.status === 'error') {
                tempMessage.remove();
                showNotification(`خطا در آپلود فایل: ${data.message}`, 'error');
                return;
            }
            tempMessage.remove();
            sendMessageWithFiles(data.file_ids);
            showNotification('فایل‌ها با موفقیت آپلود شدند', 'success');
        } else {
            tempMessage.remove();
            showNotification(`خطا در آپلود فایل: خطای سرور ${xhr.status}`, 'error');
        }
        currentUpload = null;
    };

    xhr.onerror = function() {
        tempMessage.remove();
        showNotification('خطا در اتصال به سرور', 'error');
        currentUpload = null;
    };

    xhr.send(formData);
}

function sendMessageWithFiles(fileIds = [], content = null) {
    const messageInput = document.getElementById('message-input');
    const message = content || messageInput.value.trim();
    if (!message && !fileIds.length) {
        showNotification('پیام یا فایل الزامی است', 'error');
        return;
    }
    const data = { content: message, file_ids: fileIds };
    if (currentTab === 'group' && currentGroupId) {
        data.group_id = currentGroupId;
    } else if (currentTab === 'private' && currentPrivateUserId) {
        data.recipient_id = currentPrivateUserId;
    } else {
        showNotification('لطفاً یک چت خصوصی یا گروهی انتخاب کنید', 'error');
        return;
    }
    fetch('/api/messages/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify(data)
    })
        .then(response => {
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            return response.json();
        })
        .then(data => {
            if (data.status === 'error') throw new Error(data.message);
            if (!content) messageInput.value = '';
            document.getElementById('file-input').value = '';
            showNotification('پیام ارسال شد', 'success');
            fetchMessages();
        })
        .catch(error => {
            showNotification(`خطا در ارسال پیام: ${error.message}`, 'error');
        });
}

function markMessagesSeen() {
    if (currentTab === 'group' && currentGroupId) {
        fetch('/api/messages/seen/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({ group_id: currentGroupId })
        });
    } else if (currentTab === 'private' && currentPrivateUserId) {
        fetch('/api/messages/seen/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({ recipient_id: currentPrivateUserId })
        });
    }
}

function fetchMessages() {
    if (isFetching) return;
    isFetching = true;
    const params = new URLSearchParams({ last_message_id: lastMessageId });
    if (currentTab === 'group' && currentGroupId) {
        params.append('group_id', currentGroupId);
    } else if (currentTab === 'private' && currentPrivateUserId) {
        params.append('recipient_id', currentPrivateUserId);
    }
    fetch(`/api/messages/?${params.toString()}`, {
        headers: { 'X-CSRFToken': getCsrfToken() }
    })
        .then(response => {
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            return response.json();
        })
        .then(messages => {
            const chatMessages = document.getElementById('chat-messages');
            messages.forEach(msg => {
                if (!displayedMessageIds.has(msg.id)) {
                    if (msg.id > lastMessageId) lastMessageId = msg.id;
                    displayedMessageIds.add(msg.id);
                    const messageElement = document.createElement('div');
                    const isSender = msg.sender.id === getCurrentUserId();
                    messageElement.className = `message flex ${isSender ? 'justify-end' : 'justify-start'}`;
                    messageElement.dataset.messageId = msg.id;
                    let content = msg.content || '';
                    content = content.replace(/["'>]/g, '');
                    let filesHtml = msg.files.map(file => {
                        if (file.file_type === 'image') return `<img src="${file.file}" alt="File" class="max-w-full rounded-lg mt-2">`;
                        if (file.file_type === 'video') return `<video src="${file.file}" controls class="max-w-full rounded-lg mt-2"></video>`;
                        if (file.file_type === 'audio') return `<audio src="${file.file}" controls class="w-full mt-2"></audio>`;
                        return `<a href="${file.file}" class="text-blue-400 underline mt-2 block">دانلود فایل</a>`;
                    }).join('');
                    const timestamp = new Date(msg.timestamp).toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit' });
                    const senderName = msg.sender.display_name || msg.sender.username;
                    messageElement.innerHTML = `
                        <div class="message-bubble ${isSender ? 'sent' : 'received'}">
                            <p class="message-sender">${senderName}</p>
                            <p class="message-content">${content}</p>
                            ${filesHtml}
                            <p class="text-xs">${timestamp}</p>
                            ${isSender ? `<span class="message-ticks ${msg.read_at ? 'read' : msg.delivered_at ? 'delivered' : ''}"></span>` : ''}
                        </div>
                    `;
                    chatMessages.appendChild(messageElement);
                    messageElement.addEventListener('contextmenu', e => showContextMenu(e, msg.id, isSender));
                    gsap.from(messageElement, { duration: 0.3, y: 10, opacity: 0, ease: "power2.out" });
                }
            });
            if (messages.length) {
                chatMessages.scrollTop = chatMessages.scrollHeight;
                saveMessages();
                markMessagesSeen();
            }
        })
        .catch(error => {
            showNotification(`خطا در دریافت پیام‌ها: ${error.message}`, 'error');
        })
        .finally(() => {
            isFetching = false;
        });
}







function fetchChats() {
    if (currentTab === 'private') {
        fetch('/api/users/chatted/', {
            headers: { 'X-CSRFToken': getCsrfToken() }
        })
            .then(response => response.json())
            .then(data => {
                const privateChats = document.getElementById('private-chats');
                privateChats.innerHTML = data.users.map(user => `
                    <div class="chat-item glass-effect" data-user-id="${user.id}">
                        <img src="${user.profile_image || '/static/profiles/ICON_PROF.jpg'}" alt="Profile" class="w-10 h-10 rounded-full object-cover">
                        <div class="mr-3 flex-1">
                            <h3 class="font-semibold text-white">${user.display_name || user.username}</h3>
                            <p class="text-sm text-gray-400">${user.username}</p>
                        </div>
                        <span class="w-3 h-3 rounded-full ${user.is_online ? 'bg-green-500' : 'bg-gray-500'}"></span>
                    </div>
                `).join('');
                gsap.from(".chat-item", { duration: 0.5, y: 20, opacity: 0, stagger: 0.05, ease: "power2.out" });
            })
            .catch(error => {
                showNotification(`خطا در دریافت چت‌های خصوصی: ${error.message}`, 'error');
            });
    } else {
        fetch('/api/groups/', {
            headers: { 'X-CSRFToken': getCsrfToken() }
        })
            .then(response => response.json())
            .then(data => {
                const groups = document.getElementById('groups');
                groups.innerHTML = data.map(group => `
                    <div class="chat-item glass-effect" data-group-id="${group.id}">
                        <img src="${group.image || '/static/profiles/ICON_GROUP.jpg'}" alt="Group" class="w-10 h-10 rounded-full object-cover">
                        <div class="mr-3">
                            <h3 class="font-semibold text-white">${group.name}</h3>
                            <p class="text-sm text-gray-400">${group.description || 'بدون توضیحات'}</p>
                        </div>
                    </div>
                `).join('');
                gsap.from(".chat-item", { duration: 0.5, y: 20, opacity: 0, stagger: 0.05, ease: "power2.out" });
            })
            .catch(error => {
                showNotification(`خطا در دریافت گروه‌ها: ${error.message}`, 'error');
            });
    }
}

function startPolling() {
    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = setInterval(fetchMessages, 5000);
}

document.getElementById('sidebar-toggle').addEventListener('click', () => {
    document.getElementById('chat-sidebar').classList.remove('open');
});

document.getElementById('sidebar-open').addEventListener('click', () => {
    document.getElementById('chat-sidebar').classList.add('open');
});

document.getElementById('private-tab').addEventListener('click', () => {
    if (currentTab !== 'private') {
        currentTab = 'private';
        currentGroupId = null;
        clearMessages();
        document.getElementById('private-tab').classList.add('text-blue-400', 'border-blue-400');
        document.getElementById('private-tab').classList.remove('text-gray-400', 'border-transparent');
        document.getElementById('group-tab').classList.add('text-gray-400', 'border-transparent');
        document.getElementById('group-tab').classList.remove('text-blue-400', 'border-blue-400');
        document.getElementById('private-chats').classList.remove('hidden');
        document.getElementById('groups').classList.add('hidden');
        document.getElementById('chat-title').textContent = 'چت خصوصی';
        document.getElementById('chat-image').src = '/static/profiles/ICON_PROF.jpg';
        fetchChats();
    }
});

document.getElementById('group-tab').addEventListener('click', () => {
    if (currentTab !== 'group') {
        currentTab = 'group';
        currentPrivateUserId = null;
        clearMessages();
        document.getElementById('group-tab').classList.add('text-blue-400', 'border-blue-400');
        document.getElementById('group-tab').classList.remove('text-gray-400', 'border-transparent');
        document.getElementById('private-tab').classList.add('text-gray-400', 'border-transparent');
        document.getElementById('private-tab').classList.remove('text-blue-400', 'border-blue-400');
        document.getElementById('groups').classList.remove('hidden');
        document.getElementById('private-chats').classList.add('hidden');
        document.getElementById('chat-title').textContent = 'چت گروهی';
        document.getElementById('chat-image').src = '/static/profiles/ICON_GROUP.jpg';
        fetchChats();
    }
});

document.getElementById('sidebar-content').addEventListener('click', (e) => {
    const chatItem = e.target.closest('.chat-item');
    if (chatItem) {
        clearMessages();
        if (currentTab === 'private') {
            currentPrivateUserId = parseInt(chatItem.dataset.userId);
            currentGroupId = null;
            fetch(`/api/users/${currentPrivateUserId}/`, {
                headers: { 'X-CSRFToken': getCsrfToken() }
            })
                .then(response => response.json())
                .then(data => {
                    document.getElementById('chat-title').textContent = data.display_name || data.username;
                    document.getElementById('chat-image').src = data.profile_image || '/static/profiles/ICON_PROF.jpg';
                    loadMessages();
                    fetchMessages();
                    startPolling();
                });
        } else {
            currentGroupId = parseInt(chatItem.dataset.groupId);
            currentPrivateUserId = null;
            fetch(`/api/groups/${currentGroupId}/`, {
                headers: { 'X-CSRFToken': getCsrfToken() }
            })
                .then(response => response.json())
                .then(data => {
                    document.getElementById('chat-title').textContent = data.name;
                    document.getElementById('chat-image').src = data.image || '/static/profiles/ICON_GROUP.jpg';
                    loadMessages();
                    fetchMessages();
                    startPolling();
                });
        }
        document.getElementById('chat-sidebar').classList.remove('open');
    }
});

document.getElementById('header-menu-toggle').addEventListener('click', (e) => {
    e.stopPropagation();
    const menu = document.getElementById('header-menu');
    menu.classList.toggle('hidden');
    menu.classList.toggle('show');
});

document.getElementById('create-group').addEventListener('click', (e) => {
    e.stopPropagation();
    justOpenedModal = true;
    document.getElementById('header-menu').classList.add('hidden');
    document.getElementById('header-menu').classList.remove('show');
    const modal = document.getElementById('create-group-modal');
    modal.classList.remove('hidden');
    setTimeout(() => modal.querySelector('.modal-content').classList.add('show'), 10);
});

document.getElementById('join-group').addEventListener('click', (e) => {
    e.stopPropagation();
    justOpenedModal = true;
    document.getElementById('header-menu').classList.add('hidden');
    document.getElementById('header-menu').classList.remove('show');
    const modal = document.getElementById('join-group-modal');
    modal.classList.remove('hidden');
    setTimeout(() => modal.querySelector('.modal-content').classList.add('show'), 10);
});

document.getElementById('logout').addEventListener('click', (e) => {
    e.stopPropagation();
    fetch('/api/users/logout/', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrfToken() }
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'error') throw new Error(data.message);
            clearUserData();
            document.getElementById('header-menu').classList.add('hidden');
            document.getElementById('header-menu').classList.remove('show');
            setTimeout(() => window.location.reload(), 500);
        })
        .catch(error => {
            showNotification(`خطا در خروج: ${error.message}`, 'error');
        });
});

document.getElementById('login-submit').addEventListener('click', () => {
    const username = document.getElementById('login-username').value.trim();
    const displayName = document.getElementById('login-display-name').value.trim();
    const password = document.getElementById('login-password').value;
    if (!username || !password) {
        showNotification('نام کاربری و رمز عبور الزامی است', 'error');
        return;
    }
    fetch('/api/users/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ username, display_name: displayName, password })
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'error') throw new Error(data.message);
            currentUserId = data.user_id;
            saveUserData(data);
            document.getElementById('display-name').textContent = data.display_name || data.username;
            document.getElementById('username').textContent = data.username;
            document.getElementById('profile-image').src = data.profile_image || '/static/profiles/ICON_PROF.jpg';
            document.getElementById('login-modal').classList.add('hidden');
            fetchChats();
            startPolling();
            startOnlineStatusPolling();
        })
        .catch(error => {
            showNotification(`خطا در ورود: ${error.message}`, 'error');
        });
});

document.getElementById('edit-profile-submit').addEventListener('click', () => {
    const formData = new FormData();
    const username = document.getElementById('edit-username').value.trim();
    const displayName = document.getElementById('edit-display-name').value.trim();
    const password = document.getElementById('edit-password').value;
    const description = document.getElementById('edit-description').value.trim();
    const profileImage = document.getElementById('edit-profile-image').files[0];
    if (username) formData.append('username', username);
    if (displayName) formData.append('display_name', displayName);
    if (password) formData.append('password', password);
    if (description) formData.append('description', description);
    if (profileImage) formData.append('profile_image', profileImage);
    fetch('/api/users/current/', {
        method: 'PATCH',
        headers: { 'X-CSRFToken': getCsrfToken() },
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'error') throw new Error(data.message);
            saveUserData(data);
            document.getElementById('display-name').textContent = data.display_name || data.username;
            document.getElementById('username').textContent = data.username;
            document.getElementById('profile-image').src = data.profile_image || '/static/profiles/ICON_PROF.jpg';
            document.getElementById('edit-profile-modal').classList.add('hidden');
            showNotification('پروفایل به‌روزرسانی شد', 'success');
        })
        .catch(error => {
            showNotification(`خطا در ویرایش پروفایل: ${error.message}`, 'error');
        });
});

document.getElementById('edit-profile-cancel').addEventListener('click', () => {
    document.getElementById('edit-profile-modal').classList.add('hidden');
});

document.getElementById('create-group-submit').addEventListener('click', () => {
    const formData = new FormData();
    const name = document.getElementById('group-name').value.trim();
    const description = document.getElementById('group-description').value.trim();
    const password = document.getElementById('group-password').value;
    const image = document.getElementById('group-image').files[0];
    if (!name) {
        showNotification('نام گروه الزامی است', 'error');
        return;
    }
    formData.append('name', name);
    if (description) formData.append('description', description);
    if (password) formData.append('password', password);
    if (image) formData.append('image', image);
    fetch('/api/groups/', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrfToken() },
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'error') throw new Error(data.message);
            document.getElementById('create-group-modal').classList.add('hidden');
            fetchChats();
            showNotification('گروه ایجاد شد', 'success');
        })
        .catch(error => {
            showNotification(`خطا در ایجاد گروه: ${error.message}`, 'error');
        });
});

document.getElementById('create-group-cancel').addEventListener('click', () => {
    document.getElementById('create-group-modal').classList.add('hidden');
});

document.getElementById('join-group-search').addEventListener('input', (e) => {
    const query = e.target.value.trim();
    if (query) {
        fetch('/api/groups/search/?search=' + encodeURIComponent(query), {
            headers: { 'X-CSRFToken': getCsrfToken() }
        })
            .then(response => response.json())
            .then(data => {
                const results = document.getElementById('group-search-results');
                results.innerHTML = data.groups.map(group => `
                    <div class="chat-item glass-effect" data-group-id="${group.id}">
                        <h3 class="font-semibold text-white">${group.name}</h3>
                        <p class="text-sm text-gray-400">${group.description || 'بدون توضیحات'}</p>
                    </div>
                `).join('');
            });
    } else {
        document.getElementById('group-search-results').innerHTML = '';
    }
});

document.getElementById('group-search-results').addEventListener('click', (e) => {
    const groupItem = e.target.closest('.chat-item');
    if (groupItem) {
        document.getElementById('join-group-id').value = groupItem.dataset.groupId;
        document.getElementById('join-group-search').value = groupItem.querySelector('h3').textContent;
        document.getElementById('group-search-results').innerHTML = '';
    }
});

document.getElementById('join-group-submit').addEventListener('click', () => {
    const groupId = document.getElementById('join-group-id').value;
    const password = document.getElementById('join-group-password').value;
    if (!groupId) {
        showNotification('لطفاً یک گروه انتخاب کنید', 'error');
        return;
    }
    fetch('/api/groups/join/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ group_id: groupId, password })
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'error') throw new Error(data.message);
            document.getElementById('join-group-modal').classList.add('hidden');
            fetchChats();
            showNotification('با موفقیت به گروه پیوستید', 'success');
        })
        .catch(error => {
            showNotification(`خطا در پیوستن به گروه: ${error.message}`, 'error');
        });
});

document.getElementById('join-group-cancel').addEventListener('click', () => {
    document.getElementById('join-group-modal').classList.add('hidden');
});

document.getElementById('download-cancel').addEventListener('click', () => {
    document.getElementById('download-modal').classList.add('hidden');
});

document.getElementById('profile-modal-edit').addEventListener('click', () => {
    document.getElementById('profile-modal').classList.add('hidden');
    justOpenedModal = true;
    const modal = document.getElementById('edit-profile-modal');
    modal.classList.remove('hidden');
    setTimeout(() => modal.querySelector('.modal-content').classList.add('show'), 10);
});

document.getElementById('profile-modal-close').addEventListener('click', () => {
    document.getElementById('profile-modal').classList.add('hidden');
});

document.getElementById('file-upload').addEventListener('click', () => {
    document.getElementById('file-input').click();
});

document.getElementById('file-input').addEventListener('change', handleFileSelect);

document.getElementById('send-message').addEventListener('click', () => {
    sendMessageWithFiles();
});

document.getElementById('message-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessageWithFiles();
    }
});

document.getElementById('profile-image').addEventListener('click', showUserProfile);
document.getElementById('chat-image').addEventListener('click', showChatProfile);

document.getElementById('search-input').addEventListener('input', (e) => {
    const query = e.target.value.trim();
    if (currentTab === 'private') {
        fetch('/api/users/?search=' + encodeURIComponent(query), {
            headers: { 'X-CSRFToken': getCsrfToken() }
        })
            .then(response => response.json())
            .then(data => {
                const privateChats = document.getElementById('private-chats');
                privateChats.innerHTML = data.users.map(user => `
                    <div class="chat-item flex items-center p-2 hover:bg-gray-700 rounded cursor-pointer" data-user-id="${user.id}">
                        <img src="${user.profile_image || '/static/profiles/ICON_PROF.jpg'}" alt="Profile" class="w-10 h-10 rounded-full object-cover">
                        <div class="mr-3 flex-1">
                            <h3 class="font-semibold text-white">${user.display_name || user.username}</h3>
                            <p class="text-sm text-gray-400">${user.username}</p>
                        </div>
                        <span class="w-3 h-3 rounded-full ${user.is_online ? 'bg-green-500' : 'bg-gray-500'}"></span>
                    </div>
                `).join('');
            });
    }
});

document.addEventListener('click', (e) => {
    if (!justOpenedModal) {
        const modals = document.querySelectorAll('#login-modal, #edit-profile-modal, #create-group-modal, #join-group-modal, #download-modal, #profile-modal');
        modals.forEach(modal => {
            if (!modal.classList.contains('hidden') && !modal.contains(e.target)) {
                modal.classList.add('hidden');
            }
        });
        const headerMenu = document.getElementById('header-menu');
        if (!headerMenu.classList.contains('hidden') && !headerMenu.contains(e.target) && e.target.id !== 'header-menu-toggle' && !e.target.closest('#header-menu-toggle')) {
            headerMenu.classList.add('hidden');
            headerMenu.classList.remove('show');
        }
    }
    justOpenedModal = false;
});

document.addEventListener('contextmenu', (e) => {
    if (!e.target.closest('#context-menu')) {
        hideContextMenu();
    }
});

// Initialize
document.addEventListener('DOMContentLoaded', checkStoredUser);