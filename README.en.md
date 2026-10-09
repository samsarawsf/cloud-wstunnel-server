# Cloud Wstunnel Server

[中文](README.md)

An Agent Skill for deploying private services in ChatGPT Work/Codex cloud environments through your own VPS, **wstunnel**, and **Tailscale**.

The cloud application listens on loopback. A cloud-side client initiates a verified WSS connection to the VPS. Your devices access an assigned VPS **Tailscale address and port**, which forwards requests through that connection to the application.

The workflow has been demonstrated with an actual Docker web application, including its login page, redirects, and resources. It also covers adding services, assigning ports across environments, diagnostics, and recovery after replacing an environment. Continuous availability still depends on the platform's supported lifecycle.

## Install

Ask Codex:

```text
Use $skill-installer to install
https://github.com/samsarawsf/cloud-wstunnel-server/tree/main/skills/cloud-wstunnel-server
```

Alternatively, clone this repository and copy the complete `skills/cloud-wstunnel-server` directory into your Agent's skill directory. For Codex, use `${CODEX_HOME:-$HOME/.codex}/skills/`. Back up an existing installation before replacing it.

The skill's detailed operational instructions are currently in Chinese. Scripts use Python's standard library and English command-line options.

## Invoke

```text
$cloud-wstunnel-server
Deploy my Docker application in the new cloud environment, reuse my VPS relay,
and provide a tested private Tailscale URL without restarting existing services.
```

Provide the authorized cloud conversation/environment, VPS access method, its Tailscale address, verified TLS identity, and application port. Do not publish credentials or private deployment logs in this repository.

## Requirements and boundaries

- Your VPS runs wstunnel with valid TLS and explicit reverse-listener restrictions.
- The VPS and accessing devices are connected to Tailscale.
- The cloud's supported HTTP proxy must allow the actual WSS destination and protocol.
- Keep inherited proxies, platform CA trust, and certificate verification enabled.
- Root passwords stay out of the cloud; only narrowly scoped tunnel credentials are needed.
- Python 3.9+ is required only for the optional health tools and local tests.
- Public VPS WSS ports are tunnel transport endpoints, not public application URLs.
- Cloud suspension, process cleanup, replacement, database persistence, and certificate renewal require supported recovery procedures. This is not a permanent-compute or 24/7 SLA guarantee.

Start with [SKILL.md](skills/cloud-wstunnel-server/SKILL.md), [relay deployment](skills/cloud-wstunnel-server/references/deployment.md), and [application onboarding and recovery](skills/cloud-wstunnel-server/references/services.md).

## Tests

```sh
python3 -m unittest discover -s tests -v
```

Tests use temporary loopback services and do not contact a VPS or cloud environment. See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

MIT licensed. Third-party tools retain their own licenses and service terms; no third-party binaries or account credentials are distributed here.

Application tunnels now default to detached Docker Compose services with `restart: unless-stopped`. Tool sessions are for short diagnostics. See [Docker client deployment](skills/cloud-wstunnel-server/references/docker-client.md) for networking, proxy/CA, migration and recovery checks. This does not guarantee availability across cloud suspension or replacement.
