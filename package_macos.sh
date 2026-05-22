#!/bin/zsh

# IconifyGo macOS Packaging Script
echo "🚀 Starting IconifyGo macOS packaging process..."

# 1. Setup paths
PROJECT_ROOT=$(pwd)
DIST_DIR="$PROJECT_ROOT/dist"
BUILD_DIR="$PROJECT_ROOT/build"
ICON_PATH="$PROJECT_ROOT/res/iconifygo.icns"
MAIN_SCRIPT="$PROJECT_ROOT/src/main.py"

# 2. Cleanup previous builds
echo "🧹 Cleaning up previous builds..."
rm -rf "$DIST_DIR" "$BUILD_DIR" *.spec

# 3. Ensure environment is ready
if [[ -d "venv" ]]; then
    echo "🐍 Activating virtual environment..."
    source venv/bin/activate
fi

# Check if pyinstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    echo "❌ PyInstaller not found. Installing..."
    pip install pyinstaller
fi

# 4. Build the application
echo "📦 Running PyInstaller..."

# Note: on macOS, add-data uses colon separator (source:dest)
# We add src to ensures all packages are found
pyinstaller --noconfirm --windowed \
    --name "IconifyGo" \
    --icon "$ICON_PATH" \
    --add-data "res:res" \
    --paths "$PROJECT_ROOT" \
    --hidden-import "PySide6.QtSvg" \
    --hidden-import "PySide6.QtSvgWidgets" \
    --collect-all "rembg" \
    --collect-all "onnxruntime" \
    --exclude-module "pymatting" \
    --exclude-module "numba" \
    --exclude-module "llvmlite" \
    --exclude-module "scipy" \
    --exclude-module "skimage" \
    --exclude-module "PySide6.QtPdf" \
    --exclude-module "PySide6.QtQml" \
    --exclude-module "PySide6.QtQuick" \
    --exclude-module "PySide6.QtVirtualKeyboard" \
    --exclude-module "PySide6.QtDBus" \
    --exclude-module "PySide6.QtNetwork" \
    --exclude-module "PySide6.QtOpenGL" \
    "$MAIN_SCRIPT"

# 5. Check result
if [[ -d "$DIST_DIR/IconifyGo.app" ]]; then
    echo "\n✅ Packaging complete!"
    echo "📂 Your app is located at: $DIST_DIR/IconifyGo.app"
    echo "✨ You can run it with: open $DIST_DIR/IconifyGo.app"
else
    echo "\n❌ Packaging failed. Please check the logs above."
    exit 1
fi
