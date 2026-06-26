import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from rag_runtime import InMemoryRagIndex, RagChunk
from state_memory import initialize_agent_state
from workflow_state import (
    agent_state_from_graph,
    agent_state_to_graph,
    append_unique,
    merge_dicts,
    rag_index_from_payload,
    rag_index_to_payload,
)


def test_agent_state_graph_round_trip_is_json_serializable():
    domain = initialize_agent_state(
        {"ticker": "2330.TW", "company_name": "台積電"},
        run_id="run-1",
    )

    graph = agent_state_to_graph(domain, pipeline_id="v1")
    json.dumps(graph, ensure_ascii=False)
    restored = agent_state_from_graph(graph)

    assert graph["pipeline_id"] == "v1"
    assert restored.model_dump(mode="json") == domain.model_dump(mode="json")


def test_agent_state_from_graph_ignores_workflow_only_fields():
    domain = initialize_agent_state(
        {"ticker": "2308.TW", "company_name": "台達電"},
        run_id="run-extra",
    )
    graph = agent_state_to_graph(domain, pipeline_id="v4")
    graph["status"] = "running"
    graph["blocking_issues"] = ["retryable"]

    restored = agent_state_from_graph(graph)

    assert restored.run_id == "run-extra"
    assert not hasattr(restored, "status")


def test_reducers_merge_parallel_agent_deltas_without_aliasing():
    left = {"1": {"markdown": "a"}}
    right = {"2": {"markdown": "b"}}

    merged = merge_dicts(left, right)
    right["2"]["markdown"] = "changed"

    assert set(merged) == {"1", "2"}
    assert merged["2"]["markdown"] == "b"


def test_append_unique_deduplicates_stable_ids():
    assert append_unique([{"id": "x"}], [{"id": "x"}, {"id": "y"}]) == [
        {"id": "x"},
        {"id": "y"},
    ]


def test_append_unique_deduplicates_json_equivalent_values():
    assert append_unique([{"b": 2, "a": 1}], [{"a": 1, "b": 2}]) == [
        {"b": 2, "a": 1},
    ]


def test_rag_index_payload_round_trip_preserves_searchable_chunks():
    index = InMemoryRagIndex(
        [
            RagChunk(
                "c1",
                "filing",
                "revenue grew",
                {"page": 1},
                [1.0, 0.0],
            )
        ],
        metadata={"model": "fake-embedding"},
    )

    restored = rag_index_from_payload(rag_index_to_payload(index))

    assert restored.chunks[0].text == "revenue grew"
    assert restored.chunks[0].metadata == {"page": 1}
    assert restored.metadata == {"model": "fake-embedding"}
    assert restored.has_embeddings is True

