"""MQTT client service — subscribes to ESP32 sensor data, publishes commands.

A-07 FIX: Uses a thread-safe queue bridge to dispatch MQTT messages
from paho's thread to the FastAPI asyncio event loop, preventing
RuntimeError: 'no running event loop' crashes.
"""
import json
import logging
import queue
import threading
import time
import paho.mqtt.client as mqtt
from typing import Optional, Callable

logger = logging.getLogger("agrimaster.mqtt")

# Thread-safe message queue — paho thread writes, asyncio task reads
_msg_queue: queue.Queue = queue.Queue()


class MqttService:
    def __init__(self, config: dict):
        self.broker = config.get("broker", "localhost")
        self.port = config.get("port", 1883)
        self.keepalive = config.get("keepalive", 60)
        self.topics = config.get("topics", {})
        self.client_id = config.get("client_id", "agrimaster_backend")
        self.client: Optional[mqtt.Client] = None
        self._on_sensor_data: Optional[Callable] = None
        self._connected = False
        self._thread: Optional[threading.Thread] = None
        self._latest_state: dict = {}

    def set_sensor_callback(self, callback: Callable):
        self._on_sensor_data = callback

    def connect(self):
        try:
            self.client = mqtt.Client(client_id=self.client_id)
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            self.client.connect(self.broker, self.port, self.keepalive)
            self._thread = threading.Thread(target=self.client.loop_forever, daemon=True)
            self._thread.start()
            logger.info(f"MQTT connecting to {self.broker}:{self.port}")
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}")

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            sensor_topic = self.topics.get("sensors", "agrimaster/sensors")
            status_topic = self.topics.get("status", "agrimaster/status")
            # C-09: QoS 0 for sensor data (high frequency, loss acceptable)
            client.subscribe(sensor_topic, qos=0)
            client.subscribe(status_topic, qos=0)
            # QoS 1 for command topic (must not be lost)
            cmd_topic = self.topics.get("commands", "agrimaster/commands")
            client.subscribe(cmd_topic, qos=1)
            logger.info(f"MQTT connected, subscribed to {sensor_topic}")
        else:
            logger.error(f"MQTT connect failed with rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        logger.warning(f"MQTT disconnected (rc={rc}), will auto-reconnect")

    def _on_message(self, client, userdata, msg):
        """A-07 FIX: Only put to queue, never call async functions directly."""
        try:
            payload = json.loads(msg.payload.decode())
            topic = msg.topic
            sensor_topic = self.topics.get("sensors", "agrimaster/sensors")

            # Always enqueue for async dispatch
            _msg_queue.put_nowait({
                "topic": topic,
                "payload": payload,
                "timestamp": time.time()
            })

            # Also update latest state cache (thread-safe dict assignment)
            if topic == sensor_topic:
                self._latest_state = payload
                # Direct callback for non-async processing
                if self._on_sensor_data:
                    self._on_sensor_data(payload)

        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON on {msg.topic}: {e}")
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    def publish_command(self, target: str, action: str = "SET_RELAY",
                        value=True, duration: int = 0):
        if not self._connected or not self.client:
            logger.warning("MQTT not connected, cannot publish command")
            return False
        cmd_topic = self.topics.get("commands", "agrimaster/commands")
        payload = json.dumps({
            "action": action, "target": target,
            "value": value, "duration_sec": duration,
            "timestamp": int(time.time() * 1000)
        })
        # C-09: QoS 1 for actuator commands (must not be lost)
        result = self.client.publish(cmd_topic, payload, qos=1)
        if result.rc == 0:
            logger.info(f"Published command: {target} → {action}({value})")
            return True
        logger.error(f"MQTT publish failed for {target}, rc={result.rc}")
        return False

    def get_latest_state(self) -> dict:
        return self._latest_state

    def is_connected(self) -> bool:
        return self._connected

    def disconnect(self):
        if self.client:
            self.client.disconnect()
            self._connected = False


def get_mqtt_client():
    """Module-level accessor for the global MQTT client."""
    return None  # Set by MqttService — use MqttService.client instead


def get_message_queue() -> queue.Queue:
    """Return the thread-safe message queue for async dispatch."""
    return _msg_queue
