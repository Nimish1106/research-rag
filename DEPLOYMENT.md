# Deployment Guide: Render + Vercel + Cloudflare R2

This guide walks through deploying **research-rag** to production using free-tier services: Render (backend), Vercel (frontend), and Cloudflare R2 (object storage).

---

## Prerequisites

- GitHub repo with this code committed
- Render account (free tier)
- Vercel account (free tier)
- Cloudflare account with R2 enabled
- Google Gemini API key
- Environment values ready (see `.env.example`)

---

## 1. Cloudflare R2 Setup (Object Storage)

1. **Create R2 Bucket:**
   - Go to Cloudflare Dashboard → R2 → Create bucket
   - Name: `research-rag-storage` (or preferred name)
   - Region: `wnam` (nearest to you, no extra cost)

2. **Generate API Token:**
   - R2 → API Tokens → Create API Token
   - Name: `research-rag-api`
   - **Permissions:**
     - `Admin - Object List Read/Write` (or custom: GetObject, PutObject, DeleteObject, ListBucket)
     - Apply to bucket: `research-rag-storage`
   - Copy: **Access Key ID** and **Secret Access Key**

3. **Get Endpoint:**
   - Go to R2 Settings → Endpoints
   - Copy the S3 API URL: `https://<account-id>.r2.cloudflarestorage.com`

---

## 2. PostgreSQL on Render

1. **Create Database:**
   - Render Dashboard → New → PostgreSQL
   - **Name:** `research-rag-postgres`
   - **Database:** `research_rag`
   - **User:** `postgres`
   - **Region:** (select closest to users)
   - **PostgreSQL Version:** 15
   - **Plan:** Free (500MB storage limit)
   - Click Create

2. **Copy Connection String:**
   - Once created, copy the **External Database URL** (looks like `postgresql://user:password@host:port/db`)
   - Store securely (contains credentials)

---

## 3. Qdrant Vector DB on Render

Qdrant doesn't have native Render support, so we use a Docker container approach:

1. **Create Web Service:**
   - Render Dashboard → New → Web Service
   - **Name:** `research-rag-qdrant`
   - **Runtime:** Docker
   - **Build Command:** (leave empty, uses built-in Dockerfile)
   - **Start Command:** `./qdrant`
   - **Plan:** Free
   - Deploy

2. **Set Environment:**
   - In Service Settings → Environment:
     ```
     QDRANT_API_KEY=your_strong_random_key_here
     ```
   - Redeploy

3. **Get Service URL:**
   - After deployment, copy the service URL: `https://research-rag-qdrant.onrender.com`

---

## 4. Backend API on Render

1. **Create Web Service:**
   - Render Dashboard → New → Web Service
   - **GitHub Repo:** Select your repo
   - **Branch:** `main` (or your branch)
   - **Name:** `research-rag-backend`
   - **Root Directory:** `backend`
   - **Runtime:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port 8000`
   - **Plan:** Free
   - Click Create

2. **Configure Environment Variables:**
   - In Service Settings → Environment, add all from `.env`:
     ```
     DATABASE_URL=postgresql://user:pass@host:5432/research_rag
     QDRANT_HOST=https://research-rag-qdrant.onrender.com
     QDRANT_PORT=6333
     QDRANT_API_KEY=your_strong_random_key_here
     
     LLM_PROVIDER=gemini
     GEMINI_API_KEY=your_gemini_key
     
     STORAGE_BACKEND=s3
     STORAGE_S3_BUCKET=research-rag-storage
     STORAGE_S3_REGION=auto
     STORAGE_S3_ACCESS_KEY=r2_access_key
     STORAGE_S3_SECRET_KEY=r2_secret_key
     STORAGE_S3_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
     
     CORS_ORIGINS=https://your-frontend.vercel.app
     ```
   - Click Save and Auto-Deploy

3. **Wait for Deployment:**
   - Check build logs for errors (dependencies, import issues)
   - Once live, test: `https://your-backend.onrender.com/api/health`

4. **Copy Backend URL:**
   - Service URL: `https://research-rag-backend.onrender.com`

