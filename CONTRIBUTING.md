# Contributing to captive-portal

Contributions are welcome. The most useful ones right now:

- Reports from real deployments: which BNG, how subscribers are steered to
  the box, and which devices did or did not show the sign-in sheet.
- Bug fixes with a test, in `portalctl/tests` or `scripts/sandbox-test.sh`.
- Captive portal detection details for an OS or browser, with a reference
  to its source or documentation.

Open an issue before starting a large change so the design can be agreed
first.

## Build and test

Docker with Compose and [uv](https://docs.astral.sh/uv/) are required.

```sh
scripts/bootstrap.sh
```

The unit tests check the config schema and compare rendered nginx, nftables
and dnsmasq configs against the golden files in `portalctl/tests/golden`.
After an intentional template change, delete the affected golden files and
run the tests again to regenerate them.

```sh
cd portalctl && uv run pytest
```

The sandbox runs the whole stack in containers and checks it from a
subscriber's point of view. CI runs both.

```sh
docker compose -f docker-compose-sandbox.yml up -d --build --wait
./scripts/sandbox-test.sh
docker compose -f docker-compose-sandbox.yml down -v
```

## Commits and pull requests

- Branch from `main` and open a pull request against `main`. PRs are
  squash-merged, so keep one logical change per PR.
- The PR title is the commit subject and reads `type(area): imperative
  summary`, for example `fix(nftables): keep DoT reset ahead of the drop`.
  Types: feat, fix, perf, revert, docs, refactor, test, build, ci, chore,
  style. CI checks the title.
- New behaviour needs a test. A change to what subscribers see or can reach
  needs a sandbox check.
- Plain punctuation in anything a subscriber or operator reads: no dashes
  used as punctuation, arrows or emoji.
