// Dispatches .github/workflows/collect.yml on main. Needs a fine-grained token
// scoped to ignaciovi/gta6-effect with only "Actions: Read and write".
const URL = "https://api.github.com/repos/ignaciovi/gta6-effect/actions/workflows/collect.yml/dispatches";

async function dispatch(env) {
  const r = await fetch(URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "gta6-effect-timer",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  if (r.status !== 204) throw new Error(`dispatch failed: ${r.status} ${await r.text()}`);
  console.log("workflow dispatched");
}

export default {
  async scheduled(_event, env, ctx) {
    ctx.waitUntil(dispatch(env));
  },
};
