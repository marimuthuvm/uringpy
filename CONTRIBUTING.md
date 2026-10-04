# Contributing to uringpy

Contributions, bug reports, and questions are welcome.

## Reporting issues

Please open an issue on the
[GitHub issue tracker](https://github.com/marimuthuvm/uringpy/issues) with:

- your OS, kernel version (`uname -r`), Python version, and `liburing` version,
- steps to reproduce, and the expected vs. actual behavior,
- relevant logs or a minimal example.

## Development setup

`uringpy` requires Linux (kernel ≥ 5.6), `liburing` (≥ 2.3), Python ≥ 3.9, and a
C compiler.

```bash
git clone https://github.com/marimuthuvm/uringpy.git
cd uringpy
sudo apt-get install -y liburing-dev gcc
pip install -e .
pytest
```

A reproducible container build is also provided:

```bash
docker build -t uringpy:gil .
docker run --rm --security-opt seccomp=unconfined uringpy:gil pytest
```

## Pull requests

1. Fork the repository and create a feature branch.
2. Keep changes focused; add or update tests under `tests/` where practical.
3. Ensure `pytest` passes and the extension builds cleanly.
4. Open a pull request describing the change and its motivation.

## Code of conduct

Please be respectful and constructive in all interactions.

## License

By contributing, you agree that your contributions are licensed under the
project's MIT License.
