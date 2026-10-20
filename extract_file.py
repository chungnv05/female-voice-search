import zipfile
import csv
import os
import wave
from collections import Counter
import matplotlib.pyplot as plt

# File paths
ZIP_FILE = "download/vox1_dev_wav.zip"
METADATA_FILE = "dataset/metadata/vox1_meta.csv"
OUTPUT_DIR = "dataset/female"
OUTPUT_METADATA = "dataset/metadata/female_audio.csv"

# Speaker config
MIN_FILES_PER_SPEAKER = 4
MAX_FILES_PER_SPEAKER = 5

# Audio duration
TARGET_DURATION = 10.0

# Expected dataset
MIN_TOTAL_FILES = 2000
MAX_TOTAL_FILES = 2300

female_speakers = []

with open(METADATA_FILE, "r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f, delimiter="\t")

    print("Metadata columns:")
    print(reader.fieldnames)

    for row in reader:
        speaker = row["VoxCeleb1 ID"].strip()
        gender = row["Gender"].strip().lower()
        dataset_set = row["Set"].strip().lower()

        if gender == "f" and dataset_set == "dev":
            female_speakers.append(speaker)

print("Female DEV speakers:", len(female_speakers))

if not female_speakers:
    raise RuntimeError("Không tìm thấy speaker nữ trong metadata.")


def get_wav_info(zip_file, info):
    try:
        with zip_file.open(info) as audio_file:
            with wave.open(audio_file, "rb") as wav:
                frames = wav.getnframes()
                sample_rate = wav.getframerate()

                if sample_rate <= 0:
                    return None

                return {
                    "frames": frames,
                    "sample_rate": sample_rate,
                    "channels": wav.getnchannels(),
                    "sample_width": wav.getsampwidth(),
                    "duration": frames / sample_rate,
                }

    except Exception:
        return None


def extract_10_seconds(zip_file, info, output_path, wav_info):
    sample_rate = wav_info["sample_rate"]
    target_frames = int(sample_rate * TARGET_DURATION)

    with zip_file.open(info) as audio_file:
        with wave.open(audio_file, "rb") as source_wav:
            frames = source_wav.readframes(target_frames)

            with wave.open(output_path, "wb") as output_wav:
                output_wav.setnchannels(source_wav.getnchannels())
                output_wav.setsampwidth(source_wav.getsampwidth())
                output_wav.setframerate(source_wav.getframerate())
                output_wav.writeframes(frames)


# Create output directories
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUTPUT_METADATA), exist_ok=True)


# Step 1: Scan ZIP
print("\nOpening ZIP...")

with zipfile.ZipFile(ZIP_FILE, "r") as z:
    infos = z.infolist()

    print("Total ZIP entries:", len(infos))
    print("Scanning female WAV files...")

    speaker_files = {speaker: [] for speaker in female_speakers}

    for index, info in enumerate(infos, start=1):
        path = info.filename

        if not path.lower().endswith(".wav"):
            continue

        parts = path.split("/")

        if len(parts) != 4:
            continue

        speaker = parts[1]
        video = parts[2]
        filename = parts[3]

        if speaker not in speaker_files:
            continue

        wav_info = get_wav_info(z, info)

        if wav_info is None:
            continue

        if wav_info["duration"] < TARGET_DURATION:
            continue

        speaker_files[speaker].append({
            "info": info,
            "speaker": speaker,
            "video": video,
            "filename": filename,
            "source_file": path,
            "duration": wav_info["duration"],
            "wav_info": wav_info,
        })

        if index % 10000 == 0:
            print(f"Scanned {index}/{len(infos)} entries...")


# Step 2: Analyze speakers
print("\n======================================")
print("SPEAKER ANALYSIS")
print("======================================")

qualified_speakers = []
rejected_speakers = []

for speaker in female_speakers:
    count = len(speaker_files[speaker])

    if count >= MIN_FILES_PER_SPEAKER:
        qualified_speakers.append({
            "speaker": speaker,
            "available": count,
        })
    else:
        rejected_speakers.append({
            "speaker": speaker,
            "available": count,
        })

print("Female DEV speakers:", len(female_speakers))
print("Qualified speakers:", len(qualified_speakers))
print("Rejected speakers:", len(rejected_speakers))


# Step 3: Sort speakers
qualified_speakers.sort(
    key=lambda x: (
        min(x["available"], MAX_FILES_PER_SPEAKER),
        x["speaker"],
    )
)


# Step 4: Select speakers
selected_speakers = []
total_possible = 0

for item in qualified_speakers:
    file_count = min(
        item["available"],
        MAX_FILES_PER_SPEAKER,
    )

    if total_possible + file_count <= MAX_TOTAL_FILES:
        selected_speakers.append(item)
        total_possible += file_count

print("\nSelected speakers:", len(selected_speakers))
print("Potential total files:", total_possible)

if total_possible < MIN_TOTAL_FILES:
    raise RuntimeError(
        f"Không thể tạo dataset {MIN_TOTAL_FILES}-{MAX_TOTAL_FILES} file. "
        f"Hiện chỉ có thể tạo {total_possible} file."
    )


# Step 5: Extract dataset
print("\n======================================")
print("CREATING DATASET")
print("======================================")

output_metadata = []
total_files = 0

