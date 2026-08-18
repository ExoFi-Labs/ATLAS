const ASCII_BANNER = `
██████ █████   ████   █████               ████  ██████ ██      ████   █████
██     ██  ██ ██  ██ ██                  ██  ██   ██   ██     ██  ██ ██
█████  █████  ██  ██  ████      ████     ██████   ██   ██     ██████  ████
██     ██  ██ ██  ██     ██              ██  ██   ██   ██     ██  ██     ██
██████ █████   ████  █████               ██  ██   ██   ██████ ██  ██ █████`.trim();

function nav(active) {
  const link = (id, href, label) =>
    `<a href="${href}"${active === id ? ' aria-current="page" class="active"' : ""}>${label}</a>`;
  return `
    <header class="topbar">
      <a class="brand" href="/">ATLAS</a>
      <nav class="nav" aria-label="Primary">
        ${link("chat", "/", "Chat")}
        ${link("qdrant", "/qdrant.html", "Qdrant")}
        ${link("ollama", "/ollama.html", "Ollama")}
        ${link("about", "/about.html", "About")}
        ${link("settings", "/settings.html", "Settings")}
      </nav>
    </header>`;
}

function terminal(title, kicker) {
  return `
    <section class="masthead">
      <div class="terminal">
        <div class="term-bar">
          <span class="dot r" aria-hidden="true"></span>
          <span class="dot y" aria-hidden="true"></span>
          <span class="dot g" aria-hidden="true"></span>
          <span class="term-title">atlas@local</span>
        </div>
        <div class="term-body">
          <pre class="ascii" aria-hidden="true">${ASCII_BANNER}</pre>
          <h1 class="term-prompt"><span aria-hidden="true">&gt; </span>${title}<span class="cursor" aria-hidden="true"></span></h1>
          ${kicker ? `<p class="term-kicker">${kicker}</p>` : ""}
        </div>
      </div>
    </section>`;
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : "Request failed");
  }
  return data;
}

function bytes(n) {
  if (!n) return "0 B";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
