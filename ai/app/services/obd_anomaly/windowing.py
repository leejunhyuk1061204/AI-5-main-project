from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ai.app.schemas.obd_anomaly_schema import ObdSample


@dataclass(frozen=True)
class Window:
    window_index: int
    start_t: int
    end_t: int
    samples: List[ObdSample]


def make_windows(
    data: List[ObdSample],
    sampling_hz: int,
    window_sec: int,
    stride_sec: int,
) -> List[Window]:
    if sampling_hz <= 0:
        raise ValueError("sampling_hz must be >= 1")

    wsize = window_sec * sampling_hz
    step = stride_sec * sampling_hz

    if wsize <= 0 or step <= 0:
        raise ValueError("window_sec/stride_sec must be >= 1")

    windows: List[Window] = []
    idx = 0

    for start in range(0, len(data) - wsize + 1, step):
        end = start + wsize
        # start_t/end_t는 "초" 기준으로 맞춤(샘플 t를 신뢰해도 되지만, 인덱스 기반이 안정적)
        start_t = start // sampling_hz
        end_t = (end - 1) // sampling_hz  # inclusive end

        windows.append(
            Window(
                window_index=idx,
                start_t=start_t,
                end_t=end_t,
                samples=data[start:end],
            )
        )
        idx += 1

    return windows
