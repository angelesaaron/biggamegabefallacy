# Deployment Guide - BGGTDM

Complete guide to deploy your TD prediction app so friends can use it.

## Prerequisites

### 1. Upgrade Node.js (Required for Frontend)

Your current Node version (12) is too old. Upgrade to Node 18+:

```bash
# Install nvm (Node Version Manager)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# Restart terminal, then:
nvm install 18
nvm use 18
node --version  # Should show v18.x.x

# Reinstall frontend dependencies
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### 2. Test Locally First

```bash
# Terminal 1 - Backend
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
# Running on http://localhost:8000

# Terminal 2 - Frontend
cd frontend
npm run dev
# Running on http://localhost:3000

# Open browser: http://localhost:3000/value-finder
# Should see Week 17 predictions with odds!
```

---

## Option 1: Deploy to Render + Vercel (Recommended - FREE)

### A. Deploy Backend to Render

**1. Sign Up & Connect GitHub**
- Go to [render.com](https://render.com)
- Sign up with GitHub
- Click "New +" → "Web Service"
- Connect your GitHub account
- Select `biggamegabefallacy` repository

**2. Configure Web Service**
- **Name**: `bggtdm-api`
- **Region**: Choose closest to you
- **Branch**: `main`
- **Root Directory**: `backend`
- **Runtime**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

**3. Add Environment Variables**
Click "Advanced" → "Add Environment Variable":

```
TANK01_API_KEY=<your-tank01-api-key>
DATABASE_URL=<will-be-added-after-database-creation>
```

**4. Create PostgreSQL Database**
- Click "New +" → "PostgreSQL"
- **Name**: `bggtdm-db`
- **Region**: Same as web service
- **Plan**: Free tier
- Click "Create Database"

**5. Connect Database to Web Service**
- Go back to your web service
- "Environment" tab → Add variable:
  - **Key**: `DATABASE_URL`
  - **Value**: Copy "Internal Database URL" from PostgreSQL dashboard

**6. Deploy!**
- Click "Create Web Service"
- Wait 5-10 minutes for build
- Your API will be at: `https://bggtdm-api.onrender.com`

**7. Migrate Database**

Once deployed, run migrations via Render shell:

```bash
# In Render dashboard, go to your web service
# Click "Shell" tab
python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)"
```

**8. Import Local Data to Production**

Export from local:
```bash
cd backend
pg_dump -h localhost -U your_user -d biggamegabefallacy > backup.sql
```

Import to Render (get credentials from Render PostgreSQL dashboard):
```bash
psql -h <render-host> -U <render-user> -d <render-db> < backup.sql
```

---

### B. Deploy Frontend to Vercel

**1. Sign Up & Import Project**
- Go to [vercel.com](https://vercel.com)
- Sign up with GitHub
- Click "Add New..." → "Project"
- Import `biggamegabefallacy` repository

**2. Configure Project**
- **Framework Preset**: Next.js
- **Root Directory**: `frontend`
- **Build Command**: `npm run build` (auto-detected)
- **Output Directory**: `.next` (auto-detected)

**3. Add Environment Variables**
- Click "Environment Variables"
- Add:
  - **Name**: `NEXT_PUBLIC_API_URL`
  - **Value**: `https://bggtdm-api.onrender.com` (your Render URL)

**4. Deploy!**
- Click "Deploy"
- Wait 2-3 minutes
- Your app will be at: `https://bggtdm.vercel.app`

**5. Share with Friends!**
Send them: `https://bggtdm.vercel.app/value-finder`

---

## Option 2: Deploy to Single Server (Railway)

Railway provides both backend + database in one place.

**1. Sign Up**
- Go to [railway.app](https://railway.app)
- Sign up with GitHub

**2. Deploy Backend**
- "New Project" → "Deploy from GitHub repo"
- Select `biggamegabefallacy`
- Railway auto-detects Python app
- Set root directory: `backend`

**3. Add PostgreSQL**
- Click "+ New" → "Database" → "PostgreSQL"
- Railway auto-connects to your app

**4. Environment Variables**
Railway auto-sets `DATABASE_URL`. Add:
```
TANK01_API_KEY=<your-key>
```

**5. Deploy Frontend**
- Repeat process for frontend directory
- Set `NEXT_PUBLIC_API_URL` to backend Railway URL

**Cost**: ~$5/month after free trial

---

## Post-Deployment Tasks

### 1. Update Weekly Data (Run Every Tuesday)

SSH into Render or run locally:
```bash
python backend/update_weekly.py
python backend/generate_predictions.py
```

**OR** Set up cron job in Render:
- Dashboard → "Cron Jobs"
- Schedule: `0 8 * * 2` (Every Tuesday 8 AM)
- Command: `cd backend && python update_weekly.py && python generate_predictions.py`

### 2. Enable CORS (if needed)

If frontend gets CORS errors, add to `backend/app/main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://bggtdm.vercel.app"],  # Your Vercel URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 3. Custom Domain (Optional)

**Vercel**:
- Settings → Domains → Add your domain
- Update DNS records as instructed

**Render**:
- Settings → Custom Domain → Add domain
- Update DNS CNAME record

---

## Troubleshooting

### Frontend shows "API Error"
- Check `NEXT_PUBLIC_API_URL` in Vercel dashboard
- Ensure backend is deployed and running
- Check browser console for CORS errors

### Backend shows "Database connection failed"
- Verify `DATABASE_URL` is set correctly
- Check Render PostgreSQL is running
- Ensure database tables are created (run migrations)

### No predictions showing
- Check if predictions exist: `curl https://bggtdm-api.onrender.com/api/predictions/current`
- Run `python generate_predictions.py` if empty
- Verify odds are synced: `python sync_odds.py`

### Out of API calls
- Tank01 limit: 1,000/day
- Only run `update_weekly.py` once per week
- Don't re-sync historical data unnecessarily

---

## Monitoring

### Check Backend Health
```bash
curl https://bggtdm-api.onrender.com/api/predictions/current
```

### Check Frontend
Open browser: `https://bggtdm.vercel.app/value-finder`

### Logs
- **Render**: Dashboard → Logs tab
- **Vercel**: Dashboard → Deployments → Click deployment → View logs

---

## Free Tier Limits

**Render**:
- Web service sleeps after 15 min inactivity
- First request may be slow (cold start)
- PostgreSQL: 1GB storage

**Vercel**:
- 100GB bandwidth/month
- Unlimited deployments

**Solution for cold starts**:
- Use [UptimeRobot](https://uptimerobot.com) to ping API every 10 min

---

## Next Steps After Deployment

1. ✅ Share with friends
2. ✅ Collect feedback
3. ✅ Monitor Week 17 results
4. ✅ Validate model accuracy
5. → Add player names (currently just IDs)
6. → Add historical performance charts
7. → Build players search page
8. → Add email alerts for high-value bets

---

## Cost Summary

**Option 1 (Render + Vercel)**: FREE forever
**Option 2 (Railway)**: $5/month after trial
**Custom domain**: ~$12/year (optional)

**Total to run for friends**: $0-5/month 🎉
