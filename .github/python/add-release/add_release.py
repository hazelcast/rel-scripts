"""Insert new release metadata blocks into metadata text files

Supports Java client only"""

import argparse
import logging
import os
import re
from pathlib import Path

import semver
from version_metadata import VersionMetadata


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--version", required=True)
    parser.add_argument("--github-org", required=True)
    parser.add_argument("--ee-release-repo-name", required=True)
    parser.add_argument("--should-build-oss", required=True)
    parser.add_argument("--should-build-ee", required=True)
    args = parser.parse_args()

    version_metadata = VersionMetadata(
        args.version, args.github_org, args.ee_release_repo_name
    )
    logging.debug("version=%s", version_metadata.version)

    if parse_boolean(args.should_build_oss):
        update_hazelcast_open_source_metadata(version_metadata)
        update_imdg_clients_metadata(version_metadata)

    if parse_boolean(args.should_build_ee):
        update_hazelcast_enterprise_metadata(version_metadata)


def update_hazelcast_open_source_metadata(version_metadata: VersionMetadata):
    """Updates `hazelcast-open-source.txt`

    `Example diff <https://github.com/hazelcast/rel-scripts/commit/b714a819768e8ad6ac3f26d365ff46e8d2716df7>`__
    """
    file_path = Path("hazelcast-open-source.txt")

    version_block = f"""---
Version: {version_metadata.version}
Date: ${{TBC_RELEASE_DATE}}
Download_ZIP_URL: {version_metadata.os_downloads.full_zip.url}
Download_ZIP_Size: {version_metadata.os_downloads.full_zip.size}
Download_slim_ZIP_URL: {version_metadata.os_downloads.slim_zip.url}
Download_slim_ZIP_Size: {version_metadata.os_downloads.slim_zip.size}
Download_TAR_URL: {version_metadata.os_downloads.full_tar.url}
Download_TAR_Size: {version_metadata.os_downloads.full_tar.size}
Download_slim_TAR_URL: {version_metadata.os_downloads.slim_tar.url}
Download_slim_TAR_Size: {version_metadata.os_downloads.slim_tar.size}
Docs_HTML: {version_metadata.docs_url}
Docs_PDF:
APIDocs: {version_metadata.os_apidocs_url}
ReleaseNotes: {version_metadata.os_release_notes_url}
CodeSamples_URL: {version_metadata.code_samples_url}
CodeSamples_Size:
Github: {version_metadata.sources_url}"""

    update_hazelcast_metadata(version_metadata, file_path, version_block)


def update_hazelcast_enterprise_metadata(version_metadata: VersionMetadata):
    """Updates `hazelcast-enterprise.txt`

    `Example diff <https://github.com/hazelcast/rel-scripts/commit/d5728f98dc00da5e54455f41fbe1583768a11803>`__
    """
    file_path = Path("hazelcast-enterprise.txt")

    version_block = f"""---
Version: {version_metadata.version}
Date: ${{TBC_RELEASE_DATE}}
Download_ZIP_URL: {version_metadata.ee_downloads.full_zip.url}
Download_ZIP_Size: {version_metadata.ee_downloads.full_zip.size}
Download_slim_ZIP_URL: {version_metadata.ee_downloads.slim_zip.url}
Download_slim_ZIP_Size: {version_metadata.ee_downloads.slim_zip.size}
Download_TAR_URL: {version_metadata.ee_downloads.full_tar.url}
Download_TAR_Size: {version_metadata.ee_downloads.full_tar.size}
Download_slim_TAR_URL: {version_metadata.ee_downloads.slim_tar.url}
Download_slim_TAR_Size: {version_metadata.ee_downloads.slim_tar.size}
Docs_HTML: {version_metadata.docs_url}
Docs_PDF:
APIDocs: {version_metadata.ee_apidocs_url}
ReleaseNotes: {version_metadata.ee_release_notes_url}
CodeSamples_URL:
CodeSamples_Size:
Github:"""

    update_hazelcast_metadata(version_metadata, file_path, version_block)


def update_hazelcast_metadata(
    version_metadata: VersionMetadata, file_path, version_block
):
    """Updates `hazelcast-xxx_txt`"""

    header = "========== "
    current_stable_header = header + "Current Stable"
    previous_stable_header = header + "Previous Stable"

    # Assume the first "version"
    content = file_path.read_text()
    current_stable_section = content.split(current_stable_header, 1)[1].split(
        previous_stable_header
    )[0]
    latest = is_latest(version_metadata.version, current_stable_section)
    logging.debug("latest=%s", latest)

    if latest:
        # Example - https://github.com/hazelcast/rel-scripts/commit/d5728f98dc00da5e54455f41fbe1583768a11803
        # Demote current stable -> previous stable
        content = content.replace(current_stable_header, previous_stable_header, 1)
        # Prepend new current stable
        content = os.linesep.join(
            [current_stable_header, version_block, "---", content]
        )
        file_path.write_text(content)
    else:
        # Example - https://github.com/hazelcast/rel-scripts/commit/b0c175ba09fd2ecf2d2f6a9b2789d26c0150f50d
        # Just add to existing block
        insert_version_block_below_header(
            file_path, content, previous_stable_header, version_block
        )


def is_latest(version: semver.Version, content):
    """
    Returns True if version is newer than all 'Version: x.y.z' entries
    in the content string. Considers all versions in the content.
    """
    existing_versions = re.findall(r"^Version:\s*(.+)", content, re.MULTILINE)
    logging.debug("existing_versions=%s", existing_versions)

    return all(
        version > semver.Version.parse(existing_version, optional_minor_and_patch=True)
        for existing_version in existing_versions
    )


def update_imdg_clients_metadata(version_metadata: VersionMetadata):
    """Updates `imdg-clients.txt`

    `Example diff <https://github.com/hazelcast/rel-scripts/commit/897d56b72511228f0b3645a9ae8536655d97785d>`__
    """
    file_path = Path("imdg-clients.txt")

    header = "========== Java Client"

    version_block = f"""---
Version: {version_metadata.version}
Date: ${{TBC_RELEASE_DATE}}
Download: {version_metadata.os_downloads.slim_zip.url}
Download_Size: {version_metadata.os_downloads.slim_zip.size}
Github: {version_metadata.sources_url}
Docs: {version_metadata.docs_url}
APIDocs: {version_metadata.os_apidocs_url}
ReleaseNotes: {version_metadata.os_release_notes_url}"""

    insert_version_block_below_header(
        file_path, file_path.read_text(), header, version_block
    )


def insert_version_block_below_header(file_path, content, header, version_block):
    """Insert a version block immediately after the specified header."""
    content = content.replace(header, header + os.linesep + version_block, 1)
    file_path.write_text(content)


def parse_boolean(arg):
    """`Not available by default in argparse <https://stackoverflow.com/a/15008806>`__"""
    return arg.lower() == "true"


if __name__ == "__main__":
    main()
