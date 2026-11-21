#!/usr/bin/env bash
# 在 Linux 上用 Wine 交叉构建 Windows 单文件 exe。
# 产物：dist/win/SkyBlockBazaar.exe
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${ROOT}/build_wine"
PREFIX="${WORK}/prefix"
PYTHON_VERSION="3.12.10"
INSTALLER="${WORK}/python-${PYTHON_VERSION}-amd64.exe"
export WINEPREFIX="${PREFIX}"
export WINEDEBUG=-all
export DISPLAY="${DISPLAY:-:1}"

mkdir -p "${WORK}"
cd "${WORK}"

if [[ ! -f "${INSTALLER}" ]]; then
    curl -fL --retry 3 -o "${INSTALLER}" \
        "https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-amd64.exe"
fi

if [[ ! -x "${PREFIX}/drive_c/Python312/python.exe" ]]; then
    wineboot -i
    wineserver -w
    wine "${INSTALLER}" /quiet InstallAllUsers=0 PrependPath=0 \
        Include_launcher=0 Include_test=0 Include_doc=0 Include_pip=1 \
        TargetDir='C:\Python312'
    wineserver -w
fi

wine 'C:\Python312\python.exe' -m pip install --disable-pip-version-check -q \
    --upgrade pip "PySide6-Essentials==6.8.3" requests pyinstaller

cd "${ROOT}"
rm -rf build_win dist/win
wine 'C:\Python312\python.exe' -m PyInstaller --noconfirm --log-level=WARN \
    --distpath dist/win --workpath build_win deploy/skyblock-bazaar-onefile.spec
ls -lh dist/win/SkyBlockBazaar.exe
