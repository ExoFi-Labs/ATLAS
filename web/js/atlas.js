const ASCII = `
 █████╗ ████████╗██╗      █████╗ ███████╗
██╔══██╗╚══██╔══╝██║     ██╔══██╗██╔════╝
███████║   ██║   ██║     ███████║███████╗
██╔══██║   ██║   ██║     ██╔══██║╚════██║
██║  ██║   ██║   ███████╗██║  ██║███████║
╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚══════╝`.trim();

function nav(active) {
  return `
    <div class="topbar">
      <div class="brand">ATLAS</div>
      <nav class="nav">
        <a href="/" class="${active === "chat" ? "active" : ""}">Chat</a>
        <a href="/qdrant.html" class="${active === "qdrant" ? "active" : ""}">Qdrant</a>
        <a href="/ollama.html" class="${active === "ollama" ? "active" : ""}">Ollama</a>
        <a href="/about.html" class="${active === "about" ? "active" : ""}">About</a>
        <a href="/settings.html" class="${active === "settings" ? "active" : ""}">Settings</a>
      </nav>
    </div>`;
}

function terminal(subtitle) {
  return `
    <section class="terminal">
      <div class="term-bar">
        <span class="dot r"></span><span class="dot y"></span><span class="dot g"></span>
        atlas@local — secure shell
      </div>
      <div class="term-body">
        <pre class="ascii">${ASCII}</pre>
        <p class="term-sub">> ${subtitle}<span class="cursor"></span></p>
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
