import msal
import requests
import atexit
import os

class OutlookClient:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.auth_mode = getattr(self.config, "auth_mode", "delegated")
        
        # Scopes for delegated (interactive) flow
        self.scopes = ["Mail.Read"]
        
        # Token cache to persist sessions
        self.cache = msal.SerializableTokenCache()
        if os.path.exists("my_token_cache.bin"):
            self.cache.deserialize(open("my_token_cache.bin", "r").read())
        
        atexit.register(
            lambda: open("my_token_cache.bin", "w").write(self.cache.serialize())
            if self.cache.has_state_changed else None
        )

        authority = f"https://login.microsoftonline.com/{self.config.microsoft_tenant_id}"
        
        if self.auth_mode == "delegated":
            self.app = msal.PublicClientApplication(
                client_id=self.config.microsoft_client_id,
                authority=authority,
                token_cache=self.cache,
            )
        else: # App mode
            self.app = msal.ConfidentialClientApplication(
                client_id=self.config.microsoft_client_id,
                client_credential=self.config.microsoft_client_secret,
                authority=authority,
            )

    def _get_access_token(self):
        """Acquire an access token based on the configured auth mode."""
        result = None
        
        if self.auth_mode == "delegated":
            accounts = self.app.get_accounts()
            if accounts:
                self.logger.info("Account found in cache, attempting silent token acquisition.")
                result = self.app.acquire_token_silent(self.scopes, account=accounts[0])
            
            if not result:
                self.logger.info("No silent token available, initiating device code flow.")
                print("\n--- INTERACTIVE LOGIN REQUIRED ---")
                flow = self.app.initiate_device_flow(scopes=self.scopes)
                if "user_code" not in flow:
                    raise RuntimeError("Failed to create device flow. Check Azure App Registration.")
                
                print(f"1. Go to: {flow['verification_uri']}")
                print(f"2. Enter code: {flow['user_code']}")
                print("----------------------------------")
                
                result = self.app.acquire_token_by_device_flow(flow)
        
        else: # App mode
            self.logger.info("Attempting app-only (client credentials) token acquisition.")
            result = self.app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

        if "access_token" in result:
            self.logger.info("Access token acquired successfully.")
            return result['access_token']
        else:
            error_description = result.get("error_description", "No error description provided.")
            self.logger.error(f"Failed to acquire access token: {error_description}")
            raise Exception(f"Authentication failed: {error_description}")

    def fetch_unread_emails(self, max_count: int | None = None):
        """
        Fetch unread emails with optional page traversal. If max_count is provided, stop after that many.
        """
        try:
            access_token = self._get_access_token()
            headers = {'Authorization': f'Bearer {access_token}'}

            if self.auth_mode == "delegated":
                principal_path = "me"
            else:
                target_user = self.config.target_email_address
                if not target_user:
                    raise ValueError("TARGET_EMAIL_ADDRESS must be set in .env for app authentication.")
                principal_path = f"users/{target_user}"

            # Use $top to pull decent page sizes and order by most recent first
            endpoint = (
                f"https://graph.microsoft.com/v1.0/{principal_path}/mailfolders/inbox/messages"
                f"?$filter=isRead eq false&$orderby=receivedDateTime desc&$top=50"
            )
            emails_all = []
            url = endpoint

            while url:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                data = response.json() or {}
                page = data.get('value', [])
                emails_all.extend(page)

                # Respect max_count if provided
                if max_count and len(emails_all) >= max_count:
                    emails_all = emails_all[:max_count]
                    break

                url = data.get('@odata.nextLink')
                if not url:
                    break

            self.logger.info(f"Successfully fetched {len(emails_all)} unread emails.")
            return emails_all
        except Exception as e:
            self.logger.error(f"Failed to fetch emails: {e}")
            return []

    def fetch_message_by_id(self, message_id: str):
        """Fetch a single message by Graph message ID using the appropriate principal."""
        try:
            access_token = self._get_access_token()
            headers = {'Authorization': f'Bearer {access_token}'}

            if self.auth_mode == "delegated":
                principal_path = "me"
            else:
                target_user = self.config.target_email_address
                if not target_user:
                    raise ValueError("TARGET_EMAIL_ADDRESS must be set in .env for app authentication.")
                principal_path = f"users/{target_user}"

            endpoint = f"https://graph.microsoft.com/v1.0/{principal_path}/messages/{message_id}?$select=subject,from,bodyPreview,receivedDateTime,webLink"
            resp = requests.get(endpoint, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self.logger.error(f"Failed to fetch message {message_id}: {e}")
            return None
