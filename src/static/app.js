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
    // 숨어 있던 동안에는 폭이 0이라 못 그렸다. 보이는 지금 다시 그린다.
    if (tab.dataset.tab === "step4") 미리보기();
    if (tab.dataset.tab === "build") 영상탭열기();
    if (tab.dataset.tab === "setup") 설정읽기();
    if (tab.dataset.tab === "wire") {
      연결읽기();
      준비읽기();
    }
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
      box.innerHTML =
        '클로드 API 키가 안 잡힙니다. ' +
        '<button class="small" id="go-wire" style="margin-left:8px">연결하러 가기</button>';
      const 가기 = $("go-wire");
      if (가기) 가기.addEventListener("click", () => goTab("wire"));
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
          <button class="small" data-deep="${esc(s.slug)}">화면까지 뜯기</button>
          <button class="small danger" data-del="${esc(s.slug)}">지우기</button>
        </div>
        ${스킬쓰는법(s)}
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
    .querySelectorAll("[data-deep]")
    .forEach((b) => b.addEventListener("click", () => 화면까지뜯기(b.dataset.deep, b)));

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
    folder: $("p-folder").value.trim(),
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
    const data = await api("/api/produce", postJSON(payload));
    renderScript(data);
    await 작업열기(data);
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
        <button class="small" id="p-fix">고치러 가기</button>
        <button class="small" id="p-build">영상 만들러 가기</button>
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
  $("p-fix").addEventListener("click", () => goTab("step4"));
  $("p-build").addEventListener("click", () => goTab("build"));
}

/* ------------------------------------------------------------------ 시작 */

checkHealth();
loadSkills();

/* ============================================================ 4단계 고치기

   자막 글꼴과 색과 위치는 클로드를 안 부른다.
   손잡이를 돌리면 그 자리에서 미리보기가 바뀐다.
   "이대로 저장"을 눌러야 파일에 들어간다.
   ============================================================ */

let 작업 = null; // 지금 열려 있는 작업 전체
let 옵션 = null; // 글꼴 목록 등

/* 서버는 아무것도 기억하지 않는다. 지금 상태는 이쪽이 들고 다닌다. */
const 상태 = { pending: null, project_id: null };

/* 글꼴 이름을 브라우저가 아는 이름으로 바꿔준다. 없으면 기본 고딕으로 떨어진다. */
const FONT_CSS = {
  Pretendard: "Pretendard, 'Apple SD Gothic Neo', sans-serif",
  나눔고딕: "'NanumGothic', 'Nanum Gothic', sans-serif",
  나눔명조: "'NanumMyeongjo', 'Nanum Myeongjo', serif",
  "본고딕 (Noto Sans KR)": "'Noto Sans KR', sans-serif",
  "본명조 (Noto Serif KR)": "'Noto Serif KR', serif",
  "애플 SD 산돌고딕": "'Apple SD Gothic Neo', sans-serif",
  "맑은 고딕": "'Malgun Gothic', sans-serif",
  에스코어드림: "'S-Core Dream', sans-serif",
};

const 기준너비 = { "16:9": 1920, "9:16": 1080, "1:1": 1080 };

