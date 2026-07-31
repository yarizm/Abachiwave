from collections.abc import AsyncIterator
from typing import cast
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from abachiwave.evaluations.samples import load_sample_set, sample_set_summary
from abachiwave.services.evaluations import (
    evaluation_run_lock_statement,
    execute_text_evaluation,
)
from abachiwave.services.task_queue import get_text_evaluation_task_queue
from abachiwave.services.text_provider import (
    TextGenerationRequest,
    TextGenerationResult,
    TextProviderUnavailableError,
)


class FakeEvaluationQueue:
    def __init__(self) -> None:
        self.enqueued: list[UUID] = []

    async def enqueue_text_evaluation(self, run_id: UUID) -> str:
        self.enqueued.append(run_id)
        return f"evaluation-job-{run_id}"


class FailingTextProvider:
    name = "failing"
    version = "1"

    async def generate(self, request: TextGenerationRequest) -> TextGenerationResult:
        raise TextProviderUnavailableError("Provider unavailable during evaluation")


@pytest_asyncio.fixture
async def evaluation_client(
    app: FastAPI,
) -> AsyncIterator[tuple[AsyncClient, FakeEvaluationQueue]]:
    queue = FakeEvaluationQueue()
    app.dependency_overrides[get_text_evaluation_task_queue] = lambda: queue
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, queue
    app.dependency_overrides.pop(get_text_evaluation_task_queue, None)


def test_fixed_sample_set_covers_product_scenarios() -> None:
    summary = sample_set_summary()
    samples = load_sample_set()

    assert summary["sample_count"] == 32
    assert summary["workflows"] == {
        "song_spec": 8,
        "lyrics": 8,
        "arrangement": 8,
        "revision": 8,
    }
    assert {
        "chinese_indie_rock",
        "english_pop",
        "instrumental_soundtrack",
        "existing_lyrics_continuation",
        "incomplete_input",
    }.issubset(set(cast(list[str], summary["categories"])))
    assert len({sample.id for sample in samples}) == len(samples)


