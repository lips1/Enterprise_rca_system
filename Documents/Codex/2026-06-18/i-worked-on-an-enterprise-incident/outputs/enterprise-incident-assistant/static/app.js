function bodyFromForm() {
  return {
    user_id: "demo_user",
    role: document.getElementById("role").value,
    incident_id: document.getElementById("incidentId").value,
    service_name: document.getElementById("serviceName").value,
    query: document.getElementById("query").value,
    start_time: document.getElementById("startTime").value,
    end_time: document.getElementById("endTime").value
  };
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail);
  }
  return response.json();
}

function renderResponse(data) {
  document.getElementById("summary").textContent = data.summary;
  document.getElementById("rootCause").textContent = data.probable_root_cause;
  renderList("actions", data.recommended_actions);
  renderList("timeline", data.timeline);

  const obs = data.observability;
  document.getElementById("metrics").innerHTML = [
    metric("Latency", `${obs.total_latency_ms} ms`),
    metric("Tool Time", `${obs.tool_latency_ms} ms`),
    metric("Tokens", obs.estimated_total_tokens),
    metric("Evidence", obs.evidence_count),
    metric("Agents", obs.agent_count),
    metric("Tools", obs.tool_count),
    metric("Memory Turns", obs.memory_turns_for_incident),
    metric("Mode", obs.sync_or_async)
  ].join("");

  document.getElementById("agents").innerHTML = data.agent_observations.map(item => `
    <div class="row">
      <span>${item.agent_name}</span>
      <span>${item.latency_ms} ms</span>
      <span>${item.input_tokens_estimate + item.output_tokens_estimate} tok</span>
      <span>${item.notes}</span>
    </div>
  `).join("");

  document.getElementById("tools").innerHTML = data.tool_observations.map(item => `
    <div class="row">
      <span>${item.tool_name}</span>
      <span>${item.latency_ms} ms</span>
      <span>${item.row_count} rows</span>
      <span>${item.notes}</span>
    </div>
  `).join("");

  document.getElementById("guardrails").innerHTML = data.guardrails.map(item => `
    <div class="row">
      <span>${item.name}</span>
      <span class="${item.passed ? "pass" : "fail"}">${item.passed ? "PASS" : "FAIL"}</span>
      <span>${item.severity}</span>
      <span>${item.message}</span>
    </div>
  `).join("");

  document.getElementById("evals").innerHTML = data.agent_evaluations.map(item => `
    <div class="row">
      <span>${item.agent_name}</span>
      <span class="${item.passed ? "pass" : "fail"}">${item.score}</span>
      <span>${item.passed ? "PASS" : "REVIEW"}</span>
      <span>${item.findings.join(" ")}</span>
    </div>
  `).join("");
}

function metric(label, value) {
  return `<div class="metric"><strong>${value}</strong><span>${label}</span></div>`;
}

function renderList(id, values) {
  document.getElementById(id).innerHTML = values.map(item => `<li>${item}</li>`).join("");
}

async function runSync() {
  try {
    const data = await postJson("/investigate", bodyFromForm());
    renderResponse(data);
  } catch (error) {
    alert(error.message);
  }
}

async function runAsync() {
  try {
    const job = await postJson("/investigate/async", bodyFromForm());
    document.getElementById("summary").textContent = `Async job submitted: ${job.job_id}`;
    const timer = setInterval(async () => {
      const state = await fetch(job.poll_url).then(response => response.json());
      if (state.status === "complete") {
        clearInterval(timer);
        renderResponse(state.result);
      }
      if (state.status === "failed") {
        clearInterval(timer);
        alert(state.error);
      }
    }, 1000);
  } catch (error) {
    alert(error.message);
  }
}

async function runEval() {
  const result = await postJson("/eval/run", {});
  alert(`Eval passed ${result.passed_cases}/${result.total_cases}, avg groundedness ${result.average_groundedness}`);
}

document.getElementById("syncBtn").addEventListener("click", runSync);
document.getElementById("asyncBtn").addEventListener("click", runAsync);
document.getElementById("evalBtn").addEventListener("click", runEval);
