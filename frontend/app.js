/* ===================================================
   Snake Game — Frontend Application
   =================================================== */

// ===================== Configuration =====================

const API_BASE = 'http://localhost:5000/api';
const COLS = 20;
const ROWS = 20;
const CELL_SIZE = 25;
const GAME_SPEED = 150; // ms

// ===================== API Layer =====================

const api = {
  _token: null,

  getToken() {
    if (!this._token) {
      this._token = localStorage.getItem('token');
    }
    return this._token;
  },

  setToken(token) {
    this._token = token;
    if (token) {
      localStorage.setItem('token', token);
    } else {
      localStorage.removeItem('token');
    }
  },

  async _fetch(path, options = {}) {
    const url = `${API_BASE}${path}`;
    const headers = { 'Content-Type': 'application/json' };
    const token = this.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const res = await fetch(url, { ...options, headers });

    let data = null;
    const contentType = res.headers.get('Content-Type') || '';
    if (contentType.includes('application/json')) {
      data = await res.json();
    }

    if (!res.ok) {
      const message = (data && data.error) || `Request failed with status ${res.status}`;
      throw new Error(message);
    }

    return data;
  },

  async register(username, password) {
    return this._fetch('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
  },

  async login(username, password) {
    const data = await this._fetch('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    if (data.token) {
      this.setToken(data.token);
    }
    return data;
  },

  async getProfile() {
    return this._fetch('/profile');
  },

  async saveScore(score) {
    return this._fetch('/score', {
      method: 'POST',
      body: JSON.stringify({ score }),
    });
  },

  async getLeaderboard() {
    return this._fetch('/leaderboard');
  },
};

// ===================== Screen Management =====================

function showScreen(screenId) {
  document.querySelectorAll('.screen').forEach((s) => {
    s.classList.remove('active');
    s.classList.add('hidden');
  });
  const screen = document.getElementById(screenId);
  screen.classList.remove('hidden');
  screen.classList.add('active');
}

// ===================== DOM References =====================

const authScreen = document.getElementById('auth-screen');
const gameScreen = document.getElementById('game-screen');
const leaderboardScreen = document.getElementById('leaderboard-screen');
const gameoverModal = document.getElementById('gameover-modal');

const authForm = document.getElementById('auth-form');
const authTitle = document.getElementById('auth-title');
const authSubmit = document.getElementById('auth-submit');
const authToggle = document.getElementById('auth-toggle');
const authError = document.getElementById('auth-error');
const usernameInput = document.getElementById('username');
const passwordInput = document.getElementById('password');

const scoreDisplay = document.getElementById('score');
const finalScoreDisplay = document.getElementById('final-score');
const canvas = document.getElementById('game-canvas');
const ctx = canvas.getContext('2d');

const newGameBtn = document.getElementById('new-game-btn');
const leaderboardBtn = document.getElementById('leaderboard-btn');
const logoutBtn = document.getElementById('logout-btn');
const playAgainBtn = document.getElementById('play-again-btn');
const gameoverLeaderboardBtn = document.getElementById('gameover-leaderboard-btn');
const backToGameBtn = document.getElementById('back-to-game-btn');

const leaderboardList = document.getElementById('leaderboard-list');
const leaderboardLoading = document.getElementById('leaderboard-loading');
const leaderboardEmpty = document.getElementById('leaderboard-empty');

// ===================== Auth State =====================

let isRegisterMode = false;

// ===================== Auth: Toggle Mode =====================

authToggle.addEventListener('click', () => {
  isRegisterMode = !isRegisterMode;
  if (isRegisterMode) {
    authTitle.textContent = 'Register';
    authSubmit.textContent = 'Register';
    authToggle.textContent = 'Already have an account? Login';
    passwordInput.autocomplete = 'new-password';
  } else {
    authTitle.textContent = 'Login';
    authSubmit.textContent = 'Login';
    authToggle.textContent = "Don't have an account? Register";
    passwordInput.autocomplete = 'current-password';
  }
  authError.classList.add('hidden');
});

// ===================== Auth: Submit =====================

authForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  authError.classList.add('hidden');

  const username = usernameInput.value.trim();
  const password = passwordInput.value;

  if (!username || !password) {
    showAuthError('Please fill in all fields.');
    return;
  }

  authSubmit.disabled = true;
  authSubmit.textContent = 'Loading...';

  try {
    if (isRegisterMode) {
      // Register first, then login
      await api.register(username, password);
      // Auto-login after successful registration
      await api.login(username, password);
    } else {
      await api.login(username, password);
    }

    // Success — go to game
    usernameInput.value = '';
    passwordInput.value = '';
    startNewGame();
    showScreen('game-screen');
    gameoverModal.classList.add('hidden');
  } catch (err) {
    showAuthError(err.message);
  } finally {
    authSubmit.disabled = false;
    authSubmit.textContent = isRegisterMode ? 'Register' : 'Login';
  }
});