with zipfile.ZipFile(ZIP_FILE, "r") as z:
    for item in selected_speakers:
        speaker = item["speaker"]
        candidates = speaker_files[speaker]

        selected_files = candidates[:MAX_FILES_PER_SPEAKER]

        if len(selected_files) < MIN_FILES_PER_SPEAKER:
            continue

        speaker_dir = os.path.join(OUTPUT_DIR, speaker)
        os.makedirs(speaker_dir, exist_ok=True)

        print(f"\nSpeaker: {speaker}")
        print(f"Available: {len(candidates)}")
        print(f"Selected: {len(selected_files)}")

        for number, audio in enumerate(selected_files, start=1):
            output_name = f"{speaker}_{number:03d}.wav"
            output_path = os.path.join(speaker_dir, output_name)

            extract_10_seconds(
                z,
                audio["info"],
                output_path,
                audio["wav_info"],
            )

            total_files += 1

            output_metadata.append({
                "speaker_id": speaker,
                "video_id": audio["video"],
                "source_file": audio["source_file"],
                "output_file": output_path,
                "original_duration": round(audio["duration"], 4),
                "output_duration": TARGET_DURATION,
            })

            print(
                f"  [{number}/{len(selected_files)}] "
                f"{audio['filename']} ({audio['duration']:.2f}s)"
            )


# Step 6: Write metadata CSV
with open(
    OUTPUT_METADATA,
    "w",
    encoding="utf-8",
    newline="",
) as f:
    fieldnames = [
        "speaker_id",
        "video_id",
        "source_file",
        "output_file",
        "original_duration",
        "output_duration",
    ]

    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(output_metadata)

def create_statistics(output_metadata, speaker_result, total_files, valid):
    os.makedirs("dataset/statistics", exist_ok=True)

    output_path = "dataset/statistics/female_dataset_statistics.png"

    durations = [
        float(row["original_duration"])
        for row in output_metadata
    ]

    distribution = Counter(speaker_result.values())

    speakers_with_4 = distribution.get(4, 0)
    speakers_with_5 = distribution.get(5, 0)
    total_speakers = len(speaker_result)

    avg_duration = (
        sum(durations) / len(durations)
        if durations else 0
    )

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle(
        "Female VoxCeleb1 DEV Dataset Statistics",
        fontsize=16,
    )

    # 1. Số speaker có 4 hoặc 5 file
    ax = axes[0, 0]
    bars = ax.bar(
        ["4 files", "5 files"],
        [speakers_with_4, speakers_with_5],
    )
    ax.set_title("Number of Files per Speaker")
    ax.set_ylabel("Number of Speakers")
    ax.bar_label(bars)

    # 2. Phân bố thời lượng âm thanh gốc
    ax = axes[0, 1]
    ax.hist(durations, bins=20, edgecolor="black")
    ax.set_title("Original Audio Duration Distribution")
    ax.set_xlabel("Duration (seconds)")
    ax.set_ylabel("Number of Files")

    # 3. Số file theo từng speaker
    ax = axes[1, 0]
    counts = sorted(speaker_result.values())
    ax.hist(
        counts,
        bins=[3.5, 4.5, 5.5],
        edgecolor="black",
        rwidth=0.7,
    )
    ax.set_xticks([4, 5])
    ax.set_title("Speaker File Count Distribution")
    ax.set_xlabel("Files per Speaker")
    ax.set_ylabel("Number of Speakers")

    # 4. Tổng quan bộ dữ liệu
    ax = axes[1, 1]
    ax.axis("off")

    summary = (
        f"DATASET SUMMARY\n\n"
        f"Total speakers: {total_speakers}\n"
        f"Total audio files: {total_files}\n"
        f"Speakers with 4 files: {speakers_with_4}\n"
        f"Speakers with 5 files: {speakers_with_5}\n"
        f"Target audio duration: 10 seconds\n"
        f"Average original duration: {avg_duration:.2f}s\n\n"
        f"Validation: {'PASS' if valid else 'CHECK REQUIRED'}"
    )

    ax.text(
        0.05, 0.95, summary,
        va="top",
        fontsize=12,
        family="monospace",
    )

    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    print(f"\nĐã tạo ảnh thống kê: {output_path}")

# Step 7: Validate dataset
speaker_result = {}

for row in output_metadata:
    speaker = row["speaker_id"]
    speaker_result[speaker] = speaker_result.get(speaker, 0) + 1

valid = MIN_TOTAL_FILES <= total_files <= MAX_TOTAL_FILES

for speaker, count in speaker_result.items():
    if not MIN_FILES_PER_SPEAKER <= count <= MAX_FILES_PER_SPEAKER:
        valid = False
        print(f"ERROR: {speaker} có {count} file.")

print("\n======================================")
print("DATASET CREATION COMPLETE")
print("======================================")
print("Speakers:", len(speaker_result))
print("Total audio files:", total_files)
print("Files per speaker:")

for speaker, count in sorted(speaker_result.items()):
    print(f"  {speaker}: {count}")

print("\nMetadata:", OUTPUT_METADATA)

if valid:
    print("\nSUCCESS: Dataset hợp lệ.")
    print(f"- {len(speaker_result)} speakers")
    print(f"- {total_files} audio files")
    print(f"- Mỗi speaker có {MIN_FILES_PER_SPEAKER}-{MAX_FILES_PER_SPEAKER} file")
    print(f"- Mỗi audio dài {TARGET_DURATION} giây")
else:
    print("\nWARNING: Dataset chưa thỏa tất cả điều kiện.")

create_statistics(
    output_metadata,
    speaker_result,
    total_files,
    valid,
)