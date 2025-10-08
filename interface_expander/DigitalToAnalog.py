from __future__ import annotations
from interface_expander.proto.proto_py import dac_pb2
from enum import Enum
from typing import Callable, Iterable
from copy import copy
import interface_expander.tiny_frame as tf
import interface_expander.InterfaceExpander as intexp
import time, math


DAC_MAX_QUEUE_SPACE = 4
DAC_MAX_SAMPLE_BUFFER_SPACE = 1024
DAC_MAX_DATA_SAMPLES = 128 // 2  # 128 bytes, 2 bytes per sample (16-bit DAC)
DAC_MIN_SAMPLE_VALUE = 0
DAC_MAX_SAMPLE_VALUE = 0xFFFF  # 16-bit DAC
DAC_MIN_SAMPLING_RATE = 1  # Minimum sampling rate in Hz
DAC_MAX_SAMPLING_RATE = 500000  # Maximum sampling rate in Hz (500 kHz)
DAC_VREF = 2.5  # Reference voltage for DAC in Volts
DAC_STEP = DAC_VREF / DAC_MAX_SAMPLE_VALUE  # Step size for DAC output
DAC_GAIN_CH0 = 10.0  # Gain for DAC output
DAC_GAIN_CH1 = 10.0
DAC_OPAMP_OFFSET = DAC_VREF / 2.0  # Op-amp offset for DAC output
DAC_CORRECTION_CH0 = int(0.0023 * DAC_MAX_SAMPLE_VALUE / DAC_GAIN_CH0 / DAC_VREF)  # Channel 0 offset correction
DAC_CORRECTION_CH1 = int(0.0042 * DAC_MAX_SAMPLE_VALUE / DAC_GAIN_CH1 / DAC_VREF)  # Channel 1 offset correction

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
    def __init__(
        self,
        mode_ch0: DacMode,
        sampling_rate_ch0: int,
        sample_count_ch0: int,
        mode_ch1: DacMode,
        sampling_rate_ch1: int,
        sample_count_ch1: int,
    ):
        self.status_code = DacConfigStatusCode.NOT_INIT
        self.request_id = None  # This will be set when the request is sent

        self.mode_ch0 = mode_ch0
        self.sampling_rate_ch0 = sampling_rate_ch0
        self.sample_count_ch0 = sample_count_ch0  # For periodic mode, number of samples

        self.mode_ch1 = mode_ch1
        self.sampling_rate_ch1 = sampling_rate_ch1
        self.sample_count_ch1 = sample_count_ch1  # For periodic mode, number of samples


class DacDataRequest:
    def __init__(self, run_ch0: bool, sequence_ch0: list, run_ch1: bool, sequence_ch1: list):
        self.status_code = DacDataStatusCode.NOT_INIT
        self.request_id = None

        self.run_ch0 = run_ch0
        self.sequence_ch0 = sequence_ch0

        self.run_ch1 = run_ch1
        self.sequence_ch1 = sequence_ch1


