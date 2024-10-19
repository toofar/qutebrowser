#!/usr/bin/bash

patch_dir="$(realpath $(dirname $0))"
ls $patch_dir

if [ -z "$CI" ] ;then
  echo "Not running on CI, not applying patches."
  exit 1
fi

qt_ver="$(pacman -Q qt6-webengine | cut -d' ' -f2)"
pyqt_ver="$(python -c 'import PyQt6.QtWebEngineCore; print(PyQt6.QtWebEngineCore.PYQT_WEBENGINE_VERSION_STR)')"

list_patches () {
  if [[ "$qt_ver" =~ ^6.8.* ]] && [[ "$pyqt_ver" =~ 6.7.* ]] ;then
    echo $patch_dir/6.8_persistant_permissions_minimal.patch
  fi
}
patches="$(list_patches)"

case "$1" in
  -t|--test)
    TEST_ONLY="y"
  ;;
esac

if [ -z "$patches" ] ;then
  echo "No patches to apply to this webengine version. qt_ver=$qt_ver pyqt_ver=$pyqt_ver"
  if [ -n "$TEST_ONLY" ] ;then
    exit 1
  fi
  exit 0
fi

if [ -n "$TEST_ONLY" ] ;then
  echo "Applying patches: $patches"
fi

# Get the latest PyQt6_WebEngine souce
# Scrape pypi.org for the source link since pip isn't capable of downloading
# source without also building a wheel.
# Parsing: <a href="https://files.pythonhosted.org/..." data-requires-python="&gt;=3.8" >PyQt6_WebEngine-6.7.0.tar.gz</a><br />
href="$(curl "https://pypi.org/simple/pyqt6-webengine/" | grep tar.gz | tail -n1 | cut -d'"' -f2)"
curl -LO "$href"
tar -xaf PyQt6_WebEngine-*.tar.gz
cd PyQt6_WebEngine-*/

for p in $(list_patches) ;do
  git apply $p
done

sip-build --no-make --jobs 2 --qmake "$(command -v qmake6)"
cd build
make -j8
make install
