"""Perception contracts without optional models, optional installs, or network."""
from __future__ import annotations

from contextlib import nullcontext
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
from PIL import Image
import pytest

from northcel.cli import build_parser, main
from northcel import perceive


# Literal contracts: do not derive expected diagnostics from the implementation.
HINTS = {
    "segment": 'SAM 2 is unavailable. Install with: python3 -m pip install "git+https://github.com/facebookresearch/sam2.git". Licence: Apache-2.0 (code and official checkpoints; optional cc_torch: BSD-3-Clause). Supply a local --checkpoint and --config; no model is downloaded by NorthCel.',
    "vectorize": 'VTracer is unavailable. Install with: python3 -m pip install "vtracer==0.6.11". Licence: MIT. The fit --stacked fallback requires already-installed northcel[fit].',
    "flow": 'RAFT is unavailable. Install with: python3 -m pip install torch torchvision (choose compatible builds at https://pytorch.org/get-started/locally/). Licence: BSD-3-Clause (TorchVision/RAFT), BSD-style (PyTorch). Supply a local --checkpoint; no model is downloaded by NorthCel.',
    "guide": 'FILM is unavailable. Install with: python3 -m pip install tensorflow. Licence: Apache-2.0 (TensorFlow and FILM code). Supply a local FILM SavedModel with --model-dir and check its weight licence; no model is downloaded by NorthCel. Guides are not output frames or quality evidence.',
}
LOCATIONS = {"segment": "sam2", "vectorize": "vtracer", "flow": "torchvision", "guide": "tensorflow"}
OPTIONAL = {"sam2", "sam3", "vtracer", "torch", "torchvision", "tensorflow", "film", "rife", "cv2", "skimage"}


@pytest.fixture
def files(tmp_path):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    Image.new("RGB", (40, 24), (0, 20, 40)).save(a)
    Image.new("RGB", (40, 24), (100, 120, 140)).save(b)
    checkpoint = tmp_path / "local.pt"
    checkpoint.write_bytes(b"fake local weights")
    model = tmp_path / "model"
    model.mkdir()
    (model / "saved_model.pb").write_bytes(b"fake local SavedModel")
    return SimpleNamespace(a=a, b=b, checkpoint=checkpoint, model=model, out=tmp_path / "out")