---

## 5. Frontend on Vercel

1. **Deploy via GitHub:**
   - Go to Vercel Dashboard → New Project
   - Select your GitHub repo
   - **Framework:** Next.js
   - **Root Directory:** `frontend`
   - Click Deploy

2. **Configure Environment Variables:**
   - Project Settings → Environment Variables
   - Add:
     ```
     NEXT_PUBLIC_API_URL=https://research-rag-backend.onrender.com/api
     ```
   - Save and trigger redeployment

3. **Verify Deployment:**
   - Once live, test the app: `https://your-project.vercel.app`
   - Open browser console to confirm no API URL errors
   - Try uploading a document and asking a question

---

## 6. Production Hardening

### Security: Rotate Exposed Keys
If you previously pasted credentials in chat/logs:
- **Render:** Rotate Gemini API key in Google Cloud Console
- **Cloudflare R2:** Rotate Access Key in R2 API Tokens
- **Regenerate** in `.env` before committing

### Monitoring & Logs
- **Render logs:** Service → Logs tab
- **Vercel logs:** Project → Deployments → Logs
- **Check API health regularly:** `curl https://your-backend.onrender.com/api/health`

### Database Backups
- Render free Postgres has **no automatic backups**; export dumps manually if needed
- Consider upgrading to standard tier for production reliability

### Rate Limiting
- Render free tier has concurrent request limits
- For high traffic, upgrade plan or add API gateway

---

## 7. Local Development vs. Production

| Item | Local | Production |
|------|-------|-----------|
| **API URL** | `http://localhost:8000/api` | `https://your-backend.onrender.com/api` |
| **Database** | Docker Compose local | Render managed Postgres |
| **Vector Store** | Docker Compose local | Render Qdrant service |
| **Storage** | Local filesystem or S3 | S3-compatible (R2) |
| **LLM** | Ollama or Gemini | Gemini (free API) |
| **Frontend Build** | `NEXT_PUBLIC_API_URL=http://localhost:8000/api npm run dev` | Built on Vercel, env injected |

---

## 8. Troubleshooting

### **CORS Error on Frontend**
- Check `CORS_ORIGINS` in backend env matches Vercel domain
- Restart backend after env change

### **API 502 Bad Gateway**
- Check Render backend logs for startup errors
- Verify all env vars are set (esp. `DATABASE_URL`, `GEMINI_API_KEY`)
- Check if Postgres/Qdrant services are running

### **Figures/PDFs Show as Black**
- Verify `STORAGE_S3_*` env vars are correct
- Check R2 bucket exists and token has `GetObject` permission
- Test: `aws s3 ls s3://research-rag-storage/ --endpoint-url https://<account>.r2.cloudflarestorage.com`

### **Long Build Times**
- Render free tier builds can take 10–30 min
- Check build logs for slow steps (e.g., huggingface model download)
- Consider caching dependencies in Dockerfile

### **Vercel 404 on `/api/*`**
- Ensure `NEXT_PUBLIC_API_URL` is set at build time
- Rebuild in Vercel dashboard after updating env vars

---

## 9. Next Steps

1. **Domain Setup:** Add custom domain to Vercel (DNS only, free tier)
2. **Error Tracking:** Integrate Sentry or similar
3. **Auto-Scaling:** Move from free to pro tier if needed
4. **CI/CD:** Add GitHub Actions for automated testing on push

---

## Cost Estimate (Free Tier)

| Service | Plan | Cost/Month |
|---------|------|------------|
| Render Database | Free | $0 (500MB limit) |
| Render Backend | Free | $0 (500 hours/month) |
| Render Qdrant | Free | $0 (if using free tier) |
| Vercel Frontend | Free | $0 (bandwidth limits ~100GB) |
| Cloudflare R2 | Standard | ~$0.015/GB stored + $0.005/request (~$5-10 typical) |
| Google Gemini | Free API | $0 (50 RPM quota) |
| **Total** | | **~$5–10/month** |

---

**Done!** Your app is now live. Share the Vercel URL with users.
