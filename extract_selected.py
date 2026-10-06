import zipfile
import csv
import os
import wave

# File path
ZIP_FILE = "download/vox1_dev_wav.zip"
METADATA_FILE = "dataset/metadata/vox1_meta.csv"
OUTPUT_DIR = "dataset/female"
OUTPUT_METADATA = "dataset/metadata/female_audio.csv"

# Speaker config
MIN_FILES_PER_SPEAKER = 20
MAX_FILES_PER_SPEAKER = 25

# Audio duration
TARGET_DURATION = 10.0

# Expected dataset
MIN_TOTAL_FILES = 1000
MAX_TOTAL_FILES = 1300

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


# Read WAV information
def get_wav_info(zip_file, info):
    try:
        with zip_file.open(info) as audio_file:
            with wave.open(audio_file, "rb") as wav:
                frames = wav.getnframes()
                sample_rate = wav.getframerate()

                if sample_rate <= 0:
                    return None

                duration = frames / sample_rate

                return {
                    "frames": frames,
                    "sample_rate": sample_rate,
                    "channels": wav.getnchannels(),
                    "sample_width": wav.getsampwidth(),
                    "duration": duration,
                }

    except Exception:
        return None


# Extract the first 10 seconds of audio
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
print()
print("Opening ZIP...")

with zipfile.ZipFile(ZIP_FILE, "r") as z:
    infos = z.infolist()

    print("Total ZIP entries:", len(infos))
    print()
    print("Scanning female WAV files...")

    # Store valid WAV files for each female speaker
    speaker_files = {
        speaker: []
        for speaker in female_speakers
    }

    # Scan all files in the ZIP
    for index, info in enumerate(infos, start=1):
        path = info.filename

        # Only process WAV files
        if not path.lower().endswith(".wav"):
            continue

        # Expected path:
        # wav/idXXXXX/videoID/00001.wav
        parts = path.split("/")

        if len(parts) != 4:
            continue

        speaker = parts[1]
        video = parts[2]
        filename = parts[3]

        # Only keep female DEV speakers
        if speaker not in speaker_files:
            continue

        wav_info = get_wav_info(z, info)

        if wav_info is None:
            continue

        duration = wav_info["duration"]

        # Only keep files that are at least 10 seconds long
        if duration < TARGET_DURATION:
            continue

        # Save the file as a valid candidate
        speaker_files[speaker].append({
            "info": info,
            "speaker": speaker,
            "video": video,
            "filename": filename,
            "source_file": path,
            "duration": duration,
            "wav_info": wav_info,
        })

        # Show progress every 10,000 entries
        if index % 10000 == 0:
            print(f"Scanned {index}/{len(infos)} entries...")


# Step 2: Analyze speakers
print()
print("======================================")
print("SPEAKER ANALYSIS")
print("======================================")

qualified_speakers = []
rejected_speakers = []

for speaker in female_speakers:
    count = len(speaker_files[speaker])

    # A speaker must have at least 20 valid files
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
# Speakers with fewer valid files are selected first.
qualified_speakers.sort(
    key=lambda x: (
        min(x["available"], MAX_FILES_PER_SPEAKER),
        x["speaker"],
    )
)


# Step 4: Select speakers
# Total files must be between 1,000 and 1,300.
# Each speaker contributes between 20 and 25 files.
selected_speakers = []
total_possible = 0

for item in qualified_speakers:
    speaker = item["speaker"]
    available = item["available"]

    # Each speaker contributes at most 25 files.
    file_count = min(available, MAX_FILES_PER_SPEAKER)

    # Do not exceed the maximum dataset size.
    if total_possible + file_count <= MAX_TOTAL_FILES:
        selected_speakers.append(item)
        total_possible += file_count


# Check whether the selected speakers can create enough files
print()
print("Selected speakers:", len(selected_speakers))
print("Potential total files:", total_possible)

if total_possible < MIN_TOTAL_FILES:
    raise RuntimeError(
        f"Không thể tạo dataset {MIN_TOTAL_FILES}-{MAX_TOTAL_FILES} file. "
        f"Hiện chỉ có thể tạo {total_possible} file."
    )


# Step 5: Extract dataset
print()
print("======================================")
print("CREATING DATASET")
print("======================================")

output_metadata = []
total_files = 0

with zipfile.ZipFile(ZIP_FILE, "r") as z:
    for item in selected_speakers:
        speaker = item["speaker"]
        candidates = speaker_files[speaker]

        # Take at most 25 files for each speaker.
        selected_files = candidates[:MAX_FILES_PER_SPEAKER]

        # Skip speakers with fewer than 20 selected files.
        if len(selected_files) < MIN_FILES_PER_SPEAKER:
            continue

        # Create the speaker output directory.
        speaker_dir = os.path.join(OUTPUT_DIR, speaker)
        os.makedirs(speaker_dir, exist_ok=True)

        print()
        print(f"Speaker: {speaker}")
        print(f"Available: {len(candidates)}")
        print(f"Selected: {len(selected_files)}")

        # Extract selected audio files.
        for number, audio in enumerate(selected_files, start=1):
            output_name = f"{speaker}_{number:03d}.wav"
            output_path = os.path.join(speaker_dir, output_name)

            # Extract exactly 10 seconds.
            extract_10_seconds(
                z,
                audio["info"],
                output_path,
                audio["wav_info"],
            )

            total_files += 1

            # Save output metadata.
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


# Step 7: Check the result
speaker_result = {}

for row in output_metadata:
    speaker = row["speaker_id"]
    speaker_result[speaker] = speaker_result.get(speaker, 0) + 1


# Final report
print()
print("======================================")
print("DATASET CREATION COMPLETE")
print("======================================")

print()
print("Speakers:", len(speaker_result))
print("Total audio files:", total_files)
print(
    "Required range:",
    f"{MIN_TOTAL_FILES}-{MAX_TOTAL_FILES}",
)

print()
print("Files per speaker:")

for speaker, count in sorted(speaker_result.items()):
    print(f"  {speaker}: {count}")

print()
print("Metadata:", OUTPUT_METADATA)


# Validate the dataset
valid = True

# Check total file count
if not MIN_TOTAL_FILES <= total_files <= MAX_TOTAL_FILES:
    valid = False

    print()
    print("ERROR: Tổng số file nằm ngoài khoảng yêu cầu.")


# Check file count for each speaker
for speaker, count in speaker_result.items():
    if not MIN_FILES_PER_SPEAKER <= count <= MAX_FILES_PER_SPEAKER:
        valid = False

        print(
            f"ERROR: {speaker} có {count} file."
        )


# Final validation result
print()

if valid:
    print("======================================")
    print("SUCCESS")
    print("======================================")
    print("Dataset hợp lệ.")
    print(f"- {len(speaker_result)} speakers")
    print(f"- {total_files} audio files")
    print(
        f"- Mỗi speaker: "
        f"{MIN_FILES_PER_SPEAKER}-{MAX_FILES_PER_SPEAKER} files"
    )
    print("- Mỗi audio: 10 giây")
else:
    print("======================================")
    print("WARNING")
    print("======================================")
    print("Dataset chưa thỏa tất cả điều kiện.")
