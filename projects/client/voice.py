# ─────────────────────────────────────────────
# client/voice.py — 语音通话（简洁版外壳）
# 实现提示：底层可用 pyaudio + asyncio + DTLS/TLS
# ─────────────────────────────────────────────

import asyncio
from typing import Tuple

# 占位
StreamReader = asyncio.StreamReader
StreamWriter = asyncio.StreamWriter
P2PChannel   = Tuple[StreamReader, StreamWriter]

# 音频参数（可从 settings.ini 读取后覆盖）
SAMPLE_RATE    = 48000     # Hz
FRAME_DURATION = 20        # ms
CHANNELS       = 1
FRAME_BYTES    = int(SAMPLE_RATE / 1000 * FRAME_DURATION) * 2  # 16-bit mono

# 活跃通话表：peer → tasks
_active_calls: dict[str, list[asyncio.Task]] = {}


async def start_voice_call(peer: str, channel: P2PChannel) -> None:
    """
    发起/接管与 peer 的语音通话。
    创建两个协程：
      • _capture_loop  —— 录麦 -> 发送
      • _playback_loop —— 接收 -> 放音
    """
    reader, writer = channel
    tx = asyncio.create_task(_capture_loop(writer))
    rx = asyncio.create_task(_playback_loop(reader))
    _active_calls[peer] = [tx, rx]


async def stop_voice_call(peer: str) -> None:
    """
    结束与 peer 的语音通话，取消协程并清理资源。
    """
    for t in _active_calls.pop(peer, []):
        t.cancel()


async def _capture_loop(writer: StreamWriter) -> None:
    """
    捕获本地麦克风数据并发送。帧长 FRAME_DURATION 毫秒。
    建议：pyaudio → queue → asyncio.sleep() 对齐帧节奏。
    """
    pass


async def _playback_loop(reader: StreamReader) -> None:
    """
    接收对端语音帧并即时播放。可选抖动缓冲区平滑网络抖动。
    """
    pass
