#!/usr/bin/env python3
"""Apply the maintained AAAB fork customizations to a fresh upstream checkout.

This deliberately checks the upstream source shape before editing. If upstream
changes the relevant code, it exits instead of silently publishing a broken build.
"""
from pathlib import Path
import re, json, sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "upstream")
SRC = ROOT / "src"

def edit(path, transform):
    p = SRC / path
    s = p.read_text(encoding="utf-8")
    out = transform(s)
    if out == s:
        raise SystemExit(f"Customization made no change to {path}; upstream may have changed.")
    p.write_text(out, encoding="utf-8")

def replace_once(s, old, new, label):
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"Expected exactly one {label}; found {n}. Refusing unsafe patch.")
    return s.replace(old, new, 1)

def config(s):
    s = replace_once(s, "  disabledSites: string[];", "  allowedSites: string[];", "disabledSites interface field")
    s = replace_once(s, "  disabledSites: [],", "  allowedSites: [],", "disabledSites default")
    old = """    disabledSites: Array.isArray(r.disabledSites)
      ? r.disabledSites.map((s) => cleanHostname(String(s))).filter(Boolean)
      : [...DEFAULT_CONFIG.disabledSites],"""
    new = """    // Empty allowlist is intentional: no site runs AAAB until explicitly enabled.
    allowedSites: Array.isArray(r.allowedSites)
      ? [...new Set(r.allowedSites.map((s) => cleanHostname(String(s))).filter(Boolean))]
      : [...DEFAULT_CONFIG.allowedSites],"""
    s = replace_once(s, old, new, "disabledSites normalization")
    old = """export function hostToExcludePatterns(host: string): string[] {
  const clean = cleanHostname(host);
  if (!clean) return [];
  return [`*://${clean}/*`, `*://*.${clean}/*`];
}"""
    new = """export function hostToMatchPatterns(host: string): string[] {
  const clean = cleanHostname(host);
  if (!clean) return [];
  // Exact host only. www is treated as the same site; other subdomains
  // must be added separately to the allowlist.
  return clean.startsWith('www.')
    ? [`*://${clean}/*`, `*://${clean.slice(4)}/*`]
    : [`*://${clean}/*`, `*://www.${clean}/*`];
}"""
    return replace_once(s, old, new, "hostToExcludePatterns helper")

def worker(s):
    s = s.replace(
        "  hostToExcludePatterns,\n  type Config",
        "  cleanHostname,\n  hostToMatchPatterns,\n  type Config"
    )
    if "hostToMatchPatterns" not in s:
        raise SystemExit("Could not update service-worker imports.")
    pattern = re.compile(r"export async function syncContentScripts\(config: Config\): Promise<void> \{.*?\n\}", re.S)
    m = pattern.search(s)
    if not m:
        raise SystemExit("Could not locate syncContentScripts; refusing unsafe patch.")
    new_fn = """export async function syncContentScripts(config: Config): Promise<void> {
  if (typeof chrome === 'undefined' || !chrome.scripting) return;

  try {
    await chrome.scripting.unregisterContentScripts();
  } catch {}

  // Strict allowlist: no registered content scripts when the list is empty.
  if (!config.enabled || config.allowedSites.length === 0) return;

  const matches = [...new Set(config.allowedSites.flatMap(hostToMatchPatterns))];
  if (matches.length === 0) return;

  const scripts: chrome.scripting.RegisteredContentScript[] = [
    {
      id: 'aaab-shield',
      js: ['shield.js'],
      world: 'MAIN',
      runAt: 'document_start',
      allFrames: true,
      matchOriginAsFallback: true,
      matches
    },
    {
      id: 'aaab-cleaner',
      js: ['cleaner.js'],
      world: 'ISOLATED',
      runAt: 'document_start',
      allFrames: false,
      matches
    }
  ];

  await chrome.scripting.registerContentScripts(scripts);
}"""
    s = s[:m.start()] + new_fn + s[m.end():]
    old = """        const host = msg.host || '';
        const disabled = config.disabledSites.includes(host);
        sendResponse({ host, disabled });"""
    new = """        const host = cleanHostname(msg.host || '');
        const allowed = config.allowedSites.includes(host);
        sendResponse({ host, allowed });"""
    s = replace_once(s, old, new, "getSiteState disabled lookup")
    old = """    if (msg?.type === 'setSiteDisabled') {
      chrome.storage.local.get('config', async (data) => {
        const config = normalizeConfig(data?.config);
        const host = msg.host || '';
        if (msg.disabled) {
          if (!config.disabledSites.includes(host)) {
            config.disabledSites.push(host);
          }
        } else {
          config.disabledSites = config.disabledSites.filter((s) => s !== host);
        }
        await chrome.storage.local.set({ config });
        sendResponse({ success: true });
      });
      return true; // async
    }"""
    new = """    if (msg?.type === 'setSiteAllowed') {
      chrome.storage.local.get('config', async (data) => {
        const config = normalizeConfig(data?.config);
        const host = cleanHostname(msg.host || '');
        if (msg.allowed) {
          if (host && !config.allowedSites.includes(host)) config.allowedSites.push(host);
        } else {
          config.allowedSites = config.allowedSites.filter((site) => site !== host);
        }
        await chrome.storage.local.set({ config });
        sendResponse({ success: true });
      });
      return true; // async
    }"""
    return replace_once(s, old, new, "setSiteDisabled handler")

