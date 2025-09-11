import time
import interface_expander.tiny_frame as tf
import interface_expander.InterfaceExpander as intexp
from interface_expander.Singleton import Singleton


class EchoCom(metaclass=Singleton):
    def __init__(self):
        self.expander = intexp.InterfaceExpander()
        self.received_data = None

    def send(self, data: bytes) -> None:
        """Send an echo message to the USB interface."""
        self.received_data = None
        tf.TF_INSTANCE.send(tf.TfMsgType.TYPE_ECHO.value, data, 0)

    def read_echo(self, timeout: float):
        """Wait for an echo message from the USB interface."""
        start_time = time.monotonic()
        while True:
            self.expander._read_all()
            if self.received_data:
                break
            elif time.monotonic() - start_time > timeout:
                raise TimeoutError("Timeout waiting for echo message!")

        return self.received_data

    def _receive_msg_cb(self, msg: bytes):
        """Receive an echo message from the USB interface."""
        self.received_data = msg


def _receive_echo_msg_cb(_, tf_msg: tf.TF.TF_Msg) -> None:
    """Receive an echo message from the USB interface."""
    msg = tf_msg.data
    EchoCom()._receive_msg_cb(msg)


tf.tf_register_callback(tf.TfMsgType.TYPE_ECHO, _receive_echo_msg_cb)
