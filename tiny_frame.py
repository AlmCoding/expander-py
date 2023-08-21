import tf.TinyFrame as TF
from enum import Enum


class TfMsgType(Enum):
    TYPE_CTRL = 0x00
    TYPE_UART = 0x01
    TYPE_I2C = 0x02
    TYPE_SPI = 0x03
    TYPE_CAN = 0x04
    TYPE_GPIO = 0x05
    TYPE_PWM = 0x06
    TYPE_ADC = 0x07


TF_INSTANCE = TF.TinyFrame()


def tf_init(write_callback) -> TF.TinyFrame:
    global TF_INSTANCE
    tf = TF_INSTANCE

    tf.SOF_BYTE = 0x01
    tf.ID_BYTES = 1
    tf.LEN_BYTES = 1
    tf.TYPE_BYTES = 1
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
