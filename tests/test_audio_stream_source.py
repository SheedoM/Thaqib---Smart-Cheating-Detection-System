import io
from urllib.error import URLError

import numpy as np

from thaqib.audio.source import StreamAudioSource


class _FakeStream(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


def test_stream_audio_source_reads_synchronized_pcm16_chunks(monkeypatch):
    samples_a = np.array([0, 16384, -16384, 32767], dtype="<i2").tobytes()
    samples_b = np.array([32767, 0, 0, -32768], dtype="<i2").tobytes()
    streams = {
        "http://mic-a/feed": _FakeStream(samples_a),
        "http://mic-b/feed": _FakeStream(samples_b),
    }

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout=5.0: streams[request.full_url])

    source = StreamAudioSource(
        ["http://mic-a/feed", "http://mic-b/feed"],
        sample_rate=8,
        chunk_ms=500,
    )
    source.start()

    chunk = source.get_chunk()

    assert chunk is not None
    assert chunk.mic_data.shape == (2, 4)
    np.testing.assert_allclose(chunk.mic_data[0], [0.0, 0.5, -0.5, 0.9999695], atol=1e-5)
    np.testing.assert_allclose(chunk.mic_data[1], [0.9999695, 0.0, 0.0, -1.0], atol=1e-5)


def test_stream_audio_source_masks_unavailable_mics_with_silence(monkeypatch):
    good_samples = np.array([1000, 2000, 3000, 4000], dtype="<i2").tobytes()

    def fake_urlopen(request, timeout=5.0):
        if request.full_url == "http://mic-down/feed":
            raise URLError("offline")
        return _FakeStream(good_samples)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    source = StreamAudioSource(
        ["http://mic-ok/feed", "http://mic-down/feed"],
        sample_rate=8,
        chunk_ms=500,
    )
    source.start()

    chunk = source.get_chunk()

    assert chunk is not None
    np.testing.assert_allclose(chunk.mic_data[1], np.zeros(4, dtype=np.float32))
