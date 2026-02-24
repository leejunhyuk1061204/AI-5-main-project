"""
[파일 용도] YouTube 결함음 구간 다운로드 및 분할
- yt-dlp로 지정 구간 다운로드 (WAV)
- 2초 슬라이딩 윈도우 / 75% overlap (스텝 0.5초)
- 기존 파일명 패턴 유지: {class}_{video_id}_{segment_idx:02d}_{chunk:03d}.wav
- 저장 위치: ai/data/audio/train/abnormal/{brake, starter}
"""

import os
import subprocess
import librosa
import soundfile as sf
import numpy as np
from pathlib import Path

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────
BASE_DIR = Path("c:/Users/301/AI-5-main-project/ai/data/audio/train/abnormal")
TEMP_DIR = Path("c:/Users/301/AI-5-main-project/ai/data/audio/temp/defect_download")
TARGET_SR = 16000
WINDOW_SEC = 2.0
STEP_SEC = 0.5          # 75% overlap → step = 2.0 * 0.25 = 0.5s

# ─────────────────────────────────────────────
# 수집 대상 정의
# format: (video_id, label, [(start_sec, end_sec), ...])
# ─────────────────────────────────────────────
CLIPS = [
    # ── 시동음 결함 (starter) ──
    ("_DCCDisByMc",  "starter", [(0,   26)]),
    ("wmXrZgpHA_A",  "starter", [(8,   37)]),
    ("QvCVptaOng0",  "starter", [(323, 350), (377, 393), (480, 500),
                                  (728, 738), (833, 838), (1081, 1094), (1224, 1241)]),

    # ── 브레이크 결함 (brake) ──
    ("PNbNItYJUzo",  "brake",   [(56,  65)]),
    ("ijRe69fMEkI",  "brake",   [(27,  31), (43, 48), (54, 60),
                                  (63,  66), (77, 87), (135, 140), (169, 174)]),
    ("7V53XBkw65Y",  "brake",   [(0,    6), (210, 218), (323, 326)]),
    ("QiFgqzHWlRc",  "brake",   [(7,   16)]),
    ("KTKPW3FBbZo",  "brake",   [(1,   13)]),
]


def download_clip(video_id: str, start: int, end: int, out_path: Path) -> bool:
    """yt-dlp로 지정 구간을 WAV로 다운로드"""
    url = f"https://www.youtube.com/watch?v={video_id}"
    cmd = [
        "yt-dlp",
        "-x", "--audio-format", "wav",
        "--audio-quality", "0",
        "--postprocessor-args", f"ffmpeg:-ss {start} -to {end} -ar {TARGET_SR} -ac 1",
        "-o", str(out_path),
        url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and out_path.exists():
            return True
        # yt-dlp가 .wav 확장자를 자동으로 붙이는 경우 대비
        wav_path = out_path.with_suffix(".wav")
        if wav_path.exists():
            wav_path.rename(out_path)
            return True
        print(f"  ❌ 다운로드 실패: {result.stderr[-300:]}")
        return False
    except subprocess.TimeoutExpired:
        print(f"  ❌ 타임아웃: {video_id} {start}~{end}")
        return False
    except FileNotFoundError:
        print("  ❌ yt-dlp가 설치되어 있지 않습니다. `pip install yt-dlp` 를 먼저 실행하세요.")
        return False


def sliding_window_chunks(audio: np.ndarray, sr: int):
    """2초 윈도우 / 0.5초 스텝으로 청크 생성"""
    window = int(WINDOW_SEC * sr)
    step   = int(STEP_SEC   * sr)
    total  = len(audio)
    i = 0
    while i + window <= total:
        yield audio[i:i + window]
        i += step
    # 마지막 조각 처리: 최소 1초 이상이면 패딩해서 포함
    if i < total and (total - i) >= int(0.5 * sr):
        chunk = audio[i:]
        chunk = np.pad(chunk, (0, window - len(chunk)))
        yield chunk


def process_video(video_id: str, label: str, segments: list):
    out_dir = BASE_DIR / label
    out_dir.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"📹 {video_id}  |  클래스: {label}  |  구간 수: {len(segments)}")

    for seg_idx, (start, end) in enumerate(segments, start=1):
        seg_sec = end - start
        expected = int((seg_sec - WINDOW_SEC) / STEP_SEC) + 1
        print(f"\n  📌 구간 {seg_idx:02d}: {start}s ~ {end}s  ({seg_sec}초, 예상 청크 {expected}개)")

        # ── 다운로드 ──
        tmp_file = TEMP_DIR / f"{video_id}_{seg_idx:02d}.wav"
        if tmp_file.exists():
            print(f"  ♻️  캐시 사용: {tmp_file.name}")
        else:
            print(f"  ⬇️  다운로드 중...")
            if not download_clip(video_id, start, end, tmp_file):
                continue

        # ── 로드 ──
        try:
            audio, sr = librosa.load(str(tmp_file), sr=TARGET_SR, mono=True)
        except Exception as e:
            print(f"  ❌ 오디오 로드 실패: {e}")
            continue

        print(f"  🔊 로드 완료: {len(audio)/sr:.2f}초")

        # ── 슬라이딩 윈도우 분할 ──
        prefix = f"{label}_{video_id}_{seg_idx:02d}"

        # 기존 파일 충돌 방지: 이미 같은 prefix 파일이 있으면 건너뜀
        existing = list(out_dir.glob(f"{prefix}_*.wav"))
        if existing:
            print(f"  ⚠️  이미 존재 ({len(existing)}개) → 건너뜀. 재생성하려면 기존 파일을 삭제하세요.")
            continue

        count = 0
        for chunk in sliding_window_chunks(audio, TARGET_SR):
            count += 1
            filename = f"{prefix}_{count:03d}.wav"
            save_path = out_dir / filename
            sf.write(str(save_path), chunk, TARGET_SR)

        print(f"  ✅ {count}개 저장 완료 → {out_dir}")


def main():
    print("🚀 YouTube 결함음 수집 시작")
    print(f"   저장 위치: {BASE_DIR}")
    print(f"   윈도우: {WINDOW_SEC}초  |  스텝: {STEP_SEC}초 (75% overlap)")

    total_by_label = {"starter": 0, "brake": 0}

    for video_id, label, segments in CLIPS:
        process_video(video_id, label, segments)

    # ── 최종 통계 ──
    print(f"\n{'='*60}")
    print("📊 최종 통계")
    for label in ["starter", "brake"]:
        folder = BASE_DIR / label
        files = list(folder.glob("*.wav"))
        count = len(files)
        total_by_label[label] = count
        print(f"  {label:8s}: {count:4d}개")
    print(f"  {'합계':8s}: {sum(total_by_label.values()):4d}개")
    print("\n✅ 완료!")


if __name__ == "__main__":
    main()
