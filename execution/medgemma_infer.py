"""
Run local inference with google/medgemma-1.5-4b-it.

Usage examples:
  python execution/medgemma_infer.py
  python execution/medgemma_infer.py --image-url "https://.../image.jpg" --prompt "Describe findings"
  python execution/medgemma_infer.py --allow-cpu
"""

import argparse
import os
import sys

import torch
from dotenv import load_dotenv
from huggingface_hub import login
from transformers import AutoModelForImageTextToText, AutoProcessor


DEFAULT_MODEL = "google/medgemma-1.5-4b-it"
DEFAULT_IMAGE = "https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/p-blog/candy.JPG"
DEFAULT_PROMPT = "What animal is on the candy?"


def _build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MedGemma local image-text inference")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Hugging Face model id")
    parser.add_argument("--image-url", default=DEFAULT_IMAGE, help="Remote image URL")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Text prompt")
    parser.add_argument("--max-new-tokens", type=int, default=64, help="Generation length")
    parser.add_argument(
        "--allow-cpu",
        action="store_true",
        help="Run on CPU if CUDA is unavailable (much slower).",
    )
    return parser.parse_args()


def _ensure_login() -> None:
    token = os.getenv("HF_TOKEN", "").strip()
    if token:
        # huggingface_hub login signature varies across versions.
        try:
            login(token=token, skip_if_logged_in=True)
        except TypeError:
            login(token=token)
    else:
        print(
            "HF_TOKEN not found. Set HF_TOKEN in your environment or .env for gated model access.",
            file=sys.stderr,
        )


def main() -> int:
    load_dotenv()
    args = _build_args()

    has_cuda = torch.cuda.is_available()
    if not has_cuda and not args.allow_cpu:
        print(
            "CUDA is not available in this Python env. Install CUDA PyTorch or run with --allow-cpu.",
            file=sys.stderr,
        )
        return 1

    if has_cuda:
        dtype = torch.bfloat16
        device_label = f"cuda:{torch.cuda.current_device()} ({torch.cuda.get_device_name(0)})"
    else:
        dtype = torch.float32
        device_label = "cpu"

    _ensure_login()

    print(f"Loading model: {args.model}")
    print(f"Device: {device_label}")

    processor = AutoProcessor.from_pretrained(args.model)
    model = AutoModelForImageTextToText.from_pretrained(
        args.model,
        torch_dtype=dtype,
        device_map="auto",
    )

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "url": args.image_url},
                {"type": "text", "text": args.prompt},
            ],
        }
    ]

    inputs = processor.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device)

    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=args.max_new_tokens)

    decoded = processor.decode(
        outputs[0][inputs["input_ids"].shape[-1] :],
        skip_special_tokens=True,
    )
    print("\n=== Model Output ===")
    print(decoded.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
