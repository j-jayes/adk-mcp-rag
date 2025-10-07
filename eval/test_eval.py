"""Basic evalualtion for RAG Agent"""

import pathlib

import dotenv
import pytest
from google.adk.evaluation.agent_evaluator import AgentEvaluator

pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="session", autouse=True)
def load_env():
    dotenv.load_dotenv()


@pytest.mark.asyncio
async def test_all():
    """Test the agent's basic ability on a few examples."""
    await AgentEvaluator.evaluate(
        "agents", # I think this should be the module name?? Or the folder that contains the agent.py file, it needs to find the root agent declared somewhere.
        str(pathlib.Path(__file__).parent / "data"),
        num_runs=5,
    )
