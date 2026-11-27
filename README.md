# AAAB updates

English build of Anti-Anti-Adblocker (AAAB) for desktop Chromium and Microsoft Edge.

- Extension ID: `cdkcnbepbdllejmapkbffamoekdbhplj`
- Version: `1.0.2`
- Update manifest: [updates.xml](https://raw.githubusercontent.com/9mc4p9n8kk-spec/aaab-updates/main/updates.xml)
- Signed package: [aaab.crx](https://github.com/9mc4p9n8kk-spec/aaab-updates/raw/refs/heads/main/aaab.crx)

The CRX is signed with the original signing key to preserve the extension ID. The private key must never be committed to this public repository; store it as the GitHub Actions repository secret `AAAB_SIGNING_KEY`.

To publish later versions, update `extension/manifest.json` and push the changes to `main`. The GitHub Actions workflow builds and publishes the CRX and update manifest. The initial workflow run is manual so you can add the signing-key secret first.

Note: the original package notes that the extension was not functionally tested against live websites. This is a desktop Chromium/Edge extension, not an Android Edge extension.
