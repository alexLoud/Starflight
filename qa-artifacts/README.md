# Starflight Linux QA tarball (commit 0d48f2b)

Undivided archive is ~194MB (over GitHub's 100MB file limit), so it is split into three parts.

## Download + reassemble (no GitHub auth required)

```bash
curl -fL -o Starflight-1.1.3-linux.tar.gz.part00 \
  https://github.com/alexLoud/Starflight/raw/cursor/linux-qa-download-09f9/qa-artifacts/Starflight-1.1.3-linux-0d48f2b.tar.gz.part00
curl -fL -o Starflight-1.1.3-linux.tar.gz.part01 \
  https://github.com/alexLoud/Starflight/raw/cursor/linux-qa-download-09f9/qa-artifacts/Starflight-1.1.3-linux-0d48f2b.tar.gz.part01
curl -fL -o Starflight-1.1.3-linux.tar.gz.part02 \
  https://github.com/alexLoud/Starflight/raw/cursor/linux-qa-download-09f9/qa-artifacts/Starflight-1.1.3-linux-0d48f2b.tar.gz.part02

cat Starflight-1.1.3-linux.tar.gz.part* > Starflight-1.1.3-linux.tar.gz
echo '5b895ee00e475a5f8db25b0186bfd052a6817739186999530259dc255f940bcb  Starflight-1.1.3-linux.tar.gz' | sha256sum -c -
tar -xzf Starflight-1.1.3-linux.tar.gz
./Starflight/Starflight
```

SHA256 of full `Starflight-1.1.3-linux.tar.gz`: `5b895ee00e475a5f8db25b0186bfd052a6817739186999530259dc255f940bcb`

Built from PR branch commit `0d48f2b` (`cursor/linux-qt-libs-bundle-09f9` / PR #5).
Verified `_internal/libEGL.so.1`, `_internal/libGLdispatch.so.0`, `_internal/libxcb-cursor.so.0`.
