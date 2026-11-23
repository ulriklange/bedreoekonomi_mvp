import { DurableObject } from "cloudflare:workers";

const APP_PORT = 8080;
const INACTIVITY_TIMEOUT_MS = 10 * 60 * 1000;

export class AppContainer extends DurableObject {
  starting;

  async fetch(request) {
    const container = this.ctx.container;
    this.starting ??= this.startAndWaitForApp().finally(() => {
      this.starting = undefined;
    });
    await this.starting;

    const url = new URL(request.url);
    url.protocol = "http:";
    url.host = "container";
    const forwarded = new Request(url, request);
    forwarded.headers.delete("host");
    return container.getTcpPort(APP_PORT).fetch(forwarded);
  }

  async startAndWaitForApp() {
    const container = this.ctx.container;
    await container.setInactivityTimeout(INACTIVITY_TIMEOUT_MS);

    if (!container.running) {
      const required = ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"];
      const missing = required.filter((name) => !this.env[name]);
      if (missing.length) {
        throw new Error(`Missing Cloudflare Worker secrets: ${missing.join(", ")}`);
      }

      container.start({
        image: container.images.base,
        enableInternet: true,
        env: {
          DB_HOST: this.env.DB_HOST,
          DB_NAME: this.env.DB_NAME,
          DB_USER: this.env.DB_USER,
          DB_PASSWORD: this.env.DB_PASSWORD,
          DB_SSLMODE: this.env.DB_SSLMODE || "require",
        },
      });
    }

    const port = container.getTcpPort(APP_PORT);
    let lastError;
    for (let attempt = 0; attempt < 100; attempt += 1) {
      try {
        const response = await port.fetch("http://container/health", {
          signal: AbortSignal.timeout(1000),
        });
        await response.body?.cancel();
        if (!response.ok) {
          throw new Error(`Health check returned ${response.status}`);
        }
        return;
      } catch (error) {
        lastError = error;
        await scheduler.wait(200);
      }
    }

    throw new Error("Bedre Økonomi containeren blev ikke klar på port 8080", {
      cause: lastError,
    });
  }
}

export default {
  async fetch(request, env, ctx) {
    // Fail closed: no requests reach the finance app until Cloudflare Access
    // has authenticated the visitor.
    if (!ctx.access) {
      return new Response("Cloudflare Access login required", { status: 403 });
    }

    return env.APP_CONTAINER.getByName("dashboard").fetch(request);
  },
};
