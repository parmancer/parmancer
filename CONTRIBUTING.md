# Contributing

An explanation of the tools used in developing this project.

## Setup

The following developer tools are used in this project:

- `pyenv` to manage multiple versions of Python
- `pipx` to install and manage global Python CLI tools
- `poetry` for packaging and dependency management
- `pre-commit` to run automated checks when making commits
- `tox` to run tests in all supported versions of Python to check compatibility

The short version:

Install [pyenv](https://github.com/pyenv/pyenv?tab=readme-ov-file#installation) and [pipx](https://pipx.pypa.io/stable/installation/), then in this repo, run:

```sh
# Install and specify Python versions
pyenv install 3.8 3.9 3.10 3.11 3.12
pyenv local 3.8 3.9 3.10 3.11 3.12
# Install developer tools
pipx install poetry pre-commit tox
# Set up local Python environment and activate it
poetry env use 3.9
poetry install
poetry shell
# Check that the environment is active by running tests
pytest
# Run first time setup of pre-commit and check it passes
pre-commit run -a
# Check that tox was installed and passes
tox
```

The long version is in the following sections.

### Python version management with `pyenv`

Install and manage Python versions through `pyenv`.
Installation instructions and more info: https://github.com/pyenv/pyenv

Once it's installed, install all the supported versions of this package:

```sh
pyenv install 3.8 3.9 3.10 3.11 3.12
```

Then in this repo, run `pyenv local 3.8 3.9 3.10 3.11 3.12` so that all versions are available when running `tox` (see later section on `tox`)

### Using `pipx` to install developer tools

Install `pipx` which can then be used to manage and install other global Python CLI tools.
Follow installation instructions here: https://pipx.pypa.io/stable/

### Package management with `poetry`

Install `poetry`. Recommended approach:

```sh
pipx install poetry
```

See their documentation for more info or alternative installation instructions: https://python-poetry.org/docs/#installation

Then in this repo, set which version of Python `poetry` will use.
Python 3.9 is the minimum version required by some of the developer tools being used, but higher versions could also be used for development (note that all Python features used need to be backward-compatible with the lowest version of Python supported in this project).

```sh
poetry env use 3.9
```

Then install the dependencies specified in `pyproject.toml`:

```sh
poetry install
```

Enter a shell with `poetry`'s environment activated:

```sh
poetry shell
```

### Test with `pytest`

`pytest` is now already installed via `poetry`.
Tests are located in the `tests/` folder, and can be run using:

```sh
pytest
```

### Automated commit checks with `pre-commit`

Install `pre-commit`. Recommended approach:

```sh
pipx install pre-commit
```

See their documentation for more info or alternative installation instructions: https://pre-commit.com/

To check it's installed, try running `pre-commit` on all files, which runs the checks defined in `.pre-commit-config.yaml`:

```sh
pre-commit run -a
```

`pre-commit` doesn't need to be run explicitly during normal development, it will run automatically on each `git commit` as long as it has been set up by running `pre-commit` at least once.

### Check compatibility across Python versions using `tox`

Install `tox`. Recommended approach:

```sh
pipx install tox
```

See their documentation for more info or alternative installation instructions: https://tox.wiki/

It will run some first-time setup and then will run tests against version of Python, specified in `tox.ini`. Run:

```sh
tox
```

## Developing and submitting pull

Once setup is complete and the Python environment is activated:

- Run `pytest` regularly while adding tests and making changes
- Run `tox` occasionally
- `pre-commit` will automatically run on each commit

All of these need to succeed for code to be merged into `main`.
