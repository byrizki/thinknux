#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Determine Version
VERSION="${1:-}"
if [ -z "$VERSION" ]; then
    if [ -f "$PROJECT_ROOT/pyproject.toml" ]; then
        VERSION=$(grep -m 1 '^version = ' "$PROJECT_ROOT/pyproject.toml" | sed -E 's/version = "(.*)"/\1/')
    fi
fi
VERSION="${VERSION:-0.1.0}"
# Strip leading 'v' if provided
VERSION="${VERSION#v}"

ARCH="${2:-all}"
PACKAGE_NAME="thinknux"

echo "==> Building Debian package for ${PACKAGE_NAME} v${VERSION} (${ARCH})..."

# Directories
BUILD_DIR="$PROJECT_ROOT/build/deb"
PKG_DIR="$BUILD_DIR/${PACKAGE_NAME}_${VERSION}_${ARCH}"
DIST_DIR="$PROJECT_ROOT/dist"

rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR/DEBIAN"
mkdir -p "$PKG_DIR/usr/bin"
mkdir -p "$PKG_DIR/usr/lib/thinknux"
mkdir -p "$PKG_DIR/usr/lib/tmpfiles.d"
mkdir -p "$PKG_DIR/usr/lib/python3/dist-packages"
mkdir -p "$PKG_DIR/usr/share/applications"
mkdir -p "$PKG_DIR/usr/share/icons/hicolor/scalable/apps"
mkdir -p "$PKG_DIR/usr/share/pixmaps"
mkdir -p "$PKG_DIR/usr/share/polkit-1/rules.d"
mkdir -p "$PKG_DIR/usr/share/doc/${PACKAGE_NAME}"

# 1. Copy application python code
echo "==> Copying Python package..."
cp -r "$PROJECT_ROOT/thinknux" "$PKG_DIR/usr/lib/python3/dist-packages/"
find "$PKG_DIR/usr/lib/python3/dist-packages/thinknux" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$PKG_DIR/usr/lib/python3/dist-packages/thinknux" -name "*.pyc" -delete 2>/dev/null || true

# 2. Create launcher executable in /usr/bin
echo "==> Creating binary launcher..."
cat << 'EOF' > "$PKG_DIR/usr/bin/thinknux"
#!/usr/bin/python3
import sys
from thinknux.main import main

if __name__ == "__main__":
    sys.exit(main())
EOF
chmod 755 "$PKG_DIR/usr/bin/thinknux"

# 3. Copy privileged fan control helper
echo "==> Installing privileged fan control helper..."
if [ -f "$PROJECT_ROOT/packaging/helper/thinknux-fan-control" ]; then
    cp "$PROJECT_ROOT/packaging/helper/thinknux-fan-control" "$PKG_DIR/usr/lib/thinknux/thinknux-fan-control"
    chmod 755 "$PKG_DIR/usr/lib/thinknux/thinknux-fan-control"
fi

# 4. Copy polkit rule
echo "==> Installing Polkit rule..."
if [ -f "$PROJECT_ROOT/packaging/polkit/50-thinknux.rules" ]; then
    cp "$PROJECT_ROOT/packaging/polkit/50-thinknux.rules" "$PKG_DIR/usr/share/polkit-1/rules.d/50-thinknux.rules"
    chmod 644 "$PKG_DIR/usr/share/polkit-1/rules.d/50-thinknux.rules"
fi

# 5. Copy systemd tmpfiles configuration
echo "==> Installing systemd-tmpfiles configuration..."
if [ -f "$PROJECT_ROOT/packaging/tmpfiles/thinknux.conf" ]; then
    cp "$PROJECT_ROOT/packaging/tmpfiles/thinknux.conf" "$PKG_DIR/usr/lib/tmpfiles.d/thinknux.conf"
    chmod 644 "$PKG_DIR/usr/lib/tmpfiles.d/thinknux.conf"
fi

# 6. Copy desktop entry and icons
echo "==> Copying desktop file and icons..."
if [ -f "$PROJECT_ROOT/packaging/desktop/com.byrizki.thinknux.desktop" ]; then
    cp "$PROJECT_ROOT/packaging/desktop/com.byrizki.thinknux.desktop" "$PKG_DIR/usr/share/applications/com.byrizki.thinknux.desktop"
fi

if [ -f "$PROJECT_ROOT/packaging/desktop/com.byrizki.thinknux.svg" ]; then
    cp "$PROJECT_ROOT/packaging/desktop/com.byrizki.thinknux.svg" "$PKG_DIR/usr/share/icons/hicolor/scalable/apps/com.byrizki.thinknux.svg"
    cp "$PROJECT_ROOT/packaging/desktop/com.byrizki.thinknux.svg" "$PKG_DIR/usr/share/pixmaps/com.byrizki.thinknux.svg"
