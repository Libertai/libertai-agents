from datetime import date


def get_view_agent_secret_message(agent_id: str) -> str:
    return f"I confirm that I want to view the secret key of my agent {agent_id} today ({date.today()})."
