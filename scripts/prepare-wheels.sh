#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
# Resolve Python 3.12 wheels for the target Linux CPU; host pip may use another Python version.
premier_arch=$(uname -m)
case "$premier_arch" in x86_64|aarch64) ;; *) echo 'Unsupported CPU architecture'; exit 2 ;; esac
python3 -m pip download --only-binary=:all: --python-version 3.12 --implementation cp --abi cp312 --abi abi3 --abi none --platform "manylinux_2_28_$premier_arch" --platform "manylinux_2_17_$premier_arch" --platform "manylinux2014_$premier_arch" -r requirements.lock -d .wheelhouse
(cd .wheelhouse && sha256sum ./*.whl > SHA256SUMS)
