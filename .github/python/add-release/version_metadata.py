import logging
import os
from dataclasses import InitVar, dataclass, field

import requests
import semver
from humanize import naturalsize
from requests.auth import HTTPBasicAuth
from urllib.parse import urlparse


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
        # Lazily evaluates
        # So in the case of (say) an EE-only release we don't query (non-existent) OS artifacts
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

        response = requests.head(
            url,
            allow_redirects=True,
            auth=auth,
        )
        response.raise_for_status()

        content_length = response.headers["Content-Length"]

        if content_length:
            return naturalsize(int(content_length), format="%.0f")
        else:
            raise Exception(f"{url} did not return a size")

    @property
    def size(self) -> str:
        if self._size is None:
            try:
                self._size = self._get_size(self.preprod_url)
            except requests.RequestException:
                self._size = self._get_size(self.live_url)

        return self._size

    @property
    def live_url(self) -> str:
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
class VersionMetadata:
    """Release metadata derived from a semantic version."""

    version: semver.Version | str
    github_org: InitVar[str]
    ee_release_repo_name: InitVar[str]
    jfrog_preprod_files_repo: InitVar[str]

    def __post_init__(self, github_org, ee_release_repo_name, jfrog_preprod_files_repo):
        """Normalize version and populate derived URLs and metadata."""
        if isinstance(self.version, str):
            self.version = semver.Version.parse(self.version)

        self.os_downloads = self._build_downloads(
            f"https://github.com/{github_org}/hazelcast/releases/download/v{self.version}/hazelcast-{self.version}",
            f"https://repository.hazelcast.com/{jfrog_preprod_files_repo}/hazelcast/hazelcast-{self.version}",
        )
        self.ee_downloads = self._build_downloads(
            f"https://repository.hazelcast.com/{ee_release_repo_name}/hazelcast-enterprise/hazelcast-enterprise-{self.version}",
            f"https://repository.hazelcast.com/{jfrog_preprod_files_repo}/hazelcast-enterprise/hazelcast-enterprise-{self.version}",
        )

        self.sources_url = (
            f"https://github.com/{github_org}/hazelcast/tree/v{self.version}"
        )
        self.code_samples_url = (
            f"https://github.com/{github_org}/hazelcast-code-samples"
        )

        self.docs_url = f"https://docs.hazelcast.com/hazelcast/{self.version.major}.{self.version.minor}/getting-started/quickstart.html"
        self.os_release_notes_url = f"https://docs.hazelcast.com/hazelcast/{self.version.major}.{self.version.minor}/release-notes/community#{self.version.major}-{self.version.minor}-{self.version.patch}"
        self.ee_release_notes_url = f"https://docs.hazelcast.com/hazelcast/{self.version.major}.{self.version.minor}/release-notes/enterprise#{self.version.major}-{self.version.minor}-{self.version.patch}"
        self.os_apidocs_url = f"https://docs.hazelcast.org/docs/{self.version}/javadoc"
        self.ee_apidocs_url = (
            f"https://docs.hazelcast.org/hazelcast-ee-docs/{self.version}/javadoc"
        )

    def _build_downloads(self, live_base_url: str, preprod_base_url: str) -> Downloads:
        """Build a Downloads object for a given artifact base live URL."""
        return Downloads(
            full_zip=DownloadUrl(live_base_url, preprod_base_url, ".zip"),
            slim_zip=DownloadUrl(live_base_url, preprod_base_url, "-slim.zip"),
            full_tar=DownloadUrl(live_base_url, preprod_base_url, ".tar.gz"),
            slim_tar=DownloadUrl(live_base_url, preprod_base_url, "-slim.tar.gz"),
        )
