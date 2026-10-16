import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
MODULE_ROOT = HERE.parent
sys.path.insert(0, str(MODULE_ROOT))

vm = pytest.importorskip("version_metadata")


class FakeGithub:
    def __init__(self, auth):
        self.auth = auth

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get_repo(self, name):
        assert name == "hazelcast/hazelcast"
        return FakeRepo()


class FakeRepo:
    def get_releases(self):
        return [FakeRelease()]

    def __str__(self):
        return "hazelcast/hazelcast"


class FakeRelease:
    name = "v5.6.0"

    def get_assets(self):
        return [
            FakeAsset(f"hazelcast-5.6.0{suffix}", size)
            for suffix, size in zip(
                vm.DOWNLOAD_SUFFIXES,
                (41000000, 20000000, 42000000, 21000000),
            )
        ]


class FakeAsset:
    def __init__(self, name, size):
        self.name = name
        self.size = size


def test_os_downloads_use_github_release_assets(monkeypatch):
    monkeypatch.setattr(vm, "Github", FakeGithub)
    monkeypatch.setenv("GH_TOKEN", "test-token")

    metadata = vm.OSVersionMetadata("5.6.0", "hazelcast")

    downloads = metadata.downloads
    assert set(downloads) == set(vm.DOWNLOAD_SUFFIXES)
    assert downloads[".zip"].url == (
        "https://github.com/hazelcast/hazelcast/releases/download/"
        "v5.6.0/hazelcast-5.6.0.zip"
    )
    assert downloads["-slim.zip"].size_in_bytes == 20000000
    assert downloads["-slim.zip"].human_readable_size == "20 MB"


class FakeResponse:
    def __init__(self, content_length):
        self.headers = {"Content-Length": str(content_length)}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self):
        self.auth = None
        self.requested_urls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, url, **_kwargs):
        self.requested_urls.append(url)
        return FakeResponse(41000000)


def test_enterprise_download_sizes_are_cached_from_preprod(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(vm.requests, "Session", lambda: session)

    metadata = vm.EEVersionMetadata("5.4.1", "download", "preprod")

    downloads = metadata.downloads
    assert set(downloads) == set(vm.DOWNLOAD_SUFFIXES)
    assert len(session.requested_urls) == len(vm.DOWNLOAD_SUFFIXES)
    assert downloads["-slim.zip"].url == (
        "https://repository.hazelcast.com/download/hazelcast-enterprise/"
        "hazelcast-enterprise-5.4.1-slim.zip"
    )
    assert downloads["-slim.zip"].size_in_bytes == 41000000
    assert downloads["-slim.zip"].human_readable_size == "41 MB"
