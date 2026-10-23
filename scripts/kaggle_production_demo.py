"""Small public API for the Kaggle Z-Image GGUF dual-GPU demonstration.

The validated inference engine lives in kaggle_demo_steps/*.py. The steps
share one kernel namespace, just as the accepted original notebook did; this
preserves worker lifecycles, CUDA behavior and verification semantics.
"""
import ast
import json
from pathlib import Path


STEP_NAMES = (
    "source", "inputs", "dependencies", "encode", "generate", "verify",
    "studio", "consumer", "galleries", "gallery_links", "studio_link", "monitor",
)
CELL_NUMBERS = (3, 5, 7, 9, 11, 13, 16, 18, 20, 22, 24, 27)
STEP_FOR_CELL = dict(zip(CELL_NUMBERS, STEP_NAMES))
STEP_ROOT = Path(__file__).resolve().parent / "kaggle_demo_steps"


class ProductionDemo:
    """Run the verified demo steps in notebook order.

    A single namespace is intentionally retained between steps so existing
    GPU and Studio state is never reconstructed by a separate Python process.
    This is a compatibility boundary, not a new implementation of inference.
    """

    def __init__(self, project=None):
        self.project = Path(project).resolve() if project else Path(__file__).resolve().parents[1]
        self.context = {"__name__": "__main__", "__builtins__": __builtins__}
        self.completed = []

    def run(self, step):
        if step not in STEP_NAMES:
            raise ValueError("Unsupported production demo step: " + str(step))
        if step != "source" and "PROJECT" not in self.context:
            raise RuntimeError("Run the source step first.")
        path = self.project / "scripts" / "kaggle_demo_steps" / (step + ".py")
        if not path.is_file():
            raise RuntimeError("Required demo module is missing: " + str(path))
        content = path.read_text(encoding="utf8")
        ast.parse(content, filename=str(path))
        exec(compile(content, str(path), "exec"), self.context)
        if step == "source":
            self.project = Path(self.context["PROJECT"]).resolve()
        self.completed.append(step)
        return self

    def source(self): return self.run("source")
    def inputs(self): return self.run("inputs")
    def dependencies(self): return self.run("dependencies")
    def encode(self): return self.run("encode")
    def generate(self): return self.run("generate")
    def verify(self): return self.run("verify")
    def studio(self): return self.run("studio")
    def consumer(self): return self.run("consumer")
    def galleries(self): return self.run("galleries")
    def gallery_links(self): return self.run("gallery_links")
    def studio_link(self): return self.run("studio_link")
    def monitor(self): return self.run("monitor")


def engine_notebook(root):
    """Build a test-only view of the exact modules used by ProductionDemo.

    Legacy CPU contracts can inspect the actual inference source without
    keeping a second 2,000-line notebook in the public notebooks directory.
    """
    root = Path(root)
    data = json.loads((root / "notebooks" / "kaggle-dual-gpu-production-demo.ipynb").read_text(encoding="utf8"))
    assert len(data["cells"]) == 28
    for index, name in STEP_FOR_CELL.items():
        path = root / "scripts" / "kaggle_demo_steps" / (name + ".py")
        data["cells"][index]["source"] = path.read_text(encoding="utf8").splitlines(keepends=True)
    return data
