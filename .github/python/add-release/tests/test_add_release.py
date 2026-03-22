import os
import sys
from pathlib import Path

import pytest
import semver

HERE = Path(__file__).resolve().parent
MODULE_ROOT = HERE.parent
sys.path.insert(0, str(MODULE_ROOT))

from add_release import (
    insert_version_block_below_header,
    is_latest,
    update_hazelcast_metadata,
)


class DummyVersionMetadata:
    def __init__(self, version: str):
        self.version = semver.Version.parse(version)


def test_insert_version_block_inserts_after_header(tmp_path):
    header = "========== Java Client"
    version_block = "---\nVersion: 1.0.0"
    content = f"{header}\nLINE1\n"

    file_path = tmp_path / "imdg-clients.txt"
    file_path.write_text(content)

    insert_version_block_below_header(
        file_path, file_path.read_text(), header, version_block
    )

    updated = file_path.read_text()
    assert header + os.linesep + version_block in updated
    assert updated.startswith(header)


def test_insert_version_block_only_first_header(tmp_path):
    header = "========== Java Client"
    version_block = "---\nVersion: 1.0.0"
    content = f"{header}\nA\n{header}\nB\n"

    file_path = tmp_path / "imdg-clients.txt"
    file_path.write_text(content)

    insert_version_block_below_header(
        file_path, file_path.read_text(), header, version_block
    )

    updated = file_path.read_text()
    assert updated.count(version_block) == 1
    assert updated.splitlines()[0] == header


def test_update_hazelcast_metadata_latest_demotes_current_stable(tmp_path):
    header = "========== "
    current_stable_header = header + "Current Stable"
    previous_stable_header = header + "Previous Stable"
    content = (
        f"{current_stable_header}\n"
        "---\nVersion: 5.3.0\n"
        f"{previous_stable_header}\n"
        "---\nVersion: 5.2.0\n"
    )
    version_block = "---\nVersion: 5.4.0"

    file_path = tmp_path / "hazelcast-open-source.txt"
    file_path.write_text(content)

    update_hazelcast_metadata(DummyVersionMetadata("5.4.0"), file_path, version_block)

    updated = file_path.read_text()
    assert updated.startswith(current_stable_header)
    assert previous_stable_header in updated
    assert version_block in updated


def test_update_hazelcast_metadata_not_latest_inserts_under_previous(tmp_path):
    header = "========== "
    previous_stable_header = header + "Previous Stable"
    current_stable_header = header + "Current Stable"
    content = (
        f"{current_stable_header}\n"
        "---\nVersion: 5.4.0\n"
        f"{previous_stable_header}\n"
        "---\nVersion: 5.3.0\n"
    )
    version_block = "---\nVersion: 5.3.1"

    file_path = tmp_path / "hazelcast-open-source.txt"
    file_path.write_text(content)

    update_hazelcast_metadata(DummyVersionMetadata("5.3.1"), file_path, version_block)

    updated = file_path.read_text()
    assert previous_stable_header + os.linesep + version_block in updated


def test_is_latest():
    content = Path("jet-open-source.txt").read_text()

    assert is_latest(semver.Version.parse("0.0.1"), content) is False
    assert is_latest(semver.Version.parse("9.9.9"), content) is True
