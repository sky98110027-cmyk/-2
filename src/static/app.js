"use strict";

/* 결 — 화면 동작.
   외부 라이브러리는 안 쓴다. 한 파일로 끝낸다. */

const $ = (id) => document.getElementById(id);

/* 모델이 돌려준 글자를 그대로 화면에 박기 전에 한 번 막는다. */
const esc = (v) =>
  String(v == null ? "" : v)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

const list = (arr, fmt = esc) =>
  (arr || []).length
    ? `<ul>${arr.map((x) => `<li>${fmt(x)}</li>`).join("")}</ul>`
    : "<p>(없음)</p>";

let toastTimer = null;
function toast(text) {
  const box = $("toast");
  box.textContent = text;
  box.classList.add("on");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => box.classList.remove("on"), 2600);
}

async function api(path, options) {
  const res = await fetch(path, options);
  let body = null;
  try {
    body = await res.json();
  } catch (e) {
    body = null;
  }
  if (!res.ok) {
    const detail = (body && body.detail) || `서버 오류 (${res.status})`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return body;
}

const postJSON = (path, data) => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(data),
});

function showError(target, err) {
  $(target).innerHTML = `<div class="msg err">${esc(err.message)}</div>`;
}

function showWaiting(target, text) {
  $(target).innerHTML = `<div class="msg wait">${esc(text)}</div>`;
}

async function copy(text, what) {
  try {
    await navigator.clipboard.writeText(text);
    toast(`${what} 복사했습니다`);
  } catch (e) {
    toast("복사가 막혔습니다. 직접 긁어서 복사해주세요");
  }
}

/* ------------------------------------------------------------------ 탭 */

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("on"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("on"));
    tab.classList.add("on");
    $(tab.dataset.tab).classList.add("on");
    if (tab.dataset.tab !== "step1") loadSkills();
  });
});

function goTab(name) {
  const tab = document.querySelector(`.tab[data-tab="${name}"]`);
  if (tab) tab.click();
}

/* ------------------------------------------------------------- 준비 상태 */

async function checkHealth() {
  const box = $("status");
  try {
    const h = await api("/api/health");
    if (!h.api_key) {
      box.className = "status bad";
      box.textContent =
        "클로드 API 키가 안 잡힙니다. 터미널에서 export ANTHROPIC_API_KEY=키값 하신 뒤 앱을 다시 켜주세요.";
      return;
    }
    box.className = "status good";
    box.textContent = `준비됐습니다 · 모델 ${h.model} · 저장된 결 ${h.skill_count}개`;
  } catch (e) {
    box.className = "status bad";
    box.textContent = "서버에 연결이 안 됩니다.";
  }
}

/* ------------------------------------------------------------ 1단계 분석 */

let lastAnalysis = null;

$("a-go").addEventListener("click", async () => {
  const btn = $("a-go");
  const payload = {
    url: $("a-url").value.trim(),
    transcript: $("a-transcript").value.trim(),
    title: $("a-title").value.trim(),
    notes: $("a-notes").value.trim(),
  };

  if (!payload.url && !payload.transcript) {
    toast("영상 링크를 넣거나 대본을 붙여넣어주세요");
    return;
  }

  btn.disabled = true;
  btn.textContent = "뜯어보는 중입니다…";
  showWaiting("a-out", "자막을 받아서 읽고 있습니다. 1분쯤 걸립니다. 창을 닫지 말아주세요.");

  try {
    lastAnalysis = await api("/api/analyze", postJSON(payload));
    renderAnalysis(lastAnalysis);
  } catch (e) {
    showError("a-out", e);
  } finally {
    btn.disabled = false;
    btn.textContent = "결 뽑기";
  }
});