function showAuthError(message) {
  authError.textContent = message;
  authError.classList.remove('hidden');
}

// ===================== Snake Game =====================

let snake = [];
let direction = { dx: 0, dy: 0 };
let nextDirection = { dx: 0, dy: 0 };
let food = { x: 0, y: 0 };
let score = 0;
let gameInterval = null;
let isGameOver = false;
let isGameRunning = false;

function initSnake() {
  snake = [
    { x: 10, y: 10 },
    { x: 9, y: 10 },
    { x: 8, y: 10 },
  ];
}

function randomFood() {
  const occupied = new Set(snake.map((s) => `${s.x},${s.y}`));
  let pos;
  do {
    pos = {
      x: Math.floor(Math.random() * COLS),
      y: Math.floor(Math.random() * ROWS),
    };
  } while (occupied.has(`${pos.x},${pos.y}`));
  return pos;
}

function drawGame() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Draw grid lines
  ctx.strokeStyle = '#16213e';
  ctx.lineWidth = 0.5;
  for (let i = 0; i <= COLS; i++) {
    ctx.beginPath();
    ctx.moveTo(i * CELL_SIZE, 0);
    ctx.lineTo(i * CELL_SIZE, canvas.height);
    ctx.stroke();
  }
  for (let i = 0; i <= ROWS; i++) {
    ctx.beginPath();
    ctx.moveTo(0, i * CELL_SIZE);
    ctx.lineTo(canvas.width, i * CELL_SIZE);
    ctx.stroke();
  }

  // Draw snake
  snake.forEach((seg, idx) => {
    const isHead = idx === 0;
    ctx.fillStyle = isHead ? '#e94560' : '#ff6b81';
    ctx.shadowColor = isHead ? '#e94560' : 'transparent';
    ctx.shadowBlur = isHead ? 8 : 0;
    ctx.fillRect(seg.x * CELL_SIZE + 1, seg.y * CELL_SIZE + 1, CELL_SIZE - 2, CELL_SIZE - 2);
    ctx.shadowBlur = 0;
  });

  // Draw food
  ctx.fillStyle = '#00d2ff';
  ctx.shadowColor = '#00d2ff';
  ctx.shadowBlur = 10;
  ctx.beginPath();
  ctx.arc(
    food.x * CELL_SIZE + CELL_SIZE / 2,
    food.y * CELL_SIZE + CELL_SIZE / 2,
    CELL_SIZE / 2 - 2,
    0,
    Math.PI * 2
  );
  ctx.fill();
  ctx.shadowBlur = 0;
}

function moveSnake() {
  if (isGameOver) return;

  // Apply queued direction
  direction = { ...nextDirection };

  const head = snake[0];
  const newHead = {
    x: head.x + direction.dx,
    y: head.y + direction.dy,
  };

  // Wall collision
  if (newHead.x < 0 || newHead.x >= COLS || newHead.y < 0 || newHead.y >= ROWS) {
    endGame();
    return;
  }

  // Self collision
  if (snake.some((seg) => seg.x === newHead.x && seg.y === newHead.y)) {
    endGame();
    return;
  }

  snake.unshift(newHead);

  // Check food
  if (newHead.x === food.x && newHead.y === food.y) {
    score++;
    scoreDisplay.textContent = score;
    food = randomFood();
  } else {
    snake.pop();
  }

  drawGame();
}

function endGame() {
  if (isGameOver) return;
  isGameOver = true;
  isGameRunning = false;

  if (gameInterval) {
    clearInterval(gameInterval);
    gameInterval = null;
  }

  finalScoreDisplay.textContent = score;
  gameoverModal.classList.remove('hidden');

  // Save score (async, fire-and-forget-ish but we await properly)
  if (score > 0) {
    api.saveScore(score).catch((err) => {
      console.warn('Failed to save score:', err.message);
    });
  }
}

function startNewGame() {
  // Stop existing game
  if (gameInterval) {
    clearInterval(gameInterval);
    gameInterval = null;
  }

  snake = [];
  direction = { dx: 0, dy: 0 };
  nextDirection = { dx: 0, dy: 0 };
  score = 0;
  isGameOver = false;
  isGameRunning = false;

  scoreDisplay.textContent = '0';
  gameoverModal.classList.add('hidden');

  initSnake();
  food = randomFood();
  drawGame();
}

