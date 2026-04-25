# Deployment Checklist

Quick steps to go live on Render + Vercel + R2. Follow in order.

## ✅ Pre-Deployment (Local)

- [ ] **Code committed to GitHub** with `.env` excluded (check `.gitignore`)
- [ ] **Verify local build works:**
  ```bash
  docker-compose up -d
  # Test: curl http://localhost:8000/api/health
  ```
- [ ] **Environment variables ready** (see `.env.example`):
  - Google Gemini API key
  - Cloudflare R2 bucket name, credentials, endpoint
  - Qdrant API key (generate a strong random string)

## ✅ Step 1: Cloudflare R2 Setup

- [ ] **Create R2 bucket:** `research-rag-storage`
- [ ] **Generate API token** with Object Read/Write permissions
- [ ] **Copy credentials:**
  - Access Key ID
  - Secret Access Key
  - Endpoint URL: `https://<account-id>.r2.cloudflarestorage.com`
- [ ] **Store securely** (not in code or chat)

## ✅ Step 2: Render PostgreSQL

- [ ] **Create PostgreSQL service:**
  - Name: `research-rag-postgres`
  - Database: `research_rag`
  - Plan: Free
- [ ] **Copy external database URL** (connection string)
- [ ] **Wait for creation** (~1-2 min)

## ✅ Step 3: Render Qdrant

- [ ] **Create web service** (Docker):
  - Name: `research-rag-qdrant`
  - Start command: `./qdrant`
- [ ] **Set environment:** `QDRANT_API_KEY=<strong_random_key>`
- [ ] **Copy service URL** (will look like `https://research-rag-qdrant.onrender.com`)
- [ ] **Wait for deployment** (~5-10 min)

## ✅ Step 4: Render Backend

- [ ] **Connect GitHub repo** to Render
- [ ] **Create web service:**
  - Name: `research-rag-backend`
  - Root directory: `backend`
  - Start command: `uvicorn main:app --host 0.0.0.0 --port 8000`
  - Plan: Free
- [ ] **Set ALL environment variables:**
  ```
  DATABASE_URL=<from Postgres service>
  QDRANT_HOST=<R2 service URL>
  QDRANT_PORT=6333
  QDRANT_API_KEY=<same key as R2>
  LLM_PROVIDER=gemini
  GEMINI_API_KEY=<your Gemini key>
  STORAGE_BACKEND=s3
  STORAGE_S3_BUCKET=research-rag-storage
  STORAGE_S3_REGION=auto
  STORAGE_S3_ENDPOINT=<R2 endpoint URL>
  STORAGE_S3_ACCESS_KEY=<R2 access key>
  STORAGE_S3_SECRET_KEY=<R2 secret key>
  CORS_ORIGINS=https://<vercel-domain>.vercel.app
  ```
- [ ] **Check deployment logs** for errors
- [ ] **Test health:** `curl https://<backend>.onrender.com/api/health`
- [ ] **Copy backend URL**

## ✅ Step 5: Vercel Frontend

- [ ] **Deploy to Vercel:**
  - GitHub repo integration
  - Root directory: `frontend`
- [ ] **Set environment variable:**
  ```
  NEXT_PUBLIC_API_URL=https://<backend>.onrender.com/api
  ```
- [ ] **Trigger rebuild** after env change
- [ ] **Wait for deployment** (~3-5 min)
- [ ] **Test in browser:** Open Vercel domain

## ✅ Step 6: Production Verification

- [ ] **Frontend loads** without errors (check console)
- [ ] **Upload a PDF** and verify it works
- [ ] **Ask a question** and get an answer
- [ ] **Check evidence figures** display correctly
- [ ] **Verify CORS error doesn't appear**

## ✅ Step 7: Security & Hardening

- [ ] **Rotate Gemini API key** if exposed in previous chats
- [ ] **Rotate R2 credentials** if shared
- [ ] **Enable Vercel domain protection** (optional)
- [ ] **Update DEPLOYMENT.md** with your actual URLs

## ✅ Ongoing Maintenance

- [ ] **Monitor Render logs** weekly (free tier has limits)
- [ ] **Test health endpoint** regularly: `curl https://<backend>/api/health`
- [ ] **Archive old PDFs** if storage quota fills up
- [ ] **Plan upgrade path** if traffic increases

---

## Estimated Time

- R2 setup: 5 min
- Render services: 20–30 min
- Vercel deploy: 5 min
- **Total: ~35–40 min**

---

## Common Issues

| Issue | Fix |
|-------|-----|
| Backend doesn't start | Check logs in Render; verify all env vars set |
| Frontend shows 502 error | Backend likely crashing; check `DATABASE_URL` and `GEMINI_API_KEY` |
| Figures show as black | Verify R2 credentials and endpoint; test with `aws s3` CLI |
| CORS error in console | Check `CORS_ORIGINS` matches exact Vercel domain |
| Slow builds on Render | Free tier has limited resources; consider moving to paid tier |

---

**Questions?** See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed troubleshooting.