function renderAnalysis(data) {
  const d = data.dna;
  const src = data.source || {};
  const v = d.voice || {};
  const st = d.structure || {};
  const em = d.emotion || {};
  const vis = d.visual || {};
  const nar = d.narration || {};

  const beats = (st.beats || [])
    .map(
      (b, i) =>
        `<li><b>${esc(b.name)}</b> <em>(${esc(b.share)})</em><br>${esc(b.does)}</li>`
    )
    .join("");

  $("a-out").innerHTML = `
    <div class="box">
      <h3>${esc(d.title)}</h3>
      <p>${esc(d.one_line)}</p>
      <p class="meta">${esc(src.title || src.url || "")} · ${esc(src.transcript_origin || "")} · ${esc(
        src.transcript_chars || 0
      )}자</p>

      <h4>말투</h4>
      <ul>
        <li>화자 — ${esc(v.person)}</li>
        <li>온도 — ${esc(v.tone)}</li>
        <li>종결어미 — ${esc(v.speech_level)}</li>
        <li>문장 — ${esc(v.sentence_rule)}</li>
      </ul>
      <h4>입에 붙은 표현</h4>
      ${list(v.signature_phrases)}

      <h4>도입 15초</h4>
      <p>${esc(st.hook)}</p>
      <h4>전체 흐름</h4>
      ${beats ? `<ul>${beats}</ul>` : "<p>(없음)</p>"}
      <h4>마무리</h4>
      <p>${esc(st.ending)}</p>

      <h4>감정</h4>
      <p>${esc(em.curve)}<br>정점 — ${esc(em.peak)}</p>
      ${list(em.devices)}

      <h4>화면</h4>
      <p>${esc(vis.mood)}<br>자막 — ${esc(vis.caption_rule)}</p>
      ${list(vis.shot_rules)}

      <h4>소리</h4>
      <p>${esc(nar.pace)} · ${esc(nar.pause_rule)}<br>배경음 — ${esc(nar.bgm)}</p>

      <h4>제목 공식</h4>
      ${list(d.title_pattern)}
      <h4>하지 않는 것</h4>
      ${list(d.forbidden)}
      <h4>점검표</h4>
      ${list(d.checklist)}

      <div class="row">
        <button class="big" id="a-save">이 결을 스킬로 저장</button>
      </div>
      <div class="row">
        <button class="small" id="a-copy-md">스킬 파일 복사</button>
      </div>
    </div>

    <details class="fold">
      <summary>만들어진 스킬 파일 보기 (SKILL.md)</summary>
      <pre>${esc(data.skill_md)}</pre>
    </details>
  `;

  $("a-save").addEventListener("click", saveSkill);
  $("a-copy-md").addEventListener("click", () => copy(data.skill_md, "스킬 파일을"));
}

async function saveSkill() {
  if (!lastAnalysis) return;
  const btn = $("a-save");
  btn.disabled = true;
  btn.textContent = "저장 중…";
  try {
    const meta = await api(
      "/api/skills",
      postJSON({
        dna: lastAnalysis.dna,
        slug: lastAnalysis.slug,
        source: lastAnalysis.source,
        material_brief: lastAnalysis.material_brief,
      })
    );
    toast(`'${meta.name}' 저장했습니다`);
    await loadSkills();
    await checkHealth();
    goTab("step3");
    $("p-skill").value = meta.slug;
  } catch (e) {
    showError("a-out", e);
  } finally {
    btn.disabled = false;
    btn.textContent = "이 결을 스킬로 저장";
  }
}

/* ------------------------------------------------------------ 2단계 목록 */

async function loadSkills() {
  let skills = [];
  try {
    skills = (await api("/api/skills")).skills || [];
  } catch (e) {
    $("s-list").innerHTML = `<div class="msg err">${esc(e.message)}</div>`;
    return;
  }

  $("s-list").innerHTML = skills.length
    ? skills
        .map(
          (s) => `
      <div class="card">
        <h3>${esc(s.name)}</h3>
        <p class="one">${esc(s.one_line)}</p>
        <p class="meta">${esc(s.source_title || s.source_url || "직접 넣은 대본")}<br>
        ${esc(s.created_at.slice(0, 16).replace("T", " "))} · ${esc(s.slug)}</p>
        <div class="row">
          <button class="small" data-use="${esc(s.slug)}">이 결로 대본 쓰기</button>
          <a class="small" style="text-decoration:none;display:inline-flex;align-items:center"
             href="/api/skills/${esc(s.slug)}/skill.md">파일 내려받기</a>
          <button class="small danger" data-del="${esc(s.slug)}">지우기</button>
        </div>
      </div>`
        )
        .join("")
    : `<div class="msg wait">아직 저장된 결이 없습니다. 1단계에서 영상 링크를 하나 넣어보세요.</div>`;

  $("s-list")
    .querySelectorAll("[data-use]")
    .forEach((b) =>
      b.addEventListener("click", () => {
        goTab("step3");
        $("p-skill").value = b.dataset.use;
        $("p-topic").focus();
      })
    );

  $("s-list")
    .querySelectorAll("[data-del]")
    .forEach((b) =>
      b.addEventListener("click", async () => {
        if (!confirm("이 결을 지웁니다. 되돌릴 수 없습니다. 지울까요?")) return;
        try {
          await api(`/api/skills/${b.dataset.del}`, { method: "DELETE" });
          toast("지웠습니다");
          await loadSkills();
          await checkHealth();
        } catch (e) {
          toast(e.message);
        }
      })
    );

  const sel = $("p-skill");
  const keep = sel.value;
  sel.innerHTML = skills.length
    ? skills.map((s) => `<option value="${esc(s.slug)}">${esc(s.name)}</option>`).join("")
    : `<option value="">저장된 결이 없습니다</option>`;
  if (keep && skills.some((s) => s.slug === keep)) sel.value = keep;
}

