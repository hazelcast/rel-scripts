import logging
import os
from dataclasses import InitVar, dataclass, field
from datetime import datetime

import requests
import semver
from humanize import naturalsize
from requests.auth import HTTPBasicAuth


@dataclass
class DownloadUrl:
    """A download URL with lazily computed, human-friendly size."""

    url: str
    _size: str = field(default=None, init=False)

    @property
    def size(self) -> str:
        """Fetch and cache the artifact size without _actually_ downloading it."""
        # Lazily evaluates
        # So in the case of (say) an EE-only release we don't query (non-existent) OS artifacts
        if self._size is None:
            logging.debug("Getting size of %s", self.url)

            username = os.getenv("RELEASE_REPO_USER")
            password = os.getenv("RELEASE_REPO_TOKEN")

            auth = HTTPBasicAuth(username, password) if username and password else None

            logging.debug("auth=%s", auth)

            response = requests.head(
                self.url,
                allow_redirects=True,
                auth=auth,
            )
            response.raise_for_status()

            content_length = response.headers["Content-Length"]

            if content_length:
                self._size = naturalsize(int(content_length), format="%.0f")
            else:
                raise Exception(f"{self.url} did not return a size")

        return self._size


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

    def __post_init__(self, github_org, ee_release_repo_name):
        """Normalize version and populate derived URLs and metadata."""
        if isinstance(self.version, str):
            self.version = semver.Version.parse(self.version)

        self.date = datetime.now().strftime("%m/%d/%Y")

        self.os_downloads = self._build_downloads(
            f"https://github.com/{github_org}/hazelcast/releases/download/v{self.version}/hazelcast-{self.version}"
        )
        self.ee_downloads = self._build_downloads(
            f"https://repository.hazelcast.com/{ee_release_repo_name}/hazelcast-enterprise/hazelcast-enterprise-{self.version}"
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

    def _build_downloads(self, base: str) -> Downloads:
        """Build a Downloads object for a given artifact base URL."""
        return Downloads(
            full_zip=DownloadUrl(f"{base}.zip"),
            slim_zip=DownloadUrl(f"{base}-slim.zip"),
            full_tar=DownloadUrl(f"{base}.tar.gz"),
            slim_tar=DownloadUrl(f"{base}-slim.tar.gz"),
        )