function hexToRgba(hex, alpha) {
  const n = parseInt(String(hex).slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

async function 옵션받기() {
  if (!옵션) 옵션 = await api("/api/style/options");
  return 옵션;
}

/* ---------------------------------------------------------- 미리보기 그리기 */

function 미리보기() {
  if (!작업) return;
  $("r-summary").textContent = 작업.style_summary || "";
  const 폭 = $("r-stage").clientWidth;
  if (!폭) return; // 아직 화면에 안 떴다. 탭이 열릴 때 다시 부른다.
  const st = 작업.style;
  const c = st.caption;

  const stage = $("r-stage");
  stage.className = "stage" + (st.aspect_ratio === "16:9" ? "" : ` ratio-${st.aspect_ratio.replace(":", "-")}`);

  // 실제 화면 기준 px 를 미리보기 폭에 맞춰 줄인다
  const 배율 = 폭 / 기준너비[st.aspect_ratio];

  const cap = $("r-cap");
  cap.className = `stage-cap pos-${c.position}`;
  cap.style.fontFamily = FONT_CSS[c.font] || `'${c.font}', sans-serif`;
  cap.style.fontSize = `${Math.max(9, c.size * 배율)}px`;
  cap.style.fontWeight = c.bold ? "800" : "500";
  cap.style.color = c.color;
  cap.style.lineHeight = c.line_spacing;
  cap.style.textShadow = c.outline
    ? [
        `0 0 ${c.outline * 배율}px ${c.outline_color}`,
        `${c.outline * 배율}px 0 0 ${c.outline_color}`,
        `-${c.outline * 배율}px 0 0 ${c.outline_color}`,
        `0 ${c.outline * 배율}px 0 ${c.outline_color}`,
        `0 -${c.outline * 배율}px 0 ${c.outline_color}`,
      ].join(", ")
    : "none";

  if (c.position === "middle") {
    cap.style.padding = `0 ${st.safe_margin * 배율}px`;
  } else if (c.position === "bottom") {
    cap.style.padding = `0 ${st.safe_margin * 배율}px ${c.offset * 배율}px`;
  } else {
    cap.style.padding = `${c.offset * 배율}px ${st.safe_margin * 배율}px 0`;
  }

  const 글 = esc($("r-pick").value || "여기가 자막 자리입니다");
  cap.innerHTML =
    c.background === "none"
      ? 글
      : `<span class="band" style="background:${hexToRgba(
          c.background_color,
          c.background_opacity
        )}">${글}</span>`;

  $("r-summary").textContent = 작업.style_summary;
}

/* ------------------------------------------------------------ 손잡이 묶기 */

function 손잡이채우기() {
  const st = 작업.style;
  const c = st.caption;

  $("k-font").innerHTML = 옵션.fonts
    .map((f) => `<option value="${esc(f)}">${esc(f)}</option>`)
    .join("");
  if (!옵션.fonts.includes(c.font)) {
    $("k-font").insertAdjacentHTML("afterbegin", `<option value="${esc(c.font)}">${esc(c.font)}</option>`);
  }
  $("k-font").value = c.font;

  $("k-pos").innerHTML = Object.entries(옵션.positions)
    .map(([k, v]) => `<option value="${esc(k)}">${esc(v)}</option>`)
    .join("");
  $("k-pos").value = c.position;

  $("k-bg").innerHTML = Object.entries(옵션.backgrounds)
    .map(([k, v]) => `<option value="${esc(k)}">${esc(v)}</option>`)
    .join("");
  $("k-bg").value = c.background;

  $("k-ratio").value = st.aspect_ratio;
  $("k-size").value = c.size;
  $("k-out").value = c.outline;
  $("k-off").value = c.offset;
  $("k-color").value = c.color;
  $("k-ocolor").value = c.outline_color;
  $("k-bgcolor").value = c.background_color;

  $("v-size").textContent = `${c.size}px`;
  $("v-out").textContent = `${c.outline}px`;
  $("v-off").textContent = `${c.offset}px`;
}

function 손잡이읽기() {
  const c = 작업.style.caption;
  작업.style.aspect_ratio = $("k-ratio").value;
  c.font = $("k-font").value;
  c.position = $("k-pos").value;
  c.background = $("k-bg").value;
  c.size = Number($("k-size").value);
  c.outline = Number($("k-out").value);
  c.offset = Number($("k-off").value);
  c.color = $("k-color").value.toUpperCase();
  c.outline_color = $("k-ocolor").value.toUpperCase();
  c.background_color = $("k-bgcolor").value.toUpperCase();

  $("v-size").textContent = `${c.size}px`;
  $("v-out").textContent = `${c.outline}px`;
  $("v-off").textContent = `${c.offset}px`;

  작업.style_summary = `${c.font} · ${c.size}px · ${c.bold ? "굵게" : "보통"} · ${
    c.color
  } · ${옵션.positions[c.position]} 정렬${c.outline ? ` · 외곽선 ${c.outline}px` : ""}${
    c.background !== "none" ? ` · ${옵션.backgrounds[c.background]} 배경` : ""
  }`;
  미리보기();
}

[
  "k-font", "k-pos", "k-bg", "k-ratio",
  "k-size", "k-out", "k-off",
  "k-color", "k-ocolor", "k-bgcolor",
].forEach((id) => {
  const el = $(id);
  el.addEventListener("input", 손잡이읽기);
  el.addEventListener("change", 손잡이읽기);
});

$("r-pick").addEventListener("change", 미리보기);
window.addEventListener("resize", 미리보기);

/* ------------------------------------------------------------ 작업 띄우기 */

async function 작업열기(data) {
  await 옵션받기();
  작업 = data;
  // 손으로 만들었든 말로 만들었든, 이어서 고칠 수 있게 여기서 기억한다
  상태.project_id = data.project_id;

  $("r-empty").style.display = "none";
  $("r-body").style.display = "";
  $("r-title").textContent = `${data.script.topic} — ${data.skill_name} 결`;

  const 자막들 = (data.script.scenes || []).map((s) => s.caption).filter(Boolean);
  $("r-pick").innerHTML = (자막들.length ? 자막들 : ["여기가 자막 자리입니다"])
    .map((t) => `<option value="${esc(t)}">${esc(t)}</option>`)
    .join("");

  손잡이채우기();
  미리보기();
  그린내력();
}

function 그린내력() {
  const h = 작업.history || [];
  $("r-hist").innerHTML = h.length
    ? `<ul>${h
        .map((x) => `<li>${esc(x.at.slice(0, 16).replace("T", " "))} — ${esc(x.note)}</li>`)
        .join("")}</ul>`
    : "<p>아직 고친 적이 없습니다.</p>";
}

/* --------------------------------------------------------------- 저장하기 */

$("r-save").addEventListener("click", async () => {
  if (!작업) return;
  const btn = $("r-save");
  btn.disabled = true;
  btn.textContent = "저장 중…";
  try {
    const data = await api(
      `/api/projects/${작업.project_id}/style`,
      Object.assign(postJSON({ style: 작업.style }), { method: "PUT" })
    );
    await 작업열기(data);
    toast("꾸밈새를 저장했습니다");
  } catch (e) {
    toast(e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "이대로 저장";
  }
});

/* ------------------------------------------------------------ 말로 고치기 */

$("r-go").addEventListener("click", async () => {
  if (!작업) return;
  const 말 = $("r-say").value.trim();
  if (!말) {
    toast("무엇을 고칠지 적어주세요");
    return;
  }

  const btn = $("r-go");
  btn.disabled = true;
  btn.textContent = "고치는 중입니다…";
  showWaiting("r-out", "요청을 읽고 고치는 중입니다. 30초쯤 걸립니다.");

  try {
    const data = await api(
      `/api/projects/${작업.project_id}/revise`,
      postJSON({ instruction: 말 })
    );
    await 작업열기(data);
    $("r-say").value = "";
    그린고침결과(data.revision);
  } catch (e) {
    showError("r-out", e);
  } finally {
    btn.disabled = false;
    btn.textContent = "이대로 고치기";
  }
});

function 그린고침결과(rev) {
  if (!rev) return;
  const 다시뽑기 = rev.regenerate_scenes || [];

  $("r-out").innerHTML = `
    <div class="box">
      <h3>이렇게 알아들었습니다</h3>
      <p>${esc(rev.understood)}</p>
      <h4>바꾼 것</h4>
      ${list(rev.done)}
      ${
        rev.note
          ? `<h4>알아두실 것</h4><p style="white-space:pre-wrap">${esc(rev.note)}</p>`
          : ""
      }
      ${
        다시뽑기.length
          ? `<div class="warn-box">
               ${다시뽑기.join(", ")}번 장면은 그림 지시가 바뀌었습니다.<br>
               이 ${다시뽑기.length}컷은 영상 생성 도구에서 다시 뽑아야 반영됩니다.<br>
               나머지 장면은 그대로 두면 됩니다.
             </div>`
          : `<div class="box" style="margin:14px 0 0;border-color:var(--ok)">
               글자와 꾸밈새만 바뀌었습니다. 영상을 다시 뽑을 필요는 없습니다.
             </div>`
      }
    </div>`;
  toast("고쳤습니다");
}

/* ============================================================ 말로 하기

   터미널에서 하던 일을 입력칸 하나로 받는다.
   형님은 명령어를 외울 필요가 없다. 평소 말하듯 적으면 된다.
   ============================================================ */

function 말걸기칸(글) {
  const turn = document.createElement("div");
  turn.className = "turn";
  turn.innerHTML = `<div class="me">${esc(글)}</div>
    <div class="it working">생각하는 중입니다…</div>`;
  $("t-log").prepend(turn);
  return turn.querySelector(".it");
}

function 답(칸, html, bad) {
  칸.className = "it" + (bad ? " bad" : "");
  칸.innerHTML = html;
}

document.querySelectorAll(".chip").forEach((chip) =>
  chip.addEventListener("click", () => {
    $("t-say").value = chip.dataset.say;
    보내기();
  })
);

$("t-go").addEventListener("click", 보내기);

$("t-say").addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") 보내기();
});

async function 보내기() {
  const 글 = $("t-say").value.trim();
  if (!글) {
    toast("무엇을 할지 적어주세요");
    return;
  }

  const btn = $("t-go");
  const 칸 = 말걸기칸(글);
  $("t-say").value = "";
  btn.disabled = true;
  btn.textContent = "하는 중입니다…";

  try {
    const res = await api(
      "/api/say",
      postJSON({
        text: 글,
        state: { pending: 상태.pending, project_id: 상태.project_id },
        transcript: $("a-transcript").value.trim(),
        folder: $("t-folder").value.trim(),
      })
    );
    await 답그리기(칸, res);
  } catch (e) {
    답(칸, esc(e.message), true);
  } finally {
    btn.disabled = false;
    btn.textContent = "보내기";
  }
}

async function 답그리기(칸, res) {
  const 머리 = res.reply ? `<div>${esc(res.reply)}</div>` : "";

  if (res.kind === "analysis") {
    상태.pending = res.analysis;
    lastAnalysis = res.analysis;
    renderAnalysis(res.analysis);
    const d = res.analysis.dna;
    답(
      칸,
      `${머리}
       <div class="mini"><div class="item">
         <b>${esc(d.title)}</b>
         <span class="sub">${esc(d.one_line)}</span>
       </div></div>
       <div class="row">
         <button class="small" data-do="save">이 결 저장하기</button>
         <button class="small" data-do="detail">자세히 보기</button>
       </div>`
    );
    칸.querySelector('[data-do="save"]').addEventListener("click", () => {
      $("t-say").value = "이 결 저장해줘";
      보내기();
    });
    칸.querySelector('[data-do="detail"]').addEventListener("click", () => goTab("step1"));
    return;
  }

  if (res.kind === "skill_saved") {
    상태.pending = null;
    await loadSkills();
    await checkHealth();
    답(칸, `${머리}<div class="mini"><div class="item">
      <b>${esc(res.skill.name)}</b>
      <span class="sub">${esc(res.skill.slug)}</span></div></div>`);
    return;
  }

  if (res.kind === "skills") {
    답(
      칸,
      `${머리}<div class="mini">${
        (res.skills || [])
          .map(
            (s) => `<div class="item"><b>${esc(s.name)}</b>
              <span class="sub">${esc(s.one_line)}</span></div>`
          )
          .join("") || '<div class="item">아직 없습니다.</div>'
      }</div>`
    );
    return;
  }

  if (res.kind === "script" || res.kind === "scripts") {
    const 편들 = res.items || [];
    if (편들.length) {
      // 여러 편이면 맨 앞 것을 펼쳐둔다
      renderScript(편들[0]);
      await 작업열기(편들[0]);
      상태.project_id = 편들[0].project_id;
    }
    const 막힌것 = (res.failed || [])
      .map((f) => `<div class="item">${esc(f.topic)} — ${esc(f.error)}</div>`)
      .join("");
    답(
      칸,
      `${머리}
       <div class="mini">${편들
         .map(
           (p, i) => `<div class="item">
             <b>${esc(p.script.topic)}</b>
             <span class="sub">${esc((p.script.title_candidates || [])[0] || "")} ·
             ${(p.script.scenes || []).length}컷 ·
             약 ${Math.round((p.script.total_seconds || 0) / 60)}분</span>
             <div class="row"><button class="small" data-open="${i}">펼쳐보기</button></div>
           </div>`
         )
         .join("")}${막힌것}</div>`
    );
    칸.querySelectorAll("[data-open]").forEach((b) =>
      b.addEventListener("click", async () => {
        const p = 편들[Number(b.dataset.open)];
        renderScript(p);
        await 작업열기(p);
        상태.project_id = p.project_id;
        goTab("step3");
      })
    );
    return;
  }

  if (res.kind === "readiness") {
    const 속 = document.createElement("div");
    준비그리기(속, res.readiness);
    답(칸, `<div>${esc(res.reply)}</div>`);
    칸.appendChild(속);
    const 가기 = document.createElement("div");
    가기.className = "row";
    가기.innerHTML = '<button class="small">연결하러 가기</button>';
    가기.querySelector("button").addEventListener("click", () => goTab("wire"));
    칸.appendChild(가기);
    return;
  }

  if (res.kind === "answer") {
    답변그리기(칸, res);
    return;
  }

  if (res.kind === "deep") {
    await loadSkills();
    답(칸, `${머리}<pre class="tl" style="margin-top:12px">${esc(res.summary)}</pre>`);
    return;
  }

  if (res.kind === "pick_voice") {
    답(칸, `${머리}<div class="chips">${(res.voices || [])
      .slice(0, 12)
      .map((v) => `<button class="chip" data-voice="${esc(v.id)}">${esc(v.name)}</button>`)
      .join("")}</div>`);
    칸.querySelectorAll("[data-voice]").forEach((b) =>
      b.addEventListener("click", async () => {
        const 다시 = 말걸기칸(`${b.textContent} 목소리로 읽어줘`);
        try {
          const r = await api("/api/say", postJSON({ text: "읽어줘", voice_id: b.dataset.voice,
            state: { pending: 상태.pending, project_id: 상태.project_id } }));
          await 답그리기(다시, r);
        } catch (e) { 답(다시, esc(e.message), true); }
      })
    );
    return;
  }

  if (res.kind === "voice" || res.kind === "assembled") {
    영상보기 = res.view;
    답(칸, `${머리}${res.video ? `<div class="video-box"><video controls src="${esc(res.video)}"></video></div>` : ""}
      <div class="row"><button class="small" data-do="build">영상 만들기 탭 열기</button></div>`);
    칸.querySelector('[data-do="build"]').addEventListener("click", () => goTab("build"));
    return;
  }

  if (res.kind === "revised") {
    상태.project_id = res.project.project_id;
    renderScript(res.project);
    await 작업열기(res.project);
    const rev = res.project.revision || {};
    const 다시 = rev.regenerate_scenes || [];
    답(
      칸,
      `${머리}
       ${list(rev.done)}
       ${
         다시.length
           ? `<div class="warn-box">${다시.join(", ")}번 장면은 그림을 다시 뽑아야 합니다.
              나머지는 그대로 두시면 됩니다.</div>`
           : `<div class="sub">영상을 다시 뽑을 필요는 없습니다.</div>`
       }
       <div class="row"><button class="small" data-do="see">결과 보기</button></div>`
    );
    칸.querySelector('[data-do="see"]').addEventListener("click", () => goTab("step4"));
    return;
  }

  답(칸, 머리 || "<div>알겠습니다.</div>");
}

$("t-say").focus();

/* ============================================================ 설정

   만든 것이 어디에 쌓이는지 보여주고, 옮길 수 있게 한다.
   경로를 손으로 치는 건 어렵다. 폴더 창을 띄울 수 있으면 띄운다.
   ============================================================ */

let 폴더창가능 = false;

async function 설정읽기() {
  try {
    const s = await api("/api/settings");
    폴더창가능 = !!s.can_browse;
    $("c-dir").value = s.data_dir;
    $("c-browse").style.display = 폴더창가능 ? "" : "none";
    $("c-hint").textContent = 폴더창가능
      ? "폴더 고르기를 누르면 창이 뜹니다."
      : "이 컴퓨터에서는 폴더 창이 안 뜹니다. 경로를 직접 적어주세요.";
    $("c-counts").innerHTML = `
      <div class="item"><b>결 ${esc(s.skill_count)}개</b>
        <span class="sub">${esc(s.skills_dir)}</span></div>
      <div class="item"><b>만든 영상 ${esc(s.script_count)}편</b>
        <span class="sub">${esc(s.projects_dir)}</span></div>
      <div class="item"><b>클로드가 읽는 스킬</b>
        <span class="sub">${esc(s.claude_skills_dir)}</span></div>`;
  } catch (e) {
    $("c-hint").textContent = e.message;
  }
}

$("c-browse").addEventListener("click", async () => {
  const btn = $("c-browse");
  btn.disabled = true;
  try {
    const { picked } = await api("/api/settings/browse", { method: "POST" });
    if (picked) {
      $("c-dir").value = picked;
      toast("폴더를 골랐습니다. 이제 바꾸기를 눌러주세요");
    }
  } catch (e) {
    toast(e.message);
  } finally {
    btn.disabled = false;
  }
});

$("c-save").addEventListener("click", async () => {
  const btn = $("c-save");
  btn.disabled = true;
  btn.textContent = "바꾸는 중…";
  try {
    await api("/api/settings", Object.assign(
      postJSON({ data_dir: $("c-dir").value.trim() }), { method: "PUT" }
    ));
    await 설정읽기();
    await loadSkills();
    await checkHealth();
    toast("저장 폴더를 바꿨습니다");
  } catch (e) {
    toast(e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "이 폴더로 바꾸기";
  }
});

/* ============================================================ 파일 넣기

   받아둔 영상, 자막 파일, 직접 쓴 대본을 그대로 받는다.
   끌어다 놓아도 되고 눌러서 골라도 된다.
   ============================================================ */

const drop = $("t-drop");
const fileInput = $("t-file");

(async function 받는종류알리기() {
  try {
    const k = await api("/api/upload/kinds");
    fileInput.accept = k.extensions.join(",");
    $("t-kinds").textContent =
      `대본 .txt · 자막 .srt .vtt` +
      (k.ffmpeg ? " · 자막이 박힌 영상" : " (영상은 ffmpeg가 있어야 합니다)");
  } catch (e) {
    /* 목록을 못 받아도 파일 고르기는 된다 */
  }
})();

drop.addEventListener("click", () => fileInput.click());

["dragenter", "dragover"].forEach((ev) =>
  drop.addEventListener(ev, (e) => {
    e.preventDefault();
    drop.classList.add("over");
  })
);

["dragleave", "drop"].forEach((ev) =>
  drop.addEventListener(ev, (e) => {
    e.preventDefault();
    drop.classList.remove("over");
  })
);

drop.addEventListener("drop", (e) => {
  const f = e.dataTransfer.files[0];
  if (f) 파일올리기(f);
});

fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) 파일올리기(fileInput.files[0]);
});

