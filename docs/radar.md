# Radar and security check

`polaris-radar` collects what matters before you customise Omarchy: updates
and local changes of installed git plugins, watched issues and repositories,
Omarchy commits, releases and newly listed plugins matching your keywords,
and Omarchy news. It writes `handoff/omarchy-radar.md` into the machine
memory; all third-party text is defused and marked as data.

The security section compares installed packages with the
[Arch Security Tracker](https://security.archlinux.org), the running kernel
with kernel.org stable of the same branch, and actively exploited
vulnerabilities from [CISA KEV](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)
with the kernel and installed packages. For package matches it checks the
affected version ranges in the [NVD](https://nvd.nist.gov), so a package that
is already fixed does not stay yellow. A finding you have assessed as not
applicable can be acknowledged for one installed state and at most 90 days
(`security.acknowledged` in `radar.yaml`); it stays listed and comes back after
an update or expiry. It runs once a day
(`polaris-radar.timer`, about 3 MB) and after `omarchy update`. Details and
switches: [`memory/README.md`](../memory/README.md).

## Scope

The security check is an attention aid for a single desktop, not a security
suite. It points out what deserves a look, helps to assess it and, for a
serious hole before a fix arrives, to find a mitigation. Most holes close with
the next regular update. False alarms are as harmful as missed ones, because
yellow lines that never need action get ignored; therefore a finding that has
been assessed can be acknowledged, and unclear cases stay yellow rather than
red. Deliberately out of scope: protection against local tampering (anyone who
can write to the home directory can silence the check; only `radar.yaml` is
covered by the optional guard hook), complete coverage of all packages,
distribution backports, and professional vulnerability management. Changes
should keep this balance: stricter rules only where a real case was missed.

---

[Back to the README](../README.md)
