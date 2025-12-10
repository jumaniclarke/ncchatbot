# Google Authentication Setup for Statistics Chatbot

## Streamlit Cloud Secrets (Deployment)

When deploying to Streamlit Community Cloud, store your Google OAuth credentials in app secrets instead of committing the JSON file. In your app settings → Secrets, add:

```
GOOGLE_CLIENT_ID = "your-client-id.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "your-client-secret"
REDIRECT_URI = "https://<your-app-name>.streamlit.app"
```

Notes:
- Keep `http://localhost:8501` in Google Console for local development and add your Cloud URL for production.
- The app automatically uses `st.secrets` on Cloud and falls back to `google_credentials.json` locally.
