# rel-scripts

Metadata used to populate Hazelcast downloads pages:
- https://hazelcast.com/get-started/download
- https://hazelcast.com/community-edition-projects/downloads

## Implementation

An external service monitors this repository for commits, parsing the updated files to update the website.

This service does not (as of 02/2025) support reverting a commit to remove an item and instead a manual deletion is required.
