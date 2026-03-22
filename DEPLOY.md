# Norton VT Weather Agent — Deployment Guide

## What you're deploying
A small Python web app that fetches live weather data from NOAA and displays it
in a mobile-friendly interface. Once deployed, it works in any browser — including
on your iPhone.

---

## Step 1: Create a free GitHub account (if you don't have one)
1. Go to https://github.com
2. Click "Sign up" and create a free account
3. Verify your email

---

## Step 2: Create a new GitHub repository
1. Once logged in, click the **+** icon (top right) → "New repository"
2. Name it: `norton-weather`
3. Set it to **Public**
4. Click "Create repository"

---

## Step 3: Upload your files
In your new repository, click **"uploading an existing file"**

Upload these files exactly as-is (maintain the folder structure):
```
app.py
requirements.txt
Procfile
static/
  index.html
```

To upload the `static/index.html`:
- First upload `app.py`, `requirements.txt`, `Procfile`
- Then create the `static` folder by uploading `index.html` with the path `static/index.html`

Click **"Commit changes"** after each upload.

---

## Step 4: Create a free Render account
1. Go to https://render.com
2. Click "Get Started for Free"
3. Sign up with your GitHub account (easiest option)

---

## Step 5: Deploy on Render
1. In Render dashboard, click **"New +"** → **"Web Service"**
2. Click **"Connect a repository"** and select `norton-weather`
3. Fill in the settings:
   - **Name:** norton-weather (or anything you like)
   - **Region:** US East (Ohio) — closest to Vermont
   - **Branch:** main
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
4. Select the **Free** plan
5. Click **"Create Web Service"**

---

## Step 6: Wait for deployment (~2-3 minutes)
Render will show a build log. When you see:
```
Your service is live 🎉
```
...you're done!

---

## Step 7: Open your app
Render gives you a URL like:
```
https://norton-weather-xxxx.onrender.com
```

Open that URL on your iPhone — it works like a website, no App Store needed.
You can also "Add to Home Screen" in Safari to make it feel like an app.

---

## Notes
- The free Render tier "sleeps" after 15 minutes of inactivity. The first load
  after sleep takes ~30 seconds. This is normal — subsequent loads are fast.
- To wake it up faster, just refresh the page once.
- Data comes directly from NOAA/NWS — the same source as weather.gov.

---

## File structure reference
```
norton-weather/
├── app.py              ← Python backend (fetches NOAA data)
├── requirements.txt    ← Python packages needed
├── Procfile            ← Tells Render how to start the app
└── static/
    └── index.html      ← The web interface (HTML + JS)
```
