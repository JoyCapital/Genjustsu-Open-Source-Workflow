# Railway: safe, read-only preview

This Docker image serves the **real FastAPI app and its static UI**, not a
replacement landing page. It is deliberately **not generation-ready**. It has
only FastAPI, Uvicorn and multipart parsing (plus their Python dependencies),
with no video-processing packages, provider credentials, source uploads or saved
results. No paid inference is needed to build, start or inspect this preview.
Railway hosting itself can incur charges under your Railway plan.

## Deploy the preview

1. Deploy this repository to a Railway service using the root `Dockerfile`.
   Keep the repository root as the build context. Do not override the container's
   start command: it runs `uvicorn app:app` on `0.0.0.0:${PORT:-8000}`.
2. Keep `GENJUSTSU_HOSTED=1` and `GENJUSTSU_DEMO=1`. Both are image defaults;
   explicitly setting them in the service makes the preview's intent visible.
   The app also recognizes Railway's environment as hosted.
3. Configure Railway's HTTP health check as `/health` and generate a public
   domain for the service. The health check remains public and reports app
   availability, **not** processing or provider readiness.
4. Do **not** add provider/API credentials, upload private media, attach an
   existing `runs` directory, or connect a processing worker to this demo.
   A public UI is sufficient for the preview; no password is required to view it.

The container runs as an unprivileged `genjustsu` user. Only its empty `runs`
directory is writable for app initialization. The build context is allowlisted
by `.dockerignore`; only the Dockerfile, app source and static assets are sent.
Keep `static/` public-only: everything there is intentionally served publicly.

## Access and safety behavior

- `/`, `/static/…`, `/health` and `/capabilities` are public. The UI identifies demo mode as
  read-only; do not treat a visible upload form as permission to process media.
- Hosted mode uses HTTP Basic authentication with the fixed username
  `genjustsu` and the password in `GENJUSTSU_PASSWORD` for protected routes.
  A missing password fails closed for `/jobs`, `/runs`, API documentation/schema
  and mutations; it does not hide the public UI or health check.
- `GENJUSTSU_DEMO=1` is a stronger restriction: mutations, private job/results
  access (including API documentation/schema) and saved-generation startup resume
  are blocked **even with a valid password**. Hosted mode also disables startup
  resume. Adding a password does not enable generation in this image.
- If a future non-demo deployment needs a password, supply a unique strong value
  through Railway's service variables/secrets, never in source, a build argument,
  an image layer, a URL or shell history. Use HTTPS and avoid shared-browser
  Basic-auth sessions for private operations.

Do not disable demo mode to test paid processing on this preview. This image
intentionally does not copy the processing modules and does not install FFmpeg,
Demucs, model runtimes or provider clients. A real generation deployment needs a
separate, explicitly authorized setup following [SETUP-AGENT.md](SETUP-AGENT.md),
including processing dependencies, private credential injection, durable private
storage and the required visual review/submission workflow. A healthy preview
is not evidence that any of those requirements are satisfied.

## Local container smoke check

```bash
docker build -t genjustsu-preview .
docker run --rm -p 8000:8000 genjustsu-preview
```

In another shell:

```bash
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/ > /dev/null
curl -i http://localhost:8000/jobs/00000000000000000000000000000000
curl -i http://localhost:8000/runs/00000000000000000000000000000000/upload.mp4
curl -i http://localhost:8000/docs
curl -i -X POST http://localhost:8000/jobs
```

The first two checks should succeed. Protected/private routes and mutations must
return a rejection, never private artifacts or a job ID. Open the UI and verify
its read-only indication; do not submit media or call providers. Also verify
`/openapi.json` and `/redoc` are blocked. Repeat private-route and mutation checks
with valid Basic credentials in an isolated test service: demo mode must still
reject them. Test credentials are not provider keys and must not be published.
Use `-e PORT=8080 -p 8080:8080` instead to check Railway-style port configuration.

On Railway, repeat these checks over the generated HTTPS domain after deployment
and confirm the deployed revision. A successful local test does not establish
that the intended build is deployed or that the live service has the same flags.

## Preview lifecycle

No volume is needed: this preview has no saved jobs to preserve. Do not reuse
this service as a private result store. Remove the preview service when it is no
longer needed. If deployment fails, inspect build/start logs without posting
secret values; check the Dockerfile builder, injected `PORT`, `/health` path and
hosted/demo flags before changing security settings.
