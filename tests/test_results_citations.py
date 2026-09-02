"""spec-038 backend tests: metric extraction (AC-1), auto/manual metrics
lifecycle (AC-2), run compare API (AC-3), BibTeX/GB-T 7714 builders
(AC-4/AC-5) and the citation download endpoint."""
import re

import pytest

from app import config, database
from app.citations import build_bibtex, build_gbt7714
from app.experiment_runner import extract_and_store_metrics
from app.metrics_extractor import (
    KEY_PATTERN,
    extract_metrics,
    extract_metrics_from_text,
)


def _mk_run(log_text=None):
    experiment_id = database.insert_experiment("innovation", 1, [], None)
    run = database.create_experiment_run(
        experiment_id=experiment_id, server_id="srv-1", mode="manual"
    )
    if log_text is not None:
        log_file = config.settings.data_dir / "experiment_runs" / f"{run['id']}.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text(log_text, encoding="utf-8")
    return run


# ---------------------------------------------------------------------------
# AC-1: extractor matrix
# ---------------------------------------------------------------------------


def test_extractor_basic_formats():
    assert extract_metrics_from_text("loss=0.1") == {"loss": 0.1}
    assert extract_metrics_from_text("Acc: 95.2%") == {"acc": 95.2}
    assert extract_metrics_from_text("Epoch 3 - f1_score 0.88") == {
        "f1_score": 0.88
    }
    assert extract_metrics_from_text("val_loss 0.45") == {"val_loss": 0.45}


def test_extractor_last_value_wins():
    text = "epoch 1 loss 0.5\nepoch 2 loss=0.3\nepoch 3 Acc: 0.91"
    assert extract_metrics_from_text(text) == {"loss": 0.3, "acc": 0.91}


def test_extractor_ignores_non_metric_keys():
    assert extract_metrics_from_text("epoch 3\nstep 100\nlr 0.001\nit 50") == {}


def test_extractor_case_insensitive_prefix_variants():
    assert extract_metrics_from_text("VAL_LOSS 0.45\nBest_Acc: 0.91") == {
        "val_loss": 0.45,
        "best_acc": 0.91,
    }


def test_extractor_multiple_metrics_one_line():
    assert extract_metrics_from_text("loss 0.12 acc 0.95") == {
        "loss": 0.12,
        "acc": 0.95,
    }


def test_extractor_value_must_have_word_boundary():
    assert extract_metrics_from_text("loss=0.12s") == {}
    assert extract_metrics_from_text("loss 0.12s") == {}


def test_extractor_garbage_and_missing_file():
    assert extract_metrics_from_text("nothing numeric to see here !!!") == {}
    assert extract_metrics_from_text("") == {}
    assert extract_metrics(config.settings.data_dir / "definitely-missing.log") == {}


def test_key_pattern_constant_is_regex_source():
    assert re.search(KEY_PATTERN, "val_loss", re.IGNORECASE)
    assert re.search(KEY_PATTERN, "mAP", re.IGNORECASE)
    assert not re.search(KEY_PATTERN, "epoch", re.IGNORECASE)
    assert not re.search(KEY_PATTERN, "lr", re.IGNORECASE)


def _pipe_table_log():
    lines = ["[2026-09-01 10:00:00] start training"]
    lines.append("epoch | train_loss | test_loss")
    for i in range(1, 12):
        lines.append(
            f"{i:>5} |   {0.242046 - i * 0.0015:.6f}"
            f" |  {0.193377 - i * 0.0008:.6f}"
        )
    lines.append("   12 |   0.223536 |  0.182540")
    lines.append("DONE training")
    lines.append("best checkpoint saved to model.pt")
    return "\n".join(lines)


def test_extractor_pipe_table_real_training_log():
    metrics = extract_metrics_from_text(_pipe_table_log())
    assert set(metrics) == {"train_loss", "test_loss"}
    assert metrics["train_loss"] == pytest.approx(0.223536)
    assert metrics["test_loss"] == pytest.approx(0.18254)


def test_extractor_ignores_pipe_table_without_header():
    text = "1 | 0.242046 | 0.193377\n2 | 0.240000 | 0.190000\n"
    assert extract_metrics_from_text(text) == {}


def test_extractor_mixed_regex_and_pipe_table():
    text = (
        "train_loss 0.99\n"
        "epoch | train_loss | test_loss\n"
        "1 | 0.5 | 0.4\n"
        "2 | 0.3 | 0.2\n"
    )
    metrics = extract_metrics_from_text(text)
    assert metrics["train_loss"] == pytest.approx(0.3)
    assert metrics["test_loss"] == pytest.approx(0.2)
    assert set(metrics) == {"train_loss", "test_loss"}


