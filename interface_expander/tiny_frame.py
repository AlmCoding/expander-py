import interface_expander.tf.TinyFrame as TF
from enum import Enum


class TfMsgType(Enum):
    TYPE_ECHO = 0x00
    TYPE_CTRL = 0x01
    TYPE_I2C = 0x02
    TYPE_SPI = 0x03
    TYPE_DAC = 0x04
    TYPE_GPIO = 0x05


TF_INSTANCE = TF.TinyFrame()
TF_FRAME_START = 0x01
TF_START_BYTES = 1  # 0x01 => 1 byte
TF_ID_BYTES = 1
TF_LEN_BYTES = 2
TF_TYPE_BYTES = 1
TF_CKSUM_BYTES = 1  # xor => 1 byte
TF_FRAME_OVERHEAD_SIZE = TF_START_BYTES + TF_ID_BYTES + TF_LEN_BYTES + TF_TYPE_BYTES + TF_CKSUM_BYTES + 1


def tf_init(write_callback) -> TF.TinyFrame:
    global TF_INSTANCE, TF_FRAME_START, TF_ID_BYTES, TF_LEN_BYTES
    tf = TF_INSTANCE

    tf.SOF_BYTE = TF_FRAME_START
    tf.ID_BYTES = TF_ID_BYTES
    tf.LEN_BYTES = TF_LEN_BYTES
    tf.TYPE_BYTES = TF_TYPE_BYTES
    tf.CKSUM_TYPE = 'xor'
    tf.write = write_callback
    tf.add_fallback_listener(tf_fallback_cb)
    return tf


def tf_register_callback(msg_type: TfMsgType, callback) -> None:
    global TF_INSTANCE
    TF_INSTANCE.add_type_listener(msg_type.value, callback)


def tf_send(msg_type: TfMsgType, msg) -> None:
    global TF_INSTANCE
    TF_INSTANCE.send(msg_type.value, msg)


def tf_fallback_cb(tf, msg):
    raise Exception("No TF type listener fond for this msg:\n" + str(msg.data))