async function 파일올리기(file) {
  drop.classList.add("has");
  $("t-dropmsg").textContent = `${file.name} 읽는 중…`;

  const 칸 = 말걸기칸(`${file.name} 에서 결을 뽑아줘`);
  const form = new FormData();
  form.append("file", file);
  form.append("notes", $("a-notes").value.trim());

  try {
    const res = await fetch("/api/upload", { method: "POST", body: form });
    let body = null;
    try {
      body = await res.json();
    } catch (e) {
      body = null;
    }
    if (!res.ok) throw new Error((body && body.detail) || `서버 오류 (${res.status})`);

    $("t-dropmsg").textContent = `${file.name} 읽었습니다`;
    await 답그리기(칸, {
      kind: "analysis",
      reply: `'${body.dna.title}' 결을 뽑았습니다. 저장할까요?`,
      analysis: body,
    });
  } catch (e) {
    drop.classList.remove("has");
    $("t-dropmsg").textContent = "여기를 누르거나 파일을 끌어다 놓으세요";
    답(칸, esc(e.message), true);
  } finally {
    fileInput.value = "";
  }
}

/* ============================================================ 연결

   클로드가 1순위다. 나머지는 있으면 좋고 없어도 된다.
   키는 끝 네 자리만 화면에 보인다. 통째로 받아오지 않는다.
   ============================================================ */

