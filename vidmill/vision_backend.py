"""Optional local vision backend: image/text embeddings for editing.

This is vidmill's own thin wrapper around an installed Hugging Face
image-text model. Nothing here is required for the free editing path:
scene detection, frame extraction, tags and search all degrade to
colour/transcript heuristics when the backend is absent.

The model is loaded lazily, kept on the local machine and never uploads
footage. Set VIDMILL_VISION_MODEL to use another compatible checkpoint.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from . import ToolError

DEFAULT_MODEL = os.environ.get("VIDMILL_VISION_MODEL", "openai/clip-vit-base-patch32")
INSTALL_HINT = "pip install 'vidmill[vision]'"


def _spec(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def libraries() -> dict:
    """Cheap availability check (does not import torch)."""
    return {
        "torch": _spec("torch"),
        "transformers": _spec("transformers"),
        "pillow": _spec("PIL"),
        "numpy": _spec("numpy"),
    }


def device_name(torch) -> str:
    """Pick the best usable device without forcing a GPU."""
    try:
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    try:
        mps = getattr(torch.backends, "mps", None)
        if mps is not None and mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def model_cached(model: str) -> bool:
    """Best-effort check for a local Hugging Face snapshot."""
    hub = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"
    folder = "models--" + str(model).replace("/", "--")
    return (hub / folder).is_dir()


def status(model: str | None = None) -> dict:
    """Report whether semantic vision can run, without downloading anything."""
    model = model or DEFAULT_MODEL
    libs = libraries()
    missing = [n for n, ok in libs.items() if not ok and n in ("torch", "transformers", "pillow")]
    out = {
        "available": not missing,
        "model": model,
        "installed": libs,
        "cached": model_cached(model),
        "device": None,
        "torch": None,
        "transformers": None,
        "reason": None,
        "install": INSTALL_HINT,
    }
    if missing:
        out["reason"] = "missing " + ", ".join(missing)
        return out
    try:
        import torch
        import transformers
        out["torch"] = getattr(torch, "__version__", "?")
        out["transformers"] = getattr(transformers, "__version__", "?")
        out["device"] = device_name(torch)
    except Exception as e:  # broken installs are common; never crash `check`
        out["available"] = False
        out["reason"] = f"{type(e).__name__}: {e}"
    return out


def softmax_rows(values, scale: float = 1.0):
    """Softmax over the last axis without requiring a deep-learning stack."""
    import numpy as np
    x = np.asarray(values, dtype=np.float32) * float(scale)
    x = x - x.max(axis=1, keepdims=True)
    e = np.exp(x)
    return e / np.maximum(e.sum(axis=1, keepdims=True), 1e-9)


def normalize_rows(values):
    import numpy as np
    a = np.asarray(values, dtype=np.float32)
    n = np.linalg.norm(a, axis=1, keepdims=True)
    return a / np.maximum(n, 1e-9)


class VisionBackend:
    """Lazy local image-text model.

    Supports any Transformers checkpoint exposing `get_image_features`
    and `get_text_features` (CLIP, SigLIP and compatible derivatives).
    """

    def __init__(self, model: str | None = None, device: str = "auto",
                 verbose: bool = True):
        self.model_name = model or DEFAULT_MODEL
        self.device_pref = (device or "auto").lower()
        self.verbose = verbose
        self.torch = None
        self.processor = None
        self.model = None
        self.device = None
        self.dim: int | None = None
        self.model_type = ""

    # ------------------------------------------------------------- loading

    def load(self) -> "VisionBackend":
        if self.model is not None:
            return self
        libs = libraries()
        missing = [n for n, ok in libs.items() if not ok and n in ("torch", "transformers", "pillow")]
        if missing:
            raise ToolError(
                "semantic vision is optional and its libraries are missing "
                f"({', '.join(missing)}). Install them with: {INSTALL_HINT}"
            )
        try:
            import torch
            import transformers
        except Exception as e:
            raise ToolError(f"could not import the vision backend: {e}") from e

        self.torch = torch
        if self.device_pref == "auto":
            self.device = device_name(torch)
        elif self.device_pref in ("cpu", "cuda", "mps"):
            self.device = self.device_pref
        else:
            raise ToolError("device must be auto, cpu, cuda or mps")
        if self.device == "cuda" and not torch.cuda.is_available():
            raise ToolError("CUDA was requested but is not available")
        if self.device == "mps" and not getattr(torch.backends, "mps", None):
            raise ToolError("MPS was requested but is not available")

        if self.verbose:
            print(f"loading vision model {self.model_name} on {self.device} "
                  f"(first run downloads it, then it stays local)...")
        try:
            self.processor = transformers.AutoProcessor.from_pretrained(self.model_name)
            self.model = transformers.AutoModel.from_pretrained(self.model_name)
        except Exception as e:
            raise ToolError(
                f"could not load vision model '{self.model_name}': {e}\n"
                "The model is downloaded once from Hugging Face. Check the name, "
                "network access and free disk space, or run with --semantic off."
            ) from e
        self.model.to(self.device)
        self.model.eval()
        self.model_type = str(getattr(getattr(self.model, "config", None), "model_type", "") or "")
        self.dim = (getattr(self.model.config, "projection_dim", None)
                    or getattr(self.model.config, "projection_size", None))
        return self

    # --------------------------------------------------------------- encode

    def _images(self, paths: list) -> list:
        try:
            from PIL import Image
        except ImportError as e:
            raise ToolError(f"Pillow is required for semantic vision: {INSTALL_HINT}") from e
        out = []
        for p in paths:
            try:
                with Image.open(p) as im:
                    out.append(im.convert("RGB"))
            except Exception as e:
                raise ToolError(f"could not read image {p}: {e}") from e
        return out

    def _run(self, fn, **inputs):
        torch = self.torch
        moved = {k: (v.to(self.device) if hasattr(v, "to") else v) for k, v in inputs.items()}
        with torch.inference_mode():
            feats = fn(**moved)
        # Transformers 5 returns a model-output object from the feature
        # helpers; older versions return the tensor directly. Support both.
        for attr in ("image_embeds", "text_embeds", "pooler_output"):
            value = getattr(feats, attr, None)
            if value is not None and hasattr(value, "float"):
                feats = value
                break
        if isinstance(feats, (tuple, list)) and feats:
            feats = feats[0]
        if not hasattr(feats, "float"):
            raise ToolError("the vision model returned an unsupported feature format")
        feats = torch.nn.functional.normalize(feats.float(), dim=-1)
        return feats.cpu().numpy()

    def encode_images(self, paths: list, batch_size: int = 8):
        self.load()
        import numpy as np
        paths = [str(p) for p in paths]
        if not paths:
            return np.zeros((0, int(self.dim or 0)), dtype=np.float32)
        chunks = []
        for i in range(0, len(paths), max(1, batch_size)):
            images = self._images(paths[i:i + batch_size])
            inputs = self.processor(images=images, return_tensors="pt")
            chunks.append(self._run(self.model.get_image_features, **inputs))
        vectors = np.concatenate(chunks, axis=0)
        self.dim = int(vectors.shape[1])
        return vectors

    def encode_texts(self, texts: list):
        self.load()
        import numpy as np
        texts = [str(t).strip() or " " for t in texts]
        if not texts:
            return np.zeros((0, int(self.dim or 0)), dtype=np.float32)
        kwargs = {"return_tensors": "pt", "truncation": True}
        if "siglip" in self.model_type:
            # SigLIP's tokenizer expects a fixed-length padded sequence.
            kwargs["padding"] = "max_length"
        else:
            kwargs["padding"] = True
        inputs = self.processor(text=texts, **kwargs)
        vectors = self._run(self.model.get_text_features, **inputs)
        self.dim = int(vectors.shape[1])
        return vectors

    # --------------------------------------------------------------- labels

    def label_scores(self, image_vectors, label_vectors, labels: list) -> list[dict]:
        """Zero-shot label probabilities for every image row."""
        import numpy as np
        sims = np.asarray(image_vectors, dtype=np.float32) @ np.asarray(label_vectors, dtype=np.float32).T
        scale = 100.0
        try:
            scale = float(self.model.logit_scale.exp().detach().cpu().item())
        except Exception:
            pass
        probs = softmax_rows(sims, max(1.0, min(scale, 200.0)))
        out = []
        for row in probs:
            ranked = sorted(zip(labels, row.tolist()), key=lambda kv: kv[1], reverse=True)
            out.append([{"label": name, "score": round(float(score), 4)}
                        for name, score in ranked])
        return out

    def info(self) -> dict:
        return {
            "model": self.model_name,
            "type": self.model_type or "image-text",
            "device": self.device,
            "dim": self.dim,
        }
