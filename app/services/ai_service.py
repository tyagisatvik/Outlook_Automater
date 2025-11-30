"""AI service for email processing with multi-tier LLM strategy"""
import json
import asyncio
from typing import Tuple, List, Dict, Any, Optional
from datetime import datetime
from app.core.config import settings
from app.prompts.summarization import (
    SUMMARIZATION_PROMPT,
    CLASSIFICATION_PROMPT,
    SENTIMENT_PROMPT,
    URGENCY_SCORE_PROMPT
)
from app.prompts.actions import ACTION_RECOMMENDATION_PROMPT
from app.services.vector_store import vector_store


class AIService:
    """Service for AI-powered email analysis using multi-tier LLM strategy"""

    def __init__(self):
        self.last_model_used = None

    async def process_email(
        self,
        subject: str,
        sender: str,
        body: str,
        received_at: datetime,
        user_id: Optional[int] = None,
        message_id: Optional[str] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Process email with AI to generate summary and action recommendations

        Args:
            subject: Email subject
            sender: Sender email address
            body: Email body content
            received_at: When email was received
            user_id: User ID (for context retrieval)
            message_id: Message ID (for context retrieval)

        Returns:
            Tuple of (summary, suggested_actions)
        """
        # Get contextual information from vector store
        context = {}
        if user_id and message_id:
            context = await self._get_email_context(message_id, user_id, subject, body)

        # Run summarization and actions in parallel with context
        summary_task = self._generate_summary(subject, sender, body, received_at, context)
        actions_task = self._generate_actions(subject, sender, body, received_at, context)

        summary, actions = await asyncio.gather(summary_task, actions_task)

        return summary, actions

    async def _get_email_context(
        self,
        message_id: str,
        user_id: int,
        subject: str,
        body: str
    ) -> Dict[str, Any]:
        """
        Retrieve contextual information from vector store

        Args:
            message_id: Email message ID
            user_id: User ID
            subject: Email subject
            body: Email body

        Returns:
            Context dictionary with similar emails and patterns
        """
        try:
            # Search for similar emails
            query_text = f"{subject}\n\n{body[:500]}"
            similar_emails = vector_store.search_similar_emails(
                query_text=query_text,
                user_id=user_id,
                n_results=3
            )

            return {
                "similar_emails": similar_emails,
                "has_context": len(similar_emails) > 0
            }
        except Exception as e:
            print(f"Error retrieving email context: {e}")
            return {"similar_emails": [], "has_context": False}

    async def _generate_summary(
        self,
        subject: str,
        sender: str,
        body: str,
        received_at: datetime,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate email summary using Gemini Flash (cheap, fast)

        Args:
            subject: Email subject
            sender: Sender email
            body: Email body
            received_at: Receipt timestamp

        Returns:
            Summary text
        """
        prompt = SUMMARIZATION_PROMPT.format(
            subject=subject,
            sender=sender,
            body=body[:2000],  # Limit to 2000 chars to save costs
            received_at=received_at.strftime("%Y-%m-%d %H:%M")
        )

        # Try Gemini Flash first (cheapest)
        result = await self._call_gemini(prompt)

        if result:
            self.last_model_used = settings.SUMMARIZER_MODEL
            return result

        # Fallback to GPT-4 if Gemini fails
        result = await self._call_openai(prompt)

        if result:
            self.last_model_used = "gpt-4"
            return result

        # Final fallback to Claude
        result = await self._call_claude(prompt)

        if result:
            self.last_model_used = settings.REPLIES_MODEL
            return result

        # Ultimate fallback: rule-based summary
        self.last_model_used = "fallback"
        return self._fallback_summary(subject, sender, body)

    async def _generate_actions(
        self,
        subject: str,
        sender: str,
        body: str,
        received_at: datetime,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate action recommendations using GPT-4 (better reasoning)

        Args:
            subject: Email subject
            sender: Sender email
            body: Email body
            received_at: Receipt timestamp

        Returns:
            List of action items
        """
        prompt = ACTION_RECOMMENDATION_PROMPT.format(
            subject=subject,
            sender=sender,
            body=body[:2000],
            received_at=received_at.strftime("%Y-%m-%d %H:%M")
        )

        # Try GPT-4 first (best for complex reasoning)
        result = await self._call_openai(prompt, model=settings.ACTIONS_MODEL)

        if result:
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                pass

        # Fallback to Claude
        result = await self._call_claude(prompt)

        if result:
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                pass

        # Fallback to Gemini
        result = await self._call_gemini(prompt)

        if result:
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                pass

        # Ultimate fallback: simple action
        return [{
            "action": "Review email",
            "type": "review",
            "priority": "medium",
            "due_date": None,
            "reasoning": "Unable to generate AI recommendations"
        }]

    async def _call_gemini(self, prompt: str) -> Optional[str]:
        """
        Call Google Gemini API

        Args:
            prompt: Prompt text

        Returns:
            Response text or None on error
        """
        try:
            import google.generativeai as genai

            genai.configure(api_key=settings.GOOGLE_API_KEY)
            model = genai.GenerativeModel(settings.SUMMARIZER_MODEL)

            response = model.generate_content(prompt)
            return response.text

        except Exception as e:
            print(f"Gemini API error: {e}")
            return None

    async def _call_openai(self, prompt: str, model: str = "gpt-4") -> Optional[str]:
        """
        Call OpenAI API

        Args:
            prompt: Prompt text
            model: Model name

        Returns:
            Response text or None on error
        """
        if not settings.OPENAI_API_KEY:
            return None

        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful executive assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500,
            )

            return response.choices[0].message.content

        except Exception as e:
            print(f"OpenAI API error: {e}")
            return None

    async def _call_claude(self, prompt: str) -> Optional[str]:
        """
        Call Anthropic Claude API

        Args:
            prompt: Prompt text

        Returns:
            Response text or None on error
        """
        if not settings.ANTHROPIC_API_KEY:
            return None

        try:
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

            response = await client.messages.create(
                model=settings.REPLIES_MODEL,
                max_tokens=500,
                temperature=0.3,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            return response.content[0].text

        except Exception as e:
            print(f"Claude API error: {e}")
            return None

    def _fallback_summary(self, subject: str, sender: str, body: str) -> str:
        """
        Rule-based fallback summary when AI fails

        Args:
            subject: Email subject
            sender: Sender email
            body: Email body

        Returns:
            Simple text summary
        """
        # Extract first 200 characters of body
        preview = body[:200].strip()
        if len(body) > 200:
            preview += "..."

        return f"• Email from {sender}\n• Subject: {subject}\n• {preview}"