/* ------------------------------------------------------------ 3단계 집필 */

$("p-go").addEventListener("click", async () => {
  const btn = $("p-go");
  const payload = {
    slug: $("p-skill").value,
    topic: $("p-topic").value.trim(),
    minutes: Number($("p-min").value),
    notes: $("p-notes").value.trim(),
  };

  if (!payload.slug) {
    toast("먼저 1단계에서 결을 하나 만들어주세요");
    return;
  }
  if (!payload.topic) {
    toast("이번 영상 주제를 넣어주세요");
    return;
  }

  btn.disabled = true;
  btn.textContent = "쓰는 중입니다…";
  showWaiting("p-out", "대본을 쓰고 있습니다. 2분쯤 걸립니다. 창을 닫지 말아주세요.");

  try {
    renderScript(await api("/api/produce", postJSON(payload)));
  } catch (e) {
    showError("p-out", e);
  } finally {
    btn.disabled = false;
    btn.textContent = "대본 만들기";
  }
});

function renderScript(data) {
  const s = data.script;
  const mm = Math.floor((s.total_seconds || 0) / 60);
  const ss = (s.total_seconds || 0) % 60;

  const scenes = (s.scenes || [])
    .map(
      (sc) => `
    <div class="scene">
      <div class="head">${esc(sc.no)}. ${esc(sc.beat)} · ${esc(sc.seconds)}초</div>
      <div class="nar">${esc(sc.narration)}</div>
      <div class="cap">자막 — ${esc(sc.caption)}</div>
      <div class="prompt"><b>그림</b> ${esc(sc.image_prompt)}<br><b>움직임</b> ${esc(
        sc.video_prompt
      )}<br><b>소리</b> ${esc(sc.bgm)}</div>
    </div>`
    )
    .join("");

  $("p-out").innerHTML = `
    <div class="box">
      <h3>${esc(s.topic)} <em style="font-weight:400;font-size:16px">· ${esc(
        data.skill_name
      )} 결 · 약 ${mm}분 ${ss}초</em></h3>

      <h4>제목 후보</h4>
      ${list(s.title_candidates)}
      <h4>썸네일 문구</h4>
      ${list(s.thumbnail_copy)}

      <h4>첫 15초</h4>
      <p style="white-space:pre-wrap">${esc(s.hook)}</p>

      <div class="row">
        <button class="small" id="p-copy-text">나레이션 원고 복사</button>
        <button class="small" id="p-copy-order">영상 생성 지시서 복사</button>
      </div>
    </div>

    <div class="box">
      <h3>장면 ${(s.scenes || []).length}컷</h3>
      ${scenes}
      <h4>마무리</h4>
      <p style="white-space:pre-wrap">${esc(s.closing)}</p>
    </div>

    <div class="box">
      <h3>결 점검</h3>
      ${list(s.self_check)}
      <h4>설명란</h4>
      <p style="white-space:pre-wrap">${esc(s.description)}</p>
      <h4>태그</h4>
      <p>${esc((s.tags || []).join(", "))}</p>
    </div>

    <details class="fold">
      <summary>영상 생성 지시서 원본 보기 (힉스필드·톱뷰에 넣는 것)</summary>
      <pre>${esc(JSON.stringify(data.production_order, null, 2))}</pre>
    </details>
  `;

  $("p-copy-text").addEventListener("click", () => copy(data.plain_text, "원고를"));
  $("p-copy-order").addEventListener("click", () =>
    copy(JSON.stringify(data.production_order, null, 2), "지시서를")
  );
}

/* ------------------------------------------------------------------ 시작 */

checkHealth();
loadSkills();
