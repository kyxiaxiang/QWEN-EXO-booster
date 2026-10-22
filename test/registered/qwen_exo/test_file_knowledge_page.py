"""The knowledge console must page large corpora instead of shipping every file."""

from __future__ import annotations

import json

from qwen_exo_booster.file_knowledge import FileKnowledgeIndex


def _write_corpus(root, count: int, *, subdirectory: str = "") -> None:
    target = root / subdirectory if subdirectory else root
    target.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        (target / f"note-{index:05d}.md").write_text(
            f"# Note {index}\nflat corpus body\n", encoding="utf-8"
        )


def test_file_page_covers_a_flat_root_without_returning_every_row(tmp_path):
    root = tmp_path / "knowledge"
    _write_corpus(root, 250)
    _write_corpus(root, 3, subdirectory="nested")
    (root / "work-memory").mkdir()
    (root / "work-memory" / "today.md").write_text("# Today\nwork\n", encoding="utf-8")
    index = FileKnowledgeIndex(root, tmp_path / "state")
    index.refresh()

    first = index.page_files(folder="", nested=True, area="imported", limit=100, offset=0)
    assert first["total"] == 253
    assert len(first["files"]) == 100
    assert first["offset"] == 0
    assert all("content" not in row for row in first["files"])

    last = index.page_files(folder="", nested=True, area="imported", limit=100, offset=200)
    assert last["total"] == 253
    assert len(last["files"]) == 53
    assert {row["relative_path"] for row in first["files"]}.isdisjoint(
        {row["relative_path"] for row in last["files"]}
    )

    direct = index.page_files(folder="", nested=False, area="imported", limit=200, offset=0)
    assert direct["total"] == 250
    assert all("/" not in row["relative_path"] for row in direct["files"])

    nested = index.page_files(folder="nested", nested=False, area="all", limit=50, offset=0)
    assert nested["total"] == 3
    assert {row["relative_path"] for row in nested["files"]} == {
        "nested/note-00000.md",
        "nested/note-00001.md",
        "nested/note-00002.md",
    }

    titled = index.page_files(query="Note 12", area="imported", limit=50, offset=0)
    assert titled["total"] >= 1
    assert any("note-00012.md" in row["relative_path"] for row in titled["files"])

    summary = index.directory_summary()
    assert "files" not in summary
    assert summary["counts"][""]["files"] == 254
    assert summary["areas"]["imported"]["files"] == 253
    assert summary["areas"]["work"]["files"] == 1
    assert summary["counts"]["nested"]["files"] == 3
    assert "nested" in summary["directories"]


def test_directory_summary_stays_small_and_reads_still_work(tmp_path):
    root = tmp_path / "knowledge"
    _write_corpus(root, 120)
    index = FileKnowledgeIndex(root, tmp_path / "state")
    index.refresh()

    summary = index.directory_summary()
    assert "files" not in summary
    assert summary["counts"][""]["files"] == 120
    assert len(json.dumps(summary)) < 64_000

    page = index.page_files(folder="", nested=True, area="imported", limit=40, offset=80)
    assert page["total"] == 120
    assert len(page["files"]) == 40
    assert page["offset"] == 80

    opened = index.read(page["files"][0]["relative_path"], offset=0, limit=64)
    assert "flat corpus body" in opened["text"]

    renamed = index.move(page["files"][0]["relative_path"], "renamed-page.md")
    assert renamed["to"] == "renamed-page.md"
    assert index.page_files(query="renamed-page", limit=10)["total"] == 1
