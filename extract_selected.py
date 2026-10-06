import zipfile
import csv
import os
import wave


# =========================================================
# CONFIG
# =========================================================

ZIP_FILE = "download/vox1_dev_wav.zip"

METADATA_FILE = "dataset/metadata/vox1_meta.csv"

OUTPUT_DIR = "dataset/female"

OUTPUT_METADATA = "dataset/metadata/female_audio.csv"


# ---------------------------------------------------------
# Mỗi speaker
# ---------------------------------------------------------

MIN_FILES_PER_SPEAKER = 20

MAX_FILES_PER_SPEAKER = 25


# ---------------------------------------------------------
# Audio
# ---------------------------------------------------------

TARGET_DURATION = 10.0


# ---------------------------------------------------------
# Tổng dataset
# ---------------------------------------------------------

MIN_TOTAL_FILES = 1000

MAX_TOTAL_FILES = 1300


# =========================================================
# Đọc metadata VoxCeleb1
# =========================================================

female_speakers = []


with open(
    METADATA_FILE,
    "r",
    encoding="utf-8-sig",
    newline=""
) as f:

    reader = csv.DictReader(
        f,
        delimiter="\t"
    )

    print("Metadata columns:")
    print(reader.fieldnames)

    for row in reader:

        speaker = row["VoxCeleb1 ID"].strip()

        gender = row["Gender"].strip().lower()

        dataset_set = row["Set"].strip().lower()


        # -------------------------------------------------
        # Chỉ lấy:
        # Female + DEV
        # -------------------------------------------------

        if (
            gender == "f"
            and dataset_set == "dev"
        ):

            female_speakers.append(
                speaker
            )


print()

print(
    "Female DEV speakers:",
    len(female_speakers)
)


if not female_speakers:

    raise RuntimeError(
        "Không tìm thấy speaker nữ trong metadata."
    )


# =========================================================
# Hàm đọc thông tin WAV
# =========================================================

def get_wav_info(zip_file, info):

    try:

        with zip_file.open(info) as audio_file:

            with wave.open(
                audio_file,
                "rb"
            ) as wav:

                frames = wav.getnframes()

                sample_rate = wav.getframerate()


                if sample_rate <= 0:

                    return None


                duration = (
                    frames / sample_rate
                )


                return {

                    "frames": frames,

                    "sample_rate": sample_rate,

                    "channels":
                        wav.getnchannels(),

                    "sample_width":
                        wav.getsampwidth(),

                    "duration":
                        duration

                }


    except Exception:

        return None


# =========================================================
# Hàm cắt audio thành đúng 10 giây
# =========================================================

def extract_10_seconds(
    zip_file,
    info,
    output_path,
    wav_info
):

    sample_rate = (
        wav_info["sample_rate"]
    )


    target_frames = int(
        sample_rate * TARGET_DURATION
    )


    with zip_file.open(info) as audio_file:

        with wave.open(
            audio_file,
            "rb"
        ) as source_wav:


            # -------------------------------------------------
            # Đọc đúng 10 giây đầu tiên
            # -------------------------------------------------

            frames = source_wav.readframes(
                target_frames
            )


            with wave.open(
                output_path,
                "wb"
            ) as output_wav:


                output_wav.setnchannels(
                    source_wav.getnchannels()
                )


                output_wav.setsampwidth(
                    source_wav.getsampwidth()
                )


                output_wav.setframerate(
                    source_wav.getframerate()
                )


                output_wav.writeframes(
                    frames
                )


# =========================================================
# Tạo thư mục output
# =========================================================

os.makedirs(
    OUTPUT_DIR,
    exist_ok=True
)


os.makedirs(
    os.path.dirname(
        OUTPUT_METADATA
    ),
    exist_ok=True
)


# =========================================================
# BƯỚC 1
# Scan ZIP
# =========================================================

print()

print(
    "Opening ZIP..."
)


