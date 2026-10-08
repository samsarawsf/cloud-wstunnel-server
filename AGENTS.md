# Repository instructions

This is a public, standalone Python/Agent Skill repository, not an enterprise application. Keep the operational skill in skills/cloud-wstunnel-server and public packaging documents at the repository root.

Use main as the sole integration branch. Initial repository bootstrap and first release may be published directly as authorized by the owner; subsequent changes use a short-lived branch and PR. Use descriptive Conventional Commits and the authenticated GitHub owner's verified/noreply identity. Do not fabricate enterprise tickets or publish a corporate email merely to satisfy unrelated organization templates.

Run python3 -m unittest discover -s tests -v. Preserve inherited cloud proxies, CA trust, TLS verification, per-environment credentials and explicit reverse-port restrictions. Never add real deployment addresses, authentication values or account-specific cloud IDs. Distinguish verified functionality from lifecycle assumptions. Do not change live infrastructure as part of repository tests.
