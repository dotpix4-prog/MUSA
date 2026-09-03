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
