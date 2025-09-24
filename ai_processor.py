from __future__ import annotations

from typing import Optional
import os


class Summarizer:
    def __init__(self, config, logger) -> None:
        self.config = config
        self.logger = logger
        self._chain = None
        self._gen_model = None  # direct google-generativeai model if LangChain path is unavailable
        self._model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        # Default to 'gemini' per request (can be overridden in .env)
        self._mode = os.getenv("SUMMARIZER_MODE", "gemini").strip().lower()
        self._rest_enabled = False

        # Initialize Gemini model lazily to avoid import errors if packages aren't installed yet.
        api_key: Optional[str] = getattr(self.config, "google_api_key", None)
        if not api_key:
            self.logger.warning("GOOGLE_API_KEY is not set; using local fallback summarizer.")

        # Respect mode: prefer local fallback unless explicitly set to 'gemini'
        if self._mode != "gemini":
            self.logger.info("Summarizer mode: %s (using local fallback)", self._mode)
            self._chain = None
            return

        try:
            from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore
            from langchain_core.prompts import ChatPromptTemplate  # type: ignore
            from langchain_core.output_parsers import StrOutputParser  # type: ignore

            llm = ChatGoogleGenerativeAI(
                model=self._model_name,
                temperature=0.3,
                google_api_key=api_key,
                # Keep the app responsive; surface errors to our handler
                max_retries=0,
            )

            prompt = ChatPromptTemplate.from_template(
                """
You are an assistant that summarizes Outlook emails for quick triage.
Summarize the following email in 3-6 concise bullet points. Include intent and any deadlines.
Suggest one next action if appropriate. Keep it under 40 words.

Subject: {subject}
From: {sender}
Content:
{content}
"""
            )
            self._chain = prompt | llm | StrOutputParser()
        except Exception as e:
            # LangChain path failed; record why, then attempt direct SDK
            try:
                self.logger.warning("Gemini via LangChain initialization failed: %s", e)
            except Exception:
                pass
            # Attempt direct google-generativeai usage as a secondary path
            try:
                import google.generativeai as genai  # type: ignore
                genai.configure(api_key=api_key)
                self._gen_model = genai.GenerativeModel(model_name=self._model_name)
                self.logger.info("Using Gemini via google-generativeai SDK (no LangChain).")
            except Exception as e2:
                # SDK path failed; record why, then use REST API directly to avoid local package issues
                try:
                    self.logger.warning("Gemini via google-generativeai SDK initialization failed: %s", e2)
                except Exception:
                    pass
                try:
                    import requests  # noqa: F401
                    self._rest_enabled = True
                    self.logger.info("Using Gemini via REST API fallback.")
                except Exception as e3:
                    self.logger.warning(
                        "Gemini via LangChain failed (%s), direct SDK unavailable (%s), REST fallback failed (%s); using local fallback.",
                        e,
                        e2,
                        e3,
                    )
                    self._chain = None

    def _local_fallback(self, subject: str, sender: str, content: str) -> str:
        subj = subject or "(no subject)"
        sndr = sender or "(unknown)"
        text = (content or "").strip().replace("\r", " ").replace("\n", " ")
        preview = text[:220]
        bullets = [
            f"• Subject: {subj}",
            f"• From: {sndr}",
            f"• Preview: {preview}"
        ]
        return "\n".join(bullets)

    def summarize_email_content(self, subject: str, sender: str, content: str) -> str:
        if not self._chain and not self._gen_model and not self._rest_enabled:
            self.logger.info("Using local fallback summarizer for: %s", subject or "(no subject)")
            return self._local_fallback(subject, sender, content)

        try:
            self.logger.info("Summarizing email: %s", (subject or "(no subject)"))
            if self._chain:
                result: str = self._chain.invoke(
                    {"subject": subject or "(no subject)", "sender": sender or "(unknown)", "content": content or ""}
                )
                return (result or "").strip()
            # Build prompt once
            prompt = (
                "You are an assistant that summarizes Outlook emails for quick triage.\n"
                "Summarize the email in 3-6 concise bullet points. Include intent and any deadlines.\n"
                "Suggest one next action if appropriate. Keep it under 40 words.\n\n"
                f"Subject: {subject or '(no subject)'}\n"
                f"From: {sender or '(unknown)'}\n"
                "Content:\n"
                f"{content or ''}"
            )
            # Direct google-generativeai SDK path
            if self._gen_model is not None:
                resp = self._gen_model.generate_content(prompt)  # type: ignore[union-attr]
                text = getattr(resp, "text", None) or "".join(getattr(resp, "candidates", []) or [])
                return (text or "").strip() or self._local_fallback(subject, sender, content)
            # REST fallback path
            if self._rest_enabled:
                import requests
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model_name}:generateContent"
                params = {"key": getattr(self.config, "google_api_key", "")}
                body = {
                    "contents": [
                        {
                            "parts": [
                                {"text": prompt}
                            ]
                        }
                    ]
                }
                r = requests.post(endpoint, params=params, json=body, timeout=20)
                if r.status_code >= 300:
                    self.logger.warning("Gemini REST call failed (%s): %s", r.status_code, r.text)
                    return self._local_fallback(subject, sender, content)
                data = r.json() or {}
                # Extract first candidate text
                text = ""
                try:
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            text = parts[0].get("text", "")
                except Exception:
                    text = ""
                return (text or "").strip() or self._local_fallback(subject, sender, content)
        except Exception as e:
            msg = str(e)
            # Handle common quota/429 errors gracefully
            if "429" in msg or "quota" in msg.lower() or "ResourceExhausted" in msg:
                self.logger.warning("LLM rate-limited/quota issue for '%s': %s. Using local fallback.", subject, e)
                return self._local_fallback(subject, sender, content)
            self.logger.exception("Failed to summarize email '%s': %s", subject, e)
            return self._local_fallback(subject, sender, content)
