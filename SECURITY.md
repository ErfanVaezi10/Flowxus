# Security Policy — FLOWXUS Studio

FLOWXUS Studio is a CLI/toolkit that processes **untrusted geometry/mesh files** and may launch external solvers. This policy defines what we support and how to report security issues.

---

## Scope

- **In scope:** This repository’s code (e.g., `mesh/`, `solver/`, `post/`, `build/`), its CLIs, and config/rendering/validation logic.
- **Out of scope:** Third-party tools invoked via subprocess (e.g., SU2, Gmsh), OS packages, drivers, CUDA/MPI stacks, or issues caused by custom patches.

---

## Supported Versions

We follow a simple rule until 1.0: **only the latest released minor (0.x) receives security updates.**  
After 1.0: **last two minors** get fixes; LTS branches may be designated in the README.

Update the table below whenever you cut a release.

| Component        | Branch / Tag | Status               | Notes                                       |
|------------------|--------------|----------------------|---------------------------------------------|
| Studio Core      | `v0.0.x`     | ✅ Supported         | Latest patch: `v0.0.2`                      |
| Studio Core      | `≤ v0.0.1`   | ❌ Not supported     | Please upgrade to `v0.0.2` or newer         |
| Studio Modules   | match Core   | ✅/❌ per Core       | Mesh, Solve(SU2), Post, Build; reads SU2 `.dat` only |

---

## Reporting a Vulnerability

**Please do _not_ open a public issue.** Use one of:

1. **GitHub Security Advisory (preferred):** *Security → Report a vulnerability* on this repo.  
2. **Email:** erfan.vaezi.96@gmail.com

We will:
- Acknowledge receipt within **72 hours**.
- Provide triage status within **7 days**.
- Aim to release a fix or mitigation within **90 days** (or communicate a revised timeline).

---

## What to Include

- Version/commit (`git rev-parse HEAD`) and install method (pip, source).
- OS / Python version / MPI details (if relevant).
- Exact steps to reproduce (inputs, commands, minimal files).
- Expected vs. actual behavior; impact (RCE, DoS, privilege, data leak).
- Any logs/backtraces (sanitize secrets) and a PoC if available.

---

## Coordinated Disclosure

- We will assign a CVE (if applicable), prepare a private fix, and coordinate a release.
- We credit reporters by handle/name in release notes, **unless you prefer anonymity**.
- We may request up to **30 additional days** for complex issues (e.g., dependency coordination).

---

## Out-of-Scope Examples

- Vulnerabilities in SU2, Gmsh, meshio, MPI, Python itself (report upstream).
- License/compliance questions (not security).
- Pure performance or numerical-accuracy issues without a security impact.
- Attacks requiring already-compromised local system or non-default insecure configs.

---

## Safe Harbor (Good-Faith Research)

We will not pursue legal action for research conducted in good faith that:
- avoids privacy violations and service disruption,
- does not exfiltrate more data than necessary to demonstrate impact,
- respects coordinated disclosure via the channels above.

---

## Dependencies

FLOWXUS Studio invokes third-party tools (e.g., SU2, Gmsh) as **external binaries**.  
Please report vulnerabilities in those projects to their maintainers. If a vuln affects our usage, tell us so we can provide mitigations or version pins.

---

Last updated: 2025-10-04.
