# ThinkNux

A native **GTK4 + Libadwaita** desktop application for managing ThinkPad hardware on Linux, written in **Python 3**.

ThinkNux gives you full control over ThinkPad cooling, battery charge longevity thresholds, CPU frequency scaling, power profiles, and hardware monitoring—crafted with modern GNOME Human Interface Guidelines (HIG) and native desktop aesthetics.

---

## Highlights

- **⚡ Blazing Fast & Lightweight**: Pure native GTK4 application (~35 MB RAM footprint) replacing heavy webview runtimes.
- **🛡️ Hardware Safety by Design**:
  - Continuous 30-second ACPI firmware watchdog arming (`watchdog 30`).
  - Automatic, immediate fallback to `level auto` on application exit, window close, or process crash.
  - Intermediate threshold ordering checks to prevent firmware rejection (`start < stop`).
- **🔒 Secure Privilege Model**: Runs strictly unprivileged as normal user. Elevates only through hardened Polkit policies (`50-thinknux.rules`) and a whitelisted helper script (`thinknux-fan-control`).
- **🎨 GNOME Integration**: Adaptive Libadwaita widgets, system dark/light theme switching, Wayland fractional scaling, and optional system tray indicator.

---

## Features

1. **🏠 Home Dashboard**: Real-time overview of CPU utilization, package temperature, fan RPM, battery status, memory, and quick toggles for power profiles, governors, and turbo boost.
2. **🌀 Fan Control & Curve Editor**: Manual fan level control (0–7, auto, full-speed) and interactive Cairo-rendered curve canvas with drag-and-drop point manipulation and presets (Quiet, Balanced, Performance).
3. **🔋 Battery Management**: Health telemetry, dual start/stop charge thresholds (e.g. 40%–80%), and advanced charging modes (**AC Bypass / Inhibit Charge** and **Force Battery Discharge**).
4. **⚡ Performance Tuning**: CPU frequency scaling governors, power-profiles-daemon / TLP coordination, Intel Turbo Boost, and **Intel RAPL Package Power Limits (PL1/PL2 TDP)** to prevent premature firmware throttling.
5. **⌨️ Hardware Tweaks**: 
   - **ThinkPad BIOS (ThinkLMI)**: Fn ⇄ Ctrl key swap, F1–F12 as primary keys, Always-On USB charging, S3 Deep Sleep mode, and Lapmode cooling.
   - **TrackPoint**: Sensitivity slider (0–255), Press-to-Select (Tap-to-Click), and factory reset.
   - **ThinkPad LEDs**: Outer lid glowing red "i" dot (Solid, Off, Disk-Activity pulse, CPU load pulse) and power button LED ring.
6. **📊 System Monitor**: Real-time per-core CPU bars, RAM/swap memory breakdown, storage mount points, network interfaces, and top resource-consuming processes.
7. **💻 System Information**: Complete machine specifications, ThinkPad model, Linux kernel, CPU architecture, and total memory.
8. **🛡️ ClamAV Security**: Antivirus status, definition updates via `freshclam`, quick scans, and custom directory scanning with live logs and threat detection.

---

## Requirements

### Ubuntu / Debian
```bash
sudo apt update
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 \
                 gir1.2-ayatanaappindicator3-0.1 lm-sensors policykit-1 \
                 python3-psutil python3-cairo
```

### Fedora
```bash
sudo dnf install python3-gobject gtk4 libadwaita libayatana-appindicator-gtk3 \
                 lm_sensors polkit python3-psutil python3-cairo
```

### Arch Linux
```bash
sudo pacman -S python-gobject gtk4 libadwaita libayatana-appindicator \
               lm_sensors polkit python-psutil python-cairo
```

---

## Running ThinkNux

### Direct Launch
```bash
# Run via launcher script
./bin/thinknux

# Or run directly via Python
python3 -m thinknux.main
```

### Run Minimized to System Tray
```bash
./bin/thinknux --minimized
```

---

## Running Tests

Execute the comprehensive automated test suite:
```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

---

## Project Info & Credits

- **Application ID**: `com.byrizki.thinknux`
- **Creator**: Muhamad Rizki
- **Inspiration**: Inspired by [ThinkUtils](https://github.com/vietanhdev/thinkutils) by vietanhdev.

---

## License

LGPL-3.0 License.
