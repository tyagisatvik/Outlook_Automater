"""AI prompts for action recommendation"""

ACTION_RECOMMENDATION_PROMPT = """You are an executive assistant helping to triage emails and recommend actions.

Email Details:
- Subject: {subject}
- From: {sender}
- Received: {received_at}

Email Content:
{body}

Task: Identify recommended actions for this email.

Return a JSON array of action items. Each action should have:
- "action": Brief description of the action
- "type": One of [reply, delegate, schedule, review, file, no_action]
- "priority": One of [low, medium, high, urgent]
- "due_date": Suggested due date (ISO format) or null
- "reasoning": Brief explanation (1 sentence)

Example format:
[
  {{
    "action": "Reply to confirm attendance",
    "type": "reply",
    "priority": "high",
    "due_date": "2024-01-15T17:00:00Z",
    "reasoning": "Meeting is tomorrow and requires RSVP"
  }}
]

If no specific action is needed, return:
[{{"action": "No action required", "type": "no_action", "priority": "low", "due_date": null, "reasoning": "Informational email"}}]

Actions:"""


REPLY_SUGGESTION_PROMPT = """You are an executive assistant drafting a professional email reply.

Original Email:
From: {sender}
Subject: {subject}

{body}

Task: Draft a professional, concise reply to this email.

Requirements:
- Professional tone
- Address all questions/requests from original email
- Keep it brief (2-4 sentences)
- Do NOT include greeting or signature (will be added automatically)
- Start directly with the content

Draft Reply:"""


DELEGATION_PROMPT = """You are helping to identify the best team member to handle this email.

Email Subject: {subject}
Email Content: {body}

Available Team Members:
{team_members}

Task: Recommend who should handle this email and why.

Return a JSON object:
{{
  "recommended_person": "Name",
  "confidence": 0.0-1.0,
  "reasoning": "One sentence explanation"
}}

If no clear match, return:
{{
  "recommended_person": null,
  "confidence": 0.0,
  "reasoning": "Explanation"
}}

Recommendation:"""
