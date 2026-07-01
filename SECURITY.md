# Security Policy

## Reporting

Please report security issues privately to the repository maintainer instead of opening a public issue.

## Secrets And Local Data

PenMoji is local-first. Runtime data, API keys, conversations, generated artifacts, mobile sync queues, and license tokens are intended to stay outside this repository.

Do not commit:

- API keys, provider tokens, or authorization headers
- WeChat Mini Program private developer config
- `%USERPROFILE%\.content-workbench`
- `%USERPROFILE%\.content-workbench-cloud`
- exported user conversations or generated customer content

If a secret was ever committed, rotate it before publishing the repository.
