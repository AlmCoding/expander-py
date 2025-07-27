from __future__ import annotations
from interface_expander.proto.proto_py import dac_pb2
from enum import Enum
from typing import Callable
import interface_expander.tiny_frame as tf
import interface_expander.InterfaceExpander as intexp
import time, math

DAC_MAX_QUEUE_SPACE = 4
DAC_MAX_SAMPLE_BUFFER_SPACE = 1024
DAC_MAX_DATA_SAMPLES = 128 // 2  # 128 bytes, 2 bytes per sample (16-bit DAC)
DAC_MIN_SAMPLE_VALUE = 0
DAC_MAX_SAMPLE_VALUE = pow(2, 16) - 1  # 16-bit DAC
DAC_MIN_SAMPLING_RATE = 1  # Minimum sampling rate in Hz
DAC_MAX_SAMPLING_RATE = 500000  # Maximum sampling rate in Hz (500 kHz)


DAC_INSTANCE: DigitalToAnalog | None = None


class DacMode(Enum):
    STATIC_MODE = 0
    PERIODIC_MODE = 1
    STREAMING_MODE = 2


class DacConfigStatusCode(Enum):
    NOT_INIT = 0
    SUCCESS = 1
    BAD_REQUEST = 2
    INVALID_MODE = 4
    INVALID_SAMPLING_RATE = 5
    INVALID_PERIODIC_SAMPLES = 6
    PENDING = 7  # Not part of proto enum


class DacDataStatusCode(Enum):
    NOT_INIT = 0
    SUCCESS = 1
    BAD_REQUEST = 2
    BUFFER_OVERFLOW = 3
    PENDING = 4  # Not part of proto enum


class DacConfig:
    def __init__(self, mode: DacMode, sampling_rate: int, sample_count: int):
        self.status_code = DacConfigStatusCode.NOT_INIT
        self.request_id = None  # This will be set when the request is sent
        self.mode = mode
        self.sampling_rate = sampling_rate
        self.sample_count = sample_count  # For periodic mode, number of samples


class DacDataRequest:
    def __init__(self, run: bool, sequence_ch1: iter, sequence_ch2: iter):
        self.status_code = DacDataStatusCode.NOT_INIT
        self.request_id = None
        self.run = run
        self.sequence_ch1 = sequence_ch1
        self.sequence_ch2 = sequence_ch1