function startGameLoop() {
  if (gameInterval) {
    clearInterval(gameInterval);
  }
  isGameRunning = true;
  gameInterval = setInterval(moveSnake, GAME_SPEED);
}

// ===================== Keyboard Controls =====================

document.addEventListener('keydown', (e) => {
  if (!isGameRunning && !isGameOver) {
    // Start game on first arrow key press (if not over)
    if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
      e.preventDefault();
      // Set initial direction
      switch (e.key) {
        case 'ArrowUp':    nextDirection = { dx: 0, dy: -1 }; break;
        case 'ArrowDown':  nextDirection = { dx: 0, dy: 1 }; break;
        case 'ArrowLeft':  nextDirection = { dx: -1, dy: 0 }; break;
        case 'ArrowRight': nextDirection = { dx: 1, dy: 0 }; break;
      }
      direction = { ...nextDirection };
      startGameLoop();
      return;
    }
  }

  if (!isGameRunning || isGameOver) return;

  if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
    e.preventDefault();

    let newDx = 0;
    let newDy = 0;
    switch (e.key) {
      case 'ArrowUp':    newDx = 0;  newDy = -1; break;
      case 'ArrowDown':  newDx = 0;  newDy = 1;  break;
      case 'ArrowLeft':  newDx = -1; newDy = 0;  break;
      case 'ArrowRight': newDx = 1;  newDy = 0;  break;
    }

    // Prevent 180-degree turn
    if (direction.dx + newDx === 0 && direction.dy + newDy === 0) {
      return;
    }

    nextDirection = { dx: newDx, dy: newDy };
  }
});

// ===================== New Game Button =====================

function resetAndPlay() {
  startNewGame();
  if (!isGameRunning) {
    // Wait for first arrow key; the game loop will start on key press
  }
}

newGameBtn.addEventListener('click', resetAndPlay);
playAgainBtn.addEventListener('click', resetAndPlay);

// ===================== Leaderboard =====================

async function loadLeaderboard() {
  leaderboardLoading.classList.remove('hidden');
  leaderboardList.classList.add('hidden');
  leaderboardEmpty.classList.add('hidden');

  try {
    const data = await api.getLeaderboard();
    const entries = data && data.leaderboard ? data.leaderboard : (Array.isArray(data) ? data : []);

    leaderboardLoading.classList.add('hidden');

    if (entries.length === 0) {
      leaderboardEmpty.classList.remove('hidden');
      return;
    }

    // Sort by score descending
    entries.sort((a, b) => (b.score || 0) - (a.score || 0));

    const top10 = entries.slice(0, 10);
    leaderboardList.innerHTML = top10
      .map((entry, idx) => {
        const medal = idx === 0 ? '🥇' : idx === 1 ? '🥈' : idx === 2 ? '🥉' : '';
        const rank = medal || `<span class="rank">#${idx + 1}</span>`;
        return `<li>${rank}<span class="username">${escapeHtml(entry.username || 'Anonymous')}</span><span class="score">${entry.score}</span></li>`;
      })
      .join('');

    leaderboardList.classList.remove('hidden');
  } catch (err) {
    leaderboardLoading.classList.add('hidden');
    leaderboardList.innerHTML = `<li class="empty-message">Failed to load leaderboard: ${escapeHtml(err.message)}</li>`;
    leaderboardList.classList.remove('hidden');
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ===================== Screen Navigation =====================

leaderboardBtn.addEventListener('click', () => {
  showScreen('leaderboard-screen');
  loadLeaderboard();
});

gameoverLeaderboardBtn.addEventListener('click', () => {
  gameoverModal.classList.add('hidden');
  showScreen('leaderboard-screen');
  loadLeaderboard();
});

backToGameBtn.addEventListener('click', () => {
  showScreen('game-screen');
});

// ===================== Logout =====================

logoutBtn.addEventListener('click', () => {
  if (gameInterval) {
    clearInterval(gameInterval);
    gameInterval = null;
  }
  isGameRunning = false;
  isGameOver = false;
  api.setToken(null);
  showScreen('auth-screen');
  gameoverModal.classList.add('hidden');
});

// ===================== Bootstrap =====================

// Check if user is already authenticated
(function boot() {
  const token = api.getToken();
  if (token) {
    // Try to validate token by fetching profile
    api.getProfile()
      .then(() => {
        startNewGame();
        showScreen('game-screen');
      })
      .catch(() => {
        // Token invalid — clear it and show login
        api.setToken(null);
        showScreen('auth-screen');
      });
  } else {
    showScreen('auth-screen');
  }
})();
