# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1]

### Added

- Debug mode for parsers: Pass `debug=True` to the `parse()` or `match()` methods to get detailed error information when parsing fails. Debug mode shows a parse tree with successful and failed parsers, helping identify where parsing went wrong.

### Changed

- Improved concat types and docstrings for better type checking support
- Updated docstrings for generic type parameters to be more descriptive
- Dropped Python 3.8 support