async function 연결읽기() {
  let c;
  try {
    c = await api("/api/connections");
  } catch (e) {
    $("w-keys").innerHTML = `<div class="msg err">${esc(e.message)}</div>`;
    return;
  }

  $("w-where").textContent = `${c.env_file} · MCP 설정은 ${c.mcp_file}`;

  $("w-keys").innerHTML = c.keys
    .map(
      (k) => `
    <div class="wire${k.required ? " must" : ""}">
      <div class="head">
        <h3>${esc(k.name)}</h3>
        ${k.required ? '<span class="badge must">꼭 필요</span>' : ""}
        <span class="badge ${k.connected ? "on" : "off"}">${
          k.connected ? "연결됨" : "아직 없음"
        }</span>
      </div>
      <p class="note">${esc(k.note)} 키는 ${esc(k.where)} 에서 만듭니다.</p>
      ${
        k.connected
          ? `<p class="now">지금 넣어둔 키 : ${esc(k.masked)}${
              k.from_env ? " (컴퓨터 환경변수에서 옴)" : ""
            }</p>`
          : ""
      }
      <label class="field">
        <span>${k.connected ? "바꾸려면 새 키를 넣으세요" : "키를 넣으세요"}</span>
        <input type="password" data-key="${esc(k.key)}" autocomplete="off"
               placeholder="${k.connected ? "비워두면 그대로 둡니다" : "여기에 붙여넣기"}">
      </label>
      <div class="row">
        <button class="small" data-save="${esc(k.key)}">저장</button>
        ${
          k.key === "ANTHROPIC_API_KEY"
            ? '<button class="small" id="w-test">연결 확인</button>'
            : ""
        }
        ${
          k.connected && !k.from_env
            ? `<button class="small danger" data-clear="${esc(k.key)}">지우기</button>`
            : ""
        }
      </div>
    </div>`
    )
    .join("");

  $("w-keys")
    .querySelectorAll("[data-save]")
    .forEach((b) =>
      b.addEventListener("click", async () => {
        const 칸 = $("w-keys").querySelector(`[data-key="${b.dataset.save}"]`);
        const 값 = 칸.value.trim();
        if (!값) {
          toast("넣을 키를 적어주세요");
          return;
        }
        await 키저장({ [b.dataset.save]: 값 }, "저장했습니다");
        칸.value = "";
      })
    );

  $("w-keys")
    .querySelectorAll("[data-clear]")
    .forEach((b) =>
      b.addEventListener("click", async () => {
        if (!confirm("이 키를 지웁니다. 지울까요?")) return;
        await 키저장({ [b.dataset.clear]: "" }, "지웠습니다");
      })
    );

  const 확인 = $("w-test");
  if (확인) 확인.addEventListener("click", 클로드확인);

  $("w-mcp").innerHTML = c.mcp.length
    ? c.mcp
        .map(
          (m) => `<div class="item">
            <b>${esc(m.name)}</b>
            <span class="sub">${esc(m.kind)} · ${esc(m.target)}</span>
            <div class="row"><button class="small danger" data-mcp="${esc(
              m.name
            )}">떼기</button></div>
          </div>`
        )
        .join("")
    : '<div class="item">아직 붙인 것이 없습니다.</div>';

  $("w-mcp")
    .querySelectorAll("[data-mcp]")
    .forEach((b) =>
      b.addEventListener("click", async () => {
        if (!confirm(`'${b.dataset.mcp}' 를 뗍니다. 뗄까요?`)) return;
        try {
          await api(`/api/mcp/${encodeURIComponent(b.dataset.mcp)}`, { method: "DELETE" });
          await 연결읽기();
          toast("뗐습니다");
        } catch (e) {
          toast(e.message);
        }
      })
    );
}

