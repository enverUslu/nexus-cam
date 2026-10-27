import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

import samsung_wifi_client as camera_client
import samsung_wifi_web as web


class CameraResolutionTests(unittest.TestCase):
    def setUp(self):
        self.ip = "192.0.2.35"
        self.device = camera_client.Device(
            ip=self.ip,
            location=f"http://{self.ip}:49154/camera/description.xml",
        )
        self.camera = camera_client.Camera(
            device=self.device,
            friendly_name="Test camera",
            manufacturer="Samsung",
            model_name="",
            model_number="",
            content_directory_url=f"http://{self.ip}:49154/camera/content",
        )
        discovery_patch = patch.object(camera_client, "discover", return_value=[])
        self.discover = discovery_patch.start()
        self.addCleanup(discovery_patch.stop)
        ip_patch = patch.object(camera_client, "camera_from_ip", return_value=None)
        self.by_ip = ip_patch.start()
        self.addCleanup(ip_patch.stop)

    def test_uses_advertised_control_url_outside_known_paths(self):
        description = ET.fromstring("""
            <root xmlns="urn:schemas-upnp-org:device-1-0">
              <device>
                <friendlyName>Test camera</friendlyName>
                <manufacturer>Samsung</manufacturer>
                <serviceList>
                  <service>
                    <serviceType>urn:schemas-upnp-org:service:ContentDirectory:1</serviceType>
                    <controlURL>/camera/content</controlURL>
                  </service>
                </serviceList>
              </device>
            </root>
        """)
        self.discover.return_value = [self.device]
        with patch.object(camera_client, "fetch_xml", return_value=description):
            resolved = web.resolve_camera(self.ip)

        self.assertEqual(resolved.content_directory_url, self.camera.content_directory_url)
        self.by_ip.assert_not_called()

    def test_ignores_devices_with_a_different_ip(self):
        self.discover.return_value = [
            camera_client.Device(ip="192.0.2.99", location="http://192.0.2.99/device.xml")
        ]
        self.by_ip.return_value = self.camera
        with patch.object(camera_client, "camera_from_description") as from_description:
            self.assertEqual(web.resolve_camera(self.ip), self.camera)
        from_description.assert_not_called()
        self.by_ip.assert_called_once_with(self.ip)

    def test_falls_back_when_discovery_is_empty(self):
        self.by_ip.return_value = self.camera
        self.assertEqual(web.resolve_camera(self.ip), self.camera)
        self.by_ip.assert_called_once_with(self.ip)

    def test_falls_back_when_description_is_unusable(self):
        self.discover.return_value = [self.device]
        self.by_ip.return_value = self.camera
        with patch.object(camera_client, "camera_from_description", return_value=None):
            self.assertEqual(web.resolve_camera(self.ip), self.camera)
        self.by_ip.assert_called_once_with(self.ip)

    def test_tries_other_descriptions_for_the_selected_ip(self):
        self.discover.return_value = [
            camera_client.Device(ip=self.ip, location=f"http://{self.ip}/unusable.xml"),
            self.device,
        ]
        with patch.object(
            camera_client, "camera_from_description", side_effect=[None, self.camera]
        ):
            self.assertEqual(web.resolve_camera(self.ip), self.camera)
        self.by_ip.assert_not_called()

    def test_preserves_missing_camera_error(self):
        with self.assertRaises(RuntimeError) as error:
            web.resolve_camera(self.ip)
        self.assertEqual(str(error.exception), f"No Samsung camera service found at {self.ip}")


if __name__ == "__main__":
    unittest.main()
