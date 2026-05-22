# dot11test

Host-side Python/pytest framework for WiFi functionality and performance
tests on **Android** (via ADB) and **iOS** (via SSH over USB, jailbreak
required). The same tests run on both platforms; the driver is selected by
config.

## Layout

```
dot11test/
  shell.py            Shell protocol (every driver satisfies it)
  types.py            ScanResult, WifiStatus, ShellResult
  iperf.py, ping.py   tools that take any Shell
  android/            ADB-based driver
    adb.py, wifi.py, device.py
  ios/                SSH-over-iproxy driver (jailbreak)
    ssh.py, wifi.py, device.py
tests/
  functional/   scan, connect, roam
  performance/  iperf3 throughput, ping latency
  stability/    reconnect loop, long-running ping soak
config/         example config; copy to config/config.yaml
results/        per-test JSON output (created on run)
```

## Requirements

Host (both platforms):

- Python 3.9+
- `pip install -r requirements.txt`

### Android

- `adb` on `$PATH`
- Rooted / userdebug Android (11+ recommended for `cmd wifi connect-network`)
- USB debugging enabled, `adb devices` shows the DUT
- iperf3 binary at `/data/local/tmp/iperf3` (`chmod 755`)

### iOS (jailbroken)

- macOS or Linux host with `ssh` and `scp` on `$PATH`
- `libimobiledevice` / `usbmuxd` for the `iproxy` USB tunnel
  - macOS: `brew install libimobiledevice`
  - Linux: `apt install libimobiledevice-utils usbmuxd`
- Jailbroken iOS device with:
  - OpenSSH (default on most jailbreaks)
  - iperf3 (Sileo/Cydia package, or pushed manually)
  - A WiFi helper utility for control operations (see below)
- SSH key-based auth strongly recommended (default `alpine` password is a
  serious risk on a real network — change it).

Network (both platforms):

- iperf3 server reachable from the DUT's WiFi network.
- One or more known SSIDs configured under `networks`.

## Setup

```bash
pip install -r requirements.txt
cp config/config.example.yaml config/config.yaml
$EDITOR config/config.yaml          # set `platform:` and fill in the relevant section
```

### Android one-time prep

```bash
adb push /path/to/iperf3 /data/local/tmp/iperf3
adb shell chmod 755 /data/local/tmp/iperf3
```

### iOS one-time prep

```bash
# 1. Tunnel SSH over USB (leave running in another terminal):
iproxy 2222 22                              # or: iproxy 2222 22 <udid>

# 2. Push your SSH key so you stop typing 'alpine':
ssh-copy-id -p 2222 root@127.0.0.1

# 3. Install iperf3 on the device (via Sileo) or push a static binary:
scp -P 2222 iperf3 root@127.0.0.1:/usr/local/bin/iperf3
ssh -p 2222 root@127.0.0.1 'chmod 755 /usr/local/bin/iperf3'

# 4. Install or build a WiFi helper that links MobileWiFi.framework, and
#    wire its commands into config.yaml under ios.wifi_helper. See below.
```

#### iOS WiFi helper

iOS has no shipped CLI for WiFi control. The framework calls a user-provided
helper over SSH for enable/disable/scan/connect/disconnect/forget/status.
You configure command templates under `ios.wifi_helper:` in `config.yaml`.
Read-only tests (iperf, ping) work without a helper as long as the device is
already connected to a known SSID.

Expected helper output:

- `status` → one line of `key=value` pairs, e.g.
  `ssid="MySSID" bssid=aa:bb:cc:dd:ee:ff rssi=-55 freq=5180 enabled=1`
- `scan` → one network per line: `<bssid> <freq_mhz> <rssi_dbm> <ssid>`
- All others → exit 0 on success.

If a template isn't configured, tests that need that operation are skipped
with a clear message — the rest still run.

## Running

```bash
# Pick the driver (overrides config.platform):
DOT11_PLATFORM=android pytest
DOT11_PLATFORM=ios     pytest

# By category
pytest -m functional
pytest -m performance
pytest -m "stability and not soak"
pytest -m soak

# A single test
pytest tests/performance/test_throughput.py::test_tcp_downlink -v

# HTML report
pytest --html=reports/report.html --self-contained-html

# Override soak duration
DOT11_SOAK_SECONDS=3600 pytest -m soak
```

Per-test machine-readable results land in `results/` as timestamped JSON.

## Adding tests

1. Drop a `test_*.py` under `tests/<category>/`.
2. Use the `device`, `wifi_on`, or `connected` fixtures from `tests/conftest.py`.
3. For tools that just need shell access (`ping`, `iperf3`, custom scripts),
   pass `device.shell` — it satisfies the `Shell` protocol on both platforms.
4. Use `dot11test.stats.record(name, payload)` for any numeric results worth
   persisting.

## Extending the framework

- Add WiFi operations to `dot11test/android/wifi.py` or `dot11test/ios/wifi.py`.
- New measurement tools should accept a `Shell` rather than a platform-specific
  driver so they run on both platforms.
- A third platform (e.g. a Linux/Windows DUT with its own remote shell) means
  writing one driver module that satisfies `Shell` and a matching `*Device`
  + `*Wifi` class.

## Known limitations

- **Android:** `dumpsys wifi` parsing varies by version. WPA-Enterprise is
  not wired up. Forced roam is observational only.
- **iOS:** Without a jailbreak, this driver cannot work; see `README` Option B/C
  in the design discussion for non-jailbreak alternatives. WiFi control depends
  entirely on the configured helper — quality of results follows the helper.
- iOS performance numbers are sensitive to whether the screen is on and the
  device is plugged in (USB power can affect radio behavior). Document your
  test conditions in result metadata.
