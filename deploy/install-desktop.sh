#!/usr/bin/env bash
# 把项目安装为当前用户的桌面应用（无需 root）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
    PYTHON="$(command -v python3)"
fi

APPS="${HOME}/.local/share/applications"
mkdir -p "${APPS}"

sed -e "s|@ROOT@|${ROOT}|g" -e "s|@PYTHON@|${PYTHON}|g" \
    "${ROOT}/deploy/skyblock-bazaar.desktop" \
    > "${APPS}/skyblock-bazaar.desktop"
chmod 644 "${APPS}/skyblock-bazaar.desktop"

# 图标也放一份到 hicolor，便于部分桌面环境索引
ICON_DIR="${HOME}/.local/share/icons/hicolor/256x256/apps"
mkdir -p "${ICON_DIR}"
cp "${ROOT}/bazaar.png" "${ICON_DIR}/skyblock-bazaar.png"

update-desktop-database "${APPS}" >/dev/null 2>&1 || true
gtk-update-icon-cache "${HOME}/.local/share/icons/hicolor" >/dev/null 2>&1 || true

echo "已安装：${APPS}/skyblock-bazaar.desktop"
echo "Python：${PYTHON}"