class DigitalToAnalog:
    def __init__(self):
        self.expander = intexp.InterfaceExpander()
        self.config = None

        self.sequence_number = 0  # Proto message synchronization
        self.request_id_counter = 0

        self.data_requests = {}

        self.queue_space = DAC_MAX_QUEUE_SPACE
        self.buffer_space_ch0 = DAC_MAX_SAMPLE_BUFFER_SPACE
        self.buffer_space_ch1 = DAC_MAX_SAMPLE_BUFFER_SPACE

        self.buffer_underrun_ch0 = False
        self.buffer_underrun_ch1 = False

        global DAC_INSTANCE
        DAC_INSTANCE = self

        config = DacConfig(
            mode_ch0=DacMode.STATIC_MODE,
            sampling_rate_ch0=DAC_MIN_SAMPLING_RATE,
            sample_count_ch0=0,
            mode_ch1=DacMode.STATIC_MODE,
            sampling_rate_ch1=DAC_MIN_SAMPLING_RATE,
            sample_count_ch1=0,
        )
        if self._apply_config(config) != DacConfigStatusCode.SUCCESS:
            raise RuntimeError("Failed to apply DAC configuration")

    def _apply_config(
        self, config: DacConfig, force_config_ch0: bool = False, force_config_ch1: bool = False, timeout: float = 1.0
    ) -> DacConfigStatusCode:
        update_ch0_config = True
        update_ch1_config = True

        if (
            not force_config_ch0
            and self.config
            and self.config.mode_ch0 == config.mode_ch0
            and self.config.sampling_rate_ch0 == config.sampling_rate_ch0
            and self.config.sample_count_ch0 == config.sample_count_ch0
        ):
            update_ch0_config = False

        if (
            not force_config_ch1
            and self.config
            and self.config.mode_ch1 == config.mode_ch1
            and self.config.sampling_rate_ch1 == config.sampling_rate_ch1
            and self.config.sample_count_ch1 == config.sample_count_ch1
        ):
            update_ch1_config = False

        if not update_ch0_config and not update_ch1_config:
            return DacConfigStatusCode.SUCCESS

        self.data_requests = {}
        if update_ch0_config and update_ch1_config:
            self.queue_space = DAC_MAX_QUEUE_SPACE
        if update_ch0_config:
            self.buffer_space_ch0 = DAC_MAX_SAMPLE_BUFFER_SPACE
            self.buffer_underrun_ch0 = False
        if update_ch1_config:
            self.buffer_space_ch1 = DAC_MAX_SAMPLE_BUFFER_SPACE
            self.buffer_underrun_ch1 = False

        self.sequence_number += 1
        self.request_id_counter += 1

        config.status_code = DacConfigStatusCode.PENDING
        config.request_id = self.request_id_counter
        self.config = config

        def translate_mode(mode: DacMode) -> dac_pb2.DacMode:
            if mode == DacMode.STATIC_MODE:
                return dac_pb2.DacMode.DAC_MODE_STATIC
            elif mode == DacMode.PERIODIC_MODE:
                return dac_pb2.DacMode.DAC_MODE_PERIODIC
            elif mode == DacMode.STREAMING_MODE:
                return dac_pb2.DacMode.DAC_MODE_STREAMING
            else:
                raise ValueError("Invalid DAC mode: %s" % mode)

        msg = dac_pb2.DacMsg()
        msg.sequence_number = self.sequence_number

        msg.config_request.request_id = config.request_id
        msg.config_request.config_ch0 = update_ch0_config
        msg.config_request.config_ch1 = update_ch1_config
        msg.config_request.mode_ch0 = translate_mode(config.mode_ch0)
        msg.config_request.mode_ch1 = translate_mode(config.mode_ch1)
        msg.config_request.sampling_rate_ch0 = config.sampling_rate_ch0
        msg.config_request.sampling_rate_ch1 = config.sampling_rate_ch1
        msg.config_request.periodic_samples_ch0 = config.sample_count_ch0
        msg.config_request.periodic_samples_ch1 = config.sample_count_ch1

        msg_bytes = msg.SerializeToString()
        tf.TF_INSTANCE.send(tf.TfMsgType.TYPE_DAC.value, msg_bytes, 0)

        # Wait for response with timeout
        self._wait_for_response(config.request_id, timeout)
        return config.status_code

    def _can_accept_request(self, request: DacDataRequest | DacConfig) -> bool:
        accept = False

        if isinstance(request, DacDataRequest):
            if self.queue_space > 0 and (
                self.buffer_space_ch0 >= len(request.sequence_ch0)
                and self.buffer_space_ch1 >= len(request.sequence_ch1)
            ):
                accept = True
        elif isinstance(request, DacConfig):
            accept = True

        """
        if accept:
            print(
                "Accept request (queue_space: %d, buffer_space_ch0: %d, buffer_space_ch1: %d)"
                % (self.queue_space, self.buffer_space_ch0, self.buffer_space_ch1)
            )
        """

        return accept

    @staticmethod
    def _verify_parameters(mode: DacMode, sequence: list, sampling_rate: int | None) -> None:
        if mode not in DacMode:
            raise ValueError("Invalid DAC mode: %s" % mode)

        if not (DAC_MIN_SAMPLE_VALUE <= min(sequence) and max(sequence) <= DAC_MAX_SAMPLE_VALUE):
            raise ValueError(
                "Channel sequence values out of range (%d to %d)" % (DAC_MIN_SAMPLE_VALUE, DAC_MAX_SAMPLE_VALUE)
            )

        if mode == DacMode.STATIC_MODE:
            if len(sequence) != 1:
                raise ValueError("Static mode requires single value only!")
        elif mode == DacMode.PERIODIC_MODE:
            if len(sequence) > DAC_MAX_SAMPLE_BUFFER_SPACE:
                raise ValueError("Sequence length exceeds buffer space (max %d samples)" % DAC_MAX_SAMPLE_BUFFER_SPACE)

            # if sampling_rate is None:
            #    raise ValueError("Sampling rate must be provided for periodic mode!")

            if not (DAC_MIN_SAMPLING_RATE <= sampling_rate <= DAC_MAX_SAMPLING_RATE):
                raise ValueError(
                    "Sampling rate out of range (%d to %d)" % (DAC_MIN_SAMPLING_RATE, DAC_MAX_SAMPLING_RATE)
                )

    @staticmethod
    def _voltage_to_value(voltage_ch0: float | None, voltage_ch1: float | None) -> tuple[int | None, int | None]:
        # volt = ((value * DAC_STEP) - DAC_OPAMP_OFFSET) * DAC_GAIN
        # volt = ((value * DAC_VREF / DAC_MAX_SAMPLE_VALUE) - (DAC_VREF / 2)) * DAC_GAIN
        value_ch0 = None
        value_ch1 = None

        if voltage_ch0 is not None:
            # value = (voltage / DAC_GAIN + DAC_VREF / 2) * DAC_MAX_SAMPLE_VALUE / DAC_VREF + correction
            value_ch0 = int(
                (voltage_ch0 / DAC_GAIN_CH0 + DAC_OPAMP_OFFSET) * DAC_MAX_SAMPLE_VALUE / DAC_VREF - DAC_CORRECTION_CH0
            )
            if value_ch0 < DAC_MIN_SAMPLE_VALUE:
                value_ch0 = DAC_MIN_SAMPLE_VALUE
            if value_ch0 > DAC_MAX_SAMPLE_VALUE:
                value_ch0 = DAC_MAX_SAMPLE_VALUE

        if voltage_ch1 is not None:
            value_ch1 = int(
                (voltage_ch1 / DAC_GAIN_CH1 + DAC_OPAMP_OFFSET) * DAC_MAX_SAMPLE_VALUE / DAC_VREF - DAC_CORRECTION_CH1
            )
            if value_ch1 < DAC_MIN_SAMPLE_VALUE:
                value_ch1 = DAC_MIN_SAMPLE_VALUE
            if value_ch1 > DAC_MAX_SAMPLE_VALUE:
                value_ch1 = DAC_MAX_SAMPLE_VALUE

        return value_ch0, value_ch1

    def set_voltage(self, ch0: float | None = None, ch1: float | None = None) -> DacDataStatusCode:
        config = copy(self.config)
        value_ch0, value_ch1 = DigitalToAnalog._voltage_to_value(ch0, ch1)

        if value_ch0 is None and value_ch1 is None:
            raise ValueError("At least one channel value must be set!")

        sequence_ch0 = []
        if value_ch0 is not None:
            sequence_ch0 = [value_ch0]
            DigitalToAnalog._verify_parameters(DacMode.STATIC_MODE, sequence_ch0, sampling_rate=None)
            config.mode_ch0 = DacMode.STATIC_MODE
            config.sampling_rate_ch0 = DAC_MIN_SAMPLING_RATE
            config.sample_count_ch0 = 0

        sequence_ch1 = []
        if value_ch1 is not None:
            sequence_ch1 = [value_ch1]
            DigitalToAnalog._verify_parameters(DacMode.STATIC_MODE, sequence_ch1, sampling_rate=None)
            config.mode_ch1 = DacMode.STATIC_MODE
            config.sampling_rate_ch1 = DAC_MIN_SAMPLING_RATE
            config.sample_count_ch1 = 0

        if self._apply_config(config) != DacConfigStatusCode.SUCCESS:
            raise RuntimeError("Failed to apply DAC configuration!")

        request = DacDataRequest(value_ch0 is not None, sequence_ch0, value_ch1 is not None, sequence_ch1)
        rid = self._send_data_request(request)

        # Wait for response with timeout
        self._wait_for_response(rid, timeout=0.1)
        return request.status_code

    def loop_sequence(
        self,
        sequence_ch0: Iterable[float] | None,
        sampling_rate_ch0: int | None,
        sequence_ch1: Iterable[float] | None,
        sampling_rate_ch1: int | None,
    ) -> DacDataStatusCode:
        config = copy(self.config)
        sequence_ch0 = [DigitalToAnalog._voltage_to_value(v, None)[0] for v in sequence_ch0] if sequence_ch0 else None
        sequence_ch1 = [DigitalToAnalog._voltage_to_value(None, v)[1] for v in sequence_ch1] if sequence_ch1 else None

        if sequence_ch0 is None and sequence_ch1 is None:
            raise ValueError("At least one channel sequence must be set!")

        if sequence_ch0 is not None:
            DigitalToAnalog._verify_parameters(DacMode.PERIODIC_MODE, sequence_ch0, sampling_rate_ch0)
            config.mode_ch0 = DacMode.PERIODIC_MODE
            config.sampling_rate_ch0 = sampling_rate_ch0
            config.sample_count_ch0 = len(sequence_ch0)

        if sequence_ch1 is not None:
            DigitalToAnalog._verify_parameters(DacMode.PERIODIC_MODE, sequence_ch1, sampling_rate_ch1)
            config.mode_ch1 = DacMode.PERIODIC_MODE
            config.sampling_rate_ch1 = sampling_rate_ch1
            config.sample_count_ch1 = len(sequence_ch1)

        force_config_ch0 = sequence_ch0 is not None
        force_config_ch1 = sequence_ch1 is not None
        if self._apply_config(config, force_config_ch0, force_config_ch1) != DacConfigStatusCode.SUCCESS:
            raise RuntimeError("Failed to apply DAC configuration!")

        assert self.data_requests == {}
        assert self.queue_space == DAC_MAX_QUEUE_SPACE
        if sequence_ch0 is not None:
            assert self.buffer_space_ch0 == DAC_MAX_SAMPLE_BUFFER_SPACE
        if sequence_ch1 is not None:
            assert self.buffer_space_ch1 == DAC_MAX_SAMPLE_BUFFER_SPACE

        len_ch0 = len(sequence_ch0) if sequence_ch0 else 0
        len_ch1 = len(sequence_ch1) if sequence_ch1 else 0
        max_len = max(len_ch0, len_ch1)

        max_count = math.ceil(max_len / DAC_MAX_DATA_SAMPLES)
        for i in range(max_count):
            offset = i * DAC_MAX_DATA_SAMPLES
            current_sequence_ch0 = []
            if offset < len_ch0:
                length = min(DAC_MAX_DATA_SAMPLES, len(sequence_ch0) - offset)
                current_sequence_ch0 = sequence_ch0[offset : offset + length]

            current_sequence_ch1 = []
            if offset < len_ch1:
                length = min(DAC_MAX_DATA_SAMPLES, len(sequence_ch1) - offset)
                current_sequence_ch1 = sequence_ch1[offset : offset + length]

            run_ch0 = False
            run_ch1 = False
            if i == (max_count - 1):  # Last request should run the sequence(s)
                run_ch0 = sequence_ch0 is not None
                run_ch1 = sequence_ch1 is not None

            request = DacDataRequest(run_ch0, current_sequence_ch0, run_ch1, current_sequence_ch1)
            self._send_data_request(request)

        # Wait for all requests to complete
        self._wait_for_all_responses(timeout=0.1)
        assert self.data_requests == {}
        assert self.queue_space == DAC_MAX_QUEUE_SPACE
        if sequence_ch0 is not None:
            assert self.buffer_space_ch0 == DAC_MAX_SAMPLE_BUFFER_SPACE - len_ch0
        if sequence_ch1 is not None:
            assert self.buffer_space_ch1 == DAC_MAX_SAMPLE_BUFFER_SPACE - len_ch1
        return DacDataStatusCode.SUCCESS

    def stream_sequence(
        self,
        sequence_ch0: Iterable[float] | None,
        sampling_rate_ch0: int | None,
        sequence_ch1: Iterable[float] | None,
        sampling_rate_ch1: int | None,
    ) -> DacDataStatusCode:
        config = copy(self.config)
        sequence_ch0 = [DigitalToAnalog._voltage_to_value(v, None)[0] for v in sequence_ch0] if sequence_ch0 else None
        sequence_ch1 = [DigitalToAnalog._voltage_to_value(None, v)[1] for v in sequence_ch1] if sequence_ch1 else None

        if sequence_ch0 is None and sequence_ch1 is None:
            raise ValueError("At least one channel sequence must be set!")

        if sequence_ch0 is not None:
            DigitalToAnalog._verify_parameters(DacMode.STREAMING_MODE, sequence_ch0, sampling_rate_ch0)
            config.mode_ch0 = DacMode.STREAMING_MODE
            config.sampling_rate_ch0 = sampling_rate_ch0
            config.sample_count_ch0 = 0

        if sequence_ch1 is not None:
            DigitalToAnalog._verify_parameters(DacMode.STREAMING_MODE, sequence_ch1, sampling_rate_ch1)
            config.mode_ch1 = DacMode.STREAMING_MODE
            config.sampling_rate_ch1 = sampling_rate_ch1
            config.sample_count_ch1 = 0

        if self._apply_config(config) != DacConfigStatusCode.SUCCESS:
            raise RuntimeError("Failed to apply DAC configuration!")

        len_ch0 = len(sequence_ch0) if sequence_ch0 else 0
        len_ch1 = len(sequence_ch1) if sequence_ch1 else 0
        offset_ch0 = 0
        offset_ch1 = 0

        timeout = DAC_MAX_DATA_SAMPLES / max(sampling_rate_ch0 or 1, sampling_rate_ch1 or 1)
        while offset_ch0 < len_ch0 or offset_ch1 < len_ch1:
            start_time = time.monotonic()
            while (
                self.buffer_space_ch0 < DAC_MAX_DATA_SAMPLES
                or self.buffer_space_ch1 < DAC_MAX_DATA_SAMPLES
                or self.queue_space == 0
            ):
                # self.expander._read_all()
                self._wait_for_all_responses(timeout=0.1)
                if time.monotonic() - start_time > timeout + 0.42:
                    raise TimeoutError("Timeout waiting for buffer space!")

            current_sequence_ch0 = []
            if offset_ch0 < len_ch0:
                length = min(DAC_MAX_DATA_SAMPLES, len_ch0 - offset_ch0, self.buffer_space_ch0)
                current_sequence_ch0 = sequence_ch0[offset_ch0 : offset_ch0 + length]
                offset_ch0 += length
                # self.buffer_underrun_ch0 = False

            current_sequence_ch1 = []
            if offset_ch1 < len_ch1:
                length = min(DAC_MAX_DATA_SAMPLES, len_ch1 - offset_ch1, self.buffer_space_ch1)
                current_sequence_ch1 = sequence_ch1[offset_ch1 : offset_ch1 + length]
                offset_ch1 += length
                # self.buffer_underrun_ch0 = True

            request = DacDataRequest(True, current_sequence_ch0, True, current_sequence_ch1)
            self._send_data_request(request)

        # Wait for all requests to complete
        self._wait_for_all_responses(timeout=0.42)
        return DacDataStatusCode.SUCCESS

    def _send_data_request(self, request: DacDataRequest, timeout: float = 0.1) -> int:
        start_time = time.monotonic()
        while not self._can_accept_request(request):
            self.expander._read_all()
            if time.monotonic() - start_time > timeout:
                raise TimeoutError("Timeout waiting for request acceptance!")
        else:
            self.expander._read_all()

        self.sequence_number += 1
        self.request_id_counter += 1

        request.status_code = DacDataStatusCode.PENDING
        request.request_id = self.request_id_counter

        self.data_requests[request.request_id] = request

        self.queue_space -= 1
        self.buffer_space_ch0 -= len(request.sequence_ch0)
        self.buffer_space_ch1 -= len(request.sequence_ch1)

        """
        print(
            "Sending request (rid: %d, ch0_samples: %d, ch1_samples: %d, new space (queue: %d, ch0: %d, ch1: %d))"
            % (
                request.request_id,
                len(request.sequence_ch0),
                len(request.sequence_ch1),
                self.queue_space,
                self.buffer_space_ch0,
                self.buffer_space_ch1,
            )
        )
        """

        msg = dac_pb2.DacMsg()
        msg.sequence_number = self.sequence_number

        msg.data_request.request_id = request.request_id
        msg.data_request.run_ch0 = request.run_ch0
        msg.data_request.run_ch1 = request.run_ch1
        msg.data_request.data_ch0 = b"".join(x.to_bytes(2, "little") for x in request.sequence_ch0)
        msg.data_request.data_ch1 = b"".join(x.to_bytes(2, "little") for x in request.sequence_ch1)

        msg_bytes = msg.SerializeToString()
        tf.TF_INSTANCE.send(tf.TfMsgType.TYPE_DAC.value, msg_bytes, 0)
        return request.request_id

    def _wait_for_response(self, request_id: int, timeout: float) -> DacDataRequest | DacConfig:
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

        start_time = time.monotonic()
        while True:
            self.expander._read_all()
            if request.status_code != pending_code:
                break
            elif time.monotonic() - start_time > timeout:
                raise TimeoutError("Timeout waiting for response (id: %d)" % request_id)

        if container:
            del container[request_id]
        return request

    def _wait_for_all_responses(self, timeout: float) -> float:
        start_time = time.monotonic()
        while self.data_requests:
            self.expander._read_all()
            complete_rids = []
            for rid, request in self.data_requests.items():
                status_code = request.status_code
                if status_code == DacDataStatusCode.PENDING:
                    continue
                elif status_code != DacDataStatusCode.SUCCESS:
                    raise RuntimeError(f"Request {rid} failed with status {status_code}")
                else:
                    complete_rids.append(rid)

            for rid in complete_rids:
                del self.data_requests[rid]

            if time.monotonic() - start_time > timeout:
                raise TimeoutError("Timeout waiting for all responses!")
        else:
            self.expander._read_all()

        passed_time = time.monotonic() - start_time
        return passed_time

    def _receive_msg_cb(self, msg: dac_pb2.DacMsg):
        inner_msg = msg.WhichOneof("msg")
        if inner_msg == "config_status":
            self._handle_config_status(msg)
        elif inner_msg == "data_status":
            self._handle_data_status(msg)
        elif inner_msg == "notification":
            self._handle_notification(msg)
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
            self.buffer_space_ch0 = msg.data_status.buffer_space_ch0
            self.buffer_space_ch1 = msg.data_status.buffer_space_ch1
            """
            print(
                f"Updated space (queue: {self.queue_space}, ch0: {self.buffer_space_ch0}, ch1: {self.buffer_space_ch1})"
            )
            """

        request_id = msg.data_status.request_id
        if request_id not in self.data_requests:
            raise ValueError("Unknown data request status (id: %d) received!" % request_id)

        status = DacDataStatusCode(msg.data_status.status_code)
        self.data_requests[request_id].status_code = status

        if status != DacDataStatusCode.SUCCESS:
            raise RuntimeError(f"Data request {request_id} failed with status: {status}")

    def _handle_notification(self, msg: dac_pb2.DacMsg):
        if msg.sequence_number >= self.sequence_number:
            self.queue_space = msg.notification.queue_space
            self.buffer_space_ch0 = msg.notification.buffer_space_ch0
            self.buffer_space_ch1 = msg.notification.buffer_space_ch1
            """
            print(
                f"Notification - updated space (queue: {self.queue_space}, ch0: {self.buffer_space_ch0}, ch1: {self.buffer_space_ch1})"
            )
            """

        if msg.notification.buffer_underrun_ch0 and msg.notification.buffer_underrun_ch1:
            self.buffer_underrun_ch0 = True
            self.buffer_underrun_ch1 = True
            # print("Warning: Buffer underrun on both channels!")
        elif msg.notification.buffer_underrun_ch0:
            self.buffer_underrun_ch0 = True
            # print("Warning: Buffer underrun on channel 0!")
        elif msg.notification.buffer_underrun_ch1:
            self.buffer_underrun_ch1 = True
            # print("Warning: Buffer underrun on channel 1!")


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