@pytest.mark.asyncio
@pytest.mark.parametrize("workflow", ["song_spec", "lyrics", "arrangement", "revision"])
async def test_deterministic_baseline_exceeds_structured_success_target(
    workflow: str,
    evaluation_client: tuple[AsyncClient, FakeEvaluationQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, _queue = evaluation_client
    created = await client.post("/api/v1/evaluations", json={"workflow": workflow})
    assert created.status_code == 202

    completed = await execute_text_evaluation(
        UUID(created.json()["id"]),
        session_factory=session_factory,
    )

    assert completed is not None
    assert completed.status == "succeeded"
    assert completed.metrics["schema_valid_rate"] == 1.0
    assert completed.metrics["constraint_adherence_rate"] == 1.0
    assert completed.metrics["passes_schema_target"] is True


@pytest.mark.asyncio
async def test_deterministic_evaluation_records_metrics_and_blind_scores(
    evaluation_client: tuple[AsyncClient, FakeEvaluationQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, queue = evaluation_client
    sample_sets = await client.get("/api/v1/evaluations/sample-sets")
    assert sample_sets.status_code == 200
    assert sample_sets.json()[0]["sample_count"] == 32

    created = await client.post(
        "/api/v1/evaluations",
        json={"workflow": "song_spec", "sample_set": "creative-briefs-v1"},
    )
    assert created.status_code == 202
    run = created.json()
    assert run["status"] == "queued"
    assert run["sample_count"] == 8
    assert queue.enqueued == [UUID(run["id"])]

    completed = await execute_text_evaluation(
        UUID(run["id"]),
        session_factory=session_factory,
    )
    assert completed is not None
    assert completed.status == "succeeded"

    fetched = await client.get(f"/api/v1/evaluations/{run['id']}")
    assert fetched.status_code == 200
    metrics = fetched.json()["metrics"]
    assert metrics["schema_valid_rate"] == 1.0
    assert metrics["constraint_adherence_rate"] == 1.0
    assert metrics["passes_schema_target"] is True
    assert len(metrics["blind_pairs"]) == 8
    assert "_blind_assignments" not in fetched.text

    first_pair = metrics["blind_pairs"][0]
    scored = await client.post(
        f"/api/v1/evaluations/{run['id']}/human-scores",
        json={
            "evaluator_alias": "local-reviewer",
            "ratings": [
                {
                    "sample_id": first_pair["sample_id"],
                    "output_a_theme_consistency": 5,
                    "output_a_editability": 4,
                    "output_b_theme_consistency": 2,
                    "output_b_editability": 3,
                    "preferred_output": "A",
                }
            ],
            "notes": "Blind local comparison",
        },
    )
    assert scored.status_code == 201
    aggregate = scored.json()["human_scores"]["aggregate"]
    assert aggregate["submission_count"] == 1
    assert aggregate["rating_count"] == 1
    assert {aggregate["provider_theme_consistency"], aggregate["baseline_theme_consistency"]} == {
        2.0,
        5.0,
    }


@pytest.mark.asyncio
async def test_evaluation_failure_is_recorded_without_aborting_the_suite(
    evaluation_client: tuple[AsyncClient, FakeEvaluationQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, _queue = evaluation_client
    created = await client.post(
        "/api/v1/evaluations",
        json={"workflow": "revision"},
    )
    assert created.status_code == 202
    run_id = UUID(created.json()["id"])

    completed = await execute_text_evaluation(
        run_id,
        provider=FailingTextProvider(),
        session_factory=session_factory,
    )
    assert completed is not None
    assert completed.status == "failed"
    assert completed.error_code == "evaluation_no_valid_outputs"
    assert completed.metrics["schema_valid_rate"] == 0.0
    assert completed.metrics["error_counts"] == {"provider_unavailable": 8}


@pytest.mark.asyncio
async def test_evaluation_rejects_unknown_inputs_and_early_scoring(
    evaluation_client: tuple[AsyncClient, FakeEvaluationQueue],
) -> None:
    client, _queue = evaluation_client
    missing_set = await client.post(
        "/api/v1/evaluations",
        json={"workflow": "lyrics", "sample_set": "missing-v1"},
    )
    assert missing_set.status_code == 404

    created = await client.post("/api/v1/evaluations", json={"workflow": "lyrics"})
    assert created.status_code == 202
    early_score = await client.post(
        f"/api/v1/evaluations/{created.json()['id']}/human-scores",
        json={
            "evaluator_alias": "reviewer",
            "ratings": [
                {
                    "sample_id": "unknown",
                    "output_a_theme_consistency": 3,
                    "output_a_editability": 3,
                    "output_b_theme_consistency": 3,
                    "output_b_editability": 3,
                    "preferred_output": "tie",
                }
            ],
        },
    )
    assert early_score.status_code == 409


def test_evaluation_run_lock_uses_postgresql_for_update() -> None:
    statement = evaluation_run_lock_statement(uuid4())

    assert "FOR UPDATE" in str(statement)


@pytest.mark.asyncio
async def test_serial_human_score_submissions_accumulate(
    evaluation_client: tuple[AsyncClient, FakeEvaluationQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Regression guard: the read-modify-write on the human_scores JSON column
    must keep accumulating submissions after the locking refactor."""
    client, _queue = evaluation_client
    created = await client.post(
        "/api/v1/evaluations",
        json={"workflow": "song_spec", "sample_set": "creative-briefs-v1"},
    )
    assert created.status_code == 202
    run_id = UUID(created.json()["id"])

    completed = await execute_text_evaluation(run_id, session_factory=session_factory)
    assert completed is not None
    assert completed.status == "succeeded"

    fetched = await client.get(f"/api/v1/evaluations/{run_id}")
    first_pair = fetched.json()["metrics"]["blind_pairs"][0]
    rating = {
        "sample_id": first_pair["sample_id"],
        "output_a_theme_consistency": 5,
        "output_a_editability": 4,
        "output_b_theme_consistency": 2,
        "output_b_editability": 3,
        "preferred_output": "A",
    }
    for alias in ("reviewer-one", "reviewer-two"):
        scored = await client.post(
            f"/api/v1/evaluations/{run_id}/human-scores",
            json={"evaluator_alias": alias, "ratings": [rating], "notes": "double"},
        )
        assert scored.status_code == 201

    fetched_after = await client.get(f"/api/v1/evaluations/{run_id}")
    submissions = fetched_after.json()["human_scores"]["submissions"]
    assert len(submissions) == 2
    assert {item["evaluator_alias"] for item in submissions} == {
        "reviewer-one",
        "reviewer-two",
    }