# ---------------------------------------------------------------------------
# AC-2: succeeded auto-extract + manual extract + manual edit
# ---------------------------------------------------------------------------


def test_extract_and_store_metrics_writes_db(client):
    run = _mk_run("test_loss 0.42\naccuracy: 88.5%\n")
    metrics = extract_and_store_metrics(run["id"])
    assert metrics == {"test_loss": 0.42, "accuracy": 88.5}
    assert database.get_experiment_run(run["id"])["metrics"] == {
        "test_loss": 0.42,
        "accuracy": 88.5,
    }


def test_extract_and_store_metrics_without_log_stores_empty(client):
    run = _mk_run()
    metrics = extract_and_store_metrics(run["id"])
    assert metrics == {}
    assert database.get_experiment_run(run["id"])["metrics"] == {}


def test_extract_endpoint_reparse_and_missing_log(client):
    run = _mk_run()
    resp = client.post(f"/api/experiment-runs/{run['id']}/metrics/extract")
    assert resp.status_code == 400

    _mk_run_log(run, "test_loss 0.42\n")
    resp = client.post(f"/api/experiment-runs/{run['id']}/metrics/extract")
    assert resp.status_code == 200
    assert resp.json()["metrics"] == {"test_loss": 0.42}

    missing = client.post("/api/experiment-runs/999999/metrics/extract")
    assert missing.status_code == 404


def _mk_run_log(run, text):
    log_file = config.settings.data_dir / "experiment_runs" / f"{run['id']}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text(text, encoding="utf-8")
    return log_file


def test_put_metrics_endpoint_edit_and_validation(client):
    run = _mk_run()
    resp = client.put(
        f"/api/experiment-runs/{run['id']}/metrics",
        json={"metrics": {"loss": "0.33", "acc": 0.9}},
    )
    assert resp.status_code == 200
    assert resp.json()["metrics"] == {"loss": 0.33, "acc": 0.9}
    assert database.get_experiment_run(run["id"])["metrics"] == {
        "loss": 0.33,
        "acc": 0.9,
    }

    bad = client.put(
        f"/api/experiment-runs/{run['id']}/metrics",
        json={"metrics": {"loss": "not-a-number"}},
    )
    assert bad.status_code == 400
    missing = client.put(
        "/api/experiment-runs/999999/metrics", json={"metrics": {}}
    )
    assert missing.status_code == 404


def test_run_detail_returns_metrics(client):
    run = _mk_run("best_acc 0.77\n")
    assert extract_and_store_metrics(run["id"])
    data = client.get(f"/api/experiment-runs/{run['id']}").json()
    assert data["metrics"] == {"best_acc": 0.77}

    fresh = _mk_run()
    data = client.get(f"/api/experiment-runs/{fresh['id']}").json()
    assert data["metrics"] is None


# ---------------------------------------------------------------------------
# AC-3: compare API
# ---------------------------------------------------------------------------


