// Set your live Render backend URL here
const BASE_URL = "https://gymbot-2hq2.onrender.com";

let isLogin = true;
let token = localStorage.getItem("token");
let currentChatId = null;
let currentUserEmail = null;

function toggleAuth() {
  isLogin = !isLogin;
  document.getElementById("authTitle").innerText = isLogin ? "Login" : "Sign Up";
  document.getElementById("authSwitch").innerText = isLogin ? "Sign Up" : "Login";
}

function authHandler() {
  const email = document.getElementById("email").value;
  const password = document.getElementById("password").value;
  const route = isLogin ? "/login" : "/register";

  fetch(BASE_URL + route, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  })
    .then(res => res.json())
    .then(data => {
      if (data.token) {
        localStorage.setItem("token", data.token);
        localStorage.setItem("email", email);
        currentUserEmail = email;
        document.getElementById("userEmail").innerText = email;
        showChat();
        loadChats();
      } else {
        alert(data.message || data.error);
        if (data.error === "Invalid token") signOut();
      }
    })
    .catch(() => alert("Server error. Please try again later."));
}

function showChat() {
  document.getElementById("authSection").classList.add("hidden");
  document.getElementById("chatSection").classList.remove("hidden");
  const savedEmail = currentUserEmail || localStorage.getItem("email");
  if (savedEmail) document.getElementById("userEmail").innerText = savedEmail;
}

function signOut() {
  localStorage.removeItem("token");
  localStorage.removeItem("email");
  location.reload();
}

function sendMessage() {
  const input = document.getElementById("userInput");
  const message = input.value.trim();
  if (!message || !currentChatId) return;
  appendMessage("user", message);
  input.value = "";

  fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + localStorage.getItem("token")
    },
    body: JSON.stringify({ message, chat_id: currentChatId })
  })
    .then(res => res.json())
    .then(data => {
      if (data.reply) appendMessage("bot", data.reply);
      else if (data.error) {
        alert(data.error);
        if (data.error === "Invalid token") signOut();
      }
    });
}

function appendMessage(sender, text) {
  const div = document.createElement("div");
  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  div.className = sender === "user" ? "user-msg" : "bot-msg";
  div.innerText = `${sender === "user" ? "You" : "Bot"} (${time}): ${text}`;
  div.dataset.sender = sender;
  div.dataset.message = text;
  const chatBox = document.getElementById("chatBox");
  chatBox.appendChild(div);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function switchTheme() {
  const theme = document.getElementById("theme").value;
  document.body.className = theme === "dark" ? "dark" : "";
  localStorage.setItem("theme", theme);
}

function applySavedTheme() {
  const saved = localStorage.getItem("theme");
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = saved || (prefersDark ? "dark" : "light");
  document.getElementById("theme").value = theme;
  document.body.className = theme === "dark" ? "dark" : "";
}

function createNewChat() {
  const title = prompt("Enter a chat title:");
  if (!title) return;
  fetch(`${BASE_URL}/chat/new`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + localStorage.getItem("token")
    },
    body: JSON.stringify({ title })
  })
    .then(res => res.json())
    .then(data => {
      loadChats(data.chat_id);
    });
}

function loadChats(selectChatId) {
  fetch(`${BASE_URL}/chats`, {
    headers: {
      "Authorization": "Bearer " + localStorage.getItem("token")
    }
  })
    .then(res => res.json())
    .then(data => {
      const chatList = document.getElementById("chatList");
      chatList.innerHTML = "";
      data.forEach(chat => {
        const opt = document.createElement("option");
        opt.value = chat.chat_id;
        opt.textContent = chat.title;

        opt.addEventListener("contextmenu", e => {
          e.preventDefault();
          if (confirm(`Delete chat "${chat.title}"?`)) {
            fetch(`${BASE_URL}/chat/${chat.chat_id}`, {
              method: "DELETE",
              headers: {
                "Authorization": "Bearer " + localStorage.getItem("token")
              }
            }).then(() => loadChats());
          }
        });

        chatList.appendChild(opt);
      });

      if (selectChatId) {
        chatList.value = selectChatId;
        loadChatHistory();
      } else if (data.length > 0) {
        chatList.value = data[0].chat_id;
        loadChatHistory();
      }
    });
}

function loadChatHistory() {
  currentChatId = document.getElementById("chatList").value;
  if (!currentChatId) return;

  fetch(`${BASE_URL}/chat/${currentChatId}/messages`)
    .then(res => res.json())
    .then(data => {
      const chatBox = document.getElementById("chatBox");
      chatBox.innerHTML = "";
      data.forEach(m => appendMessage(m.sender, m.content));
    });
}

function changePassword() {
  const oldPass = prompt("Enter current password:");
  const newPass = prompt("Enter new password:");
  if (!oldPass || !newPass) return;

  fetch(`${BASE_URL}/change-password`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + localStorage.getItem("token")
    },
    body: JSON.stringify({ old_password: oldPass, new_password: newPass })
  })
    .then(res => res.json())
    .then(data => alert(data.message || data.error));
}

function exportChat() {
  const messages = Array.from(document.getElementById("chatBox").children);
  const text = messages.map(m => m.innerText).join("\n");
  const blob = new Blob([text], { type: "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "chat_history.txt";
  a.click();
}

// INIT
window.onload = () => {
  applySavedTheme();
  if (token) {
    currentUserEmail = localStorage.getItem("email");
    showChat();
    loadChats();
  }
};
