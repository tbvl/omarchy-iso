"""Unit tests for the orchestrator's configure_network phase.

Same harness as the Tailscale tests: the phase touches the target only
through the filesystem, so it runs against a temp directory, with
subprocess.run recorded to prove it never needs the chroot.
"""

import stat
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "configs/airootfs/usr/share/omarchy-iso"))

# phases_impl imports the archinstall adapter at module scope, which pulls in
# the archinstall library that only exists on the live ISO. configure_network
# never touches it, so stub the adapter out before the import.
sys.modules["orchestrator.archinstall_adapter"] = types.ModuleType("orchestrator.archinstall_adapter")

from orchestrator import phases_impl  # noqa: E402

WIFI = """\
[connection]
id=Home
type=wifi
autoconnect=true

[wifi]
mode=infrastructure
ssid=Home

[wifi-security]
key-mgmt=wpa-psk
psk=100%:secret;#1

[ipv4]
method=auto

[ipv6]
method=auto
"""


class ConfigureNetworkTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "mnt"
        self.target.mkdir()
        self.calls = []

        info_patch = mock.patch.object(phases_impl, "info")
        info_patch.start()
        self.addCleanup(info_patch.stop)

        run_patch = mock.patch.object(phases_impl.subprocess, "run", side_effect=self.calls.append)
        run_patch.start()
        self.addCleanup(run_patch.stop)

    def ctx(self, keyfile=None, networkmanager_installed=True):
        keyfile_path = None
        if keyfile is not None:
            keyfile_path = Path(self.tmp.name) / "network.nmconnection"
            keyfile_path.write_text(keyfile)
        if networkmanager_installed:
            unit = self.target / "usr" / "lib" / "systemd" / "system" / "NetworkManager.service"
            unit.parent.mkdir(parents=True, exist_ok=True)
            unit.touch()
        return types.SimpleNamespace(target=self.target, network_connection_path=keyfile_path)

    def configure(self, **kwargs):
        phases_impl.configure_network(self.ctx(**kwargs))

    def installed(self):
        return self.target / "etc" / "NetworkManager" / "system-connections" / "omarchy-autoinstall.nmconnection"

    def test_no_keyfile_is_a_no_op(self):
        self.configure()
        self.assertFalse((self.target / "etc").exists())
        self.assertEqual(self.calls, [])

    def test_installs_the_keyfile_byte_for_byte(self):
        self.configure(keyfile=WIFI)
        # '%', ':', ';' and '#' inside a value are the passphrase, not syntax.
        self.assertEqual(self.installed().read_text(), WIFI)

    def test_keyfile_and_directory_are_root_private(self):
        self.configure(keyfile=WIFI)
        self.assertEqual(stat.S_IMODE(self.installed().stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.installed().parent.stat().st_mode), 0o700)

    def test_needs_no_chroot(self):
        self.configure(keyfile=WIFI)
        self.assertEqual(self.calls, [])

    def test_ethernet_keyfile_needs_no_wifi_section(self):
        ethernet = "[connection]\nid=Wired\ntype=ethernet\n\n[ipv4]\nmethod=auto\n"
        self.configure(keyfile=ethernet)
        self.assertEqual(self.installed().read_text(), ethernet)

    def test_long_section_name_counts_as_wifi(self):
        keyfile = "[connection]\ntype=802-11-wireless\n\n[802-11-wireless]\nssid=Home\n"
        self.configure(keyfile=keyfile)
        self.assertEqual(self.installed().read_text(), keyfile)

    def test_fails_without_a_connection_section(self):
        with self.assertRaisesRegex(RuntimeError, r"no \[connection\] section"):
            self.configure(keyfile="[wifi]\nssid=Home\n")

    def test_fails_without_a_type(self):
        with self.assertRaisesRegex(RuntimeError, "no type"):
            self.configure(keyfile="[connection]\nid=Home\n")

    def test_fails_on_wifi_without_ssid(self):
        with self.assertRaisesRegex(RuntimeError, "without an ssid"):
            self.configure(keyfile="[connection]\ntype=wifi\n\n[wifi-security]\npsk=secret123\n")

    def test_fails_on_text_that_is_not_a_keyfile(self):
        with self.assertRaisesRegex(RuntimeError, "not a NetworkManager keyfile"):
            self.configure(keyfile="ssid=Home\npsk=secret123\n")

    def test_fails_when_networkmanager_is_not_on_the_target(self):
        with self.assertRaisesRegex(RuntimeError, "NetworkManager is not installed"):
            self.configure(keyfile=WIFI, networkmanager_installed=False)
        self.assertFalse(self.installed().exists())

    def test_keyfile_is_scrubbed_from_the_factory_snapshot(self):
        self.assertIn(
            "etc/NetworkManager/system-connections/omarchy-autoinstall.nmconnection",
            phases_impl.FACTORY_SCRUB_PATHS,
        )


if __name__ == "__main__":
    unittest.main()
