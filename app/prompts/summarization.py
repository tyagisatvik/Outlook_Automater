"""AI prompts for email summarization"""

SUMMARIZATION_PROMPT = """You are an executive assistant analyzing an email for a busy professional.

Email Details:
- Subject: {subject}
- From: {sender}
- Received: {received_at}

Email Content:
{body}

Task: Provide a concise 3-6 bullet point summary of this email.

Requirements:
- Each bullet point should be clear and actionable
- Focus on the most important information
- Highlight any requests, deadlines, or action items
- Keep each point under 20 words
- Start each point with "•"

Summary:"""


CLASSIFICATION_PROMPT = """Classify this email into ONE of the following categories:

Categories:
- urgent_action: Requires immediate action or response
- meeting_request: Meeting invitation or scheduling
- information: FYI, updates, newsletters
- task_assignment: Work assignments or delegations
- question: Asking for information or clarification
- approval: Requires approval or decision
- general: General correspondence

Email Subject: {subject}
Email From: {sender}
Email Preview: {preview}

Return ONLY the category name, nothing else."""


SENTIMENT_PROMPT = """Analyze the sentiment/tone of this email.

Email Content:
{body}

Return ONE word: positive, neutral, or negative"""


URGENCY_SCORE_PROMPT = """Rate the urgency of this email on a scale of 0.0 to 1.0.

Consider:
- Explicit urgency indicators (URGENT, ASAP, deadline)
- Implied urgency (short timeframes, waiting on response)
- Sender importance
- Content importance

Email Subject: {subject}
Email From: {sender}
Email Body Preview: {preview}

Return ONLY a decimal number between 0.0 and 1.0, nothing else.
Examples: 0.2, 0.5, 0.9"""