with zipfile.ZipFile(
    ZIP_FILE,
    "r"
) as z:


    infos = z.infolist()


    print(
        "Total ZIP entries:",
        len(infos)
    )


    print()

    print(
        "Scanning female WAV files..."
    )


    # =====================================================
    # Dictionary:
    #
    # speaker_id
    #       ↓
    # list các file >= 10s
    # =====================================================

    speaker_files = {

        speaker: []

        for speaker in female_speakers

    }


    # =====================================================
    # Duyệt ZIP
    # =====================================================

    for index, info in enumerate(
        infos,
        start=1
    ):


        path = info.filename


        # -------------------------------------------------
        # Chỉ WAV
        # -------------------------------------------------

        if not path.lower().endswith(
            ".wav"
        ):

            continue


        # -------------------------------------------------
        # Cấu trúc:
        #
        # wav/idXXXXX/videoID/00001.wav
        # -------------------------------------------------

        parts = path.split("/")


        if len(parts) != 4:

            continue


        speaker = parts[1]

        video = parts[2]

        filename = parts[3]


        # -------------------------------------------------
        # Chỉ speaker nữ + DEV
        # -------------------------------------------------

        if speaker not in speaker_files:

            continue


        # -------------------------------------------------
        # Đọc thông tin WAV
        # -------------------------------------------------

        wav_info = get_wav_info(
            z,
            info
        )


        if wav_info is None:

            continue


        duration = (
            wav_info["duration"]
        )


        # -------------------------------------------------
        # Chỉ lấy file >= 10 giây
        # -------------------------------------------------

        if duration < TARGET_DURATION:

            continue


        # -------------------------------------------------
        # Lưu candidate
        # -------------------------------------------------

        speaker_files[
            speaker
        ].append({

            "info":
                info,

            "speaker":
                speaker,

            "video":
                video,

            "filename":
                filename,

            "source_file":
                path,

            "duration":
                duration,

            "wav_info":
                wav_info

        })


        # -------------------------------------------------
        # Progress
        # -------------------------------------------------

        if index % 10000 == 0:

            print(
                f"Scanned "
                f"{index}/"
                f"{len(infos)} entries..."
            )


# =========================================================
# BƯỚC 2
# Phân tích speaker
# =========================================================

print()

print(
    "======================================"
)

print(
    "SPEAKER ANALYSIS"
)

print(
    "======================================"
)


qualified_speakers = []

rejected_speakers = []


for speaker in female_speakers:


    count = len(
        speaker_files[speaker]
    )


    # -----------------------------------------------------
    # Speaker phải có ít nhất 20 file
    # -----------------------------------------------------

    if count >= MIN_FILES_PER_SPEAKER:

        qualified_speakers.append({

            "speaker":
                speaker,

            "available":
                count

        })

    else:

        rejected_speakers.append({

            "speaker":
                speaker,

            "available":
                count

        })


print(
    "Female DEV speakers:",
    len(female_speakers)
)


print(
    "Qualified speakers:",
    len(qualified_speakers)
)


print(
    "Rejected speakers:",
    len(rejected_speakers)
)


# =========================================================
# BƯỚC 3
# Sắp xếp speaker
#
# Speaker có ít file hợp lệ được ưu tiên trước.
#
# Ví dụ:
#
# 20
# 21
# 22
# 24
# 25
# 40
# 60
#
# =========================================================

qualified_speakers.sort(
    key=lambda x: (
        min(
            x["available"],
            MAX_FILES_PER_SPEAKER
        ),
        x["speaker"]
    )
)


# =========================================================
# BƯỚC 4
# Chọn speaker sao cho:
#
# 1000 <= tổng file <= 1300
#
# Mỗi speaker:
#
# 20 <= files <= 25
#
# =========================================================

selected_speakers = []

total_possible = 0


for item in qualified_speakers:


    speaker = item["speaker"]

    available = item["available"]


    # -----------------------------------------------------
    # Mỗi speaker tối đa 25
    # -----------------------------------------------------

    file_count = min(
        available,
        MAX_FILES_PER_SPEAKER
    )


    # -----------------------------------------------------
    # Kiểm tra nếu thêm speaker
    # có vượt MAX_TOTAL_FILES không
    # -----------------------------------------------------

    if (
        total_possible + file_count
        <= MAX_TOTAL_FILES
    ):

        selected_speakers.append(
            item
        )

        total_possible += file_count


# =========================================================
# Kiểm tra tổng
# =========================================================

print()

print(
    "Selected speakers:",
    len(selected_speakers)
)

print(
    "Potential total files:",
    total_possible
)


if total_possible < MIN_TOTAL_FILES:

    raise RuntimeError(

        f"Không thể tạo dataset "
        f"{MIN_TOTAL_FILES}-"
        f"{MAX_TOTAL_FILES} file. "

        f"Hiện chỉ có thể tạo "
        f"{total_possible} file."
    )


# =========================================================
# BƯỚC 5
# Extract dataset
# =========================================================

print()

print(
    "======================================"
)

print(
    "CREATING DATASET"
)

print(
    "======================================"
)


output_metadata = []

total_files = 0


