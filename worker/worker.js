/**
 * Cloudflare Worker que deixa a página disparar a atualização sem abrir o GitHub.
 *
 * Variáveis (Settings → Variables and Secrets do Worker):
 *   GITHUB_TOKEN   (secret)  token fine-grained com "Actions: Read and write" só neste repositório
 *   CODIGO         (secret)  código que os capitães digitam para atualizar
 *   REPO           (texto)   ex.: flavio/sc2-cw-monitor
 *   ORIGEM         (texto)   endereço da página, ex.: https://flavio.github.io  (ou seu domínio)
 *
 * Rotas:
 *   POST /atualizar  {codigo, matchups}  dispara o workflow
 *   GET  /status                          situação da última atualização
 */
const WORKFLOW = "coletar.yml";

export default {
  async fetch(req, env) {
    const cors = {
      "Access-Control-Allow-Origin": env.ORIGEM || "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Vary": "Origin",
    };
    const json = (body, status = 200) =>
      new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });
    if (req.method === "OPTIONS") return new Response(null, { headers: cors });

    const gh = (path, init = {}) =>
      fetch(`https://api.github.com/repos/${env.REPO}${path}`, {
        ...init,
        headers: {
          Authorization: `Bearer ${env.GITHUB_TOKEN}`,
          Accept: "application/vnd.github+json",
          "User-Agent": "sc2-cw-monitor-worker",
          "X-GitHub-Api-Version": "2022-11-28",
          ...(init.headers || {}),
        },
      });

    const lastRun = async () => {
      const r = await gh(`/actions/workflows/${WORKFLOW}/runs?per_page=1`);
      if (!r.ok) return null;
      const run = (await r.json()).workflow_runs?.[0];
      return run ? { status: run.status, conclusion: run.conclusion, criado_em: run.created_at, atualizado_em: run.updated_at } : null;
    };

    const url = new URL(req.url);
    if (url.pathname === "/status" && req.method === "GET") {
      return json({ ultima: await lastRun() });
    }

    if (url.pathname === "/atualizar" && req.method === "POST") {
      let body = {};
      try { body = await req.json(); } catch {}
      if (!env.CODIGO || body.codigo !== env.CODIGO) return json({ erro: "Código de atualização incorreto." }, 403);

      const atual = await lastRun();
      if (atual && atual.status !== "completed") return json({ ok: true, ja_rodando: true, ultima: atual });

      const r = await gh(`/actions/workflows/${WORKFLOW}/dispatches`, {
        method: "POST",
        body: JSON.stringify({ ref: "main", inputs: { recalcular_matchups: body.matchups ? "true" : "false" } }),
      });
      if (r.status !== 204) return json({ erro: `O GitHub recusou o pedido (${r.status}). Confira o token e o nome do repositório.` }, 502);
      return json({ ok: true });
    }

    return json({ erro: "Rota não encontrada." }, 404);
  },
};
