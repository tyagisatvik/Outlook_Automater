from __future__ import annotations

from logger_setup import setup_logger
from config import Config
from email_client import OutlookClient
from ai_processor import Summarizer
from notifiers import ConsoleNotifier, get_telegram_notifier, Notifier


def run_once() -> None:
    """Fetch unread emails, summarize, and send a digest once (no webhook)."""
    logger = setup_logger("EmailAssistant")
    cfg = Config()
    client = OutlookClient(cfg, logger)
    summarizer = Summarizer(cfg, logger)

    notifier: Notifier
    if (cfg.notifier_type or "").lower() == "telegram":
        notifier = get_telegram_notifier(cfg, logger)
    else:
        notifier = ConsoleNotifier(logger)

    max_count = cfg.max_emails if getattr(cfg, "max_emails", 0) else None
    emails = client.fetch_unread_emails(max_count=max_count)
    if not emails:
        logger.info("No unread emails.")
        return

    for msg in emails:
        subject = msg.get("subject", "(no subject)")
        sender_obj = msg.get("from", {}) or {}
        email_addr = (sender_obj.get("emailAddress", {}) or {}).get("address", "")
        name = (sender_obj.get("emailAddress", {}) or {}).get("name", "")
        sender = f"{name} <{email_addr}>" if email_addr or name else "(unknown)"
        preview = msg.get("bodyPreview", "")

        summary = summarizer.summarize_email_content(subject, sender, preview)
        digest = f"Unread email\n\n{summary}"
        notifier.send(digest)


if __name__ == "__main__":
    run_once()