fi

# 7. Copy documentation
if [ -f "$PROJECT_ROOT/README.md" ]; then
    cp "$PROJECT_ROOT/README.md" "$PKG_DIR/usr/share/doc/${PACKAGE_NAME}/README.md"
fi
if [ -f "$PROJECT_ROOT/LICENSE" ]; then
    cp "$PROJECT_ROOT/LICENSE" "$PKG_DIR/usr/share/doc/${PACKAGE_NAME}/copyright"
else
    cat << EOF > "$PKG_DIR/usr/share/doc/${PACKAGE_NAME}/copyright"
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: thinknux
Upstream-Contact: Muhamad Rizki <https://github.com/byrizki/thinknux>
Source: https://github.com/byrizki/thinknux

Files: *
Copyright: 2026 Muhamad Rizki
License: LGPL-3.0
 On Debian systems, the complete text of the GNU Lesser General Public
 License version 3 can be found in "/usr/share/common-licenses/LGPL-3".
EOF
fi

# 8. Maintainer scripts (postinst, postrm)
cat << 'EOF' > "$PKG_DIR/DEBIAN/postinst"
#!/bin/sh
set -e

if [ "$1" = "configure" ]; then
    # Apply systemd tmpfiles permissions immediately
    if command -v systemd-tmpfiles >/dev/null 2>&1; then
        systemd-tmpfiles --create /usr/lib/tmpfiles.d/thinknux.conf 2>/dev/null || true
    fi

    # Reload polkit daemon if running
    if command -v systemctl >/dev/null 2>&1; then
        systemctl reload polkit 2>/dev/null || true
    fi

    # Update desktop file database
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi

    # Update icon cache
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
    fi
fi

exit 0
EOF

cat << 'EOF' > "$PKG_DIR/DEBIAN/postrm"
#!/bin/sh
set -e

if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    # Update desktop file database
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi

    # Update icon cache
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
    fi
fi

exit 0
EOF

# 9. Create DEBIAN/control file
echo "==> Generating DEBIAN/control..."
cat << EOF > "$PKG_DIR/DEBIAN/control"
Package: ${PACKAGE_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: Muhamad Rizki <https://github.com/byrizki/thinknux>
Depends: python3 (>= 3.10), python3-gi, python3-gi-cairo | python3-cairo, python3-psutil, gir1.2-gtk-4.0, gir1.2-adw-1, pkexec | policykit-1 | polkitd
Recommends: lm-sensors, gir1.2-ayatanaappindicator3-0.1
Suggests: clamav, clamav-freshclam, tlp
Homepage: https://github.com/byrizki/thinknux
Description: Native GTK4 + Libadwaita ThinkPad hardware management utility for Linux
 ThinkNux gives you full control over ThinkPad cooling, battery charge longevity
 thresholds, CPU frequency scaling, power profiles, TrackPoint, BIOS tweaks,
 and hardware monitoring with modern GNOME Human Interface Guidelines (HIG).
EOF

# 10. Normalize permissions
chmod -R u-s,g-s "$PKG_DIR"
find "$PKG_DIR" -type d -exec chmod 755 {} +
find "$PKG_DIR/usr/bin" -type f -exec chmod 755 {} +
find "$PKG_DIR/usr/lib/thinknux" -type f -exec chmod 755 {} +
find "$PKG_DIR/usr/lib/python3" -type f -exec chmod 644 {} +
find "$PKG_DIR/usr/lib/tmpfiles.d" -type f -exec chmod 644 {} +
find "$PKG_DIR/usr/share" -type f -exec chmod 644 {} +
chmod 755 "$PKG_DIR/DEBIAN"
chmod 644 "$PKG_DIR/DEBIAN/control"
chmod 755 "$PKG_DIR/DEBIAN/postinst"
chmod 755 "$PKG_DIR/DEBIAN/postrm"

# 11. Build the package with dpkg-deb
mkdir -p "$DIST_DIR"
DEB_FILE="$DIST_DIR/${PACKAGE_NAME}_${VERSION}_${ARCH}.deb"

echo "==> Building ${DEB_FILE}..."
dpkg-deb --build --root-owner-group "$PKG_DIR" "$DEB_FILE"

# 12. Inspect the package
echo "==> Package build completed successfully!"
ls -lh "$DEB_FILE"

echo ""
echo "==> Package Information:"
dpkg-deb --info "$DEB_FILE"

echo ""
echo "==> Package File List:"
dpkg-deb --contents "$DEB_FILE"