@pytest.fixture
def backends(monkeypatch):
    """Only named fakes are importable; never use an installed ML dependency."""
    modules, imports = {}, []
    original = importlib.import_module

    def load(name, *args, **kwargs):
        if name.split(".")[0] in OPTIONAL:
            imports.append(name)
            if name not in modules:
                raise ModuleNotFoundError(name)
            value = modules[name]
            if isinstance(value, Exception):
                raise value
            return value
        return original(name, *args, **kwargs)

    monkeypatch.setattr(perceive.importlib, "import_module", load)
    monkeypatch.setattr(perceive.metadata, "version", lambda name: "test-1.0")
    for name in ("NORTHCEL_SAM2_CHECKPOINT", "NORTHCEL_SAM2_CONFIG", "NORTHCEL_RAFT_CHECKPOINT", "NORTHCEL_FILM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    return SimpleNamespace(modules=modules, imports=imports)


def arguments(command, files, *, as_json=True):
    inputs = [str(files.a), "--points", "3,4"] if command == "segment" else (
        [str(files.a)] if command == "vectorize" else [str(files.a), str(files.b)])
    return ["perceive", command, *inputs, "--out", str(files.out), *(["--json"] if as_json else [])]


def invoke(args, capsys):
    code = main(args)
    captured = capsys.readouterr()
    return code, json.loads(captured.out), captured.err


@pytest.mark.parametrize("command", list(HINTS))
@pytest.mark.parametrize("as_json", [False, True])
def test_exact_absent_dependency_errors(command, as_json, files, backends, capsys):
    code = main(arguments(command, files, as_json=as_json))
    captured = capsys.readouterr()
    assert code == 1
    assert "Traceback" not in captured.err + captured.out
    if as_json:
        result = json.loads(captured.out)
        assert captured.err == ""
        assert result["errors"] == [{"location": LOCATIONS[command], "message": HINTS[command]}]
        assert result["ok"] is False
        assert result["executed"] is False
        assert result["available"] is False
        assert result["version"] is None
        assert result["input"][0] == str(files.a)
        assert result["output"] == {"requested": str(files.out)}
        if command == "guide":
            assert result["guide_only"] is True
    else:
        assert captured.out == ""
        assert captured.err == f"{LOCATIONS[command]}: error: {HINTS[command]}\n"
    assert not files.out.exists()


def test_no_optional_imports_during_package_cli_or_parser_import():
    script = '''
import importlib.abc
import sys
class BlockOptional(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname.split('.')[0] in {'sam2', 'sam3', 'vtracer', 'torch', 'torchvision', 'tensorflow', 'film', 'rife', 'cv2', 'skimage'}:
            raise AssertionError('optional import at startup: ' + fullname)
sys.meta_path.insert(0, BlockOptional())
import northcel
import northcel.perceive
import northcel.cli
import northcel.launcher.cli
northcel.cli.build_parser()
print('no optional imports')
'''
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == "no optional imports\n"


@pytest.mark.parametrize("extra", [[], ["--points", "1,2", "--boxes", "0,0,3,3"], ["--points", "1,2", "--text", "region"]])
def test_parser_requires_exclusive_prompts_and_rejects_text(extra, files, backends, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["perceive", "segment", str(files.a), "--out", str(files.out), *extra])
    assert exc.value.code == 2
    assert backends.imports == []


def test_parser_repeated_points_and_multiple_boxes(files, backends):
    parser = build_parser()
    points = parser.parse_args(arguments("segment", files) + ["--points", "5,6"])
    assert points.points == ["3,4", "5,6"]
    boxes = parser.parse_args(["perceive", "segment", str(files.a), "--boxes", "0,0,4,4", "5,5,8,8",
                               "--boxes", "9,9,12,12", "--out", str(files.out)])
    assert boxes.boxes == ["0,0,4,4", "5,5,8,8", "9,9,12,12"]
    assert backends.imports == []


@pytest.mark.parametrize("prompt", ["nan,2", "inf,2", "x,2", "1", "1,2,3", "-1,2", "40,2"])
def test_bad_point_has_located_json_error(prompt, files, backends, capsys):
    args = arguments("segment", files)
    args[args.index("--points") + 1] = prompt
    # argparse treats a negative comma pair as an option unless attached with '='.
    index = args.index("--points")
    args[index:index + 2] = [f"--points={prompt}"]
    code, result, _ = invoke(args, capsys)
    assert code == 1
    assert result["errors"][0]["location"] == "--points"
    assert backends.imports == []


@pytest.mark.parametrize("box", ["2,2,1,4", "1,1,1,3", "0,0,4", "0,0,nan,3"])
def test_bad_boxes(box, files, backends, capsys):
    code, result, _ = invoke(["perceive", "segment", str(files.a), "--boxes", box,
                              "--out", str(files.out), "--json"], capsys)
    assert code == 1
    assert result["errors"][0]["location"] == "--boxes"


def fake_sam(backends, *, video=False):
    calls = []

    class Predictor:
        def __init__(self, model):
            calls.append(("model", model))

        def set_image(self, image):
            self.image = image

        def predict(self, **kwargs):
            calls.append(("predict", kwargs))
            print("SAM progress banner")
            mask = np.zeros((1, *self.image.shape[:2]), dtype=bool)
            mask[:, 2:6, 3:8] = True
            return mask, np.array([0.75]), None

    def build(config, checkpoint, **kwargs):
        calls.append(("build", config, checkpoint, kwargs))
        return "local model"

    backends.modules.update({"sam2": SimpleNamespace(__version__="fake"),
                             "torch": SimpleNamespace(inference_mode=nullcontext),
                             "sam2.build_sam": SimpleNamespace(build_sam2=build),
                             "sam2.sam2_image_predictor": SimpleNamespace(SAM2ImagePredictor=Predictor)})
    if video:
        class Video:
            def init_state(self, **kwargs):
                calls.append(("init", kwargs))
                return "state"

            def add_new_points_or_box(self, **kwargs):
                calls.append(("seed", kwargs))

            def propagate_in_video(self, state):
                assert state == "state"
                for frame in range(2):
                    yield frame, [1], np.ones((1, 1, 24, 40))

        backends.modules["sam2.build_sam"].build_sam2_video_predictor = lambda *a, **kw: Video()
    return calls


def test_sam_points_masks_and_json_stdout(files, backends, capsys):
    calls = fake_sam(backends)
    code, result, stderr = invoke(arguments("segment", files) + ["--checkpoint", str(files.checkpoint),
                                                              "--points", "6,7"], capsys)
    assert code == 0
    assert stderr == "SAM progress banner\n"
    assert result["tool"] == "sam2"
    assert result["version"] == "test-1.0"
    assert result["available"] is result["executed"] is True
    row = result["output"]["masks"][0]
    assert row["area_px"] == 20
    assert row["bbox"] == [3, 2, 8, 6]
    assert row["score"] == 0.75
    with Image.open(row["path"]) as mask:
        assert mask.mode == "L"
        assert mask.size == (40, 24)
        assert set(np.unique(mask)) == {0, 255}
    assert json.loads(Path(result["output"]["receipt"]).read_text()) == result
    np.testing.assert_array_equal(calls[-1][1]["point_coords"], [[3, 4], [6, 7]])
    np.testing.assert_array_equal(calls[-1][1]["point_labels"], [1, 1])
    assert calls[0][0] == "build"
    assert calls[0][2] == str(files.checkpoint)
    assert calls[0][3] == {"device": "cpu"}
    assert not any(name.split(".")[0] in {"vtracer", "tensorflow", "torchvision"} for name in backends.imports)


def test_sam_boxes_are_separate_objects(files, backends, capsys):
    calls = fake_sam(backends)
    code, result, _ = invoke(["perceive", "segment", str(files.a), "--boxes", "0,0,10,10", "12,2,20,20",
                              "--checkpoint", str(files.checkpoint), "--out", str(files.out), "--json"], capsys)
    assert code == 0
    assert [row["object_id"] for row in result["output"]["masks"]] == [1, 2]
    predictions = [call[1] for call in calls if call[0] == "predict"]
    assert len(predictions) == 2
    assert predictions[0]["point_coords"] is None
    np.testing.assert_array_equal(predictions[1]["box"], [12, 2, 20, 20])


@pytest.mark.parametrize("checkpoint", [None, "missing.pt", "https://example.invalid/model.pt"])
def test_sam_requires_local_checkpoint(checkpoint, files, backends, capsys):
    calls = fake_sam(backends)
    args = arguments("segment", files)
    if checkpoint:
        args += ["--checkpoint", checkpoint]
    code, result, _ = invoke(args, capsys)
    assert code == 1
    assert result["available"] is True
    assert result["executed"] is False
    assert result["errors"][0]["location"] == "--checkpoint"
    assert calls == []


def test_sam_checkpoint_environment_is_explicit_configuration(files, backends, monkeypatch, capsys):
    fake_sam(backends)
    monkeypatch.setenv("NORTHCEL_SAM2_CHECKPOINT", str(files.checkpoint))
    code, result, _ = invoke(arguments("segment", files), capsys)
    assert code == 0
    assert result["model"]["checkpoint"] == str(files.checkpoint)


def test_sam_missing_transitive_dependency_has_exact_hint(files, backends, capsys):
    fake_sam(backends)
    del backends.modules["torch"]
    code, result, _ = invoke(arguments("segment", files), capsys)
    assert code == 1
    assert result["available"] is False
    assert result["errors"] == [{"location": "sam2", "message": HINTS["segment"]}]


def video_arguments(files):
    directory = files.a.parent / "frames"
    directory.mkdir()
    for index in (0, 10):
        Image.new("RGB", (40, 24), "white").save(directory / f"{index:05d}.jpg")
    return ["perceive", "segment", str(directory / "00000.jpg"), "--points", "3,4", "--frames", str(directory),
            "--checkpoint", str(files.checkpoint), "--out", str(files.out), "--json"]


def test_sam_propagates_masks_in_numeric_frame_order(files, backends, capsys):
    calls = fake_sam(backends, video=True)
    code, result, _ = invoke(video_arguments(files), capsys)
    assert code == 0
    assert result["propagation"] == {"requested": True, "executed": True}
    assert [row["frame"] for row in result["output"]["masks"]] == [0, 1]
    assert [row["area_px"] for row in result["output"]["masks"]] == [960, 960]
    assert result["input"][1].endswith("00010.jpg")
    assert calls[0][0] == "init"
    assert calls[1][0] == "seed"
    assert calls[1][1]["frame_idx"] == 0


def test_sam_without_video_api_is_honest(files, backends, capsys):
    fake_sam(backends)
    code, result, _ = invoke(video_arguments(files), capsys)
    assert code == 1
    assert result["executed"] is False
    assert result["propagation"]["executed"] is False
    assert result["errors"][0]["location"] == "--frames"
    assert "no video predictor API" in result["errors"][0]["message"]


@pytest.mark.parametrize("problem", ["wrong_seed", "bad_names", "empty", "different_size", "duplicate"])
def test_sam_validates_video_inputs(problem, files, backends, capsys):
    fake_sam(backends, video=True)
    args = video_arguments(files)
    directory = Path(args[args.index("--frames") + 1])
    if problem == "wrong_seed":
        args[2] = str(files.a)
    elif problem == "bad_names":
        (directory / "00010.jpg").rename(directory / "other.jpg")
    elif problem == "empty":
        args[args.index("--frames") + 1] = str(files.out)
    elif problem == "different_size":
        Image.new("RGB", (10, 10)).save(directory / "00010.jpg")
    else:
        Image.new("RGB", (40, 24)).save(directory / "0.jpg")
    code, result, _ = invoke(args, capsys)
    assert code == 1
    assert result["executed"] is False
    assert result["propagation"]["executed"] is False


def fake_vtracer(backends, *, svg='<svg xmlns="http://www.w3.org/2000/svg"></svg>'):
    calls = []

    def convert(pixels, size, **kwargs):
        calls.append((pixels, size, kwargs))
        print("VTracer banner")
        return svg

    backends.modules["vtracer"] = SimpleNamespace(convert_pixels_to_svg=convert)
    return calls


def test_vectorize_svg_uses_stacked_mode_and_pillow_pixels(files, backends, capsys):
    calls = fake_vtracer(backends)
    files.out = files.out.with_suffix(".svg")
    code, result, stderr = invoke(arguments("vectorize", files), capsys)
    assert code == 0
    assert stderr == "VTracer banner\n"
    assert result["executed"] is True
    assert result["fallback"] is None
    assert result["output"]["format"] == "svg"
    assert files.out.read_text().startswith("<svg")
    assert calls[0][1] == (40, 24)
    assert calls[0][0][0] == (0, 20, 40, 255)
    assert calls[0][2] == {"colormode": "color", "hierarchical": "stacked", "mode": "spline"}
    assert json.loads(Path(str(files.out) + ".json").read_text()) == result
    assert backends.imports == ["vtracer"]


@pytest.mark.parametrize("installed", [True, False])
def test_vectorize_rejects_misleading_output_extensions(installed, files, backends, capsys):
    if installed:
        fake_vtracer(backends)
        files.out = files.out.with_suffix(".ncel")
    else:
        backends.modules.update({"cv2": SimpleNamespace(), "skimage.measure": SimpleNamespace()})
        files.out = files.out.with_suffix(".svg")
    code, result, _ = invoke(arguments("vectorize", files), capsys)
    assert code == 1
    assert result["errors"][0]["location"] == "--out"
    assert not files.out.exists()


def test_vectorize_fit_fallback_is_not_claimed_as_vtracer(files, backends, monkeypatch, capsys):
    from northcel import fitting, shapes

    calls = []
    backends.modules.update({"cv2": SimpleNamespace(), "skimage.measure": SimpleNamespace()})
    monkeypatch.setattr(fitting, "fit_stacked", lambda image: (calls.append(image.size), {"quality": "unreviewed"}))
    monkeypatch.setattr(shapes, "stacked_source", lambda drawing: 'northcel "0.3.0-draft"\nscene Fake {}\n')
    files.out = files.out.with_suffix(".ncel")
    code, result, _ = invoke(arguments("vectorize", files), capsys)
    assert code == 0
    assert result["tool"] == "vtracer"
    assert result["available"] is False
    assert result["executed"] is False
    assert result["fallback"]["executed"] is True
    assert result["fallback"]["tool"] == "northcel fit --stacked"
    assert result["output"]["format"] == "northcel"
    assert result["warnings"] == [HINTS["vectorize"]]
    assert calls == [(40, 24)]
    assert files.out.read_text().startswith("northcel")


def test_vectorize_does_not_fallback_on_backend_runtime_failure(files, backends, capsys):
    fake_vtracer(backends, svg=None)
    files.out = files.out.with_suffix(".svg")
    code, result, _ = invoke(arguments("vectorize", files), capsys)
    assert code == 1
    assert result["executed"] is True
    assert "did not return SVG" in result["errors"][0]["message"]
    assert backends.imports == ["vtracer"]


class Tensor:
    """Small NumPy-backed torch-like tensor, only for the adapter contract."""
    def __init__(self, value):
        self.value = np.asarray(value)

    def float(self):
        return Tensor(self.value.astype(np.float32))

    def unsqueeze(self, dim):
        return Tensor(np.expand_dims(self.value, dim))

    def to(self, device):
        return self

    def __truediv__(self, other):
        return Tensor(self.value / other)

    def __sub__(self, other):
        return Tensor(self.value - other)

    def __getitem__(self, index):
        return Tensor(self.value[index])

    def detach(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self.value


def fake_raft(backends, *, vector=(3, 4)):
    calls = []

    class Model:
        def load_state_dict(self, state):
            assert state == "local state dict"

        def to(self, device):
            calls.append(("device", device))
            return self

        def eval(self):
            return self

        def __call__(self, a, b, **kwargs):
            calls.append(("infer", a.value, b.value, kwargs))
            height, width = a.value.shape[-2:]
            flow = np.broadcast_to(np.asarray(vector)[:, None, None], (2, height, width)).copy()
            return [Tensor(flow[None])]

    def builder(**kwargs):
        calls.append(("build", kwargs))
        return Model()

    def load(path, **kwargs):
        calls.append(("load", path, kwargs))
        return "local state dict"

    def pad(tensor, padding, **kwargs):
        assert kwargs == {"mode": "replicate"}
        _, right, _, bottom = padding
        return Tensor(np.pad(tensor.value, ((0, 0), (0, 0), (0, bottom), (0, right)), mode="edge"))

    backends.modules.update({"torchvision": SimpleNamespace(),
                             "torchvision.models.optical_flow": SimpleNamespace(raft_small=builder, raft_large=builder),
                             "torch": SimpleNamespace(load=load, from_numpy=Tensor, inference_mode=nullcontext,
                                                      nn=SimpleNamespace(functional=SimpleNamespace(pad=pad)))})
    return calls


@pytest.mark.parametrize("architecture", ["small", "large"])
def test_raft_local_weights_flow_image_and_motion_hints(architecture, files, backends, capsys):
    calls = fake_raft(backends)
    code, result, stderr = invoke(arguments("flow", files) + ["--checkpoint", str(files.checkpoint),
                                                           "--model", architecture], capsys)
    assert code == 0, stderr
    assert result["tool"] == "raft"
    assert result["available"] is result["executed"] is True
    assert result["motion"]["moving_pixels"] == 960
    assert result["motion"]["max_distance_px"] == 5
    assert result["motion"]["semantic_labels"] is False
    assert result["motion"]["regions"][0]["dx_px"] == 3
    assert result["motion"]["regions"][0]["dy_px"] == 4
    assert result["motion"]["regions"][1]["bbox"] == [32, 0, 40, 24]
    assert np.load(files.out / "flow.npy").shape == (24, 40, 2)
    with Image.open(result["output"]["visualization"]) as image:
        assert image.size == (40, 24)
        assert image.mode == "RGB"
        assert np.asarray(image).max() == 255
    assert calls[0] == ("build", {"weights": None, "progress": False})
    assert calls[1] == ("load", str(files.checkpoint), {"map_location": "cpu", "weights_only": True})
    assert calls[-1][1].shape == (1, 3, 128, 128)
    assert calls[-1][3] == {"num_flow_updates": 12}
    assert calls[-1][1][0, 0, 0, 0] == -1
    assert json.loads((files.out / "perception.json").read_text()) == result


def test_raft_zero_motion_is_finite_and_black(files, backends, capsys):
    fake_raft(backends, vector=(0, 0))
    code, result, _ = invoke(arguments("flow", files) + ["--checkpoint", str(files.checkpoint)], capsys)
    assert code == 0
    assert result["motion"]["moving_pixels"] == 0
    assert result["motion"]["regions"] == []
    with Image.open(files.out / "flow.png") as image:
        assert not np.asarray(image).any()


def test_raft_nonfinite_flow_is_traceback_free(files, backends, capsys):
    fake_raft(backends, vector=(np.nan, 1))
    code, result, _ = invoke(arguments("flow", files) + ["--checkpoint", str(files.checkpoint)], capsys)
    assert code == 1
    assert result["errors"][0]["location"] == "raft"
    assert not files.out.exists()


def test_raft_large_finite_vectors_do_not_overflow_json_statistics(files, backends, capsys):
    fake_raft(backends, vector=(np.float32(1e30), np.float32(1e30)))
    code, result, _ = invoke(arguments("flow", files) + ["--checkpoint", str(files.checkpoint)], capsys)
    assert code == 0
    assert np.isfinite(result["motion"]["max_distance_px"])
    assert np.isfinite(result["motion"]["regions"][0]["distance_px"])


def fake_film(backends, *, bad=None):
    calls = []

    def model(inputs, **kwargs):
        calls.append(("infer", inputs, kwargs))
        if bad == "shape":
            return {"image": np.zeros((2, 3))}
        if bad == "nan":
            return {"image": inputs["x0"] * np.nan}
        return {"image": Tensor((inputs["x0"] + inputs["x1"]) / 2)}

    def load(path):
        calls.append(("load", path))
        print("TensorFlow banner")
        return model

    backends.modules["tensorflow"] = SimpleNamespace(saved_model=SimpleNamespace(load=load))
    return calls


def test_film_midpoint_png_metadata_and_receipt_are_guide_only(files, backends, capsys):
    calls = fake_film(backends)
    code, result, stderr = invoke(arguments("guide", files) + ["--model-dir", str(files.model)], capsys)
    assert code == 0
    assert stderr == "TensorFlow banner\n"
    assert result["tool"] == "film"
    assert result["executed"] is True
    assert result["guide_only"] is result["suggestion_only"] is True
    assert result["quality"] == "unreviewed"
    frame = result["output"]["frames"][0]
    assert frame["t"] == 0.5
    assert frame["guide_only"] is True
    assert "guide-only" in frame["path"]
    with Image.open(frame["path"]) as image:
        assert image.info["guide_only"] == "true"
        assert "not an output frame" in image.info["usage"]
        assert image.size == (40, 24)
        np.testing.assert_array_equal(np.asarray(image)[0, 0], [50, 70, 90])
    assert calls[0] == ("load", str(files.model))
    assert calls[1][1]["x0"].shape == (1, 64, 64, 3)
    assert calls[1][1]["x0"].dtype == np.float32
    assert calls[1][1]["time"].tolist() == [[0.5]]
    assert calls[1][2] == {"training": False}
    assert backends.imports == ["tensorflow"]


@pytest.mark.parametrize("bad", ["shape", "nan"])
def test_film_validates_backend_outputs(bad, files, backends, capsys):
    fake_film(backends, bad=bad)
    code, result, _ = invoke(arguments("guide", files) + ["--model-dir", str(files.model)], capsys)
    assert code == 1
    assert result["guide_only"] is True
    assert result["errors"][0]["location"] == "film"
    assert not files.out.exists()


@pytest.mark.parametrize("command", ["flow", "guide"])
def test_pair_dimension_mismatch_is_located(command, files, backends, capsys):
    Image.new("RGB", (4, 4)).save(files.b)
    code, result, _ = invoke(arguments(command, files), capsys)
    assert code == 1
    assert result["errors"][0]["location"] == str(files.b)
    assert "resize explicitly" in result["errors"][0]["message"]
    assert backends.imports == []


@pytest.mark.parametrize("command", list(HINTS))
def test_missing_image_is_located_without_backend_import(command, files, backends, capsys):
    files.a = files.a.with_name("missing.png")
    code, result, _ = invoke(arguments(command, files), capsys)
    assert code == 1
    assert result["errors"][0]["location"] == str(files.a)
    assert result["executed"] is False
    assert backends.imports == []


@pytest.mark.parametrize("command", list(HINTS))
def test_vendor_exceptions_do_not_escape_command(command, files, backends, capsys):
    backends.modules[LOCATIONS[command]] = RuntimeError("incompatible binary")
    code, result, stderr = invoke(arguments(command, files), capsys)
    assert code == 1
    assert result["executed"] is False
    assert "incompatible binary" in result["errors"][0]["message"]
    assert "Traceback" not in stderr


def test_output_io_error_is_actionable_json(files, backends, capsys):
    fake_vtracer(backends)
    files.out = files.out / "drawing.svg"
    files.out.parent.write_text("not a directory")
    code, result, stderr = invoke(arguments("vectorize", files), capsys)
    assert code == 1
    assert result["ok"] is False
    assert "writable output paths" in result["errors"][0]["message"]
    assert "Traceback" not in stderr


def test_backend_version_without_distribution_metadata(files, backends, monkeypatch, capsys):
    fake_vtracer(backends)
    backends.modules["vtracer"].__version__ = "fake-pixel-api"
    def missing(name):
        raise perceive.metadata.PackageNotFoundError(name)
    monkeypatch.setattr(perceive.metadata, "version", missing)
    files.out = files.out.with_suffix(".svg")
    code, result, _ = invoke(arguments("vectorize", files), capsys)
    assert code == 0
    assert result["version"] == "fake-pixel-api"


def test_launcher_delegates_perception_without_native_probe(files, backends, monkeypatch, capsys):
    from northcel.launcher import cli as launcher

    monkeypatch.setattr(launcher.native, "available", lambda: pytest.fail("native must not be probed"))
    code = launcher.main(arguments("guide", files))
    captured = capsys.readouterr()
    assert code == 1
    result = json.loads(captured.out)
    assert result["errors"] == [{"location": "tensorflow", "message": HINTS["guide"]}]


def test_real_cli_absence_contract_without_optional_installs(files):
    # A fresh process with a blocker proves the public launcher/exit-code path.
    script = '''
import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, *args):
        if name.split('.')[0] in {'tensorflow', 'torch', 'torchvision', 'sam2', 'vtracer', 'cv2', 'skimage'}:
            raise ModuleNotFoundError(name)
sys.meta_path.insert(0, Block())
from northcel.launcher.cli import main
raise SystemExit(main(sys.argv[1:]))
'''
    proc = subprocess.run([sys.executable, "-c", script, *arguments("guide", files)],
                          capture_output=True, text=True, check=False, env=os.environ.copy())
    assert proc.returncode == 1
    assert proc.stderr == ""
    assert json.loads(proc.stdout)["errors"][0]["message"] == HINTS["guide"]


def test_native_backend_banners_cannot_corrupt_json_stdout(files, backends, capfd):
    def convert(*args, **kwargs):
        os.write(1, b"native stdout banner\n")
        return "<svg></svg>"
    backends.modules["vtracer"] = SimpleNamespace(convert_pixels_to_svg=convert)
    files.out = files.out.with_suffix(".svg")
    code, result, stderr = invoke(arguments("vectorize", files), capfd)
    assert code == 0
    assert result["ok"] is True
    assert stderr == "native stdout banner\n"


def test_stdout_descriptor_is_restored_after_backend_failure(files, backends, capfd):
    def convert(*args, **kwargs):
        os.write(1, b"native failed\n")
        raise RuntimeError("backend failure")
    backends.modules["vtracer"] = SimpleNamespace(convert_pixels_to_svg=convert)
    files.out = files.out.with_suffix(".svg")
    code, result, stderr = invoke(arguments("vectorize", files), capfd)
    assert code == 1
    assert result["executed"] is False
    assert stderr == "native failed\n"
    os.write(1, b"stdout restored\n")
    assert capfd.readouterr().out == "stdout restored\n"


def test_sam_boxes_allow_image_edge_upper_bounds(files, backends, capsys):
    fake_sam(backends)
    code, result, _ = invoke(["perceive", "segment", str(files.a), "--boxes", "0,0,40,24",
                              "--checkpoint", str(files.checkpoint), "--out", str(files.out), "--json"], capsys)
    assert code == 0
    assert result["executed"] is True


@pytest.mark.parametrize("command", ["flow", "guide"])
@pytest.mark.parametrize("path", [None, "missing", "https://example.invalid/weights"])
def test_flow_and_guide_require_local_models(command, path, files, backends, capsys):
    calls = fake_raft(backends) if command == "flow" else fake_film(backends)
    args = arguments(command, files)
    option = "--checkpoint" if command == "flow" else "--model-dir"
    if path:
        args += [option, path]
    code, result, _ = invoke(args, capsys)
    assert code == 1
    assert result["available"] is True
    assert result["executed"] is False
    assert result["errors"][0]["location"] == option
    assert calls == []


def test_film_requires_saved_model_marker(files, backends, capsys):
    calls = fake_film(backends)
    (files.model / "saved_model.pb").unlink()
    code, result, _ = invoke(arguments("guide", files) + ["--model-dir", str(files.model)], capsys)
    assert code == 1
    assert "saved_model.pb" in result["errors"][0]["message"]
    assert calls == []


def test_film_text_mode_labels_guide_only(files, backends, capsys):
    fake_film(backends)
    code = main(arguments("guide", files, as_json=False) + ["--model-dir", str(files.model)])
    captured = capsys.readouterr()
    assert code == 0
    assert "GUIDE ONLY; not output or quality evidence" in captured.out


def test_sam_rejects_nonfinite_scores(files, backends, capsys):
    fake_sam(backends)
    predictor = backends.modules["sam2.sam2_image_predictor"].SAM2ImagePredictor
    predictor.predict = lambda self, **kw: (np.ones((1, 24, 40)), np.array([np.nan]), None)
    code, result, _ = invoke(arguments("segment", files) + ["--checkpoint", str(files.checkpoint)], capsys)
    assert code == 1
    assert "non-finite mask score" in result["errors"][0]["message"]


def test_sam_incomplete_propagation_is_not_success(files, backends, capsys):
    fake_sam(backends, video=True)
    build = backends.modules["sam2.build_sam"].build_sam2_video_predictor
    def incomplete(*args, **kwargs):
        video = build(*args, **kwargs)
        video.propagate_in_video = lambda state: iter([(0, [1], np.ones((1, 1, 24, 40)))])
        return video
    backends.modules["sam2.build_sam"].build_sam2_video_predictor = incomplete
    code, result, _ = invoke(video_arguments(files), capsys)
    assert code == 1
    assert result["propagation"]["executed"] is False
    assert "incomplete propagation" in result["errors"][0]["message"]
    assert not (files.out / "perception.json").exists()
