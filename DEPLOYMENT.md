# Deployment to Streamlit Community Cloud

## 1. Prepare Repo
- Ensure entry file: `streamlit_chatbot.py`
- Generate `requirements.txt`: `pip freeze > requirements.txt`
- Add `.gitignore` (exclude `venv/`, `__pycache__/`, `*.pyc`, `google_credentials.json`)

## 2. Push to GitHub
```
git init
git branch -M main
git add streamlit_chatbot.py streamlit_google_auth.py pandas_automation.py requirements.txt AUTHENTICATION_SETUP.md DEPLOYMENT.md .gitignore
git commit -m "Initial deploy"
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

## 3. Configure Streamlit Cloud
- Go to Streamlit Cloud, connect GitHub, choose repo
- Main file path: `streamlit_chatbot.py`
- Deploy

## 4. Set Secrets
Add in App Settings → Secrets:
```
GOOGLE_CLIENT_ID = "…apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "…"
REDIRECT_URI = "https://<your-app-name>.streamlit.app"
```

## 5. Update Google OAuth
- In Google Console → Credentials → your Web client → Edit
- Authorized redirect URIs: add `https://<your-app-name>.streamlit.app` and keep `http://localhost:8501`

## 6. Verify
- Open Cloud URL
- Click Sign in with Google → returns authenticated

## Updates
- Push changes to the same branch; Cloud redeploys automatically.
- Edit Secrets in Cloud if credentials/URLs change.
