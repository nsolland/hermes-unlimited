# Hermes Unlimited

Native Hermes plugin for enabling providers to create, operate and deliver AI-native companies and services to their own customers.

Status: public repository skeleton. The existing private implementation is not yet transferred or released.

## Product boundary

- One native Hermes plugin, not a Hermes fork or a separate agent runtime.
- Provider creates companies, assigns roles, offers services and manages customers.
- JustYou identity binding is mandatory for execution; credentials must use Hermes secret scope.
- Captain's Bridge, Jackets, Veritas, The Thread, communication providers and infrastructure adapters are optional integrations.
- No direct execution or customer claim without a verified result.

## Layout

- `plugin.yaml`: Hermes plugin manifest.
- `__init__.py`: safe native plugin registration.
- `unlimited/`: provider/company/service contracts and adapters.
- `tests/`: dependency-free contract tests.
- `docs/ARCHITECTURE.md`: ownership, milestones, proof and exclusions.

## Development

Run `python3 -m unittest discover -s tests -v` and `hermes plugins validate . --install-deps` locally. GitHub Actions are not a release gate.

## Release

Skeleton is not the production plugin. Release only after the end-to-end provider → company → customer → task → result → billing journey and native Hermes installation are verified on Mac and Acer. This repository is public for transparent plugin packaging and review; no private source, token, or customer data should be copied.
