"""Unit tests for ThinkLMI firmware attributes and data models."""

import unittest

from thinknux.models.firmware import FirmwareAttribute, ThinkLmiStatus


class TestFirmware(unittest.TestCase):
    def test_firmware_attribute_model(self):
        attr = FirmwareAttribute(
            name="FnCtrlKeySwap",
            display_name="Fn and Ctrl Key Swap",
            current_value="Disable",
            possible_values=["Disable", "Enable"],
            attr_type="enumeration",
        )
        d = attr.to_dict()
        self.assertEqual(d["name"], "FnCtrlKeySwap")
        self.assertEqual(d["current_value"], "Disable")
        self.assertIn("Enable", d["possible_values"])

    def test_thinklmi_status_model(self):
        attr1 = FirmwareAttribute(
            name="FnKeyAsPrimary",
            display_name="Fn Key as Primary",
            current_value="Enable",
            possible_values=["Disable", "Enable"],
        )
        st = ThinkLmiStatus(
            supported=True,
            attributes={"FnKeyAsPrimary": attr1},
            has_admin_password=False,
        )
        d = st.to_dict()
        self.assertTrue(d["supported"])
        self.assertFalse(d["has_admin_password"])
        self.assertIn("FnKeyAsPrimary", d["attributes"])


if __name__ == "__main__":
    unittest.main()
