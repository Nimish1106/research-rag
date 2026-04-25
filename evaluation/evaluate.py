import json
import time
import requests
from typing import Dict, List, Any

API_BASE = "http://localhost:8000/api"

def ask_question(document_id: str, question: str) -> Dict[str, Any]:
    response = requests.post(
        f"{API_BASE}/query/ask",
        json={
            "document_id": document_id,
            "question": question
        },
        timeout=180
    )
    response.raise_for_status()
    return response.json()

def list_documents() -> List[Dict[str, Any]]:
    response = requests.get(f"{API_BASE}/documents", timeout=30)
    response.raise_for_status()
    return response.json()

def find_document_id_by_filename(filename: str) -> str:
    documents = list_documents()
    for doc in documents:
        if doc["filename"] == filename and doc["status"] == "ready":
            return doc["id"]
    raise ValueError(f"Ready document not found for filename: {filename}")

def answer_contains_expected(answer: str, expected_terms: List[str]) -> float:
    if not expected_terms:
        return 1.0
    answer_lower = answer.lower()
    hits = sum(1 for term in expected_terms if term.lower() in answer_lower)
    return hits / len(expected_terms)

def evidence_page_precision(evidence: List[Dict[str, Any]], expected_pages: List[int]) -> float:
    if not evidence:
        return 0.0
    if not expected_pages:
        return 1.0
    hits = sum(1 for ev in evidence if ev["page_number"] in expected_pages)
    return hits / len(evidence)

def evidence_type_precision(evidence: List[Dict[str, Any]], expected_types: List[str]) -> float:
    if not evidence:
        return 0.0
    if not expected_types:
        return 1.0
    hits = sum(1 for ev in evidence if ev["chunk_type"] in expected_types)
    return hits / len(evidence)

def run_eval(dataset_path: str):
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    results = []
    total_latency = 0.0

    for i, item in enumerate(dataset, 1):
        filename = item["document_filename"]
        question = item["question"]
        expected_terms = item.get("expected_answer_contains", [])
        expected_pages = item.get("expected_pages", [])
        expected_types = item.get("expected_chunk_types", [])

        try:
            document_id = find_document_id_by_filename(filename)
        except Exception as e:
            results.append({
                "index": i,
                "question": question,
                "error": f"document lookup failed: {e}"
            })
            continue

        start = time.time()
        try:
            response = ask_question(document_id, question)
            latency = time.time() - start
            total_latency += latency

            answer_score = answer_contains_expected(
                response["answer"],
                expected_terms
            )
            page_precision = evidence_page_precision(
                response.get("evidence", []),
                expected_pages
            )
            type_precision = evidence_type_precision(
                response.get("evidence", []),
                expected_types
            )

            results.append({
                "index": i,
                "question": question,
                "latency_sec": round(latency, 2),
                "answer_term_match": round(answer_score, 3),
                "evidence_page_precision": round(page_precision, 3),
                "evidence_type_precision": round(type_precision, 3),
                "answer": response["answer"][:500],
                "evidence_count": len(response.get("evidence", []))
            })

        except Exception as e:
            results.append({
                "index": i,
                "question": question,
                "error": str(e)
            })

    valid_results = [r for r in results if "error" not in r]
    summary = {
        "num_examples": len(dataset),
        "num_successful": len(valid_results),
        "avg_latency_sec": round(
            sum(r["latency_sec"] for r in valid_results) / len(valid_results), 2
        ) if valid_results else None,
        "avg_answer_term_match": round(
            sum(r["answer_term_match"] for r in valid_results) / len(valid_results), 3
        ) if valid_results else None,
        "avg_evidence_page_precision": round(
            sum(r["evidence_page_precision"] for r in valid_results) / len(valid_results), 3
        ) if valid_results else None,
        "avg_evidence_type_precision": round(
            sum(r["evidence_type_precision"] for r in valid_results) / len(valid_results), 3
        ) if valid_results else None,
        "results": results
    }

    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=str,
        default="evaluation/eval_dataset.sample.json",
        help="Path to evaluation dataset JSON"
    )
    args = parser.parse_args()

    run_eval(args.dataset)