import interface_expander.tiny_frame as tf
from interface_expander.proto.proto_py import ctrl_pb2
from interface_expander.Singleton import Singleton


class CtrlInterface(metaclass=Singleton):
    def __init__(self):
        self.sequence_number = 0  # Proto message synchronization

    def _send_system_reset(self) -> None:
        """Send a system reset message to the USB interface."""
        self.sequence_number += 1

        msg = ctrl_pb2.CtrlMsg()
        msg.sequence_number = self.sequence_number
        msg.ctrl_request.reset_system = True

        msg_bytes = msg.SerializeToString()
        tf.TF_INSTANCE.send(tf.TfMsgType.TYPE_CTRL.value, msg_bytes, 0)

    def _receive_msg_cb(self, msg: ctrl_pb2.CtrlMsg):
        """Receive a CTRL message from the USB interface."""
        if msg.sequence_number < self.sequence_number:
            return


def _receive_ctrl_msg_cb(_, tf_msg: tf.TF.TF_Msg) -> None:
    """Receive a CTRL message from the USB interface."""
    msg = ctrl_pb2.CtrlMsg()
    msg.ParseFromString(tf_msg.data)
    CtrlInterface()._receive_msg_cb(msg)


tf.tf_register_callback(tf.TfMsgType.TYPE_CTRL, _receive_ctrl_msg_cb)