def popup_ts(s):
    s = replace_once(s, "toggle.checked = !res?.disabled;", "toggle.checked = !!res?.allowed;", "popup disabled-state read")
    s = s.replace("    const disabled = !toggle.checked;", "")
    old = "chrome.runtime.sendMessage({ type: 'setSiteDisabled', host, disabled }, () => {"
    new = "chrome.runtime.sendMessage({ type: 'setSiteAllowed', host, allowed: toggle.checked }, () => {"
    s = replace_once(s, old, new, "popup site-toggle message")
    s = s.replace("hostElem.textContent = 'Trang hệ thống';", "hostElem.textContent = 'System page';")
    return s

def options_ts(s):
    s = s.replace("disabled-sites", "allowed-sites")
    s = s.replace("disabledSites", "allowedSites")
    s = s.replace("cfg.disabledSites", "cfg.allowedSites")
    s = s.replace("statusMsg.textContent = 'Đã lưu cấu hình!';", "statusMsg.textContent = 'Settings saved.';")
    if "disabledSites" in s or "cfg.disabledSites" in s:
        raise SystemExit("Some disabledSites references remain in options.ts.")
    return s

def html_popup(s):
    replacements = {
      '<html lang="vi">':'<html lang="en">',
      'Trang hệ thống':'System page',
      'Bật trên trang này':'Enable on this site',
      'Tải lại trang để áp dụng':'Reload the page to apply changes',
      'Tải lại':'Reload',
      'Tường chặn đã gỡ':'Walls removed',
      'Kiểm tra bị lừa':'Checks spoofed',
      'Timer bị chặn':'Timers skipped',
      'Không hoạt động trên trang này':'Not active on this page'
    }
    for a,b in replacements.items(): s=s.replace(a,b)
    return s

def html_options(s):
    replacements = {
      '<html lang="vi">':'<html lang="en">',
      'Cài đặt AAAB':'AAAB Settings',
      'Cài đặt Anti-Anti-Adblock':'Anti-Anti-Adblock Settings',
      'Trạng thái chung':'General',
      'Bật tiện ích toàn cục':'Enable extension globally',
      'Bật debug console log ([AAAB])':'Enable debug console logging ([AAAB])',
      'Kỹ thuật Shield (MAIN World)':'Shield techniques (MAIN world)',
      'Đánh lừa kích thước phần tử mồi':'Spoof bait element dimensions',
      'Giả lập biến FuckAdBlock, canRunAds, v.v.':'Mock detector globals such as FuckAdBlock and canRunAds',
      'Giả lập thành công khi tải script/ảnh quảng cáo':'Simulate successful ad script/image loads',
      'Bỏ qua timer có mã phát hiện adblock':'Skip timers containing adblock-detection code',
      'Mở Shadow DOM để dọn tường ẩn':'Open Shadow DOM so hidden walls can be cleaned',
      'Kỹ thuật Cleaner (ISOLATED World)':'Cleaner techniques (ISOLATED world)',
      'Gỡ bỏ tường chặn xuất hiện trên DOM':'Remove anti-adblock walls from the DOM',
      'Khôi phục thanh cuộn trang (Overflow / Scroll-lock)':'Restore page scrolling (overflow / scroll lock)',
      'Gỡ hiệu ứng làm mờ trang (Blur filter)':'Remove page blur effects',
      'Danh sách trang bị tắt (mỗi dòng một domain)':'Allowed sites (one exact domain per line)',
      'id="disabled-sites"':'id="allowed-sites"',
      'example.com&#10;test.org':'example.com&#10;www.example.org'
    }
    for a,b in replacements.items(): s=s.replace(a,b)
    return s