def test_compare_returns_union_keys_and_items(client):
    run_a = _mk_run()
    run_b = _mk_run()
    run_c = _mk_run()
    database.set_experiment_run_metrics(run_a["id"], {"loss": 0.1, "acc": 0.9})
    database.set_experiment_run_metrics(run_b["id"], {"loss": 0.2, "f1": 0.8})
    database.set_experiment_run_metrics(run_c["id"], {})

    resp = client.post(
        "/api/experiment-runs/compare",
        json={"ids": [run_a["id"], run_b["id"], run_c["id"]]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["metric_keys"] == ["acc", "f1", "loss"]
    assert [r["id"] for r in data["runs"]] == [run_a["id"], run_b["id"], run_c["id"]]
    assert data["runs"][0]["metrics"] == {"loss": 0.1, "acc": 0.9}
    assert data["runs"][2]["metrics"] == {}
    assert data["runs"][0]["experiment_title"] == "创新点 #1"
    assert data["runs"][0]["duration_seconds"] is not None
    assert data["runs"][0]["status"] == "pending"


def test_compare_missing_id_404(client):
    resp = client.post("/api/experiment-runs/compare", json={"ids": [1, 999999]})
    assert resp.status_code == 404


def test_compare_bad_id_count_400(client):
    one = client.post("/api/experiment-runs/compare", json={"ids": [1]})
    assert one.status_code == 400
    eleven = client.post(
        "/api/experiment-runs/compare", json={"ids": list(range(1, 12))}
    )
    assert eleven.status_code == 400


# ---------------------------------------------------------------------------
# AC-4: BibTeX builder
# ---------------------------------------------------------------------------


def _paper(**overrides):
    base = {
        "arxiv_id": "2401.00001",
        "title": "Attention Is All You Need",
        "authors": ["Ashish Vaswani", "Noam Shazeer"],
        "published": "2024-01-02",
        "url": "https://arxiv.org/abs/2401.00001",
        "source": "arxiv",
        "pdf_url": "https://arxiv.org/pdf/2401.00001",
    }
    base.update(overrides)
    return base


def test_bibtex_basic_fields():
    text = build_bibtex([_paper()])
    assert "@article{vaswani2024attention," in text
    assert "title = {Attention Is All You Need}" in text
    assert "author = {Ashish Vaswani and Noam Shazeer}" in text
    assert "year = {2024}" in text
    assert "journal = {arXiv preprint arXiv:2401.00001}" in text
    assert "url = {https://arxiv.org/abs/2401.00001}" in text


def test_bibtex_key_dedup_suffixes():
    text = build_bibtex([_paper(), _paper(), _paper()])
    assert "@article{vaswani2024attention," in text
    assert "@article{vaswani2024attention-a," in text
    assert "@article{vaswani2024attention-b," in text


def test_bibtex_escapes_latex_specials():
    text = build_bibtex([_paper(title="A & B 100% C# D_E")])
    assert "title = {A \\& B 100\\% C\\# D\\_E}" in text


def test_bibtex_missing_fields_still_valid():
    text = build_bibtex(
        [_paper(authors=[], published=None, source="cnki", url="https://x.cn/a")]
    )
    assert "author = {" not in text
    assert "year = {" not in text
    assert "journal = {" not in text
    assert "note = {Available at: https://x.cn/a}" in text
    assert "@article{unknown" in text


# ---------------------------------------------------------------------------
# AC-5: GB/T 7714 builder
# ---------------------------------------------------------------------------


def test_gbt7714_more_than_three_authors_use_et_al():
    text = build_gbt7714(
        [_paper(authors=["A One", "B Two", "C Three", "D Four"])]
    )
    assert text.startswith("[1] A One, B Two, C Three, 等.")
    assert "Attention Is All You Need[J/OL]" in text
    assert "2024[" in text
    assert re.search(r"\[\d{4}-\d{2}-\d{2}\]", text)
    assert "https://arxiv.org/abs/2401.00001" in text


def test_gbt7714_few_authors_numbered_list():
    papers = [
        _paper(authors=["A One", "B Two"]),
        _paper(arxiv_id="2402.00002", title="Second Paper"),
    ]
    text = build_gbt7714(papers)
    assert "等" not in text
    assert text.startswith("[1] A One, B Two. ")
    assert "[2] Ashish Vaswani, Noam Shazeer. Second Paper[J/OL]." in text


def test_gbt7714_missing_year_and_url_segments_skipped():
    text = build_gbt7714(
        [_paper(authors=["A One"], published=None, url="", pdf_url="")]
    )
    assert not re.search(r"\[\d{4}-\d{2}-\d{2}\]", text)
    assert "https://" not in text
    assert text.strip().endswith("Attention Is All You Need[J/OL].")


# ---------------------------------------------------------------------------
# Citation download endpoint (AC-4/AC-5 response headers)
# ---------------------------------------------------------------------------


def test_citation_export_endpoint_headers_and_body(client):
    paper = _paper()
    database.upsert_paper(paper)

    resp = client.post(
        "/api/papers/export/citations",
        json={"arxiv_ids": [paper["arxiv_id"]], "format": "bibtex"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert "attachment" in resp.headers["content-disposition"]
    assert "papers.bib" in resp.headers["content-disposition"]
    assert "@article{vaswani2024attention," in resp.text

    resp = client.post(
        "/api/papers/export/citations",
        json={"arxiv_ids": [paper["arxiv_id"]], "format": "gbt7714"},
    )
    assert resp.status_code == 200
    assert "references.txt" in resp.headers["content-disposition"]
    assert resp.text.startswith("[1] ")


def test_citation_export_endpoint_validation(client):
    empty = client.post("/api/papers/export/citations", json={"arxiv_ids": []})
    assert empty.status_code == 400
    bad_format = client.post(
        "/api/papers/export/citations",
        json={"arxiv_ids": ["2401.00001"], "format": "ris"},
    )
    assert bad_format.status_code == 400
    missing = client.post(
        "/api/papers/export/citations",
        json={"arxiv_ids": ["2401.99999"], "format": "bibtex"},
    )
    assert missing.status_code == 404
