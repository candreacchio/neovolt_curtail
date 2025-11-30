# Changelog

All notable changes to the Bytewatt Export Limiter Home Assistant integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Development tooling (pyproject.toml, pre-commit, GitHub Actions CI)
- MIT License
- Contributing guidelines
- Comprehensive test suite

### Changed
- Standardized type hints to modern Python 3.11+ style
- Added TypedDict for coordinator data structure
- Removed duplicate constants from modbus_client.py

## [1.0.0] - 2024-11-30

### Added
- Initial release
- Two-step config flow (Modbus connection + price automation settings)
- Export limit sensor (current limit in watts)
- Grid maximum limit sensor
- Current electricity price sensor
- Export curtailed binary sensor
- Manual export limit number entity
- Automation enable/disable switch
- Price-based automation with configurable threshold
- Grid override detection and re-application
- Debounced price entity monitoring (5 second debounce)
- HACS compatibility
- Comprehensive error handling and logging
- Timeout protection on all Modbus operations
- Retry logic for Modbus read/write operations
