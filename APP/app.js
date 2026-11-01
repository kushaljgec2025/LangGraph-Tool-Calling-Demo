document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const queryInput = document.getElementById("query-input");
  const runBtn = document.getElementById("run-btn");
  const runSpinner = document.getElementById("run-spinner");
  const statusBadge = document.getElementById("status-badge");
  const presetButtons = document.querySelectorAll(".preset-btn");

  const btnPrev = document.getElementById("btn-prev");
  const btnPlay = document.getElementById("btn-play");
  const btnNext = document.getElementById("btn-next");
  const btnReset = document.getElementById("btn-reset");
  const speedSelect = document.getElementById("speed-select");
  const stepIndicator = document.getElementById("step-indicator");

  const narrativeIcon = document.getElementById("narrative-icon");
  const narrativeTitle = document.getElementById("narrative-title");
  const narrativeDesc = document.getElementById("narrative-desc");

  const inputNodeName = document.getElementById("input-node-name");
  const inputStructure = document.getElementById("input-structure");
  const outputNodeName = document.getElementById("output-node-name");
  const outputStructure = document.getElementById("output-structure");
  const toolPayload = document.getElementById("tool-payload");
  const toolDetailsBlock = document.getElementById("tool-details-block");

  const stateStructure = document.getElementById("state-structure");
  const stateMsgCount = document.getElementById("state-msg-count");
  const timelineList = document.getElementById("timeline-list");
  const finalAnswerText = document.getElementById("final-answer-text");
  const execSummaryBadge = document.getElementById("exec-summary-badge");

  const tabButtons = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");

  const flowParticle = document.getElementById("flow-particle");

  // State
  let pipelineSteps = [];
  let currentStepIndex = -1;
  let isPlaying = false;
  let playInterval = null;
  let currentParticleAnim = null;

  // Initialize: Load Tools
  fetchTools();

  // Tab switching
  tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      tabButtons.forEach(b => b.classList.remove("active"));
      tabContents.forEach(c => c.classList.remove("active"));
      btn.classList.add("active");
      const targetId = btn.dataset.tab;
      document.getElementById(targetId)?.classList.add("active");
    });
  });

  // Preset button handling
  presetButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      queryInput.value = btn.dataset.query;
      queryInput.focus();
    });
  });

  // Run Button handling
  runBtn.addEventListener("click", handleRunPipeline);

  // Playback Controls
  btnPlay.addEventListener("click", togglePlay);
  btnNext.addEventListener("click", () => { pause(); stepForward(); });
  btnPrev.addEventListener("click", () => { pause(); stepBackward(); });
  btnReset.addEventListener("click", () => { pause(); renderStep(0); });
  speedSelect.addEventListener("change", () => {
    if (isPlaying) {
      pause();
      play();
    }
  });

  async function fetchTools() {
    try {
      const res = await fetch("/api/tools");
      if (res.ok) {
        const tools = await res.json();
        const badge = document.getElementById("tools-badge");
        if (badge) {
          badge.innerHTML = `<span class="dot dot-blue"></span> ${tools.length} Tools Loaded`;
        }
      }
    } catch (e) {
      console.warn("Could not fetch tools list", e);
    }
  }

  async function handleRunPipeline() {
    const query = queryInput.value.trim();
    if (!query) {
      alert("Please enter a custom query or select a preset.");
      return;
    }

    // UI Loading state
    runBtn.disabled = true;
    runSpinner.classList.remove("hidden");
    statusBadge.textContent = "Executing...";
    statusBadge.classList.add("running");
    narrativeIcon.textContent = "⚙️";
    narrativeTitle.textContent = "Running LangGraph Workflow";
    narrativeDesc.textContent = "Query dispatched to orchestrator. Calling Gemini model and routing tool calls...";

    pause();
    resetGraphVisuals();
    timelineList.innerHTML = `<div class="timeline-empty">Running pipeline...</div>`;

    try {
      const response = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query })
      });

      const data = await response.json();
      if (data.status === "error") {
        throw new Error(data.message);
      }

      pipelineSteps = data.steps || [];
      finalAnswerText.textContent = data.final_answer || "No response received";
      execSummaryBadge.textContent = `${pipelineSteps.length} Steps`;

      populateTimeline(pipelineSteps);

      // Enable playback
      btnPrev.disabled = false;
      btnPlay.disabled = false;
      btnNext.disabled = false;
      btnReset.disabled = false;

      statusBadge.textContent = "Completed";
      statusBadge.classList.remove("running");

      // Auto play the flow animation
      renderStep(0);
      play();

    } catch (err) {
      console.error(err);
      statusBadge.textContent = "Error";
      statusBadge.classList.remove("running");
      narrativeIcon.textContent = "⚠️";
      narrativeTitle.textContent = "Pipeline Error";
      narrativeDesc.textContent = err.message;
      alert(`Error running LangGraph: ${err.message}`);
    } finally {
      runBtn.disabled = false;
      runSpinner.classList.add("hidden");
    }
  }

  function renderStep(index) {
    if (!pipelineSteps || pipelineSteps.length === 0) return;
    if (index < 0) index = 0;
    if (index >= pipelineSteps.length) index = pipelineSteps.length - 1;

    currentStepIndex = index;
    const step = pipelineSteps[index];

    // Update Step Indicator
    stepIndicator.textContent = `Step: ${index + 1} / ${pipelineSteps.length}`;

    // Update Narrative
    narrativeTitle.textContent = step.title;
    narrativeDesc.textContent = step.description;

    const icons = {
      start: "🚀",
      agent: "🤖",
      router: "🔀",
      tool: "⚡",
      end: "🏁"
    };
    narrativeIcon.textContent = icons[step.node_type] || "🔹";

    // Update Graph Nodes and Edges visual states
    updateGraphHighlight(step, index);

    // Update Inspector Tabs
    inputNodeName.textContent = step.from_node;
    inputStructure.textContent = JSON.stringify(step.input_data, null, 2);

    outputNodeName.textContent = step.active_node;
    outputStructure.textContent = JSON.stringify(step.output_data, null, 2);

    if (step.tool_details) {
      toolDetailsBlock.classList.remove("hidden");
      toolPayload.textContent = JSON.stringify(step.tool_details, null, 2);
    } else {
      toolDetailsBlock.classList.add("hidden");
    }

    // Cumulative State
    stateStructure.textContent = JSON.stringify({ messages: step.current_messages }, null, 2);
    stateMsgCount.textContent = step.current_messages ? step.current_messages.length : 0;

    // Highlight active timeline item
    document.querySelectorAll(".timeline-item").forEach((el, idx) => {
      el.classList.toggle("active", idx === index);
    });

    // Button states
    btnPrev.disabled = index === 0;
    btnNext.disabled = index === pipelineSteps.length - 1;
  }

  function updateGraphHighlight(step, stepIndex) {
    // Clear previous active states
    document.querySelectorAll(".graph-node").forEach(n => n.classList.remove("active"));
    document.querySelectorAll(".graph-edge").forEach(e => e.classList.remove("active"));

    // Highlight active node
    const activeNodeId = `node-${step.active_node}`;
    const activeNodeEl = document.getElementById(activeNodeId);
    if (activeNodeEl) {
      activeNodeEl.classList.add("active");
    }

    // Identify target edge
    let edgeId = null;
    const from = step.from_node;
    const to = step.to_node;

    if (from === "START" && to === "agent") {
      edgeId = "edge-START-agent";
    } else if (from === "agent" && step.active_node === "router") {
      edgeId = "edge-agent-router";
    } else if (step.active_node === "router" && to) {
      edgeId = `edge-router-${to}`;
    } else if (from && to === "agent" && from !== "START") {
      edgeId = `edge-${from}-agent`;
    } else if (to === "END") {
      edgeId = "edge-agent-END";
    }

    const edgeEl = edgeId ? document.getElementById(edgeId) : null;
    if (edgeEl) {
      edgeEl.classList.add("active");
      animateParticleAlongEdge(edgeEl);
    } else {
      flowParticle.classList.add("hidden");
    }
  }

  function animateParticleAlongEdge(edgePath) {
    if (!edgePath || typeof edgePath.getTotalLength !== "function") {
      flowParticle.classList.add("hidden");
      return;
    }

    if (currentParticleAnim) {
      cancelAnimationFrame(currentParticleAnim);
    }

    const pathLength = edgePath.getTotalLength();
    flowParticle.classList.remove("hidden");

    const duration = parseInt(speedSelect.value, 10) * 0.7; // 70% of step duration
    const startTime = performance.now();

    function stepAnimation(timestamp) {
      const elapsed = timestamp - startTime;
      const progress = Math.min(elapsed / duration, 1);

      const pt = edgePath.getPointAtLength(progress * pathLength);
      flowParticle.setAttribute("cx", pt.x);
      flowParticle.setAttribute("cy", pt.y);

      if (progress < 1) {
        currentParticleAnim = requestAnimationFrame(stepAnimation);
      } else {
        currentParticleAnim = null;
      }
    }

    currentParticleAnim = requestAnimationFrame(stepAnimation);
  }

  function togglePlay() {
    if (isPlaying) {
      pause();
    } else {
      play();
    }
  }

  function play() {
    if (currentStepIndex >= pipelineSteps.length - 1) {
      currentStepIndex = -1;
    }
    isPlaying = true;
    btnPlay.textContent = "⏸";
    btnPlay.classList.add("playing");

    const delay = parseInt(speedSelect.value, 10);
    playInterval = setInterval(() => {
      if (currentStepIndex < pipelineSteps.length - 1) {
        stepForward();
      } else {
        pause();
      }
    }, delay);
  }

  function pause() {
    isPlaying = false;
    btnPlay.textContent = "▶";
    btnPlay.classList.remove("playing");
    if (playInterval) {
      clearInterval(playInterval);
      playInterval = null;
    }
  }

  function stepForward() {
    if (currentStepIndex < pipelineSteps.length - 1) {
      renderStep(currentStepIndex + 1);
    }
  }

  function stepBackward() {
    if (currentStepIndex > 0) {
      renderStep(currentStepIndex - 1);
    }
  }

  function resetGraphVisuals() {
    document.querySelectorAll(".graph-node").forEach(n => n.classList.remove("active", "completed"));
    document.querySelectorAll(".graph-edge").forEach(e => e.classList.remove("active", "completed"));
    flowParticle.classList.add("hidden");
  }

  function populateTimeline(steps) {
    timelineList.innerHTML = "";
    steps.forEach((st, idx) => {
      const item = document.createElement("div");
      item.className = "timeline-item";
      item.innerHTML = `
        <div class="timeline-step-num">${idx + 1}</div>
        <div class="timeline-info">
          <span class="timeline-item-title">${st.title}</span>
          <span class="timeline-item-desc">${st.active_node} → ${st.to_node}</span>
        </div>
      `;
      item.addEventListener("click", () => {
        pause();
        renderStep(idx);
      });
      timelineList.appendChild(item);
    });
  }
});
