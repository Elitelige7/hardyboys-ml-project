# MLFlowPro documentation

This handbook covers installation, architecture, tracked training, Bayesian
hyperparameter tuning, the API, evaluation, deployment, and current limitations.
The source files are in `docs/source/`. Sphinx turns them into searchable HTML.

From the repository root in your activated environment:

```powershell
python -m pip install -r requirements-docs.txt
python -m sphinx -n -W --keep-going -b html docs/source docs/build/html
Start-Process .\docs\build\html\index.html
```

The build should finish with **build succeeded**. The `-W` option makes a
documentation warning fail the build; `-n` checks missing cross-references.
This also runs in `.github/workflows/documentation.yml` on relevant pushes and
pull requests. Generated `docs/build/` files are ignored; commit the sources.

Sphinx is pinned to 8.2.3 to support the project's Python 3.11 environment.
Building the handbook does not start Django, read `.env`, or require API keys.

## Pages

- [Installation and local setup](source/setup.rst)
- [Architecture and concepts](source/architecture.rst)
- [Training, tuning, and versioning](source/experiments.rst)
- [API reference](source/api.rst)
- [Models, evaluation, and results](source/evaluation.rst)
- [Deployment, testing, and project scope](source/deployment.rst)

## Keep the documentation accurate

Update these pages when routes, settings, measurements, or deployment behavior
change. Keep the repository README and presentation consistent with the actual
implementation. The October 19 tuned run measured 91.06% test accuracy and
91.05% test macro F1; suggestions from an LLM are not measured experiments.
