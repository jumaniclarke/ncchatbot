import json
import os
import urllib.parse
from dataclasses import dataclass

import streamlit as st

try:
    import requests
except Exception as e:  # prag cover
    requests = None


GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"


@dataclass
class _OAuthConfig:
    client_id: str
    client_secret: str
    auth_uri: str
    token_uri: str
    redirect_uri: str


class Authenticate:
    """
    Minimal Google OAuth for Streamlit.

    Expected usage in your app:

        from streamlit_google_auth import Authenticate

        authenticator = Authenticate(
            secret_credentials_path='google_credentials.json',
            cookie_name='streamlit_auth_cookie',
            cookie_key='streamlit_auth_key',
            redirect_uri='http://localhost:8501',
        )

        authenticator.check_authentification()
        if not st.session_state['connected']:
            authenticator.login()
            st.stop()
        # ... later ...
        authenticator.logout()
    """

    def __init__(
        self,
        *,
        secret_credentials_path: str,
        cookie_name: str,
        cookie_key: str,
        redirect_uri: str,
        scopes: list[str] | None = None,
    ) -> None:
        self.secret_path = secret_credentials_path
        self.cookie_name = cookie_name
        self.cookie_key = cookie_key
        self.redirect_uri = redirect_uri
        self.scopes = scopes or ["openid", "email", "profile"]
        self._cfg = self._load_config()

    # Keep the misspelling to match existing app usage
    def check_authentification(self) -> None:
        """Initialize default session state and detect existing login state."""
        st.session_state.setdefault("connected", False)
        st.session_state.setdefault("user_info", {})
        st.session_state.setdefault("_oauth_tokens", {})

    def login(self) -> None:
        """Render a Google Sign-In flow and complete OAuth if code present."""
        if st.session_state.get("connected"):
            return

        if requests is None:
            st.error(
                "The 'requests' package is required for Google sign-in.\n"
                "Please install it: pip install requests"
            )
            return

        code = st.query_params.get("code", None)
        error = st.query_params.get("error", None)

        if error:
            st.error(f"Google OAuth error: {error}")
            self._render_signin_link()
            return

        if code:
            # Exchange auth code for tokens
            token_data = self._exchange_code_for_tokens(code)
            if not token_data:
                st.error("Failed to exchange authorization code for tokens.")
                self._render_signin_link()
                return

            # Fetch user info with access token
            user_info = self._fetch_user_info(token_data.get("access_token"))
            if not user_info:
                st.error("Failed to fetch user information from Google.")
                self._render_signin_link()
                return

            st.session_state["_oauth_tokens"] = token_data
            st.session_state["user_info"] = {
                "email": user_info.get("email"),
                "name": user_info.get("name"),
                "picture": user_info.get("picture"),
                "hd": user_info.get("hd"),
                "sub": user_info.get("sub"),
            }
            st.session_state["connected"] = True

            # Optionally clean query params by removing OAuth params
            try:
                # Preserve non-OAuth params like 'task'
                keep = {k: v for k, v in st.query_params.items() if k not in {"code", "scope", "authuser", "prompt"}}
                st.query_params.clear()
                if keep:
                    for k, v in keep.items():
                        st.query_params[k] = v
            except Exception:
                # If query_params isn't mutable in this Streamlit version, just rerun
                pass

            st.success(f"Signed in as {st.session_state['user_info'].get('email', 'unknown')}.")
            st.rerun()
            return

        # No code yet: show Sign in link
        self._render_signin_link()

    def logout(self) -> None:
        """Clear session and prompt user to sign in again."""
        for k in ("_oauth_tokens", "user_info", "connected"):
            if k in st.session_state:
                del st.session_state[k]
        st.session_state["connected"] = False
        st.success("You have been logged out.")
        # Best-effort removal of OAuth-related query params
        try:
            keep = {k: v for k, v in st.query_params.items() if k not in {"code", "scope", "authuser", "prompt"}}
            st.query_params.clear()
            if keep:
                for k, v in keep.items():
                    st.query_params[k] = v
        except Exception:
            pass
        st.rerun()

    # ----- Internal helpers -----

    def _load_config(self) -> _OAuthConfig:
        # 1) Prefer Streamlit secrets when available (for Cloud)
        try:
            secrets_obj = st.secrets  # Access may raise StreamlitSecretNotFoundError locally
            # Support both flat and nested secrets structures
            sid = secrets_obj.get("GOOGLE_CLIENT_ID")
            ssecret = secrets_obj.get("GOOGLE_CLIENT_SECRET")
            sredirect = secrets_obj.get("REDIRECT_URI")
            # Nested: [auth.google] and [auth]
            try:
                if not sid:
                    sid = secrets_obj.get("auth", {}).get("google", {}).get("GOOGLE_CLIENT_ID")
                if not ssecret:
                    ssecret = secrets_obj.get("auth", {}).get("google", {}).get("GOOGLE_CLIENT_SECRET")
                if not sredirect:
                    sredirect = secrets_obj.get("auth", {}).get("REDIRECT_URI")
            except Exception:
                pass
            sredirect = sredirect or self.redirect_uri
            sauth = secrets_obj.get("AUTH_URI") or GOOGLE_AUTH_ENDPOINT
            stoken = secrets_obj.get("TOKEN_URI") or GOOGLE_TOKEN_ENDPOINT
            if sid and ssecret and sredirect:
                return _OAuthConfig(
                    client_id=sid,
                    client_secret=ssecret,
                    auth_uri=sauth,
                    token_uri=stoken,
                    redirect_uri=sredirect,
                )
        except Exception:
            # No secrets configured; continue with local file
            pass

        # 2) Fallback to local JSON file for dev
        if not os.path.exists(self.secret_path):
            raise FileNotFoundError(
                f"Google credentials file not found at '{self.secret_path}'. "
                "Download your OAuth client JSON and place it there, or set Streamlit secrets."
            )
        with open(self.secret_path, "r", encoding="utf-8") as f:
            try:
                content = f.read().strip()
                if not content:
                    raise ValueError(
                        "google_credentials.json is empty. Download your OAuth client JSON from Google Cloud Console and place it here."
                    )
                data = json.loads(content)
            except json.JSONDecodeError as e:
                raise ValueError(
                    "google_credentials.json is not valid JSON. Replace it with the downloaded OAuth client JSON.\n"
                    "You can use google_credentials_template.json as a reference."
                ) from e

        # Support both 'web' and 'installed' style JSONs
        block = data.get("web") or data.get("installed") or {}
        client_id = block.get("client_id")
        client_secret = block.get("client_secret")
        auth_uri = block.get("auth_uri") or GOOGLE_AUTH_ENDPOINT
        token_uri = block.get("token_uri") or GOOGLE_TOKEN_ENDPOINT

        if not client_id or not client_secret:
            raise ValueError("Invalid google_credentials.json: missing client_id or client_secret")

        # Validate redirect uri
        ru = self.redirect_uri
        allowed = set(block.get("redirect_uris", []))
        if allowed and ru not in allowed:
            st.warning(
                "The redirect_uri configured in code does not match the URIs in google_credentials.json.\n"
                f"Configured: {ru}\n"
                f"Allowed: {sorted(allowed)}\n"
                "Google will reject the login if they don't match."
            )

        return _OAuthConfig(
            client_id=client_id,
            client_secret=client_secret,
            auth_uri=auth_uri,
            token_uri=token_uri,
            redirect_uri=ru,
        )

    def _authorization_url(self) -> str:
        params = {
            "client_id": self._cfg.client_id,
            "redirect_uri": self._cfg.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "access_type": "online",
            "include_granted_scopes": "true",
            "prompt": "select_account",
        }
        # Keep current non-OAuth params (e.g., task) across the redirect using 'state'
        try:
            keep = {k: v for k, v in st.query_params.items() if k not in {"code", "scope", "authuser", "prompt"}}
            if keep:
                params["state"] = urllib.parse.urlencode(keep, doseq=True)
        except Exception:
            pass
        base = self._cfg.auth_uri or GOOGLE_AUTH_ENDPOINT
        # Prefer the v2 endpoint for OpenID scopes when possible
        if "oauth2/auth" in base and "v2" not in base:
            base = GOOGLE_AUTH_ENDPOINT
        return f"{base}?{urllib.parse.urlencode(params, doseq=True)}"

    def _exchange_code_for_tokens(self, code: str) -> dict | None:
        data = {
            "code": code,
            "client_id": self._cfg.client_id,
            "client_secret": self._cfg.client_secret,
            "redirect_uri": self._cfg.redirect_uri,
            "grant_type": "authorization_code",
        }
        try:
            try:
                cid = self._cfg.client_id
                csec = self._cfg.client_secret
                rid = self._cfg.redirect_uri
                st.info(
                    "OAuth debug:\n"
                    f"client_id: {cid[:8]}…{cid[-12:]}\n"
                    f"client_secret length: {len(csec)}\n"
                    f"redirect_uri: {rid}"
                )
            except Exception:
                pass
            resp = requests.post(self._cfg.token_uri or GOOGLE_TOKEN_ENDPOINT, data=data, timeout=15)
            if resp.status_code != 200:
                try:
                    st.error(
                        "Google token exchange failed.\n"
                        f"Status: {resp.status_code}\n"
                        f"Body: {resp.text[:500]}"
                    )
                except Exception:
                    pass
                return None
            return resp.json()
        except Exception:
            return None

    def _fetch_user_info(self, access_token: str | None) -> dict | None:
        if not access_token:
            return None
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            resp = requests.get(GOOGLE_USERINFO_ENDPOINT, headers=headers, timeout=15)
            if resp.status_code != 200:
                return None
            return resp.json()
        except Exception:
            return None

    def _render_signin_link(self) -> None:
        url = self._authorization_url()
        st.markdown(
            f"""
            <a href="{url}" target="_self" style="
                display:inline-block;
                padding:0.5rem 0.75rem;
                background:#1a73e8;
                color:white; text-decoration:none; border-radius:4px;">
                Sign in with Google
            </a>
            """,
            unsafe_allow_html=True,
        )
