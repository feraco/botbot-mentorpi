#!/usr/bin/env python3
"""
bot_camera.camera_node
Reads frames from a V4L2/UVC camera using OpenCV and publishes them as
sensor_msgs/Image on a configurable topic, and also as
sensor_msgs/CompressedImage (JPEG) on compressed_camera for the web UI.

Parameters (all declared, all have defaults):
  device_id          (int)    : V4L2 device index, e.g. 0 for /dev/video0
  topic_name         (string) : raw image output topic
  compressed_topic   (string) : compressed image output topic (for cockpit UI)
  width              (int)    : capture width  (0 = don't set, use camera default)
  height             (int)    : capture height (0 = don't set)
  fps                (int)    : capture framerate (0 = don't set)
  frame_id           (string) : frame_id in the Header
  jpeg_quality       (int)    : JPEG compression quality 1-100 (default 80)
"""
import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CompressedImage
from cv_bridge import CvBridge


class CameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')

        self.declare_parameter('device_id',        0)
        self.declare_parameter('topic_name',       'front_camera/color/image_raw')
        self.declare_parameter('compressed_topic', 'compressed_camera')
        self.declare_parameter('width',            640)
        self.declare_parameter('height',           480)
        self.declare_parameter('fps',              30)
        self.declare_parameter('frame_id',         'front_camera_link')
        self.declare_parameter('jpeg_quality',     80)

        device_id         = self.get_parameter('device_id').value
        topic_name        = self.get_parameter('topic_name').value
        compressed_topic  = self.get_parameter('compressed_topic').value
        width             = self.get_parameter('width').value
        height            = self.get_parameter('height').value
        fps               = self.get_parameter('fps').value
        self.frame_id     = self.get_parameter('frame_id').value
        self._jpeg_quality = self.get_parameter('jpeg_quality').value

        self._bridge        = CvBridge()
        self._pub           = self.create_publisher(Image, topic_name, 10)
        self._pub_compressed = self.create_publisher(
            CompressedImage, compressed_topic, 10
        )

        self._cap = cv2.VideoCapture(device_id)
        if not self._cap.isOpened():
            self.get_logger().error(f'Failed to open camera at index {device_id}')
            raise RuntimeError(f'Cannot open /dev/video{device_id}')

        if width  > 0: self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  width)
        if height > 0: self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        if fps    > 0: self._cap.set(cv2.CAP_PROP_FPS,          fps)

        actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_f = self._cap.get(cv2.CAP_PROP_FPS)
        self.get_logger().info(
            f'Camera opened: /dev/video{device_id} '
            f'{actual_w}x{actual_h} @ {actual_f:.1f} fps → "{topic_name}"'
        )

        period = 1.0 / (fps if fps > 0 else 30)
        self._timer = self.create_timer(period, self._capture)

    def _capture(self):
        ret, frame = self._cap.read()
        if not ret:
            self.get_logger().warn('Camera read failed', throttle_duration_sec=5.0)
            return

        now = self.get_clock().now().to_msg()

        # Publish raw image
        msg = self._bridge.cv2_to_imgmsg(frame, encoding='bgr8')
        msg.header.stamp    = now
        msg.header.frame_id = self.frame_id
        self._pub.publish(msg)

        # Publish compressed JPEG for cockpit web UI (/compressed_camera)
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality]
        ret2, buf = cv2.imencode('.jpg', frame, encode_params)
        if ret2:
            compressed = CompressedImage()
            compressed.header.stamp    = now
            compressed.header.frame_id = self.frame_id
            compressed.format          = 'jpeg'
            compressed.data            = buf.tobytes()
            self._pub_compressed.publish(compressed)

    def destroy_node(self):
        self._cap.release()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = CameraNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
