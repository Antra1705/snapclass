"""Old-vs-new pipeline parity verification.

Runs the SAME images/audio through:
  - OLD: verification/old_face_pipeline.py / old_voice_pipeline.py
    (extracted byte-for-byte from git HEAD, still using st.cache_resource)
  - NEW: src/pipelines/face_pipeline.py / voice_pipeline.py

Both sides are given an identical in-memory student DB (get_all_students is
monkeypatched), so the only thing under test is the inference code itself.

Usage: .venv/bin/python verification/run_parity.py
"""

import importlib.util
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ASSETS = os.path.join(HERE, "assets")
sys.path.insert(0, REPO)

os.environ.setdefault("SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "dummy-key-for-verification")

import numpy as np
import soundfile as sf
from PIL import Image


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


old_face = load_module("old_face_pipeline", os.path.join(HERE, "old_face_pipeline.py"))
old_voice = load_module("old_voice_pipeline", os.path.join(HERE, "old_voice_pipeline.py"))

import src.pipelines.face_pipeline as new_face
import src.pipelines.voice_pipeline as new_voice


def asset(name):
    return os.path.join(ASSETS, name)


def img_rgb(path):
    return np.array(Image.open(path).convert("RGB"))


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


report = {"face": {}, "voice": {}, "preprocessing": {}}

# ---------------------------------------------------------------------------
# Build the shared synthetic student DB (computed ONCE, via the OLD pipeline,
# then injected into both old and new modules).
# ---------------------------------------------------------------------------
print("== Building shared synthetic student DB ==")
enroll_obama = old_face.get_face_embeddings(img_rgb(asset("obama.jpg")))
enroll_biden = old_face.get_face_embeddings(img_rgb(asset("biden.jpg")))
assert len(enroll_obama) == 1 and len(enroll_biden) == 1, "enrollment images must have 1 face"

alice_voice = old_voice.get_voice_embedding(read_bytes(asset("alice_enroll.wav")))
bob_voice = old_voice.get_voice_embedding(read_bytes(asset("bob_enroll.wav")))
assert alice_voice and bob_voice, "voice enrollment failed"

STUDENTS = [
    {
        "student_id": 1,
        "name": "Student1-Obama/Alice",
        "face_embedding": enroll_obama[0].tolist(),
        "voice_embedding": alice_voice,
    },
    {
        "student_id": 2,
        "name": "Student2-Biden/Bob",
        "face_embedding": enroll_biden[0].tolist(),
        "voice_embedding": bob_voice,
    },
]

old_face.get_all_students = lambda: STUDENTS
new_face.get_all_students = lambda: STUDENTS

# ---------------------------------------------------------------------------
# Determinism self-check (jitter/randomness would invalidate exact diffs)
# ---------------------------------------------------------------------------
_e1 = old_face.get_face_embeddings(img_rgb(asset("obama2.jpg")))
_e2 = old_face.get_face_embeddings(img_rgb(asset("obama2.jpg")))
face_deterministic = all(np.array_equal(a, b) for a, b in zip(_e1, _e2))

_v1 = old_voice.get_voice_embedding(read_bytes(asset("alice_probe.wav")))
_v2 = old_voice.get_voice_embedding(read_bytes(asset("alice_probe.wav")))
voice_deterministic = _v1 == _v2

report["determinism"] = {
    "face_embeddings_repeatable": bool(face_deterministic),
    "voice_embeddings_repeatable": bool(voice_deterministic),
}
print(f"determinism: face={face_deterministic} voice={voice_deterministic}")


def score_detail(mod, image_np):
    """Replicate predict_attendance's internal scoring to expose the values it
    thresholds (predicted id + L2 distance vs the 0.4 threshold)."""
    encodings = mod.get_face_embeddings(image_np)
    model_data = mod.get_trained_model()
    clf = model_data["clf"]
    X, y = model_data["X"], model_data["y"]
    all_students = sorted(list(set(y)))
    rows = []
    for encoding in encodings:
        if len(all_students) >= 2:
            predicted_id = int(clf.predict([encoding])[0])
        else:
            predicted_id = int(all_students[0])
        dist = float(np.linalg.norm(X[y.index(predicted_id)] - encoding))
        rows.append(
            {"predicted_id": predicted_id, "distance": dist, "passes_0.4_threshold": dist <= 0.4}
        )
    return rows


# ---------------------------------------------------------------------------
# FACE parity
# ---------------------------------------------------------------------------
print("\n== FACE parity ==")
for image_name in ["obama.jpg", "obama2.jpg", "biden.jpg", "two_people.jpg"]:
    image_np = img_rgb(asset(image_name))

    o_emb = old_face.get_face_embeddings(image_np)
    n_emb = new_face.get_face_embeddings(image_np)
    emb_equal = len(o_emb) == len(n_emb) and all(
        np.array_equal(a, b) for a, b in zip(o_emb, n_emb)
    )

    o_det, o_all, o_n = old_face.predict_attendance(image_np)
    n_det, n_all, n_n = new_face.predict_attendance(image_np)

    entry = {
        "old": {
            "num_faces": o_n,
            "detected": {str(k): v for k, v in o_det.items()},
            "all_students": o_all,
            "scores": score_detail(old_face, image_np),
        },
        "new": {
            "num_faces": n_n,
            "detected": {str(k): v for k, v in n_det.items()},
            "all_students": n_all,
            "scores": score_detail(new_face, image_np),
        },
        "embeddings_bitwise_equal": bool(emb_equal),
        "outputs_match": bool(o_det == n_det and o_all == n_all and o_n == n_n),
    }
    report["face"][image_name] = entry
    print(
        f"{image_name}: faces old={o_n} new={n_n} | detected old={o_det} new={n_det} "
        f"| emb_equal={emb_equal} | match={entry['outputs_match']}"
    )

# ---------------------------------------------------------------------------
# VOICE parity
# ---------------------------------------------------------------------------
print("\n== VOICE parity ==")
candidates = {1: alice_voice, 2: bob_voice}

for clip in ["alice_probe.wav", "bob_probe.wav"]:
    audio_bytes = read_bytes(asset(clip))
    o_emb = old_voice.get_voice_embedding(audio_bytes)
    n_emb = new_voice.get_voice_embedding(audio_bytes)
    emb_equal = o_emb == n_emb

    o_sid, o_score = old_voice.identify_speaker(o_emb, candidates)
    n_sid, n_score = new_voice.identify_speaker(n_emb, candidates)

    entry = {
        "old": {"identified_sid": o_sid, "score": float(o_score)},
        "new": {"identified_sid": n_sid, "score": float(n_score)},
        "embeddings_equal": bool(emb_equal),
        "outputs_match": bool(o_sid == n_sid and float(o_score) == float(n_score)),
    }
    report["voice"][clip] = entry
    print(
        f"{clip}: old=({o_sid}, {float(o_score):.6f}) new=({n_sid}, {float(n_score):.6f}) "
        f"| emb_equal={emb_equal} | match={entry['outputs_match']}"
    )

# Build a bulk clip: alice_probe + 1.2s silence + bob_probe
a, sr_a = sf.read(asset("alice_probe.wav"))
b, sr_b = sf.read(asset("bob_probe.wav"))
assert sr_a == sr_b
silence = np.zeros(int(sr_a * 1.2))
bulk = np.concatenate([a, silence, b])
sf.write(asset("bulk.wav"), bulk, sr_a)

bulk_bytes = read_bytes(asset("bulk.wav"))
o_bulk = old_voice.process_bulk_audio(bulk_bytes, candidates)
n_bulk = new_voice.process_bulk_audio(bulk_bytes, candidates)
bulk_entry = {
    "old": {str(k): float(v) for k, v in o_bulk.items()},
    "new": {str(k): float(v) for k, v in n_bulk.items()},
    "outputs_match": bool(o_bulk == n_bulk),
}
report["voice"]["bulk.wav (alice + 1.2s silence + bob)"] = bulk_entry
print(f"bulk.wav: old={ {k: round(float(v), 6) for k, v in o_bulk.items()} } "
      f"new={ {k: round(float(v), 6) for k, v in n_bulk.items()} } | match={bulk_entry['outputs_match']}")

# ---------------------------------------------------------------------------
# PREPROCESSING: convert('RGB') vs raw Image.open on the student-login path
# ---------------------------------------------------------------------------
print("\n== PREPROCESSING: np.array(Image.open(f)) vs np.array(Image.open(f).convert('RGB')) ==")
for image_name in ["obama2.jpg", "two_people.jpg"]:
    raw = np.array(Image.open(asset(image_name)))
    conv = np.array(Image.open(asset(image_name)).convert("RGB"))
    arrays_identical = bool(np.array_equal(raw, conv))

    o_raw = old_face.predict_attendance(raw)
    o_conv = old_face.predict_attendance(conv)
    outputs_identical = bool(
        o_raw[0] == o_conv[0] and o_raw[1] == o_conv[1] and o_raw[2] == o_conv[2]
    )
    report["preprocessing"][image_name] = {
        "pil_mode": Image.open(asset(image_name)).mode,
        "arrays_bitwise_identical": arrays_identical,
        "old_pipeline_raw_output": {"detected": {str(k): v for k, v in o_raw[0].items()}, "num_faces": o_raw[2]},
        "old_pipeline_convert_output": {"detected": {str(k): v for k, v in o_conv[0].items()}, "num_faces": o_conv[2]},
        "outputs_identical": outputs_identical,
    }
    print(f"{image_name} (mode={Image.open(asset(image_name)).mode}): arrays_identical={arrays_identical}, outputs_identical={outputs_identical}")

# RGBA PNG: what each preprocessing does with an alpha channel
rgba_path = asset("obama2_rgba.png")
Image.open(asset("obama2.jpg")).convert("RGBA").save(rgba_path)

rgba_raw = np.array(Image.open(rgba_path))  # HxWx4 — the old student-login path
rgba_conv = np.array(Image.open(rgba_path).convert("RGB"))  # HxWx3 — new path

try:
    o_rgba_raw = old_face.predict_attendance(rgba_raw)
    raw_result = {"detected": {str(k): v for k, v in o_rgba_raw[0].items()}, "num_faces": o_rgba_raw[2], "error": None}
except Exception as e:
    raw_result = {"error": f"{type(e).__name__}: {e}"}

o_rgba_conv = old_face.predict_attendance(rgba_conv)
report["preprocessing"]["obama2_rgba.png"] = {
    "raw_array_shape": list(rgba_raw.shape),
    "old_pipeline_on_raw_rgba": raw_result,
    "old_pipeline_on_converted_rgb": {
        "detected": {str(k): v for k, v in o_rgba_conv[0].items()},
        "num_faces": o_rgba_conv[2],
    },
}
print(f"obama2_rgba.png raw (shape {rgba_raw.shape}): {raw_result}")
print(f"obama2_rgba.png convert('RGB'): detected={o_rgba_conv[0]} num_faces={o_rgba_conv[2]}")

with open(os.path.join(HERE, "parity_report.json"), "w") as f:
    json.dump(report, f, indent=2)

all_match = (
    all(v["outputs_match"] for v in report["face"].values())
    and all(v["outputs_match"] for v in report["voice"].values())
)
print(f"\nALL PIPELINE OUTPUTS MATCH: {all_match}")
print("Report written to verification/parity_report.json")
