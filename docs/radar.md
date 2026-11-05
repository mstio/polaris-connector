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
is already fixed does not stay yellow. It runs once a day
(`polaris-radar.timer`, about 3 MB) and after `omarchy update`. Details and
switches: [`memory/README.md`](../memory/README.md).

---

[Back to the README](../README.md)
