# AAAB updates

English-first build of Anti-Anti-Adblocker (AAAB) for desktop Chromium browsers.

- Original project: https://github.com/thanhds/anti-anti-adblocker
- Extension ID: `cdkcnbepbdllejmapkbffamoekdbhplj`
- Current published version: `1.0.2`
- Update manifest: [updates.xml](https://raw.githubusercontent.com/9mc4p9n8kk-spec/aaab-updates/main/updates.xml)
- Signed package: [aaab.crx](https://github.com/9mc4p9n8kk-spec/aaab-updates/raw/refs/heads/main/aaab.crx)

## What the automated fork preserves

The workflow checks the author's `master` branch every six hours. When it detects a new upstream commit, it:

1. Checks out the latest upstream source.
2. Applies the fork customizations: English as the default language and a strict per-domain allowlist (empty by default; no scripts run on sites until explicitly enabled).
3. Runs the upstream unit tests, TypeScript typecheck, and build.
4. Signs a new CRX using the original private key.
5. Publishes `aaab.crx`, updates `updates.xml`, and records the upstream commit.

The customization script checks that the expected upstream code is present. If the author changes the relevant implementation, the workflow stops instead of silently publishing a build that has lost the custom behavior.

## One-time setup required

GitHub cannot store the signing private key in a public repository. Add it as a repository secret:

1. Open this repository's **Settings → Secrets and variables → Actions**.
2. Select **New repository secret**.
3. Set the name to `AAAB_SIGNING_KEY`.
4. Paste the complete PEM private key that was used to sign version 1.0.2.

**It must be the exact original private key.** The workflow verifies that it produces extension ID `cdkcnbepbdllejmapkbffamoekdbhplj` and refuses to publish if it does not. Do not generate a replacement key and do not commit the private key to this repository. Without the original key, Chrome will reject the update as belonging to a different extension.

After adding the secret, open **Actions → Sync upstream and publish signed AAAB update → Run workflow** for the initial build. Later upstream changes are checked automatically every six hours.

## Automatic update requirement

The installed extension's manifest must contain this update URL:

`https://raw.githubusercontent.com/9mc4p9n8kk-spec/aaab-updates/main/updates.xml`

If the already-installed 1.0.2 build does not contain that `update_url`, install the first successfully published build from this repository once. Subsequent compatible signed builds can update through the manifest.

## Important

- The allowlist is strict: an empty list means AAAB is inactive everywhere. Add each domain explicitly; other subdomains are not implicitly included.
- A failed test, changed upstream source layout, or signing-key mismatch prevents publication.
- This is a desktop Chromium/Edge extension, not an Android Edge extension.
- The upstream project is licensed under MIT; see its original repository for the license and attribution.
