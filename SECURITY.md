# Security

Report vulnerabilities privately through GitHub's "Report a vulnerability" form on this
repository rather than in a public issue. Include steps to reproduce and the affected version.

Design notes relevant to reviewers:

- Broker access tokens are stored encrypted (AES-256-GCM) and are never passed to the scripts
  Claude writes. Scripts reach Kite only through a local gateway that holds the token.
- Every script runs in a separate subprocess with a scrubbed environment, a wall-clock timeout
  and an output cap.
- The library exposes no order placement, modification or cancellation.