class DigitalToAnalog:
    def __init__(self):
        self.config = None

        self.sequence_number = 0  # Proto message synchronization
        self.request_id_counter = 0

        self.data_requests = {}

        self.queue_space = DAC_MAX_QUEUE_SPACE
        self.buffer_space_ch1 = DAC_MAX_SAMPLE_BUFFER_SPACE
        self.buffer_space_ch2 = DAC_MAX_SAMPLE_BUFFER_SPACE

        global DAC_INSTANCE
        DAC_INSTANCE = self

        config = DacConfig(DacMode.STATIC_MODE, DAC_MIN_SAMPLING_RATE, 0)
        if self._apply_config(config) != DacConfigStatusCode.SUCCESS:
            raise RuntimeError("Failed to apply DAC configuration")

    def _apply_config(self, config: DacConfig, timeout: float = 1.0) -> DacConfigStatusCode:
        if config.mode not in DacMode:
            raise ValueError("Invalid DAC mode: %s" % config.mode)
        if not (DAC_MIN_SAMPLING_RATE <= config.sampling_rate <= DAC_MAX_SAMPLING_RATE):
            raise ValueError("Sampling rate out of range (%d to %d)" % (DAC_MIN_SAMPLING_RATE, DAC_MAX_SAMPLING_RATE))

        self.data_requests = {}
        self.buffer_space_ch1 = DAC_MAX_SAMPLE_BUFFER_SPACE
        self.buffer_space_ch2 = DAC_MAX_SAMPLE_BUFFER_SPACE

        self.sequence_number += 1
        self.request_id_counter += 1

        config.status_code = DacConfigStatusCode.PENDING
        config.request_id = self.request_id_counter
        self.config = config

        msg = dac_pb2.DacMsg()
        msg.sequence_number = self.sequence_number
        msg.config_request.request_id = config.request_id
        if config.mode == DacMode.STATIC_MODE:
            msg.config_request.mode = dac_pb2.DacMode.DAC_MODE_STATIC#
        elif config.mode == DacMode.PERIODIC_MODE:
            msg.config_request.mode = dac_pb2.DacMode.DAC_MODE_PERIODIC
        else:
            msg.config_request.mode = dac_pb2.DacMode.DAC_MODE_STREAMING
        msg.config_request.sampling_rate = config.sampling_rate
        msg.config_request.periodic_samples = config.sample_count

        msg_bytes = msg.SerializeToString()
        tf.TF_INSTANCE.send(tf.TfMsgType.TYPE_DAC.value, msg_bytes, 0)

        # Wait for response with timeout
        self.wait_for_response(config.request_id, timeout)
        return config.status_code

    def _verify_parameters(self, mode, sequence_ch1, sequence_ch2, sampling_rate) -> None:
        if not (DAC_MIN_SAMPLE_VALUE <= min(sequence_ch1) <= max(sequence_ch1) <= DAC_MAX_SAMPLE_VALUE):
            raise ValueError(
                "Channel 1 sequence values out of range (%d to %d)" % (DAC_MIN_SAMPLE_VALUE, DAC_MAX_SAMPLE_VALUE))
        if not (DAC_MIN_SAMPLE_VALUE <= min(sequence_ch2) <= max(sequence_ch2) <= DAC_MAX_SAMPLE_VALUE):
            raise ValueError(
                "Channel 2 sequence values out of range (%d to %d)" % (DAC_MIN_SAMPLE_VALUE, DAC_MAX_SAMPLE_VALUE))

        if not (DAC_MIN_SAMPLING_RATE <= sampling_rate <= DAC_MAX_SAMPLING_RATE):
            raise ValueError("Sampling rate out of range (%d to %d)" % (DAC_MIN_SAMPLING_RATE, DAC_MAX_SAMPLING_RATE))

        if len(sequence_ch1) != len(sequence_ch2):
            raise ValueError("Channel sequences must have the same length!")

        if mode == DacMode.STATIC_MODE:
            if len(sequence_ch1) != 1 or len(sequence_ch2) != 1:
                raise ValueError("Static mode requires single value for each channel!")
        elif mode == DacMode.PERIODIC_MODE:
            if len(sequence_ch1) > DAC_MAX_SAMPLE_BUFFER_SPACE or len(sequence_ch2) > DAC_MAX_SAMPLE_BUFFER_SPACE:
                raise ValueError("Sequence length exceeds buffer space (max %d samples)" % DAC_MAX_SAMPLE_BUFFER_SPACE)

    def _can_accept_request(self, request) -> bool:
        accept = False

        if isinstance(request, DacDataRequest):
            if self.queue_space > 0 and \
                    (self.buffer_space_ch1 >= len(request.sequence_ch1) and
                     self.buffer_space_ch2 >= len(request.sequence_ch2)):
                accept = True
        elif isinstance(request, DacConfig):
            accept = True

        if accept:
            print("Accept request ok (queue_space: %d, buffer_space_ch1: %d, buffer_space_ch2: %d)" %
                  (self.queue_space, self.buffer_space_ch1, self.buffer_space_ch2))

        return accept

    def output_value(self, value_ch1, value_ch2) -> DacDataStatusCode:
        intexp.InterfaceExpander()._read_all()
        self._verify_parameters(DacMode.STATIC_MODE, [value_ch1], [value_ch2], DAC_MIN_SAMPLING_RATE)

        if self.config.mode != DacMode.STATIC_MODE:
            config = DacConfig(DacMode.STATIC_MODE, DAC_MIN_SAMPLING_RATE, 0)
            if self._apply_config(config) != DacConfigStatusCode.SUCCESS:
                raise RuntimeError("Failed to apply DAC configuration!")

        request = DacDataRequest(True, [value_ch1], [value_ch2])
        rid = self._send_data_request(request)

        # Wait for response with timeout
        self.wait_for_response(rid, 0.1)
        return request.status_code

    def loop_sequence(self, sequence_ch1, sequence_ch2, sampling_rate) -> DacDataStatusCode:
        intexp.InterfaceExpander()._read_all()
        self._verify_parameters(DacMode.PERIODIC_MODE, sequence_ch1, sequence_ch2, sampling_rate)

        if self.config.mode != DacMode.PERIODIC_MODE or \
                self.config.sampling_rate != sampling_rate or \
                self.config.sample_count != len(sequence_ch1):
            config = DacConfig(DacMode.PERIODIC_MODE, sampling_rate, len(sequence_ch1))
            if self._apply_config(config) != DacConfigStatusCode.SUCCESS:
                raise RuntimeError("Failed to apply DAC configuration!")

        request_count = math.ceil(len(sequence_ch1) / DAC_MAX_DATA_SAMPLES)
        pending_rids = []
        for i in range(request_count):
            offset = i * DAC_MAX_DATA_SAMPLES
            length = min(DAC_MAX_DATA_SAMPLES, len(sequence_ch1) - offset)
            current_sequence_ch1 = sequence_ch1[offset:offset + length]
            current_sequence_ch2 = sequence_ch2[offset:offset + length]
            run = (i == request_count - 1) # Last request should run the sequence

            request = DacDataRequest(run, current_sequence_ch1, current_sequence_ch2)
            rid = self._send_data_request(request)
            pending_rids.append(rid)

        # Wait for all requests to complete
        for rid in pending_rids:
            request = self.wait_for_response(rid, 0.1)
            if request.status_code != DacDataStatusCode.SUCCESS:
                raise RuntimeError("Failed to set loop sequence (id: %d, status: %s)" % (rid, request.status_code.name))

        return DacDataStatusCode.SUCCESS

    def stream_sequence(self, sequence_ch1, sequence_ch2, sampling_rate) -> int:
        intexp.InterfaceExpander()._read_all()
        self._verify_parameters(DacMode.STREAMING_MODE, sequence_ch1, sequence_ch2, sampling_rate)

        if self.config.mode != DacMode.STREAMING_MODE or self.config.sampling_rate != sampling_rate:
            config = DacConfig(DacMode.STREAMING_MODE, sampling_rate)
            if self._apply_config(config) != DacConfigStatusCode.SUCCESS:
                raise RuntimeError("Failed to apply DAC configuration!")

        # TODO ...

    def _send_data_request(self, request: DacDataRequest) -> int:
        self.sequence_number += 1
        self.request_id_counter += 1

        request.status_code = DacDataStatusCode.PENDING
        request.request_id = self.request_id_counter

        self.data_requests[request.request_id] = request
        # ... update buffer space

        msg = dac_pb2.DacMsg()
        msg.sequence_number = self.sequence_number

        msg.data_request.request_id = request.request_id
        msg.data_request.run = request.run
        msg.data_request.data_ch1 = b''.join(x.to_bytes(2, 'little') for x in request.sequence_ch1)
        msg.data_request.data_ch2 = b''.join(x.to_bytes(2, 'little') for x in request.sequence_ch2)

        msg_bytes = msg.SerializeToString()
        tf.TF_INSTANCE.send(tf.TfMsgType.TYPE_DAC.value, msg_bytes, 0)
        return request.request_id

    def wait_for_response(self, request_id: int, timeout: float) -> DacDataRequest:
        if request_id in self.data_requests:
            container = self.data_requests
            request = container[request_id]
            pending_code = DacDataStatusCode.PENDING
        elif self.config.request_id == request_id:
            container = None
            request = self.config
            pending_code = DacConfigStatusCode.PENDING
        else:
            raise ValueError("Unknown request id (id: %d)" % request_id)

        start_time = time.time()
        while True:
            intexp.InterfaceExpander()._read_all()
            if request.status_code != pending_code:
                break
            elif time.time() - start_time > timeout:
                raise TimeoutError("Timeout waiting for response (id: %d)" % request_id)

        if container:
            del container[request_id]

        return request

    def _receive_msg_cb(self, msg: dac_pb2.DacMsg):
        inner_msg = msg.WhichOneof("msg")
        if inner_msg == "config_status":
            self._handle_config_status(msg)
        elif inner_msg == "data_status":
            self._handle_data_status(msg)
        else:
            raise ValueError("Invalid DAC message type!")

    def _handle_config_status(self, msg: dac_pb2.DacMsg):
        if msg.config_status.request_id == self.config.request_id:
            self.config.status_code = DacConfigStatusCode(msg.config_status.status_code)
        else:
            raise ValueError("Received config status for unknown request (id: %d)" % msg.config_status.request_id)

    def _handle_data_status(self, msg: dac_pb2.DacMsg):
        if msg.sequence_number >= self.sequence_number:
            self.queue_space = msg.data_status.queue_space
            self.buffer_space_ch1 = msg.data_status.buffer_space_ch1
            self.buffer_space_ch2 = msg.data_status.buffer_space_ch2
 
        request_id = msg.data_status.request_id
        if request_id not in self.data_requests:
            raise ValueError("Unknown data request status (id: %d) received!" % request_id)

        self.data_requests[request_id].status_code = DacDataStatusCode(msg.data_status.status_code)


def _receive_dac_msg_cb(_, tf_msg: tf.TF.TF_Msg) -> None:
    """Receive a DAC message from the USB interface."""
    msg = dac_pb2.DacMsg()
    msg.ParseFromString(tf_msg.data)

    global DAC_INSTANCE
    if DAC_INSTANCE is not None:
        DAC_INSTANCE._receive_msg_cb(msg)
    else:
        raise RuntimeError("DAC instance is not initialized!")


tf.tf_register_callback(tf.TfMsgType.TYPE_DAC, _receive_dac_msg_cb)
