import logging
from discord.ext import commands
from redbot.core import app_commands
from cogs.utilities.llm.chain import LLMChain
from cogs.utilities.llm.providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)

class LLMCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.chain = self._initialize_chain()
        
    def _initialize_chain(self) -> LLMChain:
        """Initialize LLM chain with configured providers"""
        # Import configuration for LLM from the cog's config
        from cogs.llm.config import LLMConfig
        config = LLMConfig()
        chain = LLMChain(debug=config.debug)
        
        # Add providers based on the configured default_providers list
        if "openai" in config.default_providers:
            chain.add_node(
                name="openai_default",
                provider=OpenAIProvider(),
                prompt_modifier=lambda p: f"{p} [Respond in under 500 characters]"
            )
        
        # Additional providers can be added in future iterations based on config settings
        return chain

    @app_commands.command()
    @app_commands.describe(prompt="Your question or prompt for the AI")
    async def ask(self, interaction, prompt: str):
        """Query the AI with your question"""
        await interaction.response.defer()
        
        try:
            response = await self.chain.run(prompt)
            
            if response.error:
                return await interaction.followup.send(
                    "⚠️ Error processing your request. Please try again later.",
                    ephemeral=True
                )
                
            # Format response for Discord
            formatted = f"🤖 **Response**\n{response.content}"
            
            await interaction.followup.send(formatted)
            
        except Exception as e:
            logger.error(f"LLM request failed: {str(e)}")
            await interaction.followup.send("Technical difficulty...")

async def setup(bot):
    await bot.add_cog(LLMCog(bot)) 