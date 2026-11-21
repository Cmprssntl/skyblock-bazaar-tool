#!/usr/bin/env bash
# 构建 Debian/Ubuntu 安装包。默认先跑 PyInstaller，再打包 dist/skyblock-bazaar_*.deb。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${ROOT}/.venv/bin/python"
[[ -x "${PYTHON}" ]] || PYTHON="$(command -v python3)"
VERSION="$("${PYTHON}" -c "import sys; sys.path.insert(0, '${ROOT}'); import skyblock_bazaar; print(skyblock_bazaar.__version__)")"
ARCH="$(dpkg --print-architecture)"
PREFIX="/opt/skyblock-bazaar"
GLIBC_MIN="${GLIBC_MIN:-2.38}"
WORK="${WORK:-${ROOT}/build_deb}"
DIST="${DIST:-${ROOT}/dist}"
APP="${DIST}/SkyBlockBazaar"
SKIP_BUILD=0

for arg in "$@"; do
    case "${arg}" in
        --skip-build) SKIP_BUILD=1 ;;
        -h|--help)
            echo "用法: $0 [--skip-build]"
            echo "  --skip-build  复用已有的 ${APP}"
            exit 0
            ;;
        *) echo "未知参数: ${arg}" >&2; exit 2 ;;
    esac
done

if [[ "${SKIP_BUILD}" -eq 0 ]]; then
    "${ROOT}/.venv/bin/pyinstaller" --noconfirm --log-level=WARN \
        --distpath "${DIST}" --workpath "${WORK}/pyinstaller" \
        "${ROOT}/deploy/skyblock-bazaar.spec"
fi

if [[ ! -x "${APP}/SkyBlockBazaar" ]]; then
    echo "找不到已构建的程序：${APP}/SkyBlockBazaar" >&2
    exit 1
fi

STAGE="${WORK}/pkg"
rm -rf "${STAGE}"
mkdir -p "${STAGE}/DEBIAN" \
    "${STAGE}${PREFIX}" \
    "${STAGE}/usr/bin" \
    "${STAGE}/usr/share/applications" \
    "${STAGE}/usr/share/icons/hicolor/256x256/apps" \
    "${STAGE}/usr/share/doc/skyblock-bazaar"

cp -a "${APP}/." "${STAGE}${PREFIX}/"
find "${STAGE}${PREFIX}" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "${STAGE}" -type d -exec chmod 755 {} +
find "${STAGE}${PREFIX}" -type f -exec chmod a-w {} +
ln -s "${PREFIX}/SkyBlockBazaar" "${STAGE}/usr/bin/skyblock-bazaar"
install -m 644 "${ROOT}/deploy/skyblock-bazaar-package.desktop" \
    "${STAGE}/usr/share/applications/skyblock-bazaar.desktop"
install -m 644 "${ROOT}/bazaar.png" \
    "${STAGE}/usr/share/icons/hicolor/256x256/apps/skyblock-bazaar.png"
install -m 644 "${ROOT}/deploy/deb-copyright" "${STAGE}/usr/share/doc/skyblock-bazaar/copyright"
install -m 644 "${ROOT}/README.md" "${STAGE}/usr/share/doc/skyblock-bazaar/README.md"

INSTALLED_KB="$(du -sk "${STAGE}" | cut -f1)"
cat > "${STAGE}/DEBIAN/control" <<EOF
Package: skyblock-bazaar
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: Cmprssntl <cmprssntl@gmail.com>
Installed-Size: ${INSTALLED_KB}
Depends: libc6 (>= ${GLIBC_MIN}), libstdc++6, libgl1, libegl1, libfontconfig1, libdbus-1-3, libxkbcommon0, libxkbcommon-x11-0, libxcb-cursor0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-render-util0, libxcb-shape0, libxcb-xinerama0, libxcb-xkb1
Homepage: https://github.com/Cmprssntl/skyblock-bazaar-tool
Description: Hypixel SkyBlock market analysis tool
 Bazaar / Craft / Forge / Enchant price tables with local candlestick
 charts and SQLite history recording. Data is stored in the user's
 XDG data directory when the installation directory is read-only.
EOF

cat > "${STAGE}/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
EOF

cat > "${STAGE}/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
EOF
chmod 755 "${STAGE}/DEBIAN/postinst" "${STAGE}/DEBIAN/postrm"

OUT="${DIST}/skyblock-bazaar_${VERSION}_${ARCH}.deb"
mkdir -p "${DIST}"
dpkg-deb --root-owner-group -Zxz --build "${STAGE}" "${OUT}"
echo "已生成：${OUT}"
