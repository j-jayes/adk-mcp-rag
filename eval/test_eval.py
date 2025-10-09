"""Basic evalualtion for RAG Agent"""

import pathlib
import json

import dotenv
import pytest
from google.adk.evaluation.agent_evaluator import AgentEvaluator

pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="session", autouse=True)
def load_env():
    dotenv.load_dotenv()


# Discover datasets once; only files matching *.test.json are included
DATA_DIR = pathlib.Path(__file__).parent / "data"
DATASET_FILES = sorted(DATA_DIR.glob("*.test.json"))

@pytest.mark.asyncio
@pytest.mark.parametrize("ds_path", DATASET_FILES, ids=lambda p: p.name)
async def test_dataset(ds_path: pathlib.Path):
    # Optional: get a friendly label from the file
    label = ds_path.name
    try:
        with ds_path.open("r", encoding="utf-8") as f:
            eval_set_id = json.load(f).get("eval_set_id")
            if eval_set_id:
                label = eval_set_id
    except Exception:
        pass

    print(f"[eval] Running dataset: {label} ({ds_path.name})")

    await AgentEvaluator.evaluate(
        agent_module="agents",
        eval_dataset_file_path_or_dir=str(ds_path),
        num_runs=5,
    )