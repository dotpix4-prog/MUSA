import os

class Config:
    """Configuration loader for MUSA."""

    @property
    def anthropic_api_key(self) -> str:
        """Returns the Anthropic API key or raises an EnvironmentError."""
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Please set it to use the 'ask' command."
            )
        return key

    @property
    def groq_api_key(self) -> str:
        """Returns the Groq API key or raises an EnvironmentError."""
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise EnvironmentError(
                "GROQ_API_KEY environment variable is not set. "
                "Get a free key at https://console.groq.com/keys"
            )
        return key