from proto.proto_py import ctrl_pb2
import msg.tiny_frame as tf


class CtrlInterface:
    SequenceNumber = 0
    Synchronized = True

    @staticmethod
    def send_system_reset_msg() -> None:
        CtrlInterface.SequenceNumber += 1
        CtrlInterface.Synchronized = False

        msg = ctrl_pb2.CtrlMsg()
        msg.sequence_number = CtrlInterface.SequenceNumber
        msg.system_reset = True

        msg_bytes = msg.SerializeToString()
        tf.TF_INSTANCE.send(tf.TfMsgType.TYPE_CTRL.value, msg_bytes, 0)

    @staticmethod
    def receive_msg_cb(msg: ctrl_pb2.CtrlMsg):
        if msg.sequence_number < CtrlInterface.SequenceNumber:
            print("Rejected CTRL msg! ==========================#")
            return


def receive_ctrl_msg_cb(_, tf_msg: tf.TF.TF_Msg) -> None:
    msg = ctrl_pb2.GpioMsg()
    msg.ParseFromString(bytes(tf_msg.data))
    CtrlInterface.receive_msg_cb(msg)


tf.tf_register_callback(tf.TfMsgType.TYPE_CTRL, receive_ctrl_msg_cb)
