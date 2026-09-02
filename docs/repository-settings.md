# Repository settings (CLI module)

Public operational notes for maintainers of
[xgic/wagtail-cli](https://github.com/xgic/wagtail-cli).

## Branch protection

`main` is protected:

| Rule | Intent |
|------|--------|
| No force-push / no deletion of `main` | History integrity |
| Pull request required (1 approval) | Human UI review |
| Linear history | Clean default branch |
| Required status check **Test (Python 3.14)** | Pytest + ruff contract |

PyPI releases follow [python-package-release.md](https://github.com/xgic/ai/blob/main/docs/python-package-release.md) (RC → TestPyPI → PyPI). Do not tag a final `v*` without a prior RC.

## Labels

Apply PR labels consistently (`documentation`, `bug`, `enhancement`, `chore`, …).

## Related

- [AGENTS.md](../AGENTS.md)
- [CONTRIBUTING.md](../CONTRIBUTING.md)
- [xgic/ai BASE-STANDARDS](https://github.com/xgic/ai/blob/main/docs/BASE-STANDARDS-FOR-ORCHESTRATED-REPOS.md)
