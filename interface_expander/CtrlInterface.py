from libraries.proto.proto_py import ctrl_pb2
import interface_expander.tiny_frame as tf


class CtrlInterface:
    SequenceNumber = 0
    # Synchronized = True

    @staticmethod
    def send_system_reset() -> None:
        CtrlInterface.SequenceNumber += 1
        # CtrlInterface.Synchronized = False

        msg = ctrl_pb2.CtrlMsg()
        msg.sequence_number = CtrlInterface.SequenceNumber
        msg.ctrl_request.reset_system = True

        msg_bytes = msg.SerializeToString()
        tf.TF_INSTANCE.send(tf.TfMsgType.TYPE_CTRL.value, msg_bytes, 0)

    @staticmethod
    def receive_msg_cb(msg: ctrl_pb2.CtrlMsg):
        if msg.sequence_number < CtrlInterface.SequenceNumber:
            print("Rejected CTRL msg!")
            return


def receive_ctrl_msg_cb(_, tf_msg: tf.TF.TF_Msg) -> None:
    pass


tf.tf_register_callback(tf.TfMsgType.TYPE_CTRL, receive_ctrl_msg_cb)