edit("shared/config.ts", config)
edit("background/sw.ts", worker)
edit("popup/popup.ts", popup_ts)
edit("options/options.ts", options_ts)
edit("popup/popup.html", html_popup)
edit("options/options.html", html_options)

# Keep upstream unit tests aligned with the intentional allowlist behavior.
def patch_test(path, transform):
    p = ROOT / "test" / path
    s = p.read_text(encoding="utf-8")
    out = transform(s)
    if out == s:
        raise SystemExit(f"Test customization made no change to {path}; refusing unsafe patch.")
    p.write_text(out, encoding="utf-8")

def config_test(s):
    s = s.replace("hostToExcludePatterns", "hostToMatchPatterns")
    s = s.replace("disabledSites", "allowedSites")
    s = s.replace("converts host to exclude patterns, stripping www if present",
                  "matches exact host and its www counterpart only")
    old = """    expect(hostToMatchPatterns('example.com')).toEqual([
      '*://example.com/*',
      '*://*.example.com/*'
    ]);
    expect(hostToMatchPatterns('www.vnexpress.net')).toEqual([
      '*://vnexpress.net/*',
      '*://*.vnexpress.net/*'
    ]);"""
    new = """    expect(hostToMatchPatterns('example.com')).toEqual([
      '*://example.com/*',
      '*://www.example.com/*'
    ]);
    expect(hostToMatchPatterns('www.vnexpress.net')).toEqual([
      '*://www.vnexpress.net/*',
      '*://vnexpress.net/*'
    ]);
    expect(hostToMatchPatterns('')).toEqual([]);"""
    return replace_once(s, old, new, "config test host pattern expectations")

def worker_test(s):
    old = """  it('registers shield and cleaner content scripts with excludeMatches', async () => {
    const config = {
      ...DEFAULT_CONFIG,
      disabledSites: ['example.com']
    };

    await syncContentScripts(config);

    expect(unregisterMock).toHaveBeenCalled();
    expect(registerMock).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({
          id: 'aaab-shield',
          world: 'MAIN',
          excludeMatches: ['*://example.com/*', '*://*.example.com/*']
        }),
        expect.objectContaining({
          id: 'aaab-cleaner',
          world: 'ISOLATED',
          excludeMatches: ['*://example.com/*', '*://*.example.com/*']
        })
      ])
    );
  });"""
    new = """  it('does not register content scripts when the allowlist is empty', async () => {
    await syncContentScripts({ ...DEFAULT_CONFIG, allowedSites: [] });
    expect(unregisterMock).toHaveBeenCalled();
    expect(registerMock).not.toHaveBeenCalled();
  });

  it('registers shield and cleaner only for explicitly allowed exact hosts', async () => {
    await syncContentScripts({
      ...DEFAULT_CONFIG,
      allowedSites: ['example.com']
    });

    expect(unregisterMock).toHaveBeenCalled();
    expect(registerMock).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({
          id: 'aaab-shield',
          world: 'MAIN',
          matches: ['*://example.com/*', '*://www.example.com/*']
        }),
        expect.objectContaining({
          id: 'aaab-cleaner',
          world: 'ISOLATED',
          matches: ['*://example.com/*', '*://www.example.com/*']
        })
      ])
    );
  });"""
    return replace_once(s, old, new, "background test blocklist test")

patch_test("unit/shared/config.test.ts", config_test)
patch_test("unit/background/sw.test.ts", worker_test)

manifest_path = SRC / "manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
manifest["default_locale"] = "en"
manifest["update_url"] = "https://raw.githubusercontent.com/9mc4p9n8kk-spec/aaab-updates/main/updates.xml"
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print("Applied English-default and strict per-site allowlist customizations.")
