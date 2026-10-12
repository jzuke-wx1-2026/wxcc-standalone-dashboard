(function () {
  window.LAB_PROGRESS = window.LAB_PROGRESS || { modules: [] };
  window.LAB_STANDALONE = window.LAB_STANDALONE === true;
  window.LAB_SETUP_OAUTH = window.LAB_SETUP_OAUTH || {};

  const previousStepState = {};
  let lastProgressFingerprint = "";

  // API response caches — fetch once unless manually refreshed or newly unlocked
  let usersCache = null;
  const orgCache = {
    entry_points: null,
    queues: null,
    global_variables: null,
    aux_codes: null,
    teams: null,
  };
  const webexCache = {
    people: null,
    locations: null,
    ep_pstn: null,
  };
  const reportCache = {
    csr: null,
    car: null,
    asr: null,
    aar: null,
  };
  let rtAgentsCache = null;
  const loadedModules = new Set();
  const moduleLoadInFlight = {};

  function isStandaloneDashboard() {
    return window.LAB_STANDALONE === true;
  }

  function fullDashboardRoot() {
    return document.getElementById("content-dashboard") || document.getElementById("content-module5");
  }

  function getActiveModuleId() {
    if (isStandaloneDashboard()) return "module5";
    const tab = document.querySelector(".module-tab.active");
    return (tab && tab.dataset.module) || "module0";
  }

  function isSetupComplete() {
    const status = window.LAB_CONFIG_STATUS || {};
    if (typeof status.setup_complete === "boolean") return status.setup_complete;
    const progress = getProgress();
    if (typeof progress.setup_complete === "boolean") return progress.setup_complete;
    return false;
  }

  function isModuleTabLocked(moduleId) {
    return moduleId !== "module0" && !isSetupComplete();
  }

  async function loadModule(moduleId, force) {
    if (moduleId === "module0") {
      renderSetupStatus();
      return Promise.resolve();
    }
    switch (moduleId) {
      case "module1":
        return loadUsers(force);
      case "module2":
        return loadOrgData(force);
      case "module3":
        return loadReports(force);
      case "module4":
        return loadWebexApis(force);
      case "module5":
        return loadFullDashboard(force);
      default:
        return Promise.resolve();
    }
  }

  function showModuleLoading(moduleId) {
    const ph = document.getElementById("placeholder-" + moduleId);
    if (ph) {
      ph.textContent = "Loading data from API…";
      ph.classList.remove("hidden");
    }
  }

  function hideModuleLoading(moduleId) {
    const ph = document.getElementById("placeholder-" + moduleId);
    if (ph && ph.textContent === "Loading data from API…") {
      ph.textContent = "Complete the steps above — live API data appears here as you progress.";
    }
  }

  async function ensureModuleLoaded(moduleId, force) {
    if (moduleId !== "module5" && !force && loadedModules.has(moduleId)) return;
    if (moduleLoadInFlight[moduleId]) return moduleLoadInFlight[moduleId];

    const run = (async () => {
      showModuleLoading(moduleId);
      try {
        await loadModule(moduleId, force);
        loadedModules.add(moduleId);
      } finally {
        hideModuleLoading(moduleId);
      }
    })();

    moduleLoadInFlight[moduleId] = run;
    try {
      await run;
    } finally {
      delete moduleLoadInFlight[moduleId];
    }
  }

  const REPORT_DEFS = [
    { step: "3.1", id: "csr", label: "CSR", desc: "Contact volume by channel, termination, and direction", url: "/api/reports/csr", key: "records", window: "last 30 days", summary: "channel" },
    { step: "3.3", id: "asr", label: "ASR", desc: "Agent sessions by team", url: "/api/reports/asr", key: "records", window: "last 30 days", summary: "team" },
  ];
  const RT_STEP = "3.5";

  function getProgress() {
    return window.LAB_PROGRESS || { modules: [] };
  }

  function progressFingerprint(progress) {
    return progress.modules
      .map((m) => m.module_id + ":" + m.steps.map((s) => (s.complete ? "1" : "0")).join(""))
      .join("|");
  }

  function isStepComplete(moduleId, stepId) {
    if (!isSetupComplete()) return false;
    return true;
  }

  function isModuleStarted(moduleId) {
    const mod = getProgress().modules.find((m) => m.module_id === moduleId);
    return mod && mod.completed_steps > 0;
  }

  function stepKey(moduleId, stepId) {
    return moduleId + ":" + stepId;
  }

  function detectNewlyCompletedSteps(newProgress) {
    const newlyCompleted = [];
    newProgress.modules.forEach((mod) => {
      mod.steps.forEach((step) => {
        const key = stepKey(mod.module_id, step.id);
        const wasComplete = previousStepState[key] || false;
        if (step.complete && !wasComplete) {
          newlyCompleted.push({ moduleId: mod.module_id, stepId: step.id, label: step.label });
        }
        previousStepState[key] = step.complete;
      });
    });
    return newlyCompleted;
  }

  function sortAlpha(rows, keys) {
    if (!rows || !rows.length) return rows || [];
    return [...rows].sort((a, b) => {
      for (const key of keys) {
        const av = String(a[key] ?? "").toLowerCase();
        const bv = String(b[key] ?? "").toLowerCase();
        const cmp = av.localeCompare(bv, undefined, { sensitivity: "base" });
        if (cmp !== 0) return cmp;
      }
      return 0;
    });
  }

  function setContent(el, html, force) {
    if (!el) return false;
    const overlay = el.querySelector(":scope > .refresh-overlay");
    if (overlay) overlay.remove();
    if (!force && el.innerHTML === html) {
      if (el.classList.contains("is-refreshing")) ensureRefreshOverlay(el);
      return false;
    }
    el.innerHTML = html;
    if (el.classList.contains("is-refreshing")) ensureRefreshOverlay(el);
    return true;
  }

  function isModuleActive(moduleId) {
    if (isStandaloneDashboard()) return moduleId === "module5";
    const tab = document.querySelector(`.module-tab[data-module="${moduleId}"]`);
    return Boolean(tab && tab.classList.contains("active"));
  }

  const FULL_DASH_TAB_BY_MODULE = {
    module1: "users",
    module2: "org",
    module3: "reports",
    module4: "webex",
  };

  function fullDashboardUrl(moduleId) {
    const params = new URLSearchParams();
    const tab = FULL_DASH_TAB_BY_MODULE[moduleId];
    if (tab) params.set("tab", tab);
    if (moduleId === "module2" && window._org2Tab) {
      params.set("entity", window._org2Tab);
    } else if (moduleId === "module4" && window._webex4Tab) {
      params.set("entity", window._webex4Tab);
    } else if (window._dash5OrgTab && tab === "org") {
      params.set("entity", window._dash5OrgTab);
    } else if (window._dash5WebexTab && tab === "webex") {
      params.set("entity", window._dash5WebexTab);
    }
    const query = params.toString();
    return "/dashboard" + (query ? "?" + query : "");
  }

  function applyDashboardUrlState() {
    if (!isStandaloneDashboard()) return;
    const params = new URLSearchParams(window.location.search);
    const tab = params.get("tab");
    const entity = params.get("entity");
    if (tab) window._dash5Tab = tab;
    if (entity) {
      if (tab === "webex") window._dash5WebexTab = entity;
      else window._dash5OrgTab = entity;
    }
  }

  function syncDashboardUrl() {
    if (!isStandaloneDashboard()) return;
    const url = new URL(window.location.href);
    if (window._dash5Tab) url.searchParams.set("tab", window._dash5Tab);
    else url.searchParams.delete("tab");
    if (window._dash5Tab === "org" && window._dash5OrgTab) {
      url.searchParams.set("entity", window._dash5OrgTab);
    } else if (window._dash5Tab === "webex" && window._dash5WebexTab) {
      url.searchParams.set("entity", window._dash5WebexTab);
    } else {
      url.searchParams.delete("entity");
    }
    history.replaceState({}, "", url);
  }

  window.openFullDashboardForModule = function (moduleId) {
    window.open(fullDashboardUrl(moduleId), "wxccFullDashboard");
  };

  document.querySelectorAll(".module-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const moduleId = tab.dataset.module;
      if (isModuleTabLocked(moduleId)) {
        window.alert("Complete the Setup module first to connect your bearer token and organization ID.");
        return;
      }
      document.querySelectorAll(".module-tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".module-panel").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById("panel-" + moduleId).classList.add("active");
      ensureModuleLoaded(moduleId, false);
      renderModuleWorkspace(moduleId);
      syncRtPolling(moduleId === "module3");
    });
  });

  let labWorkspace = { modules: [] };
  let activeSteps = {};

  function getNextLabModule(moduleId) {
    const mods = getProgress().modules.filter((mod) => mod.module_id !== "module5");
    const idx = mods.findIndex((mod) => mod.module_id === moduleId);
    if (idx < 0 || idx >= mods.length - 1) return null;
    return mods[idx + 1];
  }

  function goToLabModule(moduleId) {
    const tab = document.querySelector(`.module-tab[data-module="${moduleId}"]`);
    if (tab) tab.click();
  }

  function isModuleComplete(moduleId) {
    return isSetupComplete();
  }

  function isPlaceholderValue(value) {
    const v = String(value ?? "").trim();
    return !v || v === "___FILL_IN___";
  }

  function workspaceModule(moduleId) {
    return labWorkspace.modules.find((m) => m.module_id === moduleId);
  }

  function computeStepAccess(moduleId, stepId) {
    if (moduleId !== "module0" && !isSetupComplete()) return "locked";
    const mod = getProgress().modules.find((m) => m.module_id === moduleId);
    if (!mod) return "locked";
    const idx = mod.steps.findIndex((s) => s.id === stepId);
    if (idx < 0) return "locked";
    if (mod.steps[idx].complete) return "complete";
    const firstIncomplete = mod.steps.findIndex((s) => !s.complete);
    return idx === firstIncomplete ? "active" : "locked";
  }

  function isStepAccessible(moduleId, stepId) {
    const access = computeStepAccess(moduleId, stepId);
    return access === "complete" || access === "active";
  }

  function getDefaultActiveStep(moduleId) {
    const mod = getProgress().modules.find((m) => m.module_id === moduleId);
    if (!mod || !mod.steps.length) return null;
    const next = mod.steps.find((s) => !s.complete);
    return next ? next.id : mod.steps[mod.steps.length - 1].id;
  }

  function resolveActiveStep(moduleId) {
    const chosen = activeSteps[moduleId];
    if (chosen && isStepAccessible(moduleId, chosen)) return chosen;
    const fallback = getDefaultActiveStep(moduleId);
    activeSteps[moduleId] = fallback;
    return fallback;
  }

  function selectStep(moduleId, stepId) {
    if (!isStepAccessible(moduleId, stepId)) return false;
    activeSteps[moduleId] = stepId;
    renderModuleWorkspace(moduleId);
    return true;
  }

  function getNextStepId(moduleId, stepId) {
    const mod = getProgress().modules.find((m) => m.module_id === moduleId);
    if (!mod) return null;
    const idx = mod.steps.findIndex((s) => s.id === stepId);
    if (idx < 0 || idx >= mod.steps.length - 1) return null;
    return mod.steps[idx + 1].id;
  }

  function syncProgressFromServer(progress) {
    window.LAB_PROGRESS = progress;
    lastProgressFingerprint = progressFingerprint(progress);
    progress.modules.forEach((mod) => {
      mod.steps.forEach((step) => {
        previousStepState[stepKey(mod.module_id, step.id)] = step.complete;
      });
      if (activeSteps[mod.module_id] && !isStepAccessible(mod.module_id, activeSteps[mod.module_id])) {
        activeSteps[mod.module_id] = getDefaultActiveStep(mod.module_id);
      }
    });
  }

  function fieldInputHtml(field) {
    const value = isPlaceholderValue(field.value) ? "" : field.value;
    const endpointClass = field.kind === "endpoint" ? " lab-field-endpoint" : "";
    const secretClass = field.kind === "secret" ? " lab-field-secret" : "";
    const plainClass = field.hide_label ? " lab-field-plain" : "";
    const inputType = field.kind === "secret" ? "password" : "text";
    const savedNote = field.saved
      ? `<p class="lab-field-saved-note">Saved — leave blank to keep the current token.</p>`
      : "";
    const labelHtml = field.hide_label
      ? ""
      : `<label for="${escapeAttr(field.var)}">${escapeHtml(field.label)}</label>`;
    const ariaLabel = field.hide_label ? ` aria-label="${escapeAttr(field.label)}"` : "";
    return (
      `<div class="lab-field${endpointClass}${secretClass}${plainClass}" data-field="${escapeAttr(field.var)}">` +
      labelHtml +
      `<input type="${inputType}" id="${escapeAttr(field.var)}" name="${escapeAttr(field.var)}" ` +
      `data-var="${escapeAttr(field.var)}" value="${escapeAttr(value)}" ` +
      `placeholder="${escapeAttr(field.placeholder || "")}" autocomplete="off" spellcheck="false"${ariaLabel}>` +
      savedNote +
      `<p class="lab-field-hint" id="hint-${escapeAttr(field.var)}"></p>` +
      `</div>`
    );
  }

  function isLocalLabHref(href) {
    try {
      const url = new URL(href.startsWith("http") ? href : "https://" + href);
      return url.hostname === "127.0.0.1" || url.hostname === "localhost";
    } catch (_) {
      return false;
    }
  }

  function guideAnchor(href, label) {
    const text = String(label || href || "");
    if (!href || isLocalLabHref(href)) return `<code>${escapeHtml(text)}</code>`;
    return (
      `<a class="lab-api-link" href="${escapeAttr(href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(text)}</a>`
    );
  }

  function wrapDocPhrases(text, step) {
    const docUrl = (step && step.doc_url) || "";
    if (!docUrl || !text) return escapeHtml(text);
    const title = String(step.doc_title || "").trim();
    const phrases = [
      "using the link below",
      "using the link above",
      "the link below",
      "the link above",
      "the API endpoint documentation",
      "API endpoint documentation",
    ];
    const titleIsApiName = /(?:\b(?:list|get|update|retrieve|create)\b|api|dictionary)/i.test(title);
    if (title && titleIsApiName) {
      if (!/API$/i.test(title)) phrases.push(title + " API");
      phrases.push(title);
    }
    phrases.sort((a, b) => b.length - a.length);

    let html = "";
    let rest = text;
    while (rest) {
      let best = null;
      const lower = rest.toLowerCase();
      phrases.forEach((phrase) => {
        const idx = lower.indexOf(phrase.toLowerCase());
        if (idx < 0) return;
        if (!best || idx < best.idx || (idx === best.idx && phrase.length > best.phrase.length)) {
          best = { idx, phrase, matched: rest.substr(idx, phrase.length) };
        }
      });
      if (!best) {
        html += escapeHtml(rest);
        break;
      }
      html += escapeHtml(rest.slice(0, best.idx));
      const isGenericLink = /^(using )?the link (below|above)$/i.test(best.matched);
      html += guideAnchor(docUrl, isGenericLink ? "API endpoint documentation" : best.matched);
      rest = rest.slice(best.idx + best.matched.length);
    }
    return html;
  }

  function formatGuideHtml(line, step) {
    const raw = String(line || "");
    const patterns = [
      { name: "md", re: /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/ },
      { name: "url", re: /https?:\/\/[^\s<>"'()]+/ },
      { name: "host", re: /\bdeveloper\.webex\.com(?:\/[^\s<>"'(),]+)?/i },
    ];
    let html = "";
    let rest = raw;
    while (rest) {
      let next = null;
      patterns.forEach((pattern) => {
        const match = rest.match(pattern.re);
        if (!match || match.index == null) return;
        if (!next || match.index < next.index) {
          next = { name: pattern.name, match, index: match.index };
        }
      });
      if (!next) {
        html += wrapDocPhrases(rest, step);
        break;
      }
      html += wrapDocPhrases(rest.slice(0, next.index), step);
      const matched = next.match[0];
      if (next.name === "md") {
        html += guideAnchor(next.match[2], next.match[1]);
      } else {
        const href = next.name === "host" ? "https://" + matched.replace(/[.,;:]+$/g, "") : matched.replace(/[.,;:]+$/g, "");
        const label = matched.replace(/[.,;:]+$/g, "");
        html += guideAnchor(href, label);
        const trailing = matched.slice(label.length);
        if (trailing) html += escapeHtml(trailing);
      }
      rest = rest.slice(next.index + matched.length);
    }
    return html;
  }

  function buildApiRefHtml(step) {
    if (!step.doc_url && !(step.doc_guide && step.doc_guide.length)) return "";
    let html = `<div class="lab-api-ref">`;
    html += `<div class="lab-api-ref-head">`;
    if (step.doc_title) html += `<span class="lab-api-ref-title">${escapeHtml(step.doc_title)}</span>`;
    if (step.api_method) html += `<span class="lab-api-method">${escapeHtml(step.api_method)}</span>`;
    if (step.api_base) html += `<span class="lab-api-base">${escapeHtml(step.api_base)}</span>`;
    html += `</div>`;
    let guideHtml = "";
    if (step.doc_guide && step.doc_guide.length) {
      guideHtml += `<ul class="lab-api-guide">`;
      step.doc_guide.forEach((line) => {
        guideHtml += `<li>${formatGuideHtml(line, step)}</li>`;
      });
      guideHtml += `</ul>`;
    }
    html += guideHtml;
    const docUrl = step.doc_url || "";
    const guideAlreadyLinksDoc =
      Boolean(docUrl) && Boolean(guideHtml) && guideHtml.includes(`href="${escapeAttr(docUrl)}"`);
    if (docUrl && !guideAlreadyLinksDoc) {
      const linkLabel =
        step.doc_link_label ||
        (step.doc_title && /dictionary/i.test(step.doc_title)
          ? `Open ${step.doc_title} →`
          : "Open API endpoint documentation →");
      html += `<a class="lab-api-link" href="${escapeAttr(docUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(linkLabel)}</a>`;
    }
    html += `</div>`;
    return html;
  }

  function clearFieldErrors(panel) {
    if (!panel) return;
    panel.querySelectorAll(".lab-field").forEach((field) => field.classList.remove("has-error"));
    panel.querySelectorAll(".lab-field-hint").forEach((hint) => {
      hint.textContent = "";
      hint.classList.remove("visible");
    });
  }

  function applyFieldErrors(panel, errors) {
    if (!panel || !errors || !errors.length) return;
    errors.forEach((err) => {
      const field = panel.querySelector(`.lab-field[data-field="${err.var}"]`);
      const input = panel.querySelector(`[data-var="${err.var}"]`);
      if (field) field.classList.add("has-error");
      const hint = document.getElementById("hint-" + err.var) || field?.querySelector(".lab-field-hint");
      if (hint) {
        hint.textContent = err.hint || "Check this value in the API endpoint documentation.";
        hint.classList.add("visible");
      }
      if (input && errors[0] && errors[0].var === err.var) input.focus();
    });
  }

  function currentSetupAuthMethod() {
    const oauth = window.LAB_SETUP_OAUTH || {};
    const status = window.LAB_CONFIG_STATUS || {};
    return oauth.auth_method === "integration" || status.auth_method === "integration"
      ? "integration"
      : "bearer";
  }

  function selectSetupAuthMethod(method) {
    const card = document.querySelector('.lab-step-card[data-module="module0"][data-step="0.1"]');
    if (!card) return;
    card.querySelectorAll(".setup-auth-tab").forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.method === method);
    });
    card.querySelectorAll(".setup-auth-panel").forEach((panel) => {
      panel.classList.toggle("hidden", panel.dataset.method !== method);
    });
  }

  function expectedSetupCallback() {
    const oauth = window.LAB_SETUP_OAUTH || {};
    return oauth.callback_url || window.location.origin + "/setup/callback";
  }

  function requiredSetupScopeIds() {
    const oauth = window.LAB_SETUP_OAUTH || {};
    return (oauth.scopes || []).map((scope) => String(scope.id || "").toLowerCase()).filter(Boolean);
  }

  function parseOAuthAuthorizationUrl(raw) {
    const trimmed = String(raw || "").trim().replace(/^['"]|['"]$/g, "");
    if (!trimmed) {
      return { error: "Paste the OAuth Authorization URL from your Webex integration page." };
    }
    let url;
    try {
      url = new URL(trimmed);
    } catch (_) {
      return { error: "That is not a valid URL. Copy OAuth Authorization URL from the integration page." };
    }
    const host = (url.hostname || "").toLowerCase();
    const path = (url.pathname || "").replace(/\/+$/, "");
    if (url.protocol !== "https:" || host !== "webexapis.com" || path !== "/v1/authorize") {
      return { error: "Use the OAuth Authorization URL from the integration (https://webexapis.com/v1/authorize?...)." };
    }
    const clientId = (url.searchParams.get("client_id") || "").trim();
    const redirectUri = (url.searchParams.get("redirect_uri") || "").trim();
    const scopeRaw = url.searchParams.get("scope") || "";
    const scopes = scopeRaw
      .split(/[+\s]+/)
      .map((part) => part.trim().toLowerCase())
      .filter(Boolean);
    if (!clientId || /^client_id$/i.test(clientId)) {
      return { error: "This URL has no Client ID. Copy it from the integration after you save the app." };
    }
    if (!scopes.length) {
      return { error: "This URL has no scopes. Check the required chips on the integration, save, then copy the URL again." };
    }
    const expected = expectedSetupCallback();
    if (redirectUri && redirectUri !== expected) {
      return {
        error:
          "Redirect URI in this URL must match the lab callback exactly. Update the integration, save, then copy the new OAuth Authorization URL.",
      };
    }
    const missing = requiredSetupScopeIds().filter((scope) => !scopes.includes(scope));
    if (!redirectUri) {
      url.searchParams.set("redirect_uri", expected);
    }
    return { url: url.toString(), clientId, redirectUri: redirectUri || expected, scopes, missing };
  }

  function applyOAuthAuthorizationUrl(showErrors) {
    const panel = document.querySelector('.setup-auth-panel[data-method="integration"]');
    const field = document.getElementById("SETUP_OAUTH_URL");
    if (!field) return null;
    const parsed = parseOAuthAuthorizationUrl(field.value);
    highlightMissingScopes(parsed.missing || []);
    if (parsed.error) {
      if (showErrors) {
        applyFieldErrors(panel, [{ var: "SETUP_OAUTH_URL", hint: parsed.error }]);
      }
      return null;
    }
    if (parsed.missing && parsed.missing.length) {
      if (showErrors) {
        applyFieldErrors(panel, [
          {
            var: "SETUP_OAUTH_URL",
            hint:
              "This URL is missing required scopes: " +
              parsed.missing.join(", ") +
              ". Check those chips on the integration, save, then copy the new OAuth Authorization URL.",
          },
        ]);
      }
      return null;
    }
    return parsed;
  }

  function buildSetupAccessHtml(step) {
    const oauth = window.LAB_SETUP_OAUTH || {};
    const method = currentSetupAuthMethod();
    const tokenField = (step.keys || []).find((field) => field.var === "SETUP_BEARER_TOKEN") || {
      var: "SETUP_BEARER_TOKEN",
      kind: "secret",
      label: "Admin bearer token",
      placeholder: "Paste admin bearer token from your Developer Portal profile",
      value: "",
      hide_label: true,
    };
    const scopes = oauth.scopes || [];
    const callback = oauth.callback_url || window.location.origin + "/setup/callback";
    const createUrl = oauth.create_app_url || "https://developer.webex.com/my-apps/new";
    const scopeChips = scopes
      .map(
        (scope) =>
          `<button type="button" class="setup-scope-chip" data-copy-text="${escapeAttr(scope.id)}" title="${escapeAttr((scope.why || "Click to copy") + " — click to copy")}">${escapeHtml(scope.id)}</button>`
      )
      .join("");

    return (
      `<div class="setup-auth">` +
      `<div class="setup-auth-tabs" role="tablist">` +
      `<button type="button" class="setup-auth-tab${method === "bearer" ? " active" : ""}" data-method="bearer" role="tab">Admin token</button>` +
      `<button type="button" class="setup-auth-tab${method === "integration" ? " active" : ""}" data-method="integration" role="tab">Integration (advanced)</button>` +
      `</div>` +
      `<div class="setup-auth-panel${method === "bearer" ? "" : " hidden"}" data-method="bearer">` +
      buildApiRefHtml({
        doc_url: "https://developer.webex.com",
        doc_title: "Profile bearer token",
        doc_guide: [
          "Go to [developer.webex.com](https://developer.webex.com) and sign in with your Webex Contact Center admin account.",
          "Click your profile (avatar or name) in the top-right corner.",
          "Copy the bearer token shown in your profile.",
          "Paste the token string only — do not include the word Bearer.",
        ],
      }) +
      `<div class="lab-field-group lab-field-group--plain"><div class="lab-field-grid">` +
      fieldInputHtml({ ...tokenField, hide_label: true }) +
      `</div></div>` +
      `<div class="lab-step-actions">` +
      `<button type="button" class="btn btn-primary lab-save-step" data-module="module0" data-step="0.1">Check &amp; save step</button>` +
      `<span class="lab-save-status" id="save-status-module0-0.1"></span>` +
      `</div>` +
      `</div>` +
      `<div class="setup-auth-panel${method === "integration" ? "" : " hidden"}" data-method="integration">` +
      buildApiRefHtml({
        doc_url: createUrl,
        doc_title: "Webex Integration",
        api_method: "OAuth",
        api_base: "webexapis.com",
        doc_link_label: "Create a Webex Integration →",
        doc_guide: [
          "Go to [developer.webex.com/my-apps/new](https://developer.webex.com/my-apps/new) and login as a local admin.",
          "Under Integrations, click Create an Integration.",
          "Fill out the required fields: Integration Name, Icon, and App Hub Description.",
          "Fill in Redirect URI with the one provided below: http://127.0.0.1:5000/setup/callback.",
          "Add the proper scopes: for each scope chip, click to copy the name, then find and check it off in your integration.",
          "Once scopes are added, click Add Integration at the bottom of the page.",
          "Your integration will be created and you will now see your client information.",
          "Copy the Client ID from your integration, and paste it into the Client ID field in the lab.",
          "Copy the Client Secret from your integration, and paste it into the Client Secret field in the lab. The lab does not store the secret.",
          "Under OAuth Settings, copy the full OAuth Authorization URL in the black box, and paste it into the OAuth Authorization URL field in the lab.",
          "Click the Authorize in Webex button, then login with the admin user who created the integration.",
          "Hit the Accept button to authorize the integration.",
          "On the pop-up window, click the Copy code button, and paste this into the Authorization code field in the lab.",
          "You can close the pop-up window, then click Generate Token.",
        ],
      }) +
      `<div class="setup-copy-block">` +
      `<label for="setup-callback-url">Redirect URI (callback)</label>` +
      `<div class="setup-copy-row">` +
      `<input type="text" id="setup-callback-url" readonly value="${escapeAttr(callback)}">` +
      `<button type="button" class="btn btn-secondary setup-copy-btn" data-copy-target="setup-callback-url">Copy</button>` +
      `</div>` +
      `<p class="toolbar-hint">Add this Redirect URI on the integration.</p>` +
      `</div>` +
      `<div class="setup-copy-block">` +
      `<label>Required scopes</label>` +
      `<p class="toolbar-hint">Click a chip to copy that scope.</p>` +
      `<div class="setup-scope-chips">${scopeChips}</div>` +
      `</div>` +
      `<div class="lab-field-grid setup-integration-fields">` +
      `<div class="lab-field" data-field="SETUP_CLIENT_ID">` +
      `<label for="SETUP_CLIENT_ID">Client ID</label>` +
      `<input type="text" id="SETUP_CLIENT_ID" data-var="SETUP_CLIENT_ID" value="" placeholder="Paste Client ID from the integration page" autocomplete="off" spellcheck="false">` +
      `<p class="lab-field-hint" id="hint-SETUP_CLIENT_ID"></p>` +
      `</div>` +
      `<div class="lab-field lab-field-secret" data-field="SETUP_CLIENT_SECRET">` +
      `<label for="SETUP_CLIENT_SECRET">Client Secret</label>` +
      `<input type="password" id="SETUP_CLIENT_SECRET" data-var="SETUP_CLIENT_SECRET" value="" placeholder="Paste Client Secret from the integration page — not stored" autocomplete="off" spellcheck="false">` +
      `<p class="lab-field-hint" id="hint-SETUP_CLIENT_SECRET"></p>` +
      `</div>` +
      `<div class="lab-field lab-field-span" data-field="SETUP_OAUTH_URL">` +
      `<label for="SETUP_OAUTH_URL">OAuth Authorization URL</label>` +
      `<textarea id="SETUP_OAUTH_URL" data-var="SETUP_OAUTH_URL" rows="3" placeholder="Paste OAuth Authorization URL from the integration page" spellcheck="false"></textarea>` +
      `<p class="lab-field-hint" id="hint-SETUP_OAUTH_URL"></p>` +
      `<div class="lab-step-actions setup-authorize-actions">` +
      `<button type="button" class="btn btn-secondary" id="setup-authorize-btn">Authorize in Webex</button>` +
      `</div>` +
      `</div>` +
      `<div class="lab-field lab-field-span" data-field="SETUP_AUTH_CODE">` +
      `<label for="SETUP_AUTH_CODE">Authorization code</label>` +
      `<textarea id="SETUP_AUTH_CODE" data-var="SETUP_AUTH_CODE" rows="3" placeholder="Paste the code from the pop-up after you authorize"></textarea>` +
      `<p class="lab-field-hint" id="hint-SETUP_AUTH_CODE"></p>` +
      `</div>` +
      `</div>` +
      `<div class="lab-step-actions">` +
      `<button type="button" class="btn btn-primary" id="setup-integration-save">Generate token</button>` +
      `<span class="lab-save-status" id="save-status-module0-0.1-integration"></span>` +
      `</div>` +
      `</div>` +
      `</div>`
    );
  }

  function highlightMissingScopes(missing) {
    const needed = new Set((missing || []).map((scope) => String(scope).toLowerCase()));
    document.querySelectorAll(".setup-scope-chip").forEach((chip) => {
      const id = (chip.dataset.copyText || "").toLowerCase();
      chip.classList.toggle("is-missing", needed.has(id));
    });
  }

  function bindSetupAccessEvents() {
    const card = document.querySelector('.lab-step-card[data-module="module0"][data-step="0.1"]');
    if (!card) return;
    card.querySelectorAll(".setup-auth-tab").forEach((tab) => {
      tab.onclick = () => selectSetupAuthMethod(tab.dataset.method);
    });
    card.querySelectorAll(".setup-copy-btn").forEach((btn) => {
      btn.onclick = async () => {
        const el = document.getElementById(btn.dataset.copyTarget);
        const value = el ? el.value : "";
        try {
          await navigator.clipboard.writeText(value);
          btn.textContent = "Copied";
          setTimeout(() => {
            btn.textContent = "Copy";
          }, 1500);
        } catch (_) {
          if (el) el.select();
        }
      };
    });
    card.querySelectorAll(".setup-scope-chip").forEach((chip) => {
      chip.onclick = async () => {
        const value = chip.dataset.copyText || "";
        try {
          await navigator.clipboard.writeText(value);
          chip.classList.add("is-copied");
          setTimeout(() => chip.classList.remove("is-copied"), 1200);
        } catch (_) {
          /* clipboard may be blocked */
        }
      };
    });
    const oauthUrlField = document.getElementById("SETUP_OAUTH_URL");
    if (oauthUrlField) {
      oauthUrlField.addEventListener("input", () => applyOAuthAuthorizationUrl(false));
      oauthUrlField.addEventListener("paste", () => {
        setTimeout(() => applyOAuthAuthorizationUrl(false), 0);
      });
    }
    const authorizeBtn = document.getElementById("setup-authorize-btn");
    if (authorizeBtn) {
      authorizeBtn.onclick = () => {
        const panel = card.querySelector('.setup-auth-panel[data-method="integration"]');
        clearFieldErrors(panel);
        const parsed = applyOAuthAuthorizationUrl(true);
        if (!parsed) return;
        window.open(parsed.url, "lab21190-oauth", "popup=yes,width=720,height=800");
      };
    }
    const saveBtn = document.getElementById("setup-integration-save");
    if (saveBtn) saveBtn.onclick = () => saveIntegrationSetup();
  }

  function buildActiveStepCardHtml(moduleId, step, progressStep) {
    const access = computeStepAccess(moduleId, step.id);
    if (access === "locked") {
      const mod = getProgress().modules.find((m) => m.module_id === moduleId);
      const next = mod?.steps.find((s) => !s.complete);
      return (
        `<div class="lab-step-locked-msg">Complete step ${escapeHtml(next?.id || "")} ` +
        `(${escapeHtml(next?.label || "previous step")}) before continuing.</div>`
      );
    }

    if (moduleId === "module0" && step.id === "0.1") {
      const complete = progressStep && progressStep.complete;
      return (
        `<div class="lab-step-card${complete ? " complete" : ""}" data-module="module0" data-step="0.1">` +
        `<div class="lab-step-card-head">` +
        `<span class="lab-step-card-id">${escapeHtml(step.id)}</span>` +
        `<span class="lab-step-card-title">${escapeHtml(step.label)}</span>` +
        (complete
          ? `<span class="btn-info-wrap"><button type="button" class="btn-info" title="About this setup" onclick="showSectionInfo('setup-auth')">i</button></span>`
          : "") +
        `</div>` +
        buildSetupAccessHtml(step) +
        `<div class="lab-step-verify-msg hidden" id="verify-msg-module0-0.1"></div>` +
        `</div>`
      );
    }

    const complete = progressStep && progressStep.complete;
    const fieldGroups = step.field_groups || [];
    const endpointFields = step.endpoints || [];
    const keyFields = step.keys || [];
    let fieldsHtml = `<div class="lab-step-fields">`;

    if (fieldGroups.length) {
      fieldGroups.forEach((group) => {
        const groupId = group.id || "a";
        const locked = group.access === "locked";
        const partComplete = group.access === "complete";
        fieldsHtml += `<div class="lab-field-group lab-field-group--guided${locked ? " is-locked" : ""}${partComplete ? " is-complete" : ""}" data-part="${escapeAttr(groupId)}">`;
        if (group.title) fieldsHtml += `<h4>${escapeHtml(group.title)}</h4>`;
        if (locked) {
          fieldsHtml += `<p class="lab-part-locked-msg">Complete the previous part first.</p>`;
        } else {
          fieldsHtml += buildApiRefHtml({
            doc_url: group.doc_url,
            doc_title: group.doc_title,
            doc_guide: group.doc_guide,
            api_method: group.api_method || step.api_method,
            api_base: group.api_base || step.api_base,
          });
          fieldsHtml += `<div class="lab-field-grid">`;
          (group.fields || []).forEach((field) => {
            fieldsHtml += fieldInputHtml(field);
          });
          fieldsHtml += `</div>`;
          fieldsHtml += `<div class="lab-part-actions">`;
          fieldsHtml += `<button type="button" class="btn btn-primary lab-save-part" data-module="${escapeAttr(moduleId)}" data-step="${escapeAttr(step.id)}" data-part="${escapeAttr(groupId)}">Check &amp; save part</button>`;
          fieldsHtml += `<span class="lab-save-status" id="save-status-${escapeAttr(moduleId)}-${escapeAttr(step.id)}-${escapeAttr(groupId)}"></span>`;
          fieldsHtml += `</div>`;
        }
        fieldsHtml += `</div>`;
      });
    } else {
      if (endpointFields.length) {
        fieldsHtml += `<div class="lab-field-group"><h4>Endpoint${endpointFields.length > 1 ? "s" : ""}</h4><div class="lab-field-grid">`;
        endpointFields.forEach((field) => {
          fieldsHtml += fieldInputHtml({ ...field, kind: "endpoint" });
        });
        fieldsHtml += `</div></div>`;
      }

      if (keyFields.length) {
        const plainFields = step.field_layout === "plain" || moduleId === "module0";
        if (plainFields) {
          fieldsHtml += `<div class="lab-field-group lab-field-group--plain"><div class="lab-field-grid">`;
          keyFields.forEach((field) => {
            fieldsHtml += fieldInputHtml({ ...field, hide_label: true });
          });
          fieldsHtml += `</div></div>`;
        } else {
          const keysTitle = escapeHtml(step.keys_section_title || "Response keys");
          fieldsHtml += `<div class="lab-field-group"><h4>${keysTitle}</h4><div class="lab-field-grid">`;
          keyFields.forEach((field) => {
            fieldsHtml += fieldInputHtml({ ...field, kind: "key" });
          });
          fieldsHtml += `</div></div>`;
        }
      }
    }

    fieldsHtml += `</div>`;

    const showTopApiRef = !fieldGroups.length;
    const showStepSave = !fieldGroups.length;
    let actionsHtml = "";
    if (showStepSave) {
      actionsHtml =
        `<div class="lab-step-actions">` +
        `<button type="button" class="btn btn-primary lab-save-step" data-module="${escapeAttr(moduleId)}" data-step="${escapeAttr(step.id)}">Check &amp; save step</button>` +
        `<span class="lab-save-status" id="save-status-${escapeAttr(moduleId)}-${escapeAttr(step.id)}"></span>` +
        `</div>`;
    }

    return (
      `<div class="lab-step-card${complete ? " complete" : ""}" data-module="${escapeAttr(moduleId)}" data-step="${escapeAttr(step.id)}">` +
      `<div class="lab-step-card-head">` +
      `<span class="lab-step-card-id">${escapeHtml(step.id)}</span>` +
      `<span class="lab-step-card-title">${escapeHtml(step.label)}</span>` +
      `</div>` +
      (showTopApiRef ? buildApiRefHtml(step) : "") +
      fieldsHtml +
      actionsHtml +
      `<div class="lab-step-verify-msg hidden" id="verify-msg-${escapeAttr(moduleId)}-${escapeAttr(step.id)}"></div>` +
      `</div>`
    );
  }

  function updateStepNav(moduleId) {
    const mod = getProgress().modules.find((m) => m.module_id === moduleId);
    if (!mod) return;
    const activeId = resolveActiveStep(moduleId);
    mod.steps.forEach((step) => {
      const chip = document.querySelector(
        `.step-chip[data-module="${moduleId}"][data-step="${step.id}"]`
      );
      if (!chip) return;
      const access = computeStepAccess(moduleId, step.id);
      chip.classList.toggle("complete", step.complete);
      chip.classList.toggle("active", step.id === activeId);
      chip.classList.toggle("locked", access === "locked");
      chip.disabled = access === "locked";
      chip.setAttribute("aria-current", step.id === activeId ? "step" : "false");
    });
  }

  function renderModuleWorkspace(moduleId) {
    const container = document.getElementById("workspace-" + moduleId);
    const mod = workspaceModule(moduleId);
    const progressMod = getProgress().modules.find((m) => m.module_id === moduleId);
    if (!container || !mod) return;

    updateStepNav(moduleId);

    if (mod.view_only || !(mod.steps || []).length) {
      container.innerHTML = "";
      return;
    }

    const activeStepId = resolveActiveStep(moduleId);
    const step = mod.steps.find((s) => s.id === activeStepId);
    const progressStep = progressMod?.steps.find((s) => s.id === activeStepId);

    let html = "";
    if (isModuleComplete(moduleId)) {
      const nextMod = getNextLabModule(moduleId);
      html += `<div class="module-complete-cta"><p>All steps in this module are complete.</p>`;
      if (moduleId !== "module0") {
        html += `<button type="button" class="btn btn-secondary module-open-full-btn" data-module="${escapeAttr(moduleId)}">View in Full Dashboard</button>`;
      }
      if (nextMod) {
        html += `<button type="button" class="btn btn-primary module-next-btn" data-next-module="${escapeAttr(nextMod.module_id)}">Continue to ${escapeHtml(nextMod.module_name)}</button>`;
      }
      html += `</div>`;
    }
    html += step ? buildActiveStepCardHtml(moduleId, step, progressStep) : "";
    container.innerHTML = html;
    bindWorkspaceEvents(moduleId);
  }

  function renderAllWorkspaces() {
    labWorkspace.modules.forEach((mod) => renderModuleWorkspace(mod.module_id));
  }

  function bindAllStepNavEvents() {
    document.querySelectorAll(".step-chip").forEach((chip) => {
      chip.onclick = () => selectStep(chip.dataset.module, chip.dataset.step);
    });
    document.querySelectorAll(".module-reset-btn").forEach((btn) => {
      btn.onclick = () => resetModuleProgress(btn.dataset.module);
    });
  }

  async function resetModuleProgress(moduleId) {
    const mod = getProgress().modules.find((m) => m.module_id === moduleId);
    const name = mod?.module_name || moduleId;
    if (
      !window.confirm(
        `Reset all progress for "${name}"?\n\nSaved answers for this module will be cleared and you will start again at step 1.`
      )
    ) {
      return;
    }

    try {
      const res = await fetch(`/api/lab/modules/${moduleId}/reset`, { method: "POST" });
      const data = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || res.statusText);

      const wsMod = labWorkspace.modules.find((m) => m.module_id === moduleId);
      if (wsMod && data.steps) wsMod.steps = data.steps;

      activeSteps[moduleId] = data.steps?.find((s) => s.access === "active")?.id || getDefaultActiveStep(moduleId);
      syncProgressFromServer(data.progress);
      updateProgressUI(data.progress, []);

      if (data.config_status) {
        window.LAB_CONFIG_STATUS = data.config_status;
        updateConfigBanner(data.config_status);
        renderSetupStatus(data.config_status);
        updateModuleTabLocks();
      }

      if (moduleId === "module0") {
        try {
          window.LAB_SETUP_OAUTH = await fetchJSON("/api/lab/setup/oauth");
        } catch (_) {
          window.LAB_SETUP_OAUTH = window.LAB_SETUP_OAUTH || {};
          window.LAB_SETUP_OAUTH.auth_method = "";
          window.LAB_SETUP_OAUTH.client_id = "";
        }
      }

      invalidateCachesForModules(new Set([moduleId]));
      loadedModules.delete(moduleId);

      renderModuleWorkspace(moduleId);
      if (isModuleActive(moduleId)) {
        await ensureModuleLoaded(moduleId, true);
      }
    } catch (e) {
      window.alert("Could not reset module: " + e.message);
    }
  }

  function bindWorkspaceEvents(moduleId) {
    document.querySelectorAll(`.lab-save-step[data-module="${moduleId}"]`).forEach((btn) => {
      btn.onclick = () => saveStepAnswers(btn.dataset.module, btn.dataset.step);
    });
    document.querySelectorAll(`.lab-save-part[data-module="${moduleId}"]`).forEach((btn) => {
      btn.onclick = () => saveStepAnswers(btn.dataset.module, btn.dataset.step, btn.dataset.part);
    });
    document.querySelectorAll(`.module-open-full-btn[data-module="${moduleId}"]`).forEach((btn) => {
      btn.onclick = () => window.openFullDashboardForModule(btn.dataset.module);
    });
    document.querySelectorAll(`.module-next-btn[data-next-module]`).forEach((btn) => {
      btn.onclick = () => goToLabModule(btn.dataset.nextModule);
    });
    if (moduleId === "module0") bindSetupAccessEvents();
  }

  async function saveStepAnswers(moduleId, stepId, partId) {
    if (!isStepAccessible(moduleId, stepId)) return;

    const panel = document.querySelector(
      `.lab-step-card[data-module="${moduleId}"][data-step="${stepId}"]`
    );
    const statusEl = partId
      ? document.getElementById(`save-status-${moduleId}-${stepId}-${partId}`)
      : document.getElementById(`save-status-${moduleId}-${stepId}`);
    if (!panel) return;

    const scope = partId ? panel.querySelector(`[data-part="${partId}"]`) : panel;
    if (!scope) return;

    const answers = {};
    scope.querySelectorAll("input[data-var], textarea[data-var]").forEach((input) => {
      if (input.closest(".setup-auth-panel.hidden")) return;
      answers[input.dataset.var] = input.value.trim();
    });

    if (statusEl) {
      statusEl.textContent = "Checking…";
      statusEl.className = "lab-save-status";
    }
    clearFieldErrors(scope);
    const verifyMsg = document.getElementById(`verify-msg-${moduleId}-${stepId}`);
    if (verifyMsg) {
      verifyMsg.classList.add("hidden");
      verifyMsg.textContent = "";
    }

    try {
      const res = await fetch(`/api/lab/steps/${moduleId}/${stepId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answers, part: partId || undefined }),
      });
      const data = await res.json();

      if (res.status === 422 && data.errors) {
        applyFieldErrors(scope, data.errors);
        if (verifyMsg) {
          verifyMsg.textContent = data.message || "Some answers are incorrect.";
          verifyMsg.classList.remove("hidden");
        }
        if (statusEl) {
          statusEl.textContent = "Not quite — see hints";
          statusEl.className = "lab-save-status error";
        }
        return;
      }

      if (!res.ok || data.error) throw new Error(data.error || res.statusText);
      if (data.valid === false) {
        applyFieldErrors(scope, data.errors || []);
        if (statusEl) {
          statusEl.textContent = "Not quite — see hints";
          statusEl.className = "lab-save-status error";
        }
        return;
      }

      await applySuccessfulLabSave(moduleId, stepId, partId, data, statusEl);
    } catch (e) {
      if (statusEl) {
        statusEl.textContent = e.message;
        statusEl.className = "lab-save-status error";
      }
    }
  }

  async function applySuccessfulLabSave(moduleId, stepId, partId, data, statusEl, successLabel) {
    if (moduleId === "module0") {
      try {
        window.LAB_SETUP_OAUTH = await fetchJSON("/api/lab/setup/oauth");
      } catch (_) {
        /* keep existing oauth help */
      }
    }

    if (data.config_status) {
      window.LAB_CONFIG_STATUS = data.config_status;
      updateConfigBanner(data.config_status);
      renderSetupStatus(data.config_status);
      updateModuleTabLocks();
    }

    const modIndex = labWorkspace.modules.findIndex((m) => m.module_id === moduleId);
    if (modIndex >= 0 && data.step) {
      const stepIndex = labWorkspace.modules[modIndex].steps.findIndex((s) => s.id === stepId);
      if (stepIndex >= 0) labWorkspace.modules[modIndex].steps[stepIndex] = data.step;
    }

    const oldProgress = getProgress();
    const newlyCompleted = detectNewlyCompletedSteps(data.progress);
    syncProgressFromServer(data.progress);
    updateProgressUI(data.progress, newlyCompleted);

    const savedComplete = data.progress?.modules
      ?.find((mod) => mod.module_id === moduleId)
      ?.steps?.find((step) => step.id === stepId)?.complete;
    if (savedComplete) {
      const nextStepId = getNextStepId(moduleId, stepId);
      if (nextStepId) activeSteps[moduleId] = nextStepId;
    }

    renderModuleWorkspace(moduleId);

    if (statusEl) {
      statusEl.textContent = successLabel || (partId ? "Part saved!" : "Correct — saved!");
      statusEl.className = "lab-save-status success";
    }

    if (newlyCompleted.length) {
      window._newSections = new Set(newlyCompleted.map((n) => stepKey(n.moduleId, n.stepId)));
      await reloadAllSections({ newlyCompleted });
      if (isStepComplete("module3", "3.5")) {
        syncRtPolling(isRtViewActive());
      }
      setTimeout(() => {
        window._newSections = new Set();
        document.querySelectorAll(".newly-unlocked").forEach((el) => el.classList.remove("newly-unlocked"));
      }, 3000);
    } else if (progressFingerprint(oldProgress) !== progressFingerprint(data.progress)) {
      await reloadAllSections({ newlyCompleted: [] });
    }
  }

  async function saveIntegrationSetup() {
    const card = document.querySelector('.lab-step-card[data-module="module0"][data-step="0.1"]');
    const panel = card?.querySelector('.setup-auth-panel[data-method="integration"]');
    const statusEl = document.getElementById("save-status-module0-0.1-integration");
    const verifyMsg = document.getElementById("verify-msg-module0-0.1");
    if (!panel) return;

    const payload = {
      client_id: (document.getElementById("SETUP_CLIENT_ID")?.value || "").trim(),
      client_secret: (document.getElementById("SETUP_CLIENT_SECRET")?.value || "").trim(),
      code: (document.getElementById("SETUP_AUTH_CODE")?.value || "").trim(),
    };

    if (statusEl) {
      statusEl.textContent = "Generating token…";
      statusEl.className = "lab-save-status";
    }
    clearFieldErrors(panel);
    highlightMissingScopes([]);
    if (verifyMsg) {
      verifyMsg.classList.add("hidden");
      verifyMsg.textContent = "";
    }

    try {
      const res = await fetch("/api/lab/setup/integration", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (res.status === 422 && data.errors) {
        applyFieldErrors(panel, data.errors);
        highlightMissingScopes(data.missing_scopes);
        if (verifyMsg) {
          verifyMsg.textContent = data.message || "Could not generate an access token.";
          verifyMsg.classList.remove("hidden");
        }
        if (statusEl) {
          statusEl.textContent = data.missing_scopes && data.missing_scopes.length
            ? "Missing required scopes"
            : "Not quite — see hints";
          statusEl.className = "lab-save-status error";
        }
        return;
      }

      if (!res.ok || data.error) throw new Error(data.error || res.statusText);
      if (data.valid === false) {
        applyFieldErrors(panel, data.errors || []);
        highlightMissingScopes(data.missing_scopes);
        if (statusEl) {
          statusEl.textContent = "Not quite — see hints";
          statusEl.className = "lab-save-status error";
        }
        return;
      }

      const secretField = document.getElementById("SETUP_CLIENT_SECRET");
      const codeField = document.getElementById("SETUP_AUTH_CODE");
      if (secretField) secretField.value = "";
      if (codeField) codeField.value = "";

      await applySuccessfulLabSave("module0", "0.1", null, data, statusEl, "Token generated");
    } catch (e) {
      if (statusEl) {
        statusEl.textContent = e.message;
        statusEl.className = "lab-save-status error";
      }
    }
  }

  async function loadLabWorkspace() {
    labWorkspace = await fetchJSON("/api/lab/workspace");
    labWorkspace.modules.forEach((mod) => {
      if (!activeSteps[mod.module_id]) {
        activeSteps[mod.module_id] =
          mod.steps.find((s) => s.access === "active")?.id || getDefaultActiveStep(mod.module_id);
      }
    });
    bindAllStepNavEvents();
    renderAllWorkspaces();
  }

  async function fetchJSON(url, options) {
    const force = options && options.force;
    const full = force ? url + (url.includes("?") ? "&" : "?") + "refresh=1" : url;
    const res = await fetch(full);
    let data;
    try {
      data = await res.json();
    } catch (_) {
      if (!res.ok) throw new Error(res.status + " " + res.statusText);
      throw new Error("Invalid response from server");
    }
    if (data.error) throw new Error(data.error);
    if (!res.ok) throw new Error(res.status + " " + res.statusText);
    return data;
  }

  function renderError(container, msg) {
    hidePlaceholder(container);
    setContent(container, `<div class="error-box">${msg}</div>`);
  }

  function ensureRefreshOverlay(el) {
    if (!el || el.querySelector(":scope > .refresh-overlay")) return;
    const overlay = document.createElement("div");
    overlay.className = "refresh-overlay";
    overlay.setAttribute("role", "status");
    overlay.innerHTML =
      `<span class="refresh-spinner" aria-hidden="true"></span>` +
      `<span>Refreshing…</span>`;
    el.appendChild(overlay);
  }

  function markRefreshing(el, on) {
    if (!el) return;
    el.classList.toggle("is-refreshing", Boolean(on));
    el.setAttribute("aria-busy", on ? "true" : "false");
    el.querySelectorAll(".section-toolbar .btn, .card-actions .btn").forEach((btn) => {
      btn.disabled = Boolean(on);
    });
    if (on) ensureRefreshOverlay(el);
    else {
      const overlay = el.querySelector(":scope > .refresh-overlay");
      if (overlay) overlay.remove();
    }
  }

  function hidePlaceholder(container) {
    if (!container) return;
    const panel = container.closest(".module-panel") || container;
    const placeholder = panel.querySelector(".placeholder-text");
    if (placeholder) placeholder.style.display = "none";
  }

  function sectionBlock(id, title, content, isNew, infoKey) {
    return `<div class="section-block${isNew ? " newly-unlocked" : ""}" data-section="${id}">
      <div class="section-title-row"><span class="section-title">${title}</span></div>
      ${content}
    </div>`;
  }

  function chipListHtml(value) {
    const items = Array.isArray(value)
      ? value.map((item) => String(item).trim()).filter(Boolean)
      : String(value || "")
          .split(/[,;]/)
          .map((item) => item.trim())
          .filter(Boolean);
    if (!items.length) return "—";
    return (
      `<div class="stat-chips">${items
        .map((item) => `<span class="stat-chip">${escapeHtml(item)}</span>`)
        .join("")}</div>`
    );
  }

  function currentTableFilter(tableId) {
    const input = document.querySelector(`[data-table-filter="${tableId}"]`);
    return input ? input.value : "";
  }

  function restoreTableFilter(tableId, value) {
    const input = document.querySelector(`[data-table-filter="${tableId}"]`);
    if (input && value) {
      input.value = value;
      window.filterDataTable(input);
    }
  }

  window.filterDataTable = function (input) {
    const tableId = input.dataset.tableFilter;
    const table = document.getElementById(tableId);
    if (!table) return;
    const query = (input.value || "").trim().toLowerCase();
    let shown = 0;
    let total = 0;
    table.querySelectorAll("tbody tr").forEach((row) => {
      total += 1;
      const match = !query || (row.textContent || "").toLowerCase().includes(query);
      row.hidden = !match;
      if (match) shown += 1;
    });
    const count = document.querySelector(`[data-filter-count-for="${tableId.replace(/"/g, "")}"]`);
    if (count) count.textContent = query ? `${shown} of ${total}` : `${total} row${total === 1 ? "" : "s"}`;
  };

  function tableFilterBar(tableId, rowCount) {
    if (!rowCount) return "";
    return (
      `<div class="table-filter-bar">` +
      `<input type="search" class="table-filter-input" placeholder="Search this table…" ` +
      `aria-label="Search this table" data-table-filter="${escapeAttr(tableId)}" oninput="filterDataTable(this)">` +
      `<span class="table-filter-count" data-filter-count-for="${escapeAttr(tableId)}">${rowCount} row${rowCount === 1 ? "" : "s"}</span>` +
      `</div>`
    );
  }

  function buildTableHTML(headers, rows, sortKeys, tableId) {
    const sorted = sortKeys ? sortAlpha(rows, sortKeys) : rows;
    if (!sorted || !sorted.length) {
      return "<p class='placeholder-text'>No records returned yet. Verify your API token and field keys.</p>";
    }
    const id = tableId || "data-table-" + Math.random().toString(36).slice(2, 9);
    let html = tableFilterBar(id, sorted.length);
    html += `<div class="table-wrapper"><table class="data-table" id="${escapeAttr(id)}"><thead><tr>`;
    headers.forEach((h) => (html += `<th>${h.label}</th>`));
    html += "</tr></thead><tbody>";
    sorted.forEach((row) => {
      html += "<tr>";
      headers.forEach((h) => {
        const val = row[h.key];
        if (h.chips) {
          html += `<td class="chip-cell">${chipListHtml(val)}</td>`;
        } else if (h.html) {
          html += `<td>${val !== undefined && val !== null && val !== "" ? val : "—"}</td>`;
        } else {
          html += `<td>${val !== undefined && val !== null && val !== "" ? escapeHtml(String(val)) : "—"}</td>`;
        }
      });
      html += "</tr>";
    });
    html += "</tbody></table></div>";
    return html;
  }

  function buildGlobalVariablesTable(rows, editable) {
    const sorted = sortAlpha(rows || [], ["name"]);
    if (!sorted.length) {
      return "<p class='placeholder-text'>No records returned yet. Verify your API token and field keys.</p>";
    }

    const id = "tbl-global-vars";
    let html = tableFilterBar(id, sorted.length);
    html += `<div class="table-wrapper"><table class="data-table gv-table" id="${id}"><thead><tr>`;
    html += "<th>Name</th><th>Value</th><th>Type</th><th>Status</th>";
    if (editable) html += '<th class="gv-actions-col"></th>';
    html += "</tr></thead><tbody>";

    sorted.forEach((row) => {
      const id = row.id || "";
      const value = row.value !== undefined && row.value !== null && row.value !== "" ? String(row.value) : "";
      const valueDisplay = value || "—";
      html += `<tr class="gv-row${editable ? " gv-row-editable" : ""}" data-gv-id="${escapeAttr(id)}">`;
      html += `<td>${escapeHtml(row.name || "—")}</td>`;
      html += `<td class="gv-value-cell"><span class="gv-value-text">${escapeHtml(valueDisplay)}</span></td>`;
      html += `<td>${escapeHtml(row.type || "—")}</td>`;
      html += `<td>${escapeHtml(row.status || "—")}</td>`;
      if (editable) {
        html += `<td class="gv-actions-cell">`;
        if (id) {
          html += `<button type="button" class="btn btn-primary gv-edit-btn" onclick="openGlobalVariableEditModal('${escapeAttr(id)}')">Edit</button>`;
        }
        html += "</td>";
      }
      html += "</tr>";
    });

    html += "</tbody></table></div>";
    return html;
  }

  function globalVariablesHintHtml() {
    if (!isStepComplete("module2", "2.6")) return "";
    return (
      "<p class='toolbar-hint' style='margin-top:0.5rem'>Hover a row and click <strong>Edit</strong> to update that variable. " +
      "The form shows the writable Update-by-ID fields for its <code>variableType</code>. Requires <code>cjp:config_write</code>.</p>"
    );
  }

  function renderGlobalVariablesBody(gv, canEdit, statusHtml) {
    return (
      `<div id="global-vars-body" class="gv-section-body">` +
      (canEdit ? `<div id="gv-table-status">${statusHtml || ""}</div>` : "") +
      buildGlobalVariablesTable(gv.global_variables, canEdit) +
      globalVariablesHintHtml() +
      `</div>`
    );
  }

  async function refreshGlobalVariablesList(options) {
    const opts = options || {};
    const body = document.getElementById("global-vars-body");
    const canEdit = isStepComplete("module2", "2.6");

    if (body) {
      body.classList.add("is-loading");
      body.setAttribute("aria-busy", "true");
      const statusEl = document.getElementById("gv-table-status");
      if (statusEl) {
        statusEl.innerHTML = `<p class="placeholder-text">${escapeHtml(opts.loadingMessage || "Refreshing global variables…")}</p>`;
      }
    }

    try {
      const gv = await ensureOrgSection("global_variables", "/api/org/global-variables", true);
      if (!body) return gv;

      let successHtml = "";
      if (opts.successMessage) {
        successHtml =
          `<div class="status-card"><span class="status-dot"></span><span>${opts.successMessage}</span></div>`;
      }

      body.innerHTML =
        (canEdit ? `<div id="gv-table-status">${successHtml}</div>` : "") +
        buildGlobalVariablesTable(gv.global_variables, canEdit) +
        globalVariablesHintHtml();
      return gv;
    } catch (e) {
      const statusEl = document.getElementById("gv-table-status");
      if (statusEl) statusEl.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`;
      throw e;
    } finally {
      if (body) {
        body.classList.remove("is-loading");
        body.removeAttribute("aria-busy");
      }
    }
  }

  function updateModuleTabLocks() {
    document.querySelectorAll(".module-tab").forEach((tab) => {
      const locked = isModuleTabLocked(tab.dataset.module);
      tab.classList.toggle("locked", locked);
      tab.setAttribute("aria-disabled", locked ? "true" : "false");
    });
  }

  function updateConfigBanner(configStatus) {
    const alertEl = document.getElementById("setup-alert");
    if (!alertEl || !configStatus) return;

    if (isSetupComplete() && !configStatus.org_id_mismatch) {
      alertEl.className = "alert alert-success hidden";
      alertEl.innerHTML = "";
      return;
    }

    if (configStatus.org_id_mismatch) {
      alertEl.className = "alert alert-warning";
      alertEl.classList.remove("hidden");
      alertEl.innerHTML =
        `<strong>Org ID mismatch:</strong> configured org is <code>${escapeHtml(configStatus.org_id || "")}</code> ` +
        `but your token belongs to org <code>${escapeHtml(configStatus.token_org_id || "")}</code>. ` +
        "Update Connection with matching values.";
      return;
    }

    if (!isSetupComplete()) {
      alertEl.className = "alert alert-warning";
      alertEl.classList.remove("hidden");
      alertEl.innerHTML =
        "Enter your access token and organization ID to connect this dashboard to your Webex Contact Center organization.";
    }
  }

  function renderSetupStatus(configStatus) {
    const panel = document.getElementById("setup-status-module0");
    if (!panel) return;
    const status = configStatus || window.LAB_CONFIG_STATUS || {};
    if (!isSetupComplete()) {
      panel.innerHTML =
        `<p class="placeholder-text">Complete the setup steps above to connect the lab to your Webex Contact Center organization.</p>`;
      return;
    }
    const method = status.auth_method || (window.LAB_SETUP_OAUTH || {}).auth_method || "bearer";
    const methodLabel = method === "integration" ? "Webex Integration" : "admin profile token";
    panel.innerHTML =
      `<div class="status-card setup-connected">` +
      `<span class="status-dot"></span>` +
      `<div class="setup-connected-body">` +
      `<div class="setup-connected-title">` +
      `<strong>Connected</strong> — organization <code>${escapeHtml(status.org_id || "")}</code>` +
      `<span class="btn-info-wrap">` +
      `<button type="button" class="btn-info" title="About this setup" onclick="showSectionInfo('setup-auth')">i</button>` +
      `</span>` +
      `</div>` +
      `<p class="setup-connected-hint">Setup is complete using a ${escapeHtml(methodLabel)}. Open the Users module to begin the lab.</p>` +
      `</div></div>`;
  }

  function updateProgressUI(newProgress, newlyCompleted) {
    const bar = document.getElementById("overall-progress");
    const label = document.getElementById("overall-label");
    if (bar) bar.style.width = newProgress.percent + "%";
    if (label) {
      label.textContent =
        newProgress.completed_steps + " / " + newProgress.total_steps + " steps complete (" + newProgress.percent + "%)";
    }

    newProgress.modules.forEach((mod) => {
      const tab = document.querySelector(`.module-tab[data-module="${mod.module_id}"]`);
      if (tab) {
        const prog = tab.querySelector(".module-tab-progress");
        if (prog) prog.textContent = mod.completed_steps + "/" + mod.total_steps;
      }

      mod.steps.forEach((step) => {
        const chip = document.querySelector(
          `.step-chip[data-module="${mod.module_id}"][data-step="${step.id}"]`
        );
        if (!chip) return;
        const access = computeStepAccess(mod.module_id, step.id);
        const activeId = resolveActiveStep(mod.module_id);
        chip.classList.toggle("complete", step.complete);
        chip.classList.toggle("active", step.id === activeId);
        chip.classList.toggle("locked", access === "locked");
        chip.disabled = access === "locked";
        chip.setAttribute("aria-current", step.id === activeId ? "step" : "false");
        const isNew = newlyCompleted.some((n) => n.moduleId === mod.module_id && n.stepId === step.id);
        if (isNew) {
          chip.classList.add("just-completed");
          setTimeout(() => chip.classList.remove("just-completed"), 1500);
        }
      });

      const banner = document.getElementById("unlock-banner-" + mod.module_id);
      const newSteps = newlyCompleted.filter((n) => n.moduleId === mod.module_id);
      if (banner && newSteps.length) {
        banner.classList.remove("hidden");
        banner.textContent =
          "Step unlocked: " + newSteps.map((s) => s.stepId + " — " + s.label).join(", ");
        setTimeout(() => banner.classList.add("hidden"), 5000);
      }
    });
    updateModuleTabLocks();
    if (window.LAB_CONFIG_STATUS) {
      updateConfigBanner(window.LAB_CONFIG_STATUS);
    }
  }

  function isNewSection(moduleId, stepId) {
    return window._newSections && window._newSections.has(stepKey(moduleId, stepId));
  }

  function sectionToolbar(refreshLabel, refreshFn) {
    return (
      `<div class="section-toolbar"><button class="btn btn-secondary" onclick="${refreshFn}()">${refreshLabel}</button>` +
      `<span class="toolbar-hint">GET responses are cached. Use Refresh for a manual pull.</span></div>`
    );
  }

  function dashSectionRefresh(kind, label) {
    return (
      `<div class="section-toolbar"><button type="button" class="btn btn-secondary" onclick="refreshDash5Section('${kind}')">${label}</button>` +
      `<span class="toolbar-hint">GET responses are cached. Refresh this section to pull a new copy.</span></div>`
    );
  }

  function renderUsersTable(data) {
    const headers = [];
    const sortKeys = [];
    if (!isStepComplete("module1", "1.2")) {
      headers.push({ key: "display_name", label: "Name" });
      headers.push({ key: "id", label: "User ID" });
      sortKeys.push("display_name", "id");
    } else {
      headers.push({ key: "display_name", label: "Name" });
      headers.push({ key: "first_name", label: "First Name" });
      headers.push({ key: "last_name", label: "Last Name" });
      headers.push({ key: "email", label: "Email" });
      sortKeys.push("last_name", "first_name", "email");
    }

    if (isStepComplete("module1", "1.3")) {
      headers.push({ key: "agent_profile_name", label: "Agent Profile" });
      headers.push({ key: "multimedia_profile_name", label: "Multimedia Profile" });
      headers.push({ key: "user_profile_name", label: "User Profile" });
    }
    if (isStepComplete("module1", "1.4")) {
      headers.push({ key: "channel_types", label: "Channel Types", chips: true });
    }
    if (isStepComplete("module1", "1.5")) {
      headers.push({ key: "skill_profile_name", label: "Skill Profile" });
    }
    if (isStepComplete("module1", "1.6")) {
      headers.push({ key: "team_names", label: "Teams", chips: true });
    }

    const rows = data.users;

    return sectionBlock(
      "users-table",
      "Contact Center Users",
      buildTableHTML(headers, rows, sortKeys, "tbl-users"),
      isNewSection("module1", "1.1") ||
        isNewSection("module1", "1.2") ||
        isNewSection("module1", "1.3") ||
        isNewSection("module1", "1.4") ||
        isNewSection("module1", "1.5") ||
        isNewSection("module1", "1.6"),
      "users"
    );
  }

  async function loadUsers(force) {
    const el = document.getElementById("content-module1");
    if (!isStepComplete("module1", "1.1")) return;

    if (force) markRefreshing(el, true);
    try {
      if (force || usersCache === null) {
        usersCache = await fetchJSON("/api/users", { force });
      }
      hidePlaceholder(el);
      const html = sectionToolbar("Refresh users", "refreshModule1") + renderUsersTable(usersCache);
      setContent(el, html, force);
    } catch (e) {
      if (force) usersCache = null;
      renderError(el, e.message);
    } finally {
      markRefreshing(el, false);
    }
  }

  window.refreshModule1 = function () {
    loadUsers(true);
  };

  async function ensureOrgSection(cacheKey, url, force) {
    if (!force && orgCache[cacheKey] !== null) {
      return orgCache[cacheKey];
    }
    const data = await fetchJSON(url, { force });
    orgCache[cacheKey] = data;
    return data;
  }

  async function ensureWebexSection(cacheKey, url, force) {
    if (!force && webexCache[cacheKey] !== null) {
      return webexCache[cacheKey];
    }
    const data = await fetchJSON(url, { force });
    webexCache[cacheKey] = data;
    return data;
  }

  const ORG_ENTITY_TABS = [
    { id: "entry_points", step: "2.1", label: "Entry Points", cacheKey: "entry_points", url: "/api/org/entry-points", infoKey: "entry-points" },
    { id: "queues", step: "2.2", label: "Queues", cacheKey: "queues", url: "/api/org/queues", infoKey: "queues" },
    { id: "teams", step: "2.3", label: "Teams", cacheKey: "teams", url: "/api/org/teams", infoKey: "teams" },
    { id: "aux_codes", step: "2.4", label: "Auxiliary Codes", cacheKey: "aux_codes", url: "/api/org/aux-codes", infoKey: "aux-codes" },
    { id: "global_variables", step: "2.5", label: "Global Variables", cacheKey: "global_variables", url: "/api/org/global-variables", infoKey: "global-vars" },
  ];

  const WEBEX_ENTITY_TABS = [
    { id: "people", step: "4.1", label: "User Info", cacheKey: "people", url: "/api/webex/people", infoKey: "people" },
    { id: "locations", step: "4.2", label: "Locations", cacheKey: "locations", url: "/api/webex/locations", infoKey: "locations" },
    { id: "pstn", step: "4.3", label: "PSTN", cacheKey: "ep_pstn", url: "/api/webex/ep-pstn", infoKey: "pstn" },
  ];

  function orgEntityNav(activeId, selectFn) {
    let nav = `<div class="dash-inner-nav">`;
    ORG_ENTITY_TABS.forEach((tab) => {
      const ready = isStepComplete("module2", tab.step);
      const cls = `dash-inner-tab${tab.id === activeId ? " active" : ""}${ready ? "" : " locked"}`;
      if (ready) {
        nav += `<button type="button" class="${cls}" onclick="${selectFn}('${tab.id}')">${escapeHtml(tab.label)}</button>`;
      } else {
        nav += `<button type="button" class="${cls}" disabled title="Complete step ${escapeAttr(tab.step)} to unlock">${escapeHtml(tab.label)}</button>`;
      }
    });
    nav += `</div>`;
    return nav;
  }

  function resolveOrgEntityTab(storeKey) {
    const unlocked = ORG_ENTITY_TABS.filter((tab) => isStepComplete("module2", tab.step));
    if (!unlocked.length) return null;
    const currentId = window[storeKey];
    return unlocked.find((tab) => tab.id === currentId) || unlocked[0];
  }

  function applyOrgTabFromCompleted(newlyCompleted) {
    const last = [...(newlyCompleted || [])].reverse().find((item) => item.moduleId === "module2");
    if (!last) return;
    const tab =
      last.stepId === "2.6"
        ? ORG_ENTITY_TABS.find((item) => item.id === "global_variables")
        : ORG_ENTITY_TABS.find((item) => item.step === last.stepId);
    if (!tab) return;
    window._org2Tab = tab.id;
    window._dash5OrgTab = tab.id;
  }

  function webexEntityNav(activeId, selectFn) {
    let nav = `<div class="dash-inner-nav">`;
    WEBEX_ENTITY_TABS.forEach((tab) => {
      const ready = isStepComplete("module4", tab.step);
      const cls = `dash-inner-tab${tab.id === activeId ? " active" : ""}${ready ? "" : " locked"}`;
      if (ready) {
        nav += `<button type="button" class="${cls}" onclick="${selectFn}('${tab.id}')">${escapeHtml(tab.label)}</button>`;
      } else {
        nav += `<button type="button" class="${cls}" disabled title="Complete step ${escapeAttr(tab.step)} to unlock">${escapeHtml(tab.label)}</button>`;
      }
    });
    nav += `</div>`;
    return nav;
  }

  function resolveWebexEntityTab(storeKey) {
    const unlocked = WEBEX_ENTITY_TABS.filter((tab) => isStepComplete("module4", tab.step));
    if (!unlocked.length) return null;
    const currentId = window[storeKey];
    return unlocked.find((tab) => tab.id === currentId) || unlocked[0];
  }

  function applyWebexTabFromCompleted(newlyCompleted) {
    const last = [...(newlyCompleted || [])].reverse().find((item) => item.moduleId === "module4");
    if (!last) return;
    const tab = WEBEX_ENTITY_TABS.find((item) => item.step === last.stepId);
    if (!tab) return;
    window._webex4Tab = tab.id;
    window._dash5WebexTab = tab.id;
  }

  function renderOrgEntityBody(tab, payload) {
    if (tab.id === "entry_points") {
      return buildTableHTML(
        [
          { key: "name", label: "Name" },
          { key: "dn", label: "DN / Address", chips: true },
          { key: "calling_location", label: "Webex Calling Location" },
          { key: "media_region", label: "Media Region" },
          { key: "channel_type", label: "Channel" },
          { key: "flow_name", label: "Flow" },
          { key: "status", label: "Status" },
        ],
        payload.entry_points,
        ["name"],
        "tbl-entry-points"
      );
    }
    if (tab.id === "queues") {
      return buildTableHTML(
        [
          { key: "name", label: "Name" },
          { key: "contact_direction", label: "Contact Direction" },
          { key: "type", label: "Type" },
          { key: "skills_based_routing", label: "Skills Based Routing" },
          { key: "status", label: "Status" },
        ],
        payload.queues,
        ["name"],
        "tbl-queues"
      );
    }
    if (tab.id === "teams") {
      return buildTableHTML(
        [
          { key: "name", label: "Team Name" },
          { key: "site", label: "Site" },
          { key: "type", label: "Type" },
          { key: "dn", label: "DN", chips: true },
          { key: "status", label: "Status" },
        ],
        payload.teams,
        ["name"],
        "tbl-teams"
      );
    }
    if (tab.id === "aux_codes") {
      return buildTableHTML(
        [
          { key: "name", label: "Name" },
          { key: "code_type", label: "Code Type" },
          { key: "default", label: "Default" },
          { key: "status", label: "Status" },
        ],
        payload.aux_codes,
        ["name"],
        "tbl-aux-codes"
      );
    }
    const canEdit = isStepComplete("module2", "2.6");
    return renderGlobalVariablesBody(payload, canEdit, "");
  }

  async function loadOrgData(force) {
    const el = document.getElementById("content-module2");
    if (!isModuleStarted("module2")) return;

    const tab = resolveOrgEntityTab("_org2Tab");
    if (!tab) return;
    window._org2Tab = tab.id;

    const needsFetch = force || orgCache[tab.cacheKey] === null;
    if (needsFetch) markRefreshing(el, true);
    try {
      const data = await ensureOrgSection(tab.cacheKey, tab.url, force);
      const html =
        orgEntityNav(tab.id, "selectOrg2Tab") +
        sectionToolbar("Refresh " + tab.label.toLowerCase(), "refreshModule2") +
        sectionBlock(
          tab.infoKey,
          tab.label,
          renderOrgEntityBody(tab, data),
          isNewSection("module2", tab.step) ||
            (tab.id === "global_variables" && isNewSection("module2", "2.6")),
          tab.infoKey
        );
      hidePlaceholder(el);
      setContent(el, html, force || needsFetch);
    } catch (e) {
      if (force) orgCache[tab.cacheKey] = null;
      renderError(el, e.message);
    } finally {
      markRefreshing(el, false);
    }
  }

  window.selectOrg2Tab = function (tabId) {
    window._org2Tab = tabId;
    loadOrgData(false);
  };

  window.refreshModule2 = function () {
    const tab = ORG_ENTITY_TABS.find((item) => item.id === window._org2Tab);
    if (tab) orgCache[tab.cacheKey] = null;
    loadOrgData(true);
  };

  const RT_POLL_MS = 10000;
  let lastRtFingerprint = "";
  let rtPollInterval = null;

  function rtFingerprint(agents) {
    return sortAlpha(agents || [], ["agent_id"])
      .map(
        (a) =>
          `${a.agent_id}:${a.state}:${a.idle_code_name}:${a.state_duration}:${a.interaction_id}:${a.name}`
      )
      .join("|");
  }

  const RT_AGENT_COLUMNS = [
    { key: "name", label: "Agent" },
    { key: "agent_id", label: "ID" },
    { key: "state", label: "State" },
    { key: "idle_code_name", label: "Idle Code" },
    { key: "state_duration", label: "State Duration" },
    { key: "interaction_id", label: "Interaction ID" },
  ];

  const RT_POLLING_NOTE =
    "<p class='placeholder-text' style='margin-top:0.5rem;font-size:0.8rem'>" +
    "Logged-in agents come from GraphQL Search (agentSession, isActive). Current state is updated with " +
    "<code>GET /v1/agents/activities</code> (telephony). The table refreshes every 10 seconds while you are viewing " +
    "Module 3 or the Full Dashboard. Historical report counts load once — use each card's Refresh. No webhooks.</p>";

  function reportField(row, keys) {
    for (const key of keys) {
      if (row && row[key] != null && row[key] !== "") return String(row[key]);
    }
    return "";
  }

  function countBy(rows, keys) {
    const counts = {};
    (rows || []).forEach((row) => {
      const val = reportField(row, keys) || "unknown";
      counts[val] = (counts[val] || 0) + 1;
    });
    return counts;
  }

  function breakdownHtml(counts) {
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([label, value]) => `<span class="stat-chip"><strong>${escapeHtml(label)}</strong> ${value}</span>`)
      .join("");
  }

  function formatLoginDuration(ms) {
    const value = Number(ms) || 0;
    if (value <= 0) return "0m";
    const totalMin = Math.round(value / 60000);
    const hours = Math.floor(totalMin / 60);
    const mins = totalMin % 60;
    if (hours && mins) return hours + "h " + mins + "m";
    if (hours) return hours + "h";
    return mins + "m";
  }

  function sessionLoginMs(row) {
    const start = Number(row.startTime || row.start_time || 0);
    let end = Number(row.endTime || row.end_time || 0);
    if (!start) return 0;
    if (!end || end < start) end = Date.now();
    return end - start;
  }

  function reportSummaryHtml(def, rows) {
    if (def.id === "csr") {
      return (
        `<p class="card-submetric">Termination type</p>` +
        `<div class="stat-chips">${breakdownHtml(countBy(rows, ["terminationType", "termination_type"]))}</div>` +
        `<p class="card-submetric">Call direction</p>` +
        `<div class="stat-chips">${breakdownHtml(countBy(rows, ["direction", "call_direction", "contactDirection"]))}</div>` +
        `<p class="card-submetric">Channel</p>` +
        `<div class="stat-chips">${breakdownHtml(countBy(rows, ["channelType", "channel_type"]))}</div>`
      );
    }
    if (def.id === "asr") {
      const unique = new Set((rows || []).map((row) => reportField(row, ["agentId", "agent_id"])).filter(Boolean));
      const totalMs = (rows || []).reduce((sum, row) => sum + sessionLoginMs(row), 0);
      return (
        `<p class="card-submetric">${formatLoginDuration(totalMs)} total logged-in time</p>` +
        `<p class="card-submetric">${unique.size} unique agent${unique.size === 1 ? "" : "s"}</p>` +
        `<div class="stat-chips">${breakdownHtml(countBy(rows, ["teamName", "team_name"]))}</div>`
      );
    }
    return "";
  }

  function buildReportCard(def, cached) {
    const rows = cached && cached.data ? cached.data[def.key] || [] : [];
    const count = cached && cached.data ? rows.length : "…";
    const newClass = isNewSection("module3", def.step) ? " newly-unlocked" : "";
    const errorHtml = cached && cached.error
      ? `<div class="error-box" id="report-error-${def.id}">${cached.error}</div>`
      : `<div id="report-error-${def.id}"></div>`;
    const summary = cached && cached.data ? reportSummaryHtml(def, rows) : "";
    return (
      `<div class="card${newClass}" id="report-card-${def.id}">` +
      `<div class="card-title-row"><h3>${def.label}</h3></div>` +
      `<div class="metric" id="report-metric-${def.id}">${count}</div>` +
      `<p>${escapeHtml(def.desc)} — ${escapeHtml(def.window)}</p>` +
      `<div id="report-summary-${def.id}">${summary}</div>` +
      `<div class="card-actions">` +
      `<button class="btn btn-secondary" id="report-refresh-${def.id}" onclick="refreshReport('${def.step}')">Refresh</button>` +
      `</div>` +
      errorHtml +
      `</div>`
    );
  }

  async function ensureReportCached(reportId, force) {
    const def = REPORT_DEFS.find((r) => r.id === reportId);
    if (!def || !isStepComplete("module3", def.step)) return null;
    if (!force && reportCache[reportId] !== null) {
      return reportCache[reportId];
    }
    try {
      const data = await fetchJSON(def.url, { force });
      reportCache[reportId] = { data, error: null };
    } catch (e) {
      reportCache[reportId] = { data: null, error: e.message };
    }
    return reportCache[reportId];
  }

  window.refreshReport = async function (step) {
    const def = REPORT_DEFS.find((r) => r.step === step);
    if (!def) return;
    const card = document.getElementById("report-card-" + def.id);
    const btn = document.getElementById("report-refresh-" + def.id);
    const metricEl = document.getElementById("report-metric-" + def.id);
    const errEl = document.getElementById("report-error-" + def.id);
    markRefreshing(card, true);
    if (btn) btn.disabled = true;
    try {
      const data = await fetchJSON(def.url, { force: true });
      reportCache[def.id] = { data, error: null };
      if (metricEl) metricEl.textContent = (data[def.key] || []).length;
      const summaryEl = document.getElementById("report-summary-" + def.id);
      if (summaryEl) summaryEl.innerHTML = reportSummaryHtml(def, data[def.key] || []);
      if (errEl) errEl.innerHTML = "";
    } catch (e) {
      reportCache[def.id] = { data: null, error: e.message };
      if (metricEl) metricEl.textContent = "—";
      if (errEl) errEl.innerHTML = `<div class="error-box">${e.message}</div>`;
    } finally {
      markRefreshing(card, false);
      if (btn) btn.disabled = false;
    }
  };

  function updateRtAgentsTable() {
    const tableHost = document.getElementById("rt-agents-table");
    if (!tableHost || !rtAgentsCache) return;
    const prev = currentTableFilter("tbl-rt-agents");
    tableHost.innerHTML = buildTableHTML(RT_AGENT_COLUMNS, rtAgentsCache.agents, ["name"], "tbl-rt-agents");
    restoreTableFilter("tbl-rt-agents", prev);
  }

  function isRtViewActive() {
    if (isStandaloneDashboard()) return window._dash5Tab === "reports";
    return isModuleActive("module3");
  }

  async function refreshRtAgents(force) {
    if (!isStepComplete("module3", "3.5")) return;
    if (!isRtViewActive()) return;
    try {
      const rt = await fetchJSON("/api/reports/rt-agents");
      const fp = rtFingerprint(rt.agents);
      if (!force && fp === lastRtFingerprint) return;
      lastRtFingerprint = fp;
      rtAgentsCache = rt;
      updateRtAgentsTable();
    } catch (_) { /* server may be restarting or rate limited */ }
  }

  function stopRtPolling() {
    if (rtPollInterval) {
      clearInterval(rtPollInterval);
      rtPollInterval = null;
    }
  }

  function startRtPolling() {
    if (rtPollInterval) return;
    if (!isStepComplete("module3", "3.5")) return;
    if (!isRtViewActive()) return;
    rtPollInterval = setInterval(() => refreshRtAgents(false), RT_POLL_MS);
  }

  function syncRtPolling(refreshOnEnter) {
    stopRtPolling();
    if (!isStepComplete("module3", "3.5")) return;
    if (!isRtViewActive()) return;
    if (refreshOnEnter) refreshRtAgents(true);
    startRtPolling();
  }

  function sessionDetailsSectionsHtml() {
    let html = "";
    if (isStepComplete("module3", "3.2")) {
      html += sectionBlock(
        "customer-details",
        "Customer Session Details",
        `<div class="section-toolbar">` +
          `<button class="btn btn-secondary" onclick="showCustomerDetails()">More customer details</button>` +
          `<span class="toolbar-hint">CSR records from the last 30 days — click an Interaction ID to view CAR events.</span>` +
          `</div>`,
        isNewSection("module3", "3.2"),
        [
          { id: "csr-details", title: "How Customer Session Details is built", caption: "CSR" },
          { id: "car", title: "About the CAR query", caption: "CAR" },
        ]
      );
    }
    if (isStepComplete("module3", "3.4")) {
      html += sectionBlock(
        "agent-details",
        "Agent Session Details",
        `<div class="section-toolbar">` +
          `<button class="btn btn-secondary" onclick="showAgentDetails()">More agent details</button>` +
          `<span class="toolbar-hint">ASR records from the last 30 days — click an Agent Session ID to view AAR events.</span>` +
          `</div>`,
        isNewSection("module3", "3.4"),
        [
          { id: "asr-details", title: "How Agent Session Details is built", caption: "ASR" },
          { id: "aar", title: "About the AAR query", caption: "AAR" },
        ]
      );
    }
    return html;
  }

  async function loadReports(force, options) {
    const opts = options || {};
    const el = document.getElementById("content-module3");
    if (!isModuleStarted("module3")) return;

    if (force) markRefreshing(el, true);
    let html = "";

    try {
    if (!opts.skipHistorical) {
      const reportTasks = REPORT_DEFS.filter((def) => isStepComplete("module3", def.step)).map(
        async (def) => {
          const cached = await ensureReportCached(def.id, force);
          return buildReportCard(def, cached);
        }
      );
      const reportCards = reportTasks.length ? await Promise.all(reportTasks) : [];
      html += '<div class="card-grid">' + reportCards.join("") + "</div>";
      html += sessionDetailsSectionsHtml();
    }

    if (!opts.skipRt && isStepComplete("module3", "3.5")) {
      if (force) {
        lastRtFingerprint = "";
      }
      if (force || !rtAgentsCache) {
        try {
          rtAgentsCache = await fetchJSON("/api/reports/rt-agents");
          lastRtFingerprint = rtFingerprint(rtAgentsCache.agents);
        } catch (e) {
          html += `<div class="error-box">${e.message}</div>`;
          rtAgentsCache = null;
        }
      }
      if (rtAgentsCache) {
        html += sectionBlock(
          "rt-agents",
          "Real-Time Agent States",
          `<div class="section-toolbar"><button class="btn btn-secondary" onclick="refreshLiveAgents()">Refresh agent data</button>` +
            `<span class="toolbar-hint">Manual refresh — auto-updates every 10 seconds. Uses GraphQL Search plus GET /v1/agents/activities.</span></div>` +
            `<div id="rt-agents-table">${buildTableHTML(RT_AGENT_COLUMNS, rtAgentsCache.agents, ["name"], "tbl-rt-agents")}</div>` +
            RT_POLLING_NOTE,
          isNewSection("module3", "3.5"),
          "rt-agents"
        );
      }
    }

    if (html.replace('<div class="card-grid"></div>', "").trim()) {
      hidePlaceholder(el);
      setContent(el, html, force || opts.skipHistorical);
    }
    } finally {
      markRefreshing(el, false);
    }
  }

  window.refreshLiveAgents = function () {
    const host = document.getElementById("rt-agents-table") && document.getElementById("rt-agents-table").closest(".section-block");
    markRefreshing(host, true);
    Promise.resolve(refreshRtAgents(true)).finally(() => markRefreshing(host, false));
  };

  function escapeAttr(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;")
      .replace(/</g, "&lt;");
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function findGlobalVariable(variableId) {
    const rows = (orgCache.global_variables && orgCache.global_variables.global_variables) || [];
    return rows.find((row) => row.id === variableId) || null;
  }

  function gvFieldValue(values, key) {
    const value = values ? values[key] : undefined;
    if (value === undefined || value === null) return "";
    return value;
  }

  function gvBooleanChecked(value) {
    return value === true || String(value).toLowerCase() === "true";
  }

  function renderGlobalVariableField(field, values) {
    const key = field.key;
    const inputId = "gv-field-" + key;
    const current = gvFieldValue(values, key);
    const required = field.required ? " required" : "";
    const maxLength = field.maxLength ? ` maxlength="${Number(field.maxLength)}"` : "";
    const depends = field.dependsOn ? ` data-gv-depends="${escapeAttr(field.dependsOn)}"` : "";
    let control = "";

    if (field.input === "boolean") {
      control =
        `<label class="gv-toggle">` +
        `<input id="${inputId}" data-gv-field="${escapeAttr(key)}" data-gv-input="boolean" type="checkbox"${gvBooleanChecked(current) ? " checked" : ""} />` +
        `<span>${escapeHtml(field.label)}</span>` +
        `</label>`;
      return (
        `<div class="gv-field gv-field-toggle" data-gv-wrap="${escapeAttr(key)}"${depends}>` +
        control +
        (field.hint ? `<p class="gv-field-hint">${escapeHtml(field.hint)}</p>` : "") +
        `</div>`
      );
    }

    if (field.input === "boolean-value") {
      const currentLower = String(current).toLowerCase();
      control =
        `<select id="${inputId}" class="gv-modal-input" data-gv-field="${escapeAttr(key)}" data-gv-input="boolean-value"${required}>` +
        `<option value="true"${currentLower === "true" ? " selected" : ""}>true</option>` +
        `<option value="false"${currentLower === "false" ? " selected" : ""}>false</option>` +
        `</select>`;
    } else if (field.input === "integer") {
      control =
        `<input id="${inputId}" class="gv-modal-input" data-gv-field="${escapeAttr(key)}" data-gv-input="integer" type="number" step="1" value="${escapeAttr(current)}"${required} />`;
    } else if (field.input === "decimal") {
      control =
        `<input id="${inputId}" class="gv-modal-input" data-gv-field="${escapeAttr(key)}" data-gv-input="decimal" type="number" step="any" value="${escapeAttr(current)}"${required} />`;
    } else if (field.input === "textarea") {
      control =
        `<textarea id="${inputId}" class="gv-modal-input gv-modal-textarea" data-gv-field="${escapeAttr(key)}" data-gv-input="textarea"${maxLength}${required}>${escapeHtml(current)}</textarea>`;
    } else {
      const placeholder = field.input === "datetime" ? ' placeholder="YYYY-MM-DD or YYYY-MM-DDThh:mm"' : "";
      control =
        `<input id="${inputId}" class="gv-modal-input" data-gv-field="${escapeAttr(key)}" data-gv-input="${escapeAttr(field.input || "text")}" type="text" value="${escapeAttr(current)}"${placeholder}${maxLength}${required} />`;
    }

    return (
      `<div class="gv-field" data-gv-wrap="${escapeAttr(key)}"${depends}>` +
      `<label class="gv-update-label" for="${inputId}">${escapeHtml(field.label)}</label>` +
      control +
      (field.hint ? `<p class="gv-field-hint">${escapeHtml(field.hint)}</p>` : "") +
      `</div>`
    );
  }

  function bindGlobalVariableFormDependencies(root) {
    const sync = () => {
      root.querySelectorAll("[data-gv-depends]").forEach((wrap) => {
        const parent = root.querySelector(`[data-gv-field="${wrap.dataset.gvDepends}"]`);
        const enabled = parent ? parent.checked : true;
        wrap.classList.toggle("is-disabled", !enabled);
        wrap.querySelectorAll("input, select, textarea").forEach((el) => {
          el.disabled = !enabled;
          if (!enabled && el.type === "checkbox") el.checked = false;
        });
      });
    };
    root.querySelectorAll('input[data-gv-input="boolean"]').forEach((el) => {
      el.addEventListener("change", sync);
    });
    sync();
  }

  function collectGlobalVariableForm(root) {
    const values = {};
    root.querySelectorAll("[data-gv-field]").forEach((el) => {
      if (el.disabled) {
        if (el.dataset.gvInput === "boolean") values[el.dataset.gvField] = false;
        return;
      }
      if (el.dataset.gvInput === "boolean") {
        values[el.dataset.gvField] = el.checked;
      } else {
        values[el.dataset.gvField] = el.value;
      }
    });
    return values;
  }

  function buildGlobalVariableEditModalBody(form) {
    const values = form.values || {};
    const fields = (form.fields || []).map((field) => renderGlobalVariableField(field, values)).join("");
    const locked = form.systemDefault
      ? `<div class="error-box">This is a system default variable and cannot be updated from the dashboard.</div>`
      : "";
    return (
      `<div class="gv-modal-form" id="gv-edit-form">` +
      `<div class="section-title-row gv-edit-info-row">` +
      `<span class="section-title">Update by ID</span>` +
      `</div>` +
      `<p class="gv-modal-meta"><strong>Name:</strong> ${escapeHtml(form.name || form.id || "—")}</p>` +
      `<p class="gv-modal-meta"><strong>Type:</strong> ${escapeHtml(form.variableType || "—")}</p>` +
      `<p class="gv-field-hint">Name and variable type cannot be changed. The fields below are the writable Update-by-ID properties for this type.</p>` +
      locked +
      fields +
      `<div class="section-toolbar gv-modal-actions">` +
      `<button type="button" class="btn btn-primary" id="gv-save-btn"${form.systemDefault ? " disabled" : ""} onclick="saveGlobalVariableEdit('${escapeAttr(form.id)}')">Save</button>` +
      `<button type="button" class="btn btn-secondary" onclick="closeReportModal()">Cancel</button>` +
      `</div>` +
      `<div id="gv-modal-status"></div>` +
      `</div>`
    );
  }

  window.openGlobalVariableEditModal = async function (variableId) {
    openReportModal("Edit Global Variable", "<p class='placeholder-text'>Loading variable…</p>");
    try {
      const data = await fetchJSON("/api/org/global-variables/" + encodeURIComponent(variableId));
      const form = data.form;
      if (!form) throw new Error("Variable details were not returned.");
      openReportModal("Edit " + (form.name || "Global Variable"), buildGlobalVariableEditModalBody(form));
      const formEl = document.getElementById("gv-edit-form");
      if (formEl) bindGlobalVariableFormDependencies(formEl);
      const first = document.querySelector("#gv-edit-form [data-gv-field]");
      first?.focus();
      if (first && first.tagName === "INPUT" && first.type === "text") first.select();
    } catch (e) {
      openReportModal("Edit Global Variable", `<div class="error-box">${escapeHtml(e.message)}</div>`);
    }
  };

  window.saveGlobalVariableEdit = async function (variableId) {
    const formEl = document.getElementById("gv-edit-form");
    const modalStatus = document.getElementById("gv-modal-status");
    const saveBtn = document.getElementById("gv-save-btn");
    const cancelBtn = document.querySelector(".gv-modal-actions .btn-secondary");
    const values = formEl ? collectGlobalVariableForm(formEl) : {};
    const row = findGlobalVariable(variableId);

    const fields = formEl ? formEl.querySelectorAll("[data-gv-field]") : [];
    fields.forEach((el) => {
      el.disabled = true;
    });
    if (saveBtn) saveBtn.disabled = true;
    if (cancelBtn) cancelBtn.disabled = true;
    if (modalStatus) modalStatus.innerHTML = `<p class="placeholder-text">Saving changes…</p>`;

    try {
      const res = await fetch("/api/org/global-variables/" + encodeURIComponent(variableId), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      let data;
      try {
        data = await res.json();
      } catch (_) {
        throw new Error(res.status + " " + res.statusText);
      }
      if (data.error) throw new Error(data.error);
      if (!res.ok) throw new Error(res.status + " " + res.statusText);

      const updated = data.global_variable || {};
      const displayName = escapeHtml(updated.name || row?.name || variableId);
      const displayValue = escapeHtml(updated.value ?? values.defaultValue ?? "");
      closeReportModal();

      await refreshGlobalVariablesList({
        loadingMessage: "Refreshing global variables…",
        successMessage: `Updated <strong>${displayName}</strong> (default value <strong>${displayValue}</strong>)`,
      });
    } catch (e) {
      fields.forEach((el) => {
        el.disabled = false;
      });
      if (formEl) bindGlobalVariableFormDependencies(formEl);
      if (saveBtn) saveBtn.disabled = false;
      if (cancelBtn) cancelBtn.disabled = false;
      if (modalStatus) modalStatus.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`;
    }
  };

  const reportModalHistory = [];

  function isReportModalOpen() {
    const modal = document.getElementById("report-modal");
    return Boolean(modal && !modal.classList.contains("hidden"));
  }

  function snapshotReportModal() {
    const titleEl = document.getElementById("report-modal-title");
    const bodyEl = document.getElementById("report-modal-body");
    if (!titleEl || !bodyEl) return null;
    return { title: titleEl.textContent, body: bodyEl.innerHTML };
  }

  function syncReportModalBackButton() {
    const back = document.getElementById("report-modal-back");
    if (!back) return;
    const show = reportModalHistory.length > 0;
    back.classList.toggle("hidden", !show);
    back.disabled = !show;
  }

  function openReportModal(title, bodyHtml, options) {
    const opts = options || {};
    const modal = document.getElementById("report-modal");
    const titleEl = document.getElementById("report-modal-title");
    const bodyEl = document.getElementById("report-modal-body");
    if (opts.push && isReportModalOpen()) {
      const snap = snapshotReportModal();
      if (snap) reportModalHistory.push(snap);
    } else if (!opts.keepHistory) {
      reportModalHistory.length = 0;
    }
    titleEl.textContent = title;
    bodyEl.innerHTML = bodyHtml;
    modal.classList.remove("hidden");
    syncReportModalBackButton();
  }

  window.closeReportModal = function () {
    reportModalHistory.length = 0;
    const modal = document.getElementById("report-modal");
    if (modal) modal.classList.add("hidden");
    syncReportModalBackButton();
  };

  window.backReportModal = function (fallback) {
    if (reportModalHistory.length) {
      const prev = reportModalHistory.pop();
      openReportModal(prev.title, prev.body, { keepHistory: true });
      return;
    }
    if (fallback === "csr") {
      window.showCustomerDetails();
      return;
    }
    if (fallback === "asr") {
      window.showAgentDetails();
      return;
    }
    window.closeReportModal();
  };

  window.showReportQuery = async function (reportId, paramKey, paramValue) {
    openReportModal("GraphQL Query", "<p class='placeholder-text'>Loading query…</p>", { push: true });
    try {
      let url = "/api/reports/query/" + encodeURIComponent(reportId);
      if (paramKey && paramValue) {
        url += "?" + encodeURIComponent(paramKey) + "=" + encodeURIComponent(paramValue);
      }
      const data = await fetchJSON(url);
      let extra = "";
      if (data.rest) {
        extra =
          `<h4 class="modal-subheading">Live state update</h4>` +
          `<p class="toolbar-hint">${escapeHtml(data.rest.endpoint || "GET /v1/agents/activities")}</p>` +
          `<p>${escapeHtml(data.rest.how || "")}</p>` +
          `<pre class="modal-query">${escapeHtml(JSON.stringify(data.rest.params || {}, null, 2))}</pre>`;
      }
      openReportModal(
        data.label + " — GraphQL Query",
        `<p class="toolbar-hint">${escapeHtml(data.endpoint)}</p>` +
          `<h4 class="modal-subheading">Query</h4>` +
          `<pre class="modal-query">${escapeHtml(data.query)}</pre>` +
          `<h4 class="modal-subheading">Variables</h4>` +
          `<pre class="modal-query">${escapeHtml(JSON.stringify(data.variables, null, 2))}</pre>` +
          extra,
        { keepHistory: true }
      );
    } catch (e) {
      openReportModal("GraphQL Query", `<div class="error-box">${escapeHtml(e.message)}</div>`, { keepHistory: true });
    }
  };

  function detailModalToolbar(backFallback, queryReportId, queryParamKey, queryParamValue, infoKey) {
    let html = `<div class="section-toolbar" style="margin-bottom:1rem">`;
    if (backFallback) {
      html += `<button type="button" class="btn btn-secondary" onclick="backReportModal('${escapeAttr(backFallback)}')">Back</button>`;
    }
    if (queryReportId) {
      if (queryParamKey && queryParamValue) {
        html += `<button class="btn btn-secondary" onclick="showReportQuery('${escapeAttr(queryReportId)}','${escapeAttr(queryParamKey)}','${escapeAttr(queryParamValue)}')">Show query</button>`;
      } else {
        html += `<button class="btn btn-secondary" onclick="showReportQuery('${escapeAttr(queryReportId)}')">Show query</button>`;
      }
    }
    html += `</div>`;
    return html;
  }

  window.showCustomerDetails = async function () {
    openReportModal("Customer Session Details", "<p class='placeholder-text'>Loading CSR records…</p>");
    try {
      const data = await fetchJSON("/api/reports/csr-details");
      const rows = (data.records || []).map((row) => ({
        interaction_id: row.interaction_id
          ? `<button type="button" class="btn-link" onclick="showCarEvents('${escapeAttr(row.interaction_id)}')">${escapeAttr(row.interaction_id)}</button>`
          : "—",
        start_time: row.start_time,
        end_time: row.end_time,
        ani: row.ani,
        dnis: row.dnis,
        duration: row.duration,
      }));
      openReportModal(
        "Customer Session Details",
        detailModalToolbar(null, "csr-details", null, null, "csr-details") +
          buildTableHTML(
            [
              { key: "interaction_id", label: "Interaction ID", html: true },
              { key: "start_time", label: "Start Time" },
              { key: "end_time", label: "End Time" },
              { key: "ani", label: "ANI" },
              { key: "dnis", label: "DNIS" },
              { key: "duration", label: "Duration" },
            ],
            rows,
            null,
            "tbl-csr-details"
          ),
        { keepHistory: true }
      );
    } catch (e) {
      openReportModal("Customer Session Details", `<div class="error-box">${escapeHtml(e.message)}</div>`, { keepHistory: true });
    }
  };

  window.showCarEvents = async function (taskId) {
    openReportModal("CAR Events", `<p class='placeholder-text'>Loading CAR events for ${escapeAttr(taskId)}…</p>`, { push: true });
    try {
      const data = await fetchJSON("/api/reports/car/" + encodeURIComponent(taskId));
      openReportModal(
        `CAR Events — ${taskId}`,
        detailModalToolbar("csr", "car-events", "task_id", taskId, "car") +
          buildTableHTML(
            [
              { key: "event_name", label: "Events" },
              { key: "entry_point", label: "Entry Point" },
              { key: "queue_name", label: "Queue" },
              { key: "start_time", label: "Event Start Time" },
              { key: "end_time", label: "Event End Time" },
              { key: "duration", label: "Duration" },
            ],
            data.records || [],
            null,
            "tbl-car-events"
          ),
        { keepHistory: true }
      );
    } catch (e) {
      openReportModal(`CAR Events — ${taskId}`, `<div class="error-box">${escapeHtml(e.message)}</div>`, { keepHistory: true });
    }
  };

  window.showAgentDetails = async function () {
    openReportModal("Agent Session Details", "<p class='placeholder-text'>Loading ASR records…</p>");
    try {
      const data = await fetchJSON("/api/reports/asr-details");
      const rows = (data.records || []).map((row) => ({
        agent_session_id: row.agent_session_id
          ? `<button type="button" class="btn-link" onclick="showAarEvents('${escapeAttr(row.agent_session_id)}')">${escapeAttr(row.agent_session_id)}</button>`
          : "—",
        agent_name: row.agent_name,
        agent_login: row.agent_login,
        login_time: row.login_time,
        logout_time: row.logout_time,
      }));
      openReportModal(
        "Agent Session Details",
        detailModalToolbar(null, "asr-details", null, null, "asr-details") +
          buildTableHTML(
            [
              { key: "agent_session_id", label: "Agent Session ID", html: true },
              { key: "agent_name", label: "Agent Name" },
              { key: "agent_login", label: "Agent Login" },
              { key: "login_time", label: "Login Time" },
              { key: "logout_time", label: "Logout Time" },
            ],
            rows,
            null,
            "tbl-asr-details"
          ),
        { keepHistory: true }
      );
    } catch (e) {
      openReportModal("Agent Session Details", `<div class="error-box">${escapeHtml(e.message)}</div>`, { keepHistory: true });
    }
  };

  window.showAarEvents = async function (sessionId) {
    openReportModal("AAR Events", `<p class='placeholder-text'>Loading AAR events for ${escapeAttr(sessionId)}…</p>`, { push: true });
    try {
      const data = await fetchJSON("/api/reports/aar/" + encodeURIComponent(sessionId));
      openReportModal(
        `AAR Events — ${sessionId}`,
        detailModalToolbar("asr", "aar-events", "session_id", sessionId, "aar") +
          buildTableHTML(
            [
              { key: "state", label: "State" },
              { key: "start_time", label: "Event Start Time" },
              { key: "end_time", label: "Event End Time" },
              { key: "duration", label: "Duration" },
            ],
            data.records || [],
            null,
            "tbl-aar-events"
          ),
        { keepHistory: true }
      );
    } catch (e) {
      openReportModal(`AAR Events — ${sessionId}`, `<div class="error-box">${escapeHtml(e.message)}</div>`, { keepHistory: true });
    }
  };

  function renderWebexEntityBody(tab, payload) {
    if (tab.id === "people") {
      return buildTableHTML(
        [
          { key: "display_name", label: "Display Name" },
          { key: "email", label: "Email" },
          { key: "role_name", label: "Role Name" },
          { key: "license_names", label: "License Names", chips: true },
        ],
        (payload.people || []).slice(0, 20),
        ["display_name"],
        "tbl-people"
      );
    }
    if (tab.id === "locations") {
      return buildTableHTML(
        [
          { key: "name", label: "Location" },
          { key: "country", label: "Country" },
          { key: "provisioned_numbers", label: "Provisioned Numbers" },
          { key: "address", label: "Address" },
        ],
        payload.locations,
        ["name"],
        "tbl-locations"
      );
    }
    return buildTableHTML(
      [
        { key: "entry_point", label: "Entry Point" },
        { key: "number", label: "Number" },
        { key: "location_name", label: "Location" },
        { key: "connection_carrier", label: "Connection / Carrier" },
        { key: "country", label: "Country" },
      ],
      payload.numbers,
      ["entry_point", "number"],
      "tbl-pstn"
    );
  }

  async function loadWebexApis(force) {
    const el = document.getElementById("content-module4");
    if (!isModuleStarted("module4")) return;

    const tab = resolveWebexEntityTab("_webex4Tab");
    if (!tab) return;
    window._webex4Tab = tab.id;

    const needsFetch = force || webexCache[tab.cacheKey] === null;
    if (needsFetch) markRefreshing(el, true);
    try {
      const data = await ensureWebexSection(tab.cacheKey, tab.url, force);
      const html =
        webexEntityNav(tab.id, "selectWebex4Tab") +
        sectionToolbar("Refresh " + tab.label.toLowerCase(), "refreshModule4") +
        sectionBlock(
          tab.infoKey,
          tab.label,
          renderWebexEntityBody(tab, data),
          isNewSection("module4", tab.step),
          tab.infoKey
        );
      hidePlaceholder(el);
      setContent(el, html, force || needsFetch);
    } catch (e) {
      if (force) webexCache[tab.cacheKey] = null;
      renderError(el, e.message);
    } finally {
      markRefreshing(el, false);
    }
  }

  window.selectWebex4Tab = function (tabId) {
    window._webex4Tab = tabId;
    loadWebexApis(false);
  };

  window.refreshModule4 = function () {
    const tab = WEBEX_ENTITY_TABS.find((item) => item.id === window._webex4Tab);
    if (tab) webexCache[tab.cacheKey] = null;
    loadWebexApis(true);
  };

  window.showSectionInfo = async function (sectionId) {
    openReportModal("About this section", "<p class='placeholder-text'>Loading…</p>", { push: true });
    try {
      const data = await fetchJSON("/api/dashboard/info/" + encodeURIComponent(sectionId));
      const rows = (data.endpoints || [])
        .map((ep) => {
          const docs = ep.docs
            ? `<a class="lab-api-link" href="${escapeAttr(ep.docs)}" target="_blank" rel="noopener noreferrer">Reference</a>`
            : "—";
          return (
            `<tr><td><code>${escapeHtml(ep.method)}</code></td>` +
            `<td><code>${escapeHtml(ep.path)}</code></td>` +
            `<td>${escapeHtml(ep.role || "")}</td>` +
            `<td>${docs}</td></tr>`
          );
        })
        .join("");
      const labelItems = (data.labels || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
      const query = data.query || {};
      let queryHtml = "";
      if (query.query) {
        queryHtml =
          `<h4 class="modal-subheading">GraphQL query</h4>` +
          `<p class="toolbar-hint">${escapeHtml(query.endpoint || "POST /search?orgId={orgId}")}</p>` +
          `<pre class="modal-query">${escapeHtml(query.query)}</pre>`;
        if (query.variables) {
          queryHtml +=
            `<h4 class="modal-subheading">Variables</h4>` +
            `<pre class="modal-query">${escapeHtml(JSON.stringify(query.variables, null, 2))}</pre>`;
        }
        if (query.rest) {
          queryHtml +=
            `<h4 class="modal-subheading">Live state update</h4>` +
            `<p class="toolbar-hint">${escapeHtml(query.rest.endpoint || "GET /v1/agents/activities")}</p>` +
            `<p>${escapeHtml(query.rest.how || "")}</p>` +
            `<pre class="modal-query">${escapeHtml(JSON.stringify(query.rest.params || {}, null, 2))}</pre>`;
        }
      }
      openReportModal(
        data.title || "About this section",
        `<p class="toolbar-hint">HTTP ${escapeHtml(data.method || "GET")}</p>` +
          `<table class="data-table info-table"><thead><tr><th>Method</th><th>Endpoint</th><th>Used for</th><th>Docs</th></tr></thead><tbody>${rows}</tbody></table>` +
          `<h4 class="modal-subheading">How the dashboard uses this data</h4>` +
          `<p>${escapeHtml(data.how || "")}</p>` +
          (labelItems
            ? `<h4 class="modal-subheading">How labels and counts are generated</h4><ul class="info-label-list">${labelItems}</ul>`
            : "") +
          queryHtml,
        { keepHistory: true }
      );
    } catch (e) {
      openReportModal("About this section", `<div class="error-box">${escapeHtml(e.message)}</div>`, { keepHistory: true });
    }
  };

  window.selectDash5Tab = function (tabId) {
    window._dash5Tab = tabId;
    loadFullDashboard(false);
  };

  window.selectDash5OrgTab = function (tabId) {
    window._dash5OrgTab = tabId;
    loadFullDashboard(false);
  };

  window.selectDash5WebexTab = function (tabId) {
    window._dash5WebexTab = tabId;
    loadFullDashboard(false);
  };

  function dashInnerNavHtml(tabs, activeId) {
    let nav = `<div class="dash-inner-nav">`;
    tabs.forEach((tab) => {
      const ready = isModuleComplete(tab.module);
      const cls = `dash-inner-tab${tab.id === activeId && ready ? " active" : ""}${ready ? "" : " locked"}`;
      if (ready) {
        nav += `<button type="button" class="${cls}" onclick="selectDash5Tab('${tab.id}')">${escapeHtml(tab.label)}</button>`;
      } else {
        nav += `<button type="button" class="${cls}" disabled title="Complete ${escapeAttr(tab.label)} to unlock">${escapeHtml(tab.label)}</button>`;
      }
    });
    nav += `</div>`;
    return nav;
  }

  async function loadFullDashboard(force) {
    const el = fullDashboardRoot();
    if (!el) return;

    const tabs = [
      { id: "users", module: "module1", label: "Users" },
      { id: "org", module: "module2", label: "Org Data" },
      { id: "reports", module: "module3", label: "Reports" },
      { id: "webex", module: "module4", label: "Webex APIs" },
    ];
    const unlocked = tabs.filter((tab) => isModuleComplete(tab.module));
    const active = unlocked.some((tab) => tab.id === window._dash5Tab)
      ? window._dash5Tab
      : unlocked[0]
        ? unlocked[0].id
        : "";
    window._dash5Tab = active;
    syncDashboardUrl();
    const nav = dashInnerNavHtml(tabs, active);

    if (!unlocked.length) {
      const emptyMsg = isSetupComplete()
        ? "Unable to load dashboard sections. Check the browser console and API responses."
        : "Connect with your access token and organization ID to load Users, Org Data, Reports, and Webex APIs.";
      setContent(el, nav + `<p class="placeholder-text">${emptyMsg}</p>`, force);
      return;
    }

    const webexTab = active === "webex" ? resolveWebexEntityTab("_dash5WebexTab") : null;
    const waitingOnWebex = Boolean(webexTab && webexCache[webexTab.cacheKey] === null);
    const orgTab = active === "org" ? resolveOrgEntityTab("_dash5OrgTab") : null;
    const waitingOnOrg = Boolean(orgTab && orgCache[orgTab.cacheKey] === null);
    if (force || waitingOnWebex || waitingOnOrg) {
      hidePlaceholder(el);
      if (waitingOnWebex) {
        setContent(
          el,
          nav + `<p class="placeholder-text">Loading Webex APIs… first load is cached for later visits.</p>`,
          true
        );
      }
      markRefreshing(el, true);
    }
    try {
      let body = "";
      if (active === "users") {
        if (force || usersCache === null) usersCache = await fetchJSON("/api/users", { force });
        body = dashSectionRefresh("users", "Refresh users") + renderUsersTable(usersCache);
      } else if (active === "org") {
        body = await buildOrgDashboardHtml(force);
      } else if (active === "reports") {
        body = await buildReportsDashboardHtml(force);
      } else if (active === "webex") {
        body = await buildWebexDashboardHtml(force);
      }
      hidePlaceholder(el);
      setContent(
        el,
        nav +
          '<div class="section-toolbar"><button type="button" class="btn btn-secondary" onclick="refreshFullDashboardTab()">Refresh this tab</button><span class="toolbar-hint">GET responses are cached so switching tabs does not re-hit the APIs.</span></div>' +
          body,
        true
      );
      if (active === "reports") syncRtPolling(true);
    } catch (e) {
      renderError(el, e.message);
    } finally {
      markRefreshing(el, false);
    }
  }

  window.refreshFullDashboardTab = function () {
    const tab = window._dash5Tab;
    if (tab === "users") usersCache = null;
    if (tab === "org") {
      const orgTab = resolveOrgEntityTab("_dash5OrgTab");
      if (orgTab) orgCache[orgTab.cacheKey] = null;
    }
    if (tab === "reports") {
      Object.keys(reportCache).forEach((key) => { reportCache[key] = null; });
      rtAgentsCache = null;
    }
    if (tab === "webex") {
      webexCache.people = null;
      webexCache.locations = null;
      webexCache.ep_pstn = null;
    }
    loadFullDashboard(true);
  }

  window.refreshDash5Section = async function (kind) {
    const el = fullDashboardRoot();
    markRefreshing(el, true);
    try {
      if (kind === "users") usersCache = await fetchJSON("/api/users", { force: true });
      else if (kind === "entry_points") orgCache.entry_points = await fetchJSON("/api/org/entry-points", { force: true });
      else if (kind === "queues") orgCache.queues = await fetchJSON("/api/org/queues", { force: true });
      else if (kind === "teams") orgCache.teams = await fetchJSON("/api/org/teams", { force: true });
      else if (kind === "aux_codes") orgCache.aux_codes = await fetchJSON("/api/org/aux-codes", { force: true });
      else if (kind === "global_variables") orgCache.global_variables = await fetchJSON("/api/org/global-variables", { force: true });
      else if (kind === "people") webexCache.people = await fetchJSON("/api/webex/people", { force: true });
      else if (kind === "locations") webexCache.locations = await fetchJSON("/api/webex/locations", { force: true });
      else if (kind === "ep_pstn") webexCache.ep_pstn = await fetchJSON("/api/webex/ep-pstn", { force: true });
      else if (kind === "rt-agents") {
        rtAgentsCache = await fetchJSON("/api/reports/rt-agents");
        lastRtFingerprint = rtFingerprint(rtAgentsCache.agents);
      }
      await loadFullDashboard(false);
    } catch (e) {
      renderError(el, e.message);
    } finally {
      markRefreshing(el, false);
    }
  };

  async function buildOrgDashboardHtml(force) {
    const tab = resolveOrgEntityTab("_dash5OrgTab");
    if (!tab) return "";
    window._dash5OrgTab = tab.id;
    const data = await ensureOrgSection(tab.cacheKey, tab.url, force);
    return (
      orgEntityNav(tab.id, "selectDash5OrgTab") +
      sectionBlock(
        tab.infoKey,
        tab.label,
        dashSectionRefresh(tab.cacheKey, "Refresh " + tab.label.toLowerCase()) +
          renderOrgEntityBody(tab, data),
        false,
        tab.infoKey
      )
    );
  }

  async function buildReportsDashboardHtml(force) {
    const reportTasks = REPORT_DEFS.filter((def) => isStepComplete("module3", def.step)).map(async (def) => {
      const cached = await ensureReportCached(def.id, force);
      return buildReportCard(def, cached);
    });
    const cards = reportTasks.length ? await Promise.all(reportTasks) : [];
    let html = '<div class="card-grid">' + cards.join("") + "</div>";
    html += sessionDetailsSectionsHtml();
    if (isStepComplete("module3", "3.5")) {
      if (force || !rtAgentsCache) {
        rtAgentsCache = await fetchJSON("/api/reports/rt-agents");
        lastRtFingerprint = rtFingerprint(rtAgentsCache.agents);
      }
      html += sectionBlock(
        "rt-agents",
        "Real-Time Agent States",
        `<div class="section-toolbar"><button class="btn btn-secondary" onclick="refreshLiveAgents()">Refresh agent data</button></div>` +
          `<div id="rt-agents-table">${buildTableHTML(RT_AGENT_COLUMNS, rtAgentsCache.agents, ["name"], "tbl-rt-agents")}</div>` +
          RT_POLLING_NOTE,
        false,
        "rt-agents"
      );
    }
    return html;
  }

  async function buildWebexDashboardHtml(force) {
    const tab = resolveWebexEntityTab("_dash5WebexTab");
    if (!tab) return "";
    window._dash5WebexTab = tab.id;
    const data = await ensureWebexSection(tab.cacheKey, tab.url, force);
    return (
      webexEntityNav(tab.id, "selectDash5WebexTab") +
      sectionBlock(
        tab.infoKey,
        tab.label,
        dashSectionRefresh(tab.cacheKey, "Refresh " + tab.label.toLowerCase()) +
          renderWebexEntityBody(tab, data),
        false,
        tab.infoKey
      )
    );
  }

  function invalidateCachesForModules(moduleIds) {
    if (moduleIds.has("module1")) {
      usersCache = null;
    }
    if (moduleIds.has("module2")) {
      orgCache.entry_points = null;
      orgCache.queues = null;
      orgCache.global_variables = null;
      orgCache.aux_codes = null;
      orgCache.teams = null;
    }
    if (moduleIds.has("module3")) {
      REPORT_DEFS.forEach((def) => {
        reportCache[def.id] = null;
      });
      rtAgentsCache = null;
      lastRtFingerprint = "";
    }
    if (moduleIds.has("module4")) {
      webexCache.people = null;
      webexCache.locations = null;
      webexCache.ep_pstn = null;
    }
    moduleIds.forEach((id) => loadedModules.delete(id));
  }

  async function reloadAllSections(options) {
    const opts = options || {};
    const newlyCompleted = opts.newlyCompleted || [];
    applyOrgTabFromCompleted(newlyCompleted);
    applyWebexTabFromCompleted(newlyCompleted);
    const touchedModules = new Set(newlyCompleted.map((n) => n.moduleId));

    if (touchedModules.size) {
      if (touchedModules.has("module2") || touchedModules.has("module4")) {
        touchedModules.add("module2");
        touchedModules.add("module4");
      }
      invalidateCachesForModules(touchedModules);
    }

    if (isStandaloneDashboard()) {
      await loadFullDashboard(touchedModules.size > 0);
      return;
    }

    const force = (key) => touchedModules.has(key);
    const active = getActiveModuleId();

    if (!touchedModules.size) {
      await ensureModuleLoaded(active, false);
      return;
    }

    if (touchedModules.has(active)) {
      await ensureModuleLoaded(active, force(active));
    }

    [...touchedModules]
      .filter((id) => id !== active)
      .forEach((id) => {
        ensureModuleLoaded(id, force(id));
      });
  }

  async function refreshProgress() {
    try {
      const res = await fetchJSON("/api/progress");
      const fingerprint = progressFingerprint(res);
      const progressChanged = fingerprint !== lastProgressFingerprint;
      const newlyCompleted = progressChanged ? detectNewlyCompletedSteps(res) : [];

      if (progressChanged) {
        window._newSections = new Set(newlyCompleted.map((n) => stepKey(n.moduleId, n.stepId)));
        lastProgressFingerprint = fingerprint;
      }

      window.LAB_PROGRESS = res;
      updateProgressUI(res, newlyCompleted);

      // Update step nav chips only — do not re-render the form while the user is typing.
      res.modules.forEach((mod) => updateStepNav(mod.module_id));

      if (progressChanged) {
        res.modules.forEach((mod) => {
          if (isModuleActive(mod.module_id)) {
            renderModuleWorkspace(mod.module_id);
          }
        });
        await reloadAllSections({ newlyCompleted });
        if (isStepComplete("module3", "3.5")) {
          syncRtPolling(isRtViewActive());
        }
        setTimeout(() => {
          window._newSections = new Set();
          document.querySelectorAll(".newly-unlocked").forEach((el) => el.classList.remove("newly-unlocked"));
        }, 3000);
      }
    } catch (_) { /* server may be restarting */ }
  }

  window.addEventListener("message", (event) => {
    if (event.origin !== window.location.origin) return;
    if (!event.data || event.data.type !== "lab21190-oauth-code") return;
    selectSetupAuthMethod("integration");
  });

  lastProgressFingerprint = progressFingerprint(getProgress());
  getProgress().modules.forEach((mod) => {
    mod.steps.forEach((step) => {
      previousStepState[stepKey(mod.module_id, step.id)] = step.complete;
    });
  });

  if (isStandaloneDashboard()) {
    applyDashboardUrlState();
    updateConfigBanner(window.LAB_CONFIG_STATUS);
    loadFullDashboard(false).then(() => {
      if (isStepComplete("module3", "3.5")) {
        syncRtPolling(isRtViewActive());
      }
    });
  } else {
    loadLabWorkspace().then(() => {
      updateModuleTabLocks();
      updateConfigBanner(window.LAB_CONFIG_STATUS);
      renderSetupStatus(window.LAB_CONFIG_STATUS);
      ensureModuleLoaded(getActiveModuleId(), false).then(() => {
        if (isStepComplete("module3", "3.5")) {
          syncRtPolling(isRtViewActive());
        }
      });
    });
  }
  setInterval(refreshProgress, 5000);
})();
