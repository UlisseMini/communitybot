# ABOUTME: Provides /claude command for asking Claude AI questions with channel message context.
# ABOUTME: Uses Anthropic API to generate responses based on recent conversation history.

import discord
from discord.ext import commands
from discord import option
import os
import logging
from anthropic import Anthropic

# Initialize client lazily to avoid errors if API key not set
_client = None


def get_client() -> Anthropic | None:
    """Get or create Anthropic client."""
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return None
        _client = Anthropic(api_key=api_key)
    return _client


class ClaudeAI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(name="claude", description="Ask Claude a question with context from recent messages")
    @option("prompt", description="Your question or prompt for Claude")
    @option("context_messages", description="Number of past messages to include for context (default: 50)", required=False, min_value=1, max_value=100)
    async def claude(self, ctx: discord.ApplicationContext, prompt: str, context_messages: int = 50):
        client = get_client()
        if not client:
            await ctx.respond(
                "Claude AI is not configured. The server admin needs to set the ANTHROPIC_API_KEY environment variable.",
                ephemeral=True
            )
            return

        # Defer response since API call may take a while (ephemeral=False makes it visible to all)
        await ctx.defer(ephemeral=False)

        try:
            # Fetch recent messages from the channel
            messages_history = []
            async for message in ctx.channel.history(limit=context_messages):
                # Skip the command invocation itself
                if message.id == ctx.interaction.id:
                    continue

                author_name = message.author.display_name
                content = message.content

                # Include attachment info if present
                if message.attachments:
                    attachment_info = ", ".join([f"[{a.filename}]" for a in message.attachments])
                    content = f"{content} {attachment_info}".strip()

                if content:
                    messages_history.append(f"{author_name}: {content}")

            # Reverse to get chronological order
            messages_history.reverse()

            # Build context string
            context_str = "\n".join(messages_history) if messages_history else "(No recent messages)"

            # Build the prompt with context
            full_prompt = f"""User: "{prompt}"

Here is the recent conversation context from a Discord channel:

<conversation>
{context_str}
</conversation>

Please provide a helpful response based on the conversation context if relevant."""

            # Call Claude API
            # ~900 tokens ≈ 3600 chars, leaving room within Discord's 4000 char bot limit
            response = client.messages.create(
                max_tokens=900,
                messages=[{"role": "user", "content": full_prompt}],
                model="claude-sonnet-4-5",
            )

            # Extract response text
            response_text = response.content[0].text

            # Format response with who asked
            formatted = f"**{ctx.author.display_name}** asked: {prompt}\n\n{response_text}"

            # Discord has a 4000 character limit for bots, so split if needed
            if len(formatted) <= 4000:
                await ctx.followup.send(formatted)
            else:
                # Split into chunks
                chunks = [formatted[i:i+3990] for i in range(0, len(formatted), 3990)]
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await ctx.followup.send(chunk)
                    else:
                        await ctx.channel.send(chunk)

        except Exception as e:
            logging.error(f"Claude API error: {str(e)}")
            await ctx.followup.send(
                f"Error calling Claude API: {str(e)}",
                ephemeral=True
            )


def setup(bot):
    bot.add_cog(ClaudeAI(bot))
