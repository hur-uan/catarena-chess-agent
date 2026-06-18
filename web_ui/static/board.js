let state = null;
let selected = null;
let autoRunning = false;
let autoTimer = null;
let autoBusy = false;
const AUTO_MOVE_DELAY_MS = 500;

const boardEl = document.getElementById("board");
const statusText = document.getElementById("statusText");
const turnBadge = document.getElementById("turnBadge");
const historyEl = document.getElementById("history");
const fenBox = document.getElementById("fenBox");
const humanColor = document.getElementById("humanColor");
const agentColor = document.getElementById("agentColor");
const autoStatus = document.getElementById("autoStatus");
const autoButton = document.getElementById("autoPlay");

async function api(path, body = null) {
  const options = body
    ? {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    : {};
  const response = await fetch(path, options);
  const payload = await response.json();
  if (!response.ok) {
    if (payload.state) {
      state = payload.state;
      render();
    }
    return payload;
  }
  if (payload.state) {
    state = payload.state;
    render();
  }
  return payload;
}

async function loadState() {
  state = await api("/api/state");
  render();
}

function render() {
  if (!state) return;
  boardEl.innerHTML = "";
  const legalTargets = selected ? state.legal_by_from[selected] || [] : [];
  const targetSquares = new Set(legalTargets.map((move) => move.slice(2, 4)));

  state.board.flat().forEach((cell) => {
    const square = document.createElement("button");
    square.type = "button";
    square.className = `square ${cell.light ? "light" : "dark"}`;
    square.dataset.square = cell.square;
    if (cell.square === selected) square.classList.add("selected");
    if (cell.last) square.classList.add("last");
    if (targetSquares.has(cell.square)) {
      square.classList.add(cell.piece ? "capture" : "target");
    }

    if (cell.square[0] === "a") {
      const rank = document.createElement("span");
      rank.className = "coord rank";
      rank.textContent = cell.square[1];
      square.appendChild(rank);
    }
    if (cell.square[1] === "1") {
      const file = document.createElement("span");
      file.className = "coord file";
      file.textContent = cell.square[0];
      square.appendChild(file);
    }
    if (cell.piece) {
      const piece = document.createElement("span");
      piece.className = `piece ${cell.piece_symbol === cell.piece_symbol.toUpperCase() ? "white" : "black"}`;
      piece.textContent = cell.piece;
      square.appendChild(piece);
    }
    square.addEventListener("click", () => onSquareClick(cell.square));
    boardEl.appendChild(square);
  });

  const turn = title(state.turn);
  statusText.textContent = `${state.status} · ${turn} to move`;
  turnBadge.textContent = turn;
  humanColor.textContent = title(state.human_color);
  agentColor.textContent = title(state.agent_color);
  fenBox.value = state.fen;
  renderHistory();
}

function renderHistory() {
  historyEl.innerHTML = "";
  state.history.forEach((item, index) => {
    const entry = document.createElement("li");
    const moveNo = Math.floor(index / 2) + 1;
    const prefix = item.color === "White" ? `${moveNo}.` : `${moveNo}...`;
    entry.innerHTML = `<strong>${prefix} ${item.san}</strong><br><span class="actor">${item.actor} · ${item.uci}</span>`;
    historyEl.appendChild(entry);
  });
  historyEl.parentElement.scrollTop = historyEl.parentElement.scrollHeight;
}

async function onSquareClick(square) {
  if (!state || state.is_game_over || state.mode !== "human_vs_agent") return;
  if (state.turn !== state.human_color) return;

  if (!selected) {
    if (state.legal_by_from[square]) selected = square;
    render();
    return;
  }

  if (selected === square) {
    selected = null;
    render();
    return;
  }

  const candidates = state.legal_by_from[selected] || [];
  const move = candidates.find((candidate) => candidate.slice(2, 4) === square);
  if (!move) {
    selected = state.legal_by_from[square] ? square : null;
    render();
    return;
  }

  selected = null;
  state = await api("/api/move", { move });
  render();
}

function title(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

document.getElementById("newWhite").addEventListener("click", async () => {
  stopAuto();
  selected = null;
  state = await api("/api/new", { human_color: "white", mode: "human_vs_agent" });
  render();
});

document.getElementById("newBlack").addEventListener("click", async () => {
  stopAuto();
  selected = null;
  state = await api("/api/new", { human_color: "black", mode: "human_vs_agent" });
  render();
});

document.getElementById("agentStep").addEventListener("click", async () => {
  selected = null;
  state = await api("/api/agent-move", {});
  render();
});

autoButton.addEventListener("click", async () => {
  if (autoRunning) {
    stopAuto();
    return;
  }
  await startAutoLoop();
});

async function startAutoLoop() {
  selected = null;
  autoRunning = true;
  autoButton.classList.add("active");
  autoButton.textContent = "Stop";
  setAutoStatus("Auto: starting agent-vs-agent game");
  state = await api("/api/new", { mode: "agent_vs_agent", max_plies: 200 });
  render();
  scheduleAutoTick(AUTO_MOVE_DELAY_MS);
}

function stopAuto() {
  autoRunning = false;
  autoBusy = false;
  if (autoTimer) clearTimeout(autoTimer);
  autoTimer = null;
  autoButton.classList.remove("active");
  autoButton.textContent = "Auto";
  setAutoStatus("Manual mode");
}

function scheduleAutoTick(delayMs) {
  if (!autoRunning) return;
  if (autoTimer) clearTimeout(autoTimer);
  autoTimer = setTimeout(autoTick, delayMs);
}

async function autoTick() {
  if (!autoRunning || autoBusy) return;
  autoBusy = true;
  try {
    if (!state.auto_terminal) {
      setAutoStatus(`Auto: ${title(state.turn)} thinking`);
      state = await api("/api/agent-move", {});
      render();
      autoBusy = false;
      scheduleAutoTick(AUTO_MOVE_DELAY_MS);
      return;
    }

    setAutoStatus("Auto: game finished, starting background learning");
    const learnStart = await api("/api/learn", {
      backend: "profile",
      max_repair_attempts: 0,
      promote_agent: false,
      promote_profile: false,
    });
    if (learnStart.state) {
      state = learnStart.state;
      render();
    }
    if (learnStart.error) {
      setAutoStatus(`Learning failed: ${learnStart.error}`);
      stopAuto();
      return;
    }

    const learning = await monitorLearning();
    if (!learning || !autoRunning) return;
    if (learning.status === "failed") {
      setAutoStatus(`Learning failed: ${learning.error || learning.message}`);
      stopAuto();
      return;
    }

    const promotedAgent = Boolean(learning.result && learning.result.promoted_agent);
    const promotedProfile = Boolean(learning.result && learning.result.promoted_profile);
    const promoted = promotedAgent || promotedProfile;
    setAutoStatus(`Learned: ${promoted ? "baseline updated" : "candidate kept"} · next game in 2s`);
    await sleep(2000);
    if (!autoRunning) return;
    state = await api("/api/new", { mode: "agent_vs_agent", max_plies: 200 });
    render();
    autoBusy = false;
    scheduleAutoTick(AUTO_MOVE_DELAY_MS);
  } catch (error) {
    setAutoStatus(`Auto stopped: ${error}`);
    stopAuto();
  } finally {
    autoBusy = false;
  }
}

async function monitorLearning() {
  while (autoRunning) {
    const payload = await api("/api/learn-status");
    if (payload.state) {
      state = payload.state;
      render();
    }
    const learning = payload.learning || (state ? state.learning : null);
    if (!learning) {
      setAutoStatus("Learning: waiting for status");
      await sleep(1000);
      continue;
    }

    setAutoStatus(`Learning: ${learningStatusLabel(learning)}`);
    if (["promoted", "validated", "failed"].includes(learning.status)) {
      return learning;
    }
    await sleep(1000);
  }
  return null;
}

function learningStatusLabel(learning) {
  const labels = {
    queued: "queued",
    waiting: "waiting for previous job",
    saving_logs: "saving logs",
    catarena_running: "running official CATArena round",
    reading_feedback: "reading logs and memory",
    generating: "generating profile candidate",
    prescreen: "running feedback FEN prescreen",
    regression: "running historical profile regression",
    validating: "validating candidate",
    promoting: "promoting profile",
    writing_report: "writing report",
    promoted: "promoted",
    validated: "validated",
    failed: "failed",
  };
  return labels[learning.status] || learning.message || learning.status;
}

function setAutoStatus(text) {
  autoStatus.textContent = text;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

loadState();
