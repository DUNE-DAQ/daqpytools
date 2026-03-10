# daqpytools
[![Lint](https://github.com/DUNE-DAQ/daqpytools/actions/workflows/lint.yml/badge.svg)](https://github.com/DUNE-DAQ/daqpytools/actions/workflows/lint.yml)
[![pytest](https://github.com/DUNE-DAQ/daqpytools/actions/workflows/run_pytest.yml/badge.svg)](https://github.com/DUNE-DAQ/daqpytools/actions/workflows/run_pytest.yml)

Set of importable tools used to simplify DAQ development in python.


## Scope
This provides a set of tools that are used in python applications, along with their unit tests. Currently, the following tools are defined
 - logging - [code](https://github.com/DUNE-DAQ/daqpytools/tree/develop/src/daqpytools/logging)

## Start here
- Users (quickstart): `docs/Logging.md`
- Users (advanced): `docs/Logging_advanced.md`
- Developers (architecture): `docs/dev_docs.md`
- Developers (extension workflow): `docs/dev_docs_extension.md`
- Demonstrator CLI entrypoint: `daqpytools-logging-demonstrator`
- Historical/extra material: [wiki](https://github.com/DUNE-DAQ/daqpytools/wiki/Logging)

## Intended use case
This repo serves as the intended source of distribution-standard tooling. Any Python tool used by multiple repositories should be defined here.

## Setup instructions
For general users, no setup is required - when developing your python applications, it is sufficient to include e.g.
```python
from daqpytools.logging import get_daq_logger
log = get_daq_logger(...)
```
For developers, start with `docs/dev_docs.md`, then continue to `docs/dev_docs_extension.md` for extension workflows.
