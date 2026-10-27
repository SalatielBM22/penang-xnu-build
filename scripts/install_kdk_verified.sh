#!/usr/bin/env bash
# Install the Kernel Debug Kit that darwin-xnu-build expects for <macos_version>, but only after the
# installer package proves an Apple code signature (pkgutil --check-signature, trusted chain to
# Apple Root CA). The download mirror is untrusted; the signature is the trust anchor.
# Usage: install_kdk_verified.sh <macos_version> <path to build.sh> <provenance output file>
set -euo pipefail
ver="$1"; buildsh="$2"; out="$3"
# literal match of the case label (e.g. "'15.6')"), never as a regex
block=$(awk -v v="'${ver}')" '{ t = $0; sub(/^[[:space:]]+/, "", t) } t == v { f = 1 } f { print } f && /;;/ { exit }' "$buildsh")
kdk_name=$(printf '%s\n' "$block" | sed -nE "s/^[[:space:]]*KDK_NAME='([^']+)'.*/\1/p" | head -1)
kdk_root=$(printf '%s\n' "$block" | sed -nE "s/^[[:space:]]*KDKROOT='([^']+)'.*/\1/p" | head -1)
[ -n "$kdk_name" ] && [ -n "$kdk_root" ] || { echo "KDK for ${ver} not found in build.sh"; exit 2; }
echo "kdk_name=${kdk_name}" | tee "$out"
echo "kdk_root=${kdk_root}" | tee -a "$out"
if [ -d "$kdk_root" ]; then echo "kdk_preinstalled=true" | tee -a "$out"; exit 0; fi
url=$(curl -fsSL --retry 3 "https://raw.githubusercontent.com/dortania/KdkSupportPkg/gh-pages/manifest.json" \
  | python3 -c 'import json,sys; n=sys.argv[1]; print(next(e["url"] for e in json.load(sys.stdin) if e["name"]==n))' "$kdk_name")
echo "kdk_url=${url}" | tee -a "$out"
curl -fL --retry 3 --max-time 1800 -o /tmp/KDK.dmg "$url"
echo "kdk_dmg_sha256=$(shasum -a 256 /tmp/KDK.dmg | cut -d' ' -f1)" | tee -a "$out"
mnt=$(mktemp -d)
hdiutil attach -nobrowse -readonly -mountpoint "$mnt" /tmp/KDK.dmg >/dev/null
pkg=$(find "$mnt" -maxdepth 1 -name '*.pkg' | head -1)
[ -n "$pkg" ] || { echo "no .pkg in KDK image"; hdiutil detach "$mnt"; exit 3; }
echo "kdk_pkg_sha256=$(shasum -a 256 "$pkg" | cut -d' ' -f1)" | tee -a "$out"
sig=$(pkgutil --check-signature "$pkg" || true)
printf '%s\n' "$sig" | sed 's/^/pkg_signature: /' | tee -a "$out"
if ! printf '%s\n' "$sig" | grep -q "signed by a certificate trusted by" || ! printf '%s\n' "$sig" | grep -q "Apple Root CA"; then
  echo "REFUSED: KDK package is not signed with a trusted Apple chain"; hdiutil detach "$mnt"; exit 4
fi
sudo mkdir -p /Library/Developer/KDKs
sudo installer -pkg "$pkg" -target /
hdiutil detach "$mnt" >/dev/null
[ -d "$kdk_root" ] || { echo "KDK installed but ${kdk_root} is missing"; exit 5; }
echo "kdk_installed=true" | tee -a "$out"
