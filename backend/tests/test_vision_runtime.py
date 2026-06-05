from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from backend.agents.vision_agent import VisionAgent
from backend.runtimes import openvino_vision_runtime as runtime
from backend.scripts import setup_openvino_models
from backend.services import video_processing, vision_analysis


class VisionRuntimeUnitTests(unittest.TestCase):
    def tearDown(self) -> None:
        runtime._runtime = None
        for key in (
            "VISION_DET_MODEL",
            "VISION_OCR_DET_MODEL",
            "VISION_OCR_REC_MODEL",
            "VISION_OCR_ALPHABET",
            "VISION_MODELS_DIR",
        ):
            os.environ.pop(key, None)

    def test_ir_path_requires_xml_and_sibling_bin(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            xml = Path(tmp) / "model.xml"
            xml.write_text("<xml />", encoding="utf-8")
            with self.assertRaises(runtime.VisionRuntimeConfigError):
                runtime._validate_ir_xml(str(xml), "VISION_DET_MODEL")
            xml.with_suffix(".bin").write_bytes(b"fake")
            self.assertEqual(runtime._validate_ir_xml(str(xml), "VISION_DET_MODEL"), xml)

    def test_invalid_config_returns_explicit_unavailable_runtime(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            os.environ["VISION_MODELS_DIR"] = tmp
            os.environ["VISION_DET_MODEL"] = "missing.xml"
            rt = runtime.get_runtime()
            self.assertFalse(rt.detect_available)
            self.assertFalse(rt.ocr_available)
            self.assertEqual(rt.backend, "openvino-unavailable")
            self.assertTrue(rt.configuration_errors)

    def test_auto_discovers_downloaded_default_models(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            base = Path(tmp)
            det = base / "ssdlite_mobilenet_v2_fp16" / "ssdlite_mobilenet_v2_fp16.xml"
            ocr_det = (
                base
                / "horizontal-text-detection-0001"
                / "FP32"
                / "horizontal-text-detection-0001.xml"
            )
            ocr_rec = base / "text-recognition-0012" / "FP32" / "text-recognition-0012.xml"
            for xml in (det, ocr_det, ocr_rec):
                xml.parent.mkdir(parents=True, exist_ok=True)
                xml.write_text("<xml />", encoding="utf-8")
                xml.with_suffix(".bin").write_bytes(b"fake")

            os.environ["VISION_MODELS_DIR"] = str(base)
            self.assertEqual(
                runtime.discovered_model_paths(),
                {
                    "VISION_DET_MODEL": str(det),
                    "VISION_OCR_DET_MODEL": str(ocr_det),
                    "VISION_OCR_REC_MODEL": str(ocr_rec),
                },
            )

    def test_explicit_env_model_path_wins_over_auto_discovery(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            base = Path(tmp)
            auto = base / "ssdlite_mobilenet_v2_fp16" / "ssdlite_mobilenet_v2_fp16.xml"
            explicit = base / "custom" / "model.xml"
            for xml in (auto, explicit):
                xml.parent.mkdir(parents=True, exist_ok=True)
                xml.write_text("<xml />", encoding="utf-8")
                xml.with_suffix(".bin").write_bytes(b"fake")

            os.environ["VISION_MODELS_DIR"] = str(base)
            os.environ["VISION_DET_MODEL"] = str(explicit)
            self.assertEqual(runtime.discovered_model_paths()["VISION_DET_MODEL"], str(explicit))

    def test_ssd_detection_parsing_keeps_existing_shape(self) -> None:
        raw = np.array([[[[0, 1, 0.91, 0.1, 0.2, 0.5, 0.8]]]], dtype=np.float32)
        parsed = runtime._parse_ssd_detections(raw, image_w=200, image_h=100, conf=0.5)
        self.assertEqual(
            parsed,
            [{"label": "person", "confidence": 0.91, "box": [20, 20, 100, 80]}],
        )

    def test_coco_sparse_label_ids_are_mapped(self) -> None:
        self.assertEqual(runtime._label_for(84), "book")
        self.assertEqual(runtime._label_for(90), "toothbrush")

    def test_ctc_decode_collapses_repeats_and_blank(self) -> None:
        alphabet = "ab"
        logits = np.array(
            [
                [0.9, 0.1, 0.0],
                [0.8, 0.2, 0.0],
                [0.0, 0.0, 1.0],
                [0.1, 0.8, 0.1],
            ],
            dtype=np.float32,
        )
        self.assertEqual(runtime._decode_ctc_output(logits, alphabet), "ab")

    def test_text_boxes_support_heatmap_output(self) -> None:
        heatmap = np.zeros((1, 1, 12, 12), dtype=np.float32)
        heatmap[0, 0, 2:5, 3:8] = 0.9
        boxes = runtime._parse_text_boxes(heatmap, image_w=120, image_h=120, conf=0.5)
        self.assertEqual(len(boxes), 1)
        self.assertGreater(boxes[0]["box"][2], boxes[0]["box"][0])
        self.assertGreater(boxes[0]["box"][3], boxes[0]["box"][1])

    def test_ocr_text_is_deduplicated_in_service_result(self) -> None:
        class _Runtime:
            backend = "fake-openvino"
            detect_available = False
            ocr_available = True
            configuration_errors: list[str] = []

            def ocr(self, image):
                return {"text": "Revenue\nRevenue", "regions": 1, "available": True}

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            import cv2

            frame = Path(tmp) / "frame.jpg"
            cv2.imwrite(str(frame), np.zeros((20, 20, 3), dtype=np.uint8))
            with patch.object(runtime, "get_runtime", return_value=_Runtime()):
                result = vision_analysis.run_ocr([str(frame), str(frame)])
        self.assertEqual(result["combined_text"], "Revenue")

    def test_vision_summary_hides_fallback_backend_for_object_question(self) -> None:
        summary = VisionAgent._summarize(
            "ANALYZE_OBJECTS",
            {
                "backend": "opencv-fallback",
                "detect_available": False,
                "label_counts": {},
            },
            {"backend": "opencv-fallback", "ocr_available": False, "combined_text": ""},
            {"contains_graphs": True, "graph_frame_count": 2},
        )
        self.assertIn("Object detection is not configured yet", summary)
        self.assertIn("Chart-like visuals appear in 2 sampled frame(s).", summary)
        self.assertNotIn("opencv-fallback", summary)
        self.assertNotIn("OCR: unavailable", summary)

    def test_vision_summary_is_intent_specific_when_models_are_missing(self) -> None:
        objects = {
            "backend": "opencv-fallback",
            "detect_available": False,
            "label_counts": {},
        }
        ocr = {"backend": "opencv-fallback", "ocr_available": False, "combined_text": ""}
        graphs = {"contains_graphs": False, "graph_frame_count": 0}
        count_summary = VisionAgent._summarize(
            "COUNT_OBJECTS",
            objects,
            ocr,
            graphs,
            {"target": "people", "max_in_single_frame": 0},
        )
        ocr_summary = VisionAgent._summarize("ANALYZE_OCR", objects, ocr, graphs)

        self.assertIn("cannot reliably count people", count_summary)
        self.assertNotIn("describe the objects", count_summary)
        self.assertIn("OCR is not configured yet", ocr_summary)
        self.assertNotIn("Object detection is not configured", ocr_summary)

    def test_model_setup_validation_requires_all_ir_pairs(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            models_dir = Path(tmp)
            det = models_dir / "ssdlite_mobilenet_v2_fp16" / "ssdlite_mobilenet_v2_fp16.xml"
            det.parent.mkdir(parents=True, exist_ok=True)
            det.write_text("<xml />", encoding="utf-8")
            det.with_suffix(".bin").write_bytes(b"fake")

            with self.assertRaises(RuntimeError):
                setup_openvino_models._validate(models_dir)


class VideoProcessingUnitTests(unittest.TestCase):
    def test_ffmpeg_empty_output_with_real_error_raises(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            video = Path(tmp) / "video.mp4"
            video.write_bytes(b"fake")

            class _Proc:
                returncode = 1
                stderr = "Invalid data found when processing input"

            with patch.object(video_processing, "_ffmpeg_exe", return_value="ffmpeg"):
                with patch("subprocess.run", return_value=_Proc()):
                    with self.assertRaises(video_processing.VideoProcessingError):
                        video_processing.extract_audio(str(video), output_dir=tmp)

    def test_ffmpeg_no_audio_marker_returns_no_audio(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            video = Path(tmp) / "video.mp4"
            video.write_bytes(b"fake")

            class _Proc:
                returncode = 1
                stderr = "Output file #0 does not contain any stream"

            with patch.object(video_processing, "_ffmpeg_exe", return_value="ffmpeg"):
                with patch("subprocess.run", return_value=_Proc()):
                    result = video_processing.extract_audio(str(video), output_dir=tmp)
        self.assertFalse(result["has_audio"])


if __name__ == "__main__":
    unittest.main()
