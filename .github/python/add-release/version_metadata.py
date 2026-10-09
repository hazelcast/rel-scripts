import logging
import os
from abc import ABC, abstractmethod
from dataclasses import InitVar, dataclass, field
from posixpath import dirname
from urllib.parse import urlparse

import requests
import semver
from github import Auth, Github
from humanize import naturalsize
from requests.auth import HTTPBasicAuth


def _github_token() -> str | None:
    return os.getenv("GH_TOKEN")


def _github_client() -> Github:
    return Github(auth=Auth.Token(_github_token()))


@dataclass
class DownloadUrl:
    """A download URL with lazily computed, human-friendly size."""

    _live_base_url: str
    _preprod_base_url: str
    _suffix: str
    _size: str = field(default=None, init=False)

    @staticmethod
    def _get_size(url: str) -> str:
        """Fetch and cache the artifact size without _actually_ downloading it."""
        logging.debug("Getting size of %s", url)

        username = os.getenv("RELEASE_REPO_USER")
        password = os.getenv("RELEASE_REPO_TOKEN")

        auth = (
            HTTPBasicAuth(username, password)
            if urlparse(url).hostname == "repository.hazelcast.com"
            and username
            and password
            else None
        )
        headers = (
            {"Authorization": f"Bearer {_github_token()}"}
            if urlparse(url).hostname == "github.com" and _github_token()
            else None
        )

        with requests.get(
            url,
            allow_redirects=True,
            auth=auth,
            headers=headers,
            stream=True,
        ) as response:
            response.raise_for_status()

            content_length = response.headers.get("Content-Length")

            if content_length:
                return naturalsize(int(content_length), format="%.0f")

            raise Exception(f"{url} did not return a size")

    @property
    def size(self) -> str:
        if self._size is None:
            try:
                self._size = self._get_size(self.preprod_url)
            except requests.RequestException:
                self._size = self._get_size(self.public_url)

        return self._size

    @property
    def public_url(self) -> str:
        return f"{self._live_base_url}{self._suffix}"

    @property
    def preprod_url(self) -> str:
        return f"{self._preprod_base_url}{self._suffix}"


@dataclass
class Downloads:
    """Container for the set of downloadable artifact URLs."""

    full_zip: DownloadUrl
    slim_zip: DownloadUrl
    full_tar: DownloadUrl
    slim_tar: DownloadUrl


@dataclass
class VersionMetadata(ABC):
    """Release metadata derived from a semantic version."""

    version: semver.Version | str

    def __post_init__(self):
        if isinstance(self.version, str):
            self.version = semver.Version.parse(self.version)

        self.docs_url = f"https://docs.hazelcast.com/hazelcast/{self.version.major}.{self.version.minor}/getting-started/quickstart.html"

    @property
    @abstractmethod
    def downloads(self):
        """Download metadata for this release."""

    @property
    @abstractmethod
    def apidocs_url(self) -> str:
        """API documentation URL for this release."""

    def _build_downloads(self, live_base_url: str, preprod_base_url: str) -> Downloads:
        """Build a Downloads object for a given artifact base live URL."""
        return Downloads(
            full_zip=DownloadUrl(live_base_url, preprod_base_url, ".zip"),
            slim_zip=DownloadUrl(live_base_url, preprod_base_url, "-slim.zip"),
            full_tar=DownloadUrl(live_base_url, preprod_base_url, ".tar.gz"),
            slim_tar=DownloadUrl(live_base_url, preprod_base_url, "-slim.tar.gz"),
        )


@dataclass
class OSVersionMetadata(VersionMetadata):
    github_org: InitVar[str]

    def __post_init__(self, github_org):
        super().__post_init__()

        self._downloads = self._build_downloads(
            f"https://github.com/{github_org}/hazelcast/releases/download/v{self.version}/hazelcast-{self.version}",
            f"{self._get_github_release_download_base_url(github_org)}/hazelcast-{self.version}",
        )

        self.release_notes_url = f"https://docs.hazelcast.com/hazelcast/{self.version.major}.{self.version.minor}/release-notes/community#{self.version.major}-{self.version.minor}-{self.version.patch}"

        self.sources_url = (
            f"https://github.com/{github_org}/hazelcast/tree/v{self.version}"
        )
        self.code_samples_url = (
            f"https://github.com/{github_org}/hazelcast-code-samples"
        )

    @property
    def downloads(self):
        return self._downloads

    @property
    def apidocs_url(self) -> str:
        return f"https://docs.hazelcast.org/docs/{self.version}/javadoc"

    def _get_github_release_download_base_url(self, github_org: str) -> str:
        """Find the release and derive its asset download base URL - for draft releases, this is non-trivial."""

        with _github_client() as github_client:
            repo = github_client.get_repo(f"{github_org}/hazelcast")
            release_name = f"v{self.version}"

            try:
                # have to iterate as get_release(releasename) doesn't find drafts
                releases = repo.get_releases()
                release = next(
                    release for release in releases if release.name == release_name
                )

                asset = next(iter(release.get_assets()))

                if asset:
                    parsed_url = urlparse(asset.browser_download_url)
                    return parsed_url._replace(path=dirname(parsed_url.path)).geturl()
                else:
                    raise ValueError(f"No assets found for version {release}")
            except StopIteration:
                raise ValueError(
                    f"Release `{release_name}` not found in {repo} - found {[release.name for release in releases]}"
                ) from None


@dataclass
class EEVersionMetadata(VersionMetadata):
    release_repo_name: InitVar[str]
    jfrog_preprod_files_repo: InitVar[str]

    def __post_init__(self, release_repo_name, jfrog_preprod_files_repo):
        super().__post_init__()

        self._downloads = self._build_downloads(
            f"https://repository.hazelcast.com/{release_repo_name}/hazelcast-enterprise/hazelcast-enterprise-{self.version}",
            f"https://repository.hazelcast.com/{jfrog_preprod_files_repo}/hazelcast-enterprise/hazelcast-enterprise-{self.version}",
        )

        self.release_notes_url = f"https://docs.hazelcast.com/hazelcast/{self.version.major}.{self.version.minor}/release-notes/enterprise#{self.version.major}-{self.version.minor}-{self.version.patch}"

    @property
    def downloads(self):
        return self._downloads

    @property
    def apidocs_url(self) -> str:
        return f"https://docs.hazelcast.org/hazelcast-ee-docs/{self.version}/javadoc"
