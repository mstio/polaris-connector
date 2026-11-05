# Signed extension

`polaris-chatgpt-connector-<version>-signed.xpi` is the version signed by
Mozilla (AMO, unlisted, add-on 3070992), as installed in Firefox. It lives
here so that it is available right away after a reinstall, without a
Developer Hub login.

Install: `firefox dist/polaris-chatgpt-connector-0.4.4-signed.xpi`
(or drag the file into a Firefox window), then in `about:addons` →
Polaris → Permissions allow access to chatgpt.com / claude.ai.

After each new signing, put the new file here and remove the old one
(`install.sh` picks the newest).