with zipfile.ZipFile(
    ZIP_FILE,
    "r"
) as z:


    for item in selected_speakers:


        speaker = item[
            "speaker"
        ]


        candidates = speaker_files[
            speaker
        ]


        # -------------------------------------------------
        # Mỗi speaker lấy tối đa 25
        # -------------------------------------------------

        selected_files = candidates[
            :MAX_FILES_PER_SPEAKER
        ]


        # -------------------------------------------------
        # Đảm bảo >= 20
        # -------------------------------------------------

        if (
            len(selected_files)
            < MIN_FILES_PER_SPEAKER
        ):

            continue


        # -------------------------------------------------
        # Tạo folder speaker
        # -------------------------------------------------

        speaker_dir = os.path.join(
            OUTPUT_DIR,
            speaker
        )


        os.makedirs(
            speaker_dir,
            exist_ok=True
        )


        print()

        print(
            f"Speaker: {speaker}"
        )

        print(
            f"Available: "
            f"{len(candidates)}"
        )

        print(
            f"Selected: "
            f"{len(selected_files)}"
        )


        # -------------------------------------------------
        # Extract
        # -------------------------------------------------

        for number, audio in enumerate(
            selected_files,
            start=1
        ):


            output_name = (
                f"{speaker}_"
                f"{number:03d}.wav"
            )


            output_path = os.path.join(
                speaker_dir,
                output_name
            )


            # ---------------------------------------------
            # Cắt thành đúng 10 giây
            # ---------------------------------------------

            extract_10_seconds(
                z,
                audio["info"],
                output_path,
                audio["wav_info"]
            )


            total_files += 1


            # ---------------------------------------------
            # Metadata
            # ---------------------------------------------

            output_metadata.append({

                "speaker_id":
                    speaker,

                "video_id":
                    audio["video"],

                "source_file":
                    audio["source_file"],

                "output_file":
                    output_path,

                "original_duration":
                    round(
                        audio["duration"],
                        4
                    ),

                "output_duration":
                    TARGET_DURATION

            })


            print(
                f"  "
                f"[{number}/"
                f"{len(selected_files)}] "
                f"{audio['filename']} "
                f"("
                f"{audio['duration']:.2f}"
                f"s)"
            )


# =========================================================
# BƯỚC 6
# Ghi metadata CSV
# =========================================================

with open(
    OUTPUT_METADATA,
    "w",
    encoding="utf-8",
    newline=""
) as f:


    fieldnames = [

        "speaker_id",

        "video_id",

        "source_file",

        "output_file",

        "original_duration",

        "output_duration"

    ]


    writer = csv.DictWriter(
        f,
        fieldnames=fieldnames
    )


    writer.writeheader()

    writer.writerows(
        output_metadata
    )


# =========================================================
# BƯỚC 7
# Kiểm tra kết quả
# =========================================================

speaker_result = {}


for row in output_metadata:

    speaker = row[
        "speaker_id"
    ]

    speaker_result[speaker] = (
        speaker_result.get(
            speaker,
            0
        ) + 1
    )


# =========================================================
# FINAL REPORT
# =========================================================

print()

print(
    "======================================"
)

print(
    "DATASET CREATION COMPLETE"
)

print(
    "======================================"
)


print()

print(
    "Speakers:",
    len(speaker_result)
)


print(
    "Total audio files:",
    total_files
)


print(
    "Required range:",
    f"{MIN_TOTAL_FILES}"
    f"-"
    f"{MAX_TOTAL_FILES}"
)


print()

print(
    "Files per speaker:"
)


for speaker, count in sorted(
    speaker_result.items()
):

    print(
        f"  {speaker}: {count}"
    )


print()

print(
    "Metadata:",
    OUTPUT_METADATA
)


# =========================================================
# Validate
# =========================================================

valid = True


# ---------------------------------------------------------
# Tổng file
# ---------------------------------------------------------

if not (
    MIN_TOTAL_FILES
    <= total_files
    <= MAX_TOTAL_FILES
):

    valid = False

    print()

    print(
        "ERROR: Tổng số file nằm "
        "ngoài khoảng yêu cầu."
    )


# ---------------------------------------------------------
# Số file mỗi speaker
# ---------------------------------------------------------

for speaker, count in speaker_result.items():


    if not (
        MIN_FILES_PER_SPEAKER
        <= count
        <= MAX_FILES_PER_SPEAKER
    ):

        valid = False

        print(
            f"ERROR: {speaker} "
            f"có {count} file."
        )


# =========================================================
# Kết quả cuối
# =========================================================

print()

if valid:

    print(
        "======================================"
    )

    print(
        "SUCCESS"
    )

    print(
        "======================================"
    )

    print(
        "Dataset hợp lệ."
    )

    print(
        f"- {len(speaker_result)} speakers"
    )

    print(
        f"- {total_files} audio files"
    )

    print(
        "- Mỗi speaker: "
        f"{MIN_FILES_PER_SPEAKER}"
        f"-"
        f"{MAX_FILES_PER_SPEAKER}"
        " files"
    )

    print(
        "- Mỗi audio: 10 giây"
    )

else:

    print(
        "======================================"
    )

    print(
        "WARNING"
    )

    print(
        "Dataset chưa thỏa tất cả điều kiện."
    )