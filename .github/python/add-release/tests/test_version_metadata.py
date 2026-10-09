import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
MODULE_ROOT = HERE.parent
sys.path.insert(0, str(MODULE_ROOT))

vm = pytest.importorskip("version_metadata")


@pytest.fixture(autouse=True)
def github_release_download_base_url(monkeypatch):
    def fake_download_base_url(self, github_org):
        return (
            f"https://github.com/{github_org}/hazelcast/releases/download/untagged-test"
        )

    monkeypatch.setattr(
        vm.OSVersionMetadata,
        "_get_github_release_download_base_url",
        fake_download_base_url,
    )


def test_build_downloads():
    version_metadata = vm.EEVersionMetadata("5.4.1", "download", "preprod")
    downloads = version_metadata._build_downloads(
        "https://example.com/foo", "https://example.com/bar"
    )

    assert downloads.full_zip.public_url == "https://example.com/foo.zip"
    assert downloads.slim_zip.public_url == "https://example.com/foo-slim.zip"
    assert downloads.full_tar.public_url == "https://example.com/foo.tar.gz"
    assert downloads.slim_tar.public_url == "https://example.com/foo-slim.tar.gz"


def test_download_size(monkeypatch):
    def fake_get_size(url):
        assert (
            url
            == "https://github.com/hazelcast/hazelcast/releases/download/untagged-test/hazelcast-5.6.0-slim.zip"
        )
        return "41 MB"

    monkeypatch.setattr(vm.DownloadUrl, "_get_size", staticmethod(fake_get_size))

    version_metadata = vm.OSVersionMetadata("5.6.0", "hazelcast")
    slim_zip = version_metadata.downloads.slim_zip

    assert (
        slim_zip.public_url
        == "https://github.com/hazelcast/hazelcast/releases/download/v5.6.0/hazelcast-5.6.0-slim.zip"
    )
    assert slim_zip.size == "41 MB"
