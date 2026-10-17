"""Scoped compatibility for the existing accepted Diffusers GPU runtime only."""
import httpx
import huggingface_hub.utils as hub_utils
hub_utils.httpx=httpx
