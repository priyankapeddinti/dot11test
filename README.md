# dot11test

Host-side Python/pytest framework for running WiFi functionality and performance
tests on an Android device over ADB. Designed for rooted / userdebug builds.

## Layout

```
dot11test/      core library (adb wrapper, wifi control, iperf, ping, results)
tests/
  functional/   scan, connect, roam
  performance/  iperf3 throughput, ping latency
  stability/    reconnect loop, long-running ping soak
config/         example config; copy to config/config.yaml
results/        per-test JSON output (created on run)
```

## Requirements

Host:

- Python 3.9+
- `adb` on `$PATH`
- `pip install -r requirements.txt`

Device:

- Rooted / userdebug Android (11+ recommended for `cmd wifi connect-network`)
- USB debugging enabled, `adb devices` shows it
- iperf3 binary pushed to `/data/local/tmp/iperf3` and `chmod 755`
  - Prebuilt Android iperf3 binaries are widely available; or build from source
    with NDK.

Network:

- An iperf3 server reachable from the device's WiFi network (see `iperf.server`
  in config).
- One or more known SSIDs configured under `networks` in config.

## Setup

```bash
pip install -r requirements.txt
cp config/config.example.yaml config/config.yaml
$EDITOR config/config.yaml          # fill in SSIDs, iperf server, thresholds

# Push iperf3 to the device (one-time):
adb push /path/to/iperf3 /data/local/tmp/iperf3
adb shell chmod 755 /data/local/tmp/iperf3
```

If multiple devices are attached, set `device.serial` in the config or the
`ANDROID_SERIAL` env var.

## Running

```bash
# Everything
pytest

# By category
pytest -m functional
pytest -m performance
pytest -m "stability and not soak"
pytest -m soak                       # long-running

# A single test
pytest tests/performance/test_throughput.py::test_tcp_downlink -v

# HTML report
pytest --html=reports/report.html --self-contained-html

# Override soak duration (seconds)
DOT11_SOAK_SECONDS=3600 pytest -m soak
```

Per-test machine-readable results land in `results/` as timestamped JSON,
suitable for trending over time.

## Adding tests

1. Drop a new `test_*.py` under the appropriate `tests/<category>/`.
2. Use the `device`, `wifi_on`, or `connected` fixtures from `tests/conftest.py`.
3. Use `dot11test.stats.record(name, payload)` for any numeric results worth
   persisting.

## Extending the framework

- New WiFi operations: add methods to `dot11test/wifi.py` — most are thin
  wrappers around `cmd wifi` or `dumpsys wifi`.
- Other measurement tools (e.g. `tcpdump`, `wpa_cli`, vendor HALs): add a module
  alongside `iperf.py` / `ping.py`.
- CI: the framework is plain pytest, so any runner that can attach an Android
  device (or talk to a remote one via `adb connect`) will work.

## Known limitations

- Roam tests are observational; forcing a roam requires either disabling one AP
  or vendor-specific tooling.
- Parsing of `dumpsys wifi` output varies by Android version; if a field comes
  back `None`, check `adb shell dumpsys wifi` on your DUT and adjust regexes in
  `dot11test/wifi.py`.
- WPA-Enterprise (EAP) is not wired up; `cmd wifi connect-network` supports it
  but it needs additional credentials handling.
