import logging
import os
from abc import ABC, abstractmethod
from dataclasses import InitVar, dataclass, field
from urllib.parse import urlparse
import requests
import semver
from github import Auth, Github
from humanize import naturalsize
from requests.auth import HTTPBasicAuth

DOWNLOAD_SUFFIXES = (".zip", "-slim.zip", ".tar.gz", "-slim.tar.gz")


@dataclass
class DownloadUrl:
    url: str
    size_in_bytes: int

    @property
    def human_readable_size(self) -> str:
        return naturalsize(self.size_in_bytes, format="%.0f")


@dataclass
class VersionMetadata(ABC):
    """Release metadata derived from a semantic version."""

    version: semver.Version | str

    def __post_init__(self):
        if isinstance(self.version, str):
            self.version = semver.Version.parse(self.version)
        self.docs_url = (
            f"https://docs.hazelcast.com/hazelcast/"
            f"{self.version.major}.{self.version.minor}/getting-started/"
            "quickstart.html"
        )

    @property
    @abstractmethod
    def downloads(self) -> dict[str, DownloadUrl]:
        """Downloads indexed by file suffix."""

    @property
    @abstractmethod
    def apidocs_url(self) -> str:
        """API documentation URL for this release."""


@dataclass
class OSVersionMetadata(VersionMetadata):
    github_org: InitVar[str]
    _downloads: dict[str, DownloadUrl] = field(init=False)

    def __post_init__(self, github_org):
        super().__post_init__()
        release_name = f"v{self.version}"
        prefix = f"hazelcast-{self.version}"
        live_base_url = (
            f"https://github.com/{github_org}/hazelcast/releases/download/"
            f"{release_name}/{prefix}"
        )
        with Github(auth=Auth.Token(os.getenv("GH_TOKEN"))) as github_client:
            repo = github_client.get_repo(f"{github_org}/hazelcast")
            releases = repo.get_releases()
            try:
                release = next(
                    release for release in releases if release.name == release_name
                )
            except StopIteration:
                raise ValueError(
                    f"Release `{release_name}` not found in {repo} - "
                    f"found {[release.name for release in releases]}"
                ) from None
            assets = {asset.name: asset.size for asset in release.get_assets()}
            expected = {f"{prefix}{suffix}" for suffix in DOWNLOAD_SUFFIXES}
            if missing_assets := expected - assets.keys():
                raise ValueError(
                    f"Release `{release_name}` is missing assets: {missing_assets}"
                )
            self._downloads = {
                suffix: DownloadUrl(
                    url=f"{live_base_url}{suffix}",
                    size_in_bytes=assets[f"{prefix}{suffix}"],
                )
                for suffix in DOWNLOAD_SUFFIXES
            }
        self.release_notes_url = (
            f"https://docs.hazelcast.com/hazelcast/"
            f"{self.version.major}.{self.version.minor}/release-notes/community"
            f"#{self.version.major}-{self.version.minor}-{self.version.patch}"
        )
        self.sources_url = (
            f"https://github.com/{github_org}/hazelcast/tree/v{self.version}"
        )
        self.code_samples_url = (
            f"https://github.com/{github_org}/hazelcast-code-samples"
        )

    @property
    def downloads(self) -> dict[str, DownloadUrl]:
        return self._downloads

    @property
    def apidocs_url(self) -> str:
        return f"https://docs.hazelcast.org/docs/{self.version}/javadoc"


@dataclass
class EEVersionMetadata(VersionMetadata):
    release_repo_name: InitVar[str]
    jfrog_preprod_files_repo: InitVar[str]
    _downloads: dict[str, DownloadUrl] = field(init=False)

    def __post_init__(self, release_repo_name, jfrog_preprod_files_repo):
        super().__post_init__()
        prefix = f"hazelcast-enterprise-{self.version}"
        live_base_url = f"https://repository.hazelcast.com/{release_repo_name}/hazelcast-enterprise/{prefix}"
        preprod_base_url = f"https://repository.hazelcast.com/{jfrog_preprod_files_repo}/hazelcast-enterprise/{prefix}"
        auth = HTTPBasicAuth(
            os.getenv("RELEASE_REPO_USER"),
            os.getenv("RELEASE_REPO_TOKEN"),
        )
        with requests.Session() as session:
            session.auth = auth
            self._downloads = {
                suffix: self._get_download(
                    session,
                    f"{preprod_base_url}{suffix}",
                    f"{live_base_url}{suffix}",
                )
                for suffix in DOWNLOAD_SUFFIXES
            }
        self.release_notes_url = f"https://docs.hazelcast.com/hazelcast/{self.version.major}.{self.version.minor}/release-notes/enterprise#{self.version.major}-{self.version.minor}-{self.version.patch}"

    @staticmethod
    def _get_download(
        session: requests.Session,
        preprod_url: str,
        live_url: str,
    ) -> DownloadUrl:
        logging.debug("Getting size of %s", preprod_url)
        with session.get(
            preprod_url,
            allow_redirects=True,
            stream=True,
        ) as response:
            response.raise_for_status()
            content_length = response.headers.get("Content-Length")
            if content_length is None:
                raise ValueError(f"{preprod_url} did not return a Content-Length")
            try:
                size_in_bytes = int(content_length)
            except ValueError:
                raise ValueError(
                    f"{preprod_url} returned an invalid Content-Length: {content_length!r}"
                ) from None
            return DownloadUrl(url=live_url, size_in_bytes=size_in_bytes)

    @property
    def downloads(self) -> dict[str, DownloadUrl]:
        return self._downloads

    @property
    def apidocs_url(self) -> str:
        return f"https://docs.hazelcast.org/hazelcast-ee-docs/{self.version}/javadoc"
