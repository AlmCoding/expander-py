import interface_expander.tiny_frame as tf
import interface_expander.InterfaceExpander as intexp
import time


ECHO_INSTANCE = None


class EchoCom:
    def __init__(self):
        self.received_data = None

        global ECHO_INSTANCE
        ECHO_INSTANCE = self

    def send(self, data: bytes) -> None:
        """Send an echo message to the USB interface."""
        self.received_data = None
        tf.TF_INSTANCE.send(tf.TfMsgType.TYPE_ECHO.value, data, 0)

    def read_echo(self, timeout: int):
        """Wait for an echo message from the USB interface."""
        start_time = time.time()
        while not self.received_data:
            intexp.EXPANDER_INSTANCE.read_all()
            if time.time() - start_time > timeout / 1000:
                return None
        return self.received_data


def receive_echo_msg_cb(_, tf_msg: tf.TF.TF_Msg) -> None:
    """Receive an echo message from the USB interface."""
    global ECHO_INSTANCE
    if ECHO_INSTANCE:
        ECHO_INSTANCE.received_data = tf_msg.data


tf.tf_register_callback(tf.TfMsgType.TYPE_ECHO, receive_echo_msg_cb)
