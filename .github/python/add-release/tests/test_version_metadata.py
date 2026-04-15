import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
MODULE_ROOT = HERE.parent
sys.path.insert(0, str(MODULE_ROOT))

vm = pytest.importorskip("version_metadata")


def test_build_downloads():
    version_metadata = vm.VersionMetadata("5.4.1", "hazelcast", "download")
    downloads = version_metadata._build_downloads("https://example.com/foo")

    assert downloads.full_zip.url == "https://example.com/foo.zip"
    assert downloads.slim_zip.url == "https://example.com/foo-slim.zip"
    assert downloads.full_tar.url == "https://example.com/foo.tar.gz"
    assert downloads.slim_tar.url == "https://example.com/foo-slim.tar.gz"


def test_download_size():
    version_metadata = vm.VersionMetadata("5.6.0", "hazelcast", "download")
    slim_zip = version_metadata.os_downloads.slim_zip

    assert (
        slim_zip.url
        == "https://github.com/hazelcast/hazelcast/releases/download/v5.6.0/hazelcast-5.6.0-slim.zip"
    )
    assert slim_zip.size == "41 MB"