async function 키저장(changes, 말) {
  try {
    await api("/api/connections", Object.assign(postJSON({ changes }), { method: "PUT" }));
    await 연결읽기();
    await checkHealth();
    toast(말);
  } catch (e) {
    toast(e.message);
  }
}

async function 클로드확인() {
  const btn = $("w-test");
  btn.disabled = true;
  btn.textContent = "확인 중…";
  try {
    const r = await api("/api/connections/test", { method: "POST" });
    toast(r.message);
  } catch (e) {
    toast(e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "연결 확인";
  }
}

$("w-mcp-add").addEventListener("click", async () => {
  const name = $("w-mcp-name").value.trim();
  const target = $("w-mcp-target").value.trim();
  if (!name || !target) {
    toast("이름과 주소를 다 적어주세요");
    return;
  }
  try {
    await api("/api/mcp", postJSON({ name, target }));
    $("w-mcp-name").value = "";
    $("w-mcp-target").value = "";
    await 연결읽기();
    toast("붙였습니다");
  } catch (e) {
    toast(e.message);
  }
});

/* 앱 쓰는 법을 물어봤을 때. 클로드가 직접 답한다. */
function 답변그리기(칸, res) {
  const 해보기 = res.try_this || [];
  답(
    칸,
    `<div>${esc(res.reply)}</div>` +
      (해보기.length
        ? `<h4 style="margin:14px 0 8px;font-size:16px">이렇게 해보세요</h4>
           <div class="chips">${해보기
             .map((s) => `<button class="chip" data-try="${esc(s)}">${esc(s)}</button>`)
             .join("")}</div>`
        : "")
  );
  칸.querySelectorAll("[data-try]").forEach((b) =>
    b.addEventListener("click", () => {
      $("t-say").value = b.dataset.try;
      $("t-say").scrollIntoView({ behavior: "smooth", block: "center" });
      $("t-say").focus();
    })
  );
}

/* ---------------------------------------------------- 영상 만들 준비 점검 */

function 준비그리기(칸, r) {
  칸.innerHTML = r.steps
    .map(
      (s) => `
    <div class="step ${s.ok ? "ok" : "no"}">
      <div class="mark">${s.ok ? "✓" : "!"}</div>
      <div class="body">
        <b>${esc(s.step)}</b>
        <span class="sub">${esc(s.how)}</span>
        ${
          s.ok
            ? s.have.length
              ? `<span class="sub">지금 쓰는 것 — ${esc(s.have.join(", "))}</span>`
              : ""
            : `<span class="need">${esc(s.missing.join(" 또는 "))} 가 있어야 합니다</span>
               ${s.detour ? `<span class="sub">없어도 — ${esc(s.detour)}</span>` : ""}`
        }
      </div>
    </div>`
    )
    .join("");
}

async function 준비읽기() {
  try {
    const r = await api("/api/readiness");
    $("w-ready-line").textContent = r.summary;
    준비그리기($("w-ready"), r);
  } catch (e) {
    $("w-ready-line").textContent = e.message;
  }
}

/* 스킬 하나를 어떻게 쓰는지. 만들어진 이름으로 그대로 적어준다. */
function 스킬쓰는법(s) {
  return `
    <details class="fold" style="margin-top:10px">
      <summary>이 결 쓰는 법</summary>
      <p><b>이 앱에서</b></p>
      <p>맨 위 칸에 이렇게 적으시면 됩니다.</p>
      <pre>${esc(s.name)}로 &lt;주제&gt; 5분짜리 써줘</pre>
      <p><b>클로드 코드나 클로드 데스크톱에서</b></p>
      <p>이 폴더에서 클로드를 켠 다음 이렇게 말하면 됩니다.</p>
      <pre>${esc(s.name)} 결로 &lt;주제&gt; 영상 만들어줘</pre>
      <p class="meta">
        스킬 파일은 <code>.claude/skills/${esc(s.slug)}/</code> 에 깔려 있습니다.<br>
        영상 생성 MCP가 붙어 있으면 장면 뽑는 것까지 이어서 합니다.
      </p>
    </details>`;
}

/* ============================================================ 영상 만들기

   레이어 여섯을 한 줄씩 보여주고, 누가 채울지 꽂게 한다.
   재료가 모이면 묶는다. 실제 일은 서버의 ffmpeg 가 한다.
   ============================================================ */

let 영상보기 = null;

async function 영상탭열기() {
  if (!상태.project_id) {
    $("b-empty").hidden = false;
    $("b-body").hidden = true;
    return;
  }
  try {
    영상보기 = await api(`/api/projects/${encodeURIComponent(상태.project_id)}/timeline`);
    영상그리기();
  } catch (e) {
    $("b-empty").hidden = false;
    $("b-body").hidden = true;
    $("b-empty").textContent = e.message;
  }
}

function 영상그리기() {
  const v = 영상보기;
  $("b-empty").hidden = true;
  $("b-body").hidden = false;
  $("b-title").textContent = `${v.topic} — ${v.skill_name} 결`;
  $("b-summary").textContent = v.summary;

  const o = v.reference_overall;
  $("b-ref").innerHTML = v.has_reference
    ? `<div class="mini"><div class="item">
         <b>레퍼런스 모양을 따릅니다</b>
         <span class="sub">${esc(o.shot_count)}컷 · 한 장면 ${esc(o.avg_shot_seconds)}초 · 침묵 ${esc(
           o.silence_count
         )}번 · 캐릭터 ${esc(o.character_pattern || "없음")}</span>
         ${o.visual_dna ? `<span class="sub" style="font-family:var(--mono)">${esc(o.visual_dna)}</span>` : ""}
       </div></div>`
    : `<div class="msg wait">이 결은 아직 자막으로만 뜯었습니다.
       <b>내 결</b> 탭에서 <b>화면까지 뜯기</b>를 누르면 장면 수, 캐릭터 자리, 침묵까지 따라갑니다.</div>`;

  $("b-layers").innerHTML = v.layers
    .map(
      (l) => `
    <div class="layer" data-layer="${esc(l.layer)}">
      <div><span class="lname">${esc(l.name)}</span><span class="lwhat">${esc(l.what)}</span></div>
      <div>
        <select data-prov="${esc(l.layer)}">
          ${l.options
            .map(
              (p) => `<option value="${esc(p.id)}" ${p.id === l.provider ? "selected" : ""}>${esc(
                p.name
              )}${p.ready ? "" : " (연결 안 됨)"}</option>`
            )
            .join("")}
        </select>
      </div>
      <div class="lstate">
        <span class="badge ${l.ready ? "on" : "off"}">${l.ready ? "준비됨" : "연결 필요"}</span>
        <span class="lcount">${esc(l.count)}칸 · 재료 ${esc(v.assets[l.layer] ?? 0)}개</span>
      </div>
      <div class="meta">${esc(l.note)}</div>
      ${v.folders[l.layer] ? `<div class="lpath">${esc(v.folders[l.layer])}</div>` : ""}
    </div>`
    )
    .join("");

  $("b-layers")
    .querySelectorAll("[data-prov]")
    .forEach((sel) =>
      sel.addEventListener("change", async () => {
        try {
          영상보기 = await api(
            `/api/projects/${encodeURIComponent(상태.project_id)}/timeline`,
            Object.assign(postJSON({ providers: { [sel.dataset.prov]: sel.value } }), { method: "PUT" })
          );
          영상그리기();
          toast("바꿨습니다");
        } catch (e) {
          toast(e.message);
        }
      })
    );

  $("b-assemble").disabled = !v.ffmpeg;
  $("b-assemble").textContent = v.ffmpeg ? "조립해서 mp4로 뽑기" : "조립하려면 ffmpeg가 필요합니다";

  if (v.video) {
    $("b-out").innerHTML = `<div class="video-box">
      <video controls src="${esc(v.video)}"></video>
      <div class="row"><a class="small" href="${esc(v.video)}" download>mp4 내려받기</a></div>
    </div>`;
  }
}

$("b-voice").addEventListener("click", async () => {
  const btn = $("b-voice");
  btn.disabled = true;
  try {
    const { voices } = await api("/api/voices");
    $("b-voice-pick").innerHTML = voices
      .map((v) => `<option value="${esc(v.id)}">${esc(v.name)}${v.gender ? ` · ${esc(v.gender)}` : ""}${
        v.age ? ` · ${esc(v.age)}` : ""}</option>`)
      .join("");
    $("b-voices").hidden = false;
  } catch (e) {
    toast(e.message);
  } finally {
    btn.disabled = false;
  }
});

$("b-voice-cancel").addEventListener("click", () => ($("b-voices").hidden = true));

$("b-voice-go").addEventListener("click", async () => {
  const btn = $("b-voice-go");
  btn.disabled = true;
  btn.textContent = "읽는 중입니다…";
  showWaiting("b-out", "장면마다 나레이션을 읽고 있습니다. 컷 수만큼 걸립니다.");
  try {
    const r = await api(
      `/api/projects/${encodeURIComponent(상태.project_id)}/voice`,
      postJSON({ voice_id: $("b-voice-pick").value })
    );
    영상보기 = r.view;
    영상그리기();
    $("b-voices").hidden = true;
    $("b-out").innerHTML = `<div class="box">
      <h3>${r.made.length}컷 읽었습니다</h3>
      ${r.failed.length ? `<div class="warn-box">${r.failed.map((f) => `${esc(f.no)}번 — ${esc(f.error)}`).join("<br>")}</div>` : ""}
    </div>`;
    toast(`${r.made.length}컷 읽었습니다`);
  } catch (e) {
    showError("b-out", e);
  } finally {
    btn.disabled = false;
    btn.textContent = "이 목소리로 다 읽기";
  }
});

$("b-assemble").addEventListener("click", async () => {
  const btn = $("b-assemble");
  btn.disabled = true;
  btn.textContent = "묶는 중입니다…";
  showWaiting("b-out", "장면을 만들고, 잇고, 소리와 자막을 얹고 있습니다. 몇 분 걸립니다.");
  try {
    const r = await api(`/api/projects/${encodeURIComponent(상태.project_id)}/assemble`, postJSON({}));
    영상보기 = r.view;
    영상그리기();
    toast("mp4 가 나왔습니다");
  } catch (e) {
    showError("b-out", e);
  } finally {
    btn.disabled = false;
    btn.textContent = "조립해서 mp4로 뽑기";
  }
});

/* 내 결 카드의 '화면까지 뜯기' */
async function 화면까지뜯기(slug, btn) {
  btn.disabled = true;
  btn.textContent = "뜯는 중… (몇 분)";
  try {
    const r = await api(`/api/skills/${encodeURIComponent(slug)}/deep`, postJSON({}));
    toast(r.reply);
    await loadSkills();
    if (상태.project_id) 영상탭열기();
  } catch (e) {
    toast(e.message);
    btn.disabled = false;
    btn.textContent = "화면까지 뜯기";
  }
}
