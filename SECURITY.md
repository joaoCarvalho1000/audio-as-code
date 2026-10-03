# Security

Audio as Code is an early prototype. There are no maintained release
branches or promised response times.
Review the current source and dependency updates before relying on it in a service.

## Reporting a problem

Use [GitHub private vulnerability reporting](https://github.com/joaoCarvalho1000/audio-as-code/security/advisories/new).
It is enabled for this repository. Do not post exploit details or sensitive data
in public issues.

Include the package/version or source revision, operating system, a minimal
reproduction, expected impact, and any proposed fix once a private route is agreed.
Do not include API keys, personal scores, or unrelated workstation files. A normal
functional bug can use the bug-report template with a small non-sensitive example.

## Trust boundaries

- JSON scores are validated data, not executable code. Runtime validation includes
  relationships that JSON Schema alone cannot express. Unknown fields and unsupported
  instruments are rejected rather than treated as commands or fallback voices.
- Python composition examples and downloaded source are executable code. Inspect
  them before running; score validation does not make arbitrary Python safe.
- Core rendering is local and does not need network access, credentials, an audio
  device, or instrument downloads. Dependency installation and optional source-score
  importers may access the network. The example website is separate from the engine.
- Score bounds and the 300-second render limit are not a resource sandbox. Dense
  scores and effects can consume substantial CPU and memory. A service accepting
  untrusted input needs its own process isolation, resource limits and file policy.
- Export paths are caller-controlled. Path preflight rejects known collisions but
  is not an authorization boundary against concurrent filesystem changes. Use a
  dedicated output directory with appropriate operating-system permissions.

The development server and example workflows are for local use. They are not a
production service deployment or a guarantee of safe internet exposure.
