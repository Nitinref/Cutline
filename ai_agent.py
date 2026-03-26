import asyncio
import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv

from models import EditCommand

load_dotenv()

SYSTEM_PROMPT = """You are a video editing command parser. The user will describe a video edit in plain English. You must respond ONLY with a single valid JSON object — no explanation, no markdown, no extra text.

Supported actions and their JSON format:
- Trim video: {"action":"trim","start_seconds":0,"end_seconds":30}
- Remove silence: {"action":"remove_silence","threshold_db":-35}
- Add subtitles: {"action":"add_subtitles"}
- Cut out a section: {"action":"cut_clip","from_seconds":10,"to_seconds":20}
- Change speed: {"action":"speed","factor":1.5}
- Unknown/unsupported: {"action":"unknown","message":"explain what you cannot do"}

Rules:
- Always return exactly one JSON object
- Never return markdown code blocks
- Infer seconds from natural language (e.g. 'first 30 seconds' → start:0, end:30)
- Default threshold_db for silence removal is -35
- Speed factor: 0.5 = half speed, 2.0 = double speed"""


async def parse_edit_command(user_prompt: str) -> EditCommand:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        print("Anthropic API key is missing")
        raise RuntimeError("AI parsing failed")

    try:
        client = Anthropic(api_key=api_key)

        def _call_claude():
            return client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )

        response = await asyncio.to_thread(_call_claude)
        text_parts = [
            block.text for block in response.content if getattr(block, "type", "") == "text"
        ]
        raw_text = "".join(text_parts).strip()
        parsed = json.loads(raw_text)
        return EditCommand(**parsed)
    except json.JSONDecodeError:
        print("Claude returned invalid JSON")
        return EditCommand(action="unknown", message="Could not parse")
    except Exception as exc:
        print(f"Anthropic request failed: {exc}")
        raise RuntimeError("AI parsing failed") from exc
