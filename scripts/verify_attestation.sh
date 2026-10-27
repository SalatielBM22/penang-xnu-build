#!/usr/bin/env bash
# Verify Sigstore build-provenance attestations with an isolated, checksum-verified GitHub CLI
# (the system gh is left untouched). Usage: verify_attestation.sh <file>...
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
TOOLS="$HOME/Projetos/penang-xnu-lab/references/host-tools/gh"
VER=${GH_VER:-$(curl -fsSL https://api.github.com/repos/cli/cli/releases/latest | python3 -c 'import json,sys;print(json.load(sys.stdin)["tag_name"].lstrip("v"))')}
D="$TOOLS/$VER"; mkdir -p "$D"
TAR="gh_${VER}_linux_amd64.tar.gz"
if [ ! -x "$D/gh" ]; then
  ( cd "$D"
    curl -fsSL -o checksums.txt "https://github.com/cli/cli/releases/download/v${VER}/gh_${VER}_checksums.txt"
    curl -fsSL -o "$TAR" "https://github.com/cli/cli/releases/download/v${VER}/${TAR}"
    grep " ${TAR}\$" checksums.txt | sha256sum -c - >/dev/null
    tar -xzf "$TAR" --strip-components=2 "gh_${VER}_linux_amd64/bin/gh" )
fi
echo "isolated gh: $("$D/gh" --version | head -1)"
for f in "$@"; do
  echo "== $f sha256=$(sha256sum "$f" | cut -d' ' -f1)"
  set +e
  out=$(GH_TOKEN=$(gh auth token) "$D/gh" attestation verify "$f" --repo SalatielBM22/penang-xnu-build \
    --signer-workflow SalatielBM22/penang-xnu-build/.github/workflows/measure-xnu-baseline.yml --format json 2>&1)
  rc=$?; set -e
  printf '%s' "$out" | python3 -c '
import json, sys
raw = sys.stdin.read()
try:
    v = json.loads(raw)
except ValueError:
    print("  non-JSON output:", raw[:400]); sys.exit(0)
for e in v:
    s = e["verificationResult"]["signature"]["certificate"]
    st = e["verificationResult"]["statement"]
    print("  subject:", [x["name"] + "@" + x["digest"]["sha256"][:16] for x in st["subject"]])
    print("  predicate:", st["predicateType"])
    print("  signer:", s.get("buildSignerURI"), "| run:", s.get("runInvocationURI"), "| commit:", s.get("sourceRepositoryDigest"))
'
  echo "  VERIFY_EXIT=$rc"
done
