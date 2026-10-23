#!/usr/bin/env python3
"""CPU-only public notebook UI/runtime integration contracts."""
import ast
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from kaggle_production_demo import ProductionDemo, STEP_NAMES, STEP_FOR_CELL, engine_notebook

public=json.loads((ROOT/"notebooks/kaggle-dual-gpu-production-demo.ipynb").read_text())
engine=engine_notebook(ROOT)
assert len(public["cells"])==28==len(engine["cells"])
assert len(STEP_NAMES)==12 and set(STEP_FOR_CELL)=={3,5,7,9,11,13,16,18,20,22,24,27}
for i,name in STEP_FOR_CELL.items():
    src="".join(public["cells"][i]["source"])
    ast.parse(src)
    if i != 3:
        assert src.strip()=="demo."+name+"()", (i,name,src)
    engine_src="".join(engine["cells"][i]["source"])
    ast.parse(engine_src)
    assert len(engine_src)>50 and i in range(28)
    assert public["cells"][i].get("execution_count") is None
    assert public["cells"][i].get("outputs")==[]
assert len("".join(public["cells"][3]["source"]).splitlines())<=42
# First-time setup explains precisely which resource type and revision to attach.
setup="".join(public["cells"][1]["source"])
assert "## Before running: set up Kaggle and attach both required inputs" in setup
assert "Input" in setup and "Add Input" in setup
assert "Models" in setup and "Datasets" in setup
assert "gguf" in setup and "q6-k" in setup and "version" in setup
assert "dangkhoa2016/unsloth-z-image-turbo-gguf" in setup
assert "dangkhoa2016/z-image-turbo-diffusers-support-components" in setup
assert "### 3. Add the supporting components" in setup
assert "### 3. Gắn support dataset" in setup
assert "Allow space for verified model staging" not in setup
assert "Automatic checks:" not in setup  # replaced with contextual instructions
assert "tự kiểm tra GPU, model" in setup
# Public history contains no shipped load-only notebook fixtures.
public_notebooks=sorted((ROOT/"notebooks").glob("*.ipynb"))
assert [p.name for p in public_notebooks]==["kaggle-dual-gpu-production-demo.ipynb"]
assert not (ROOT/"benchmarks/notebooks").exists()

assert len("".join(engine["cells"][9]["source"]).splitlines())>400
assert len("".join(engine["cells"][11]["source"]).splitlines())>400
assert "from kaggle_production_demo import ProductionDemo" in "".join(public["cells"][3]["source"])
assert 'os.environ["ZIMAGE_SOURCE_SHA"] = revision' in "".join(public["cells"][3]["source"])
for cell in public["cells"]:
    user_src="".join(cell["source"])
    assert "P25_" not in user_src and "P27_" not in user_src
    assert "diagnostics/kaggle-run-all" not in user_src
    assert "fix/studio-tmp-monitor" not in user_src
    assert "CPU review candidate" not in user_src

# The notebook is a user guide, not merely a collection of one-line calls.
# Regressions that remove substantial English/Vietnamese explanations must fail.
markdown=[(i,"".join(c["source"])) for i,c in enumerate(public["cells"])
          if c["cell_type"]=="markdown"]
assert len(markdown)==16
# The first bilingual title must identify the same named model in both languages.
intro=dict(markdown)[0]
assert intro.count("# Z-Image Turbo Q6_K — Create Images with Two Kaggle GPUs")==1
assert intro.count("# Z-Image Turbo Q6_K — Tạo ảnh bằng hai GPU trên Kaggle")==1
assert "Tạo ảnh AI bằng hai GPU" not in intro
assert "benchmarks/notebooks/" not in intro
assert "**Notebook to import:** `notebooks/kaggle-dual-gpu-production-demo.ipynb`" in intro
assert "**Notebook cần import:** `notebooks/kaggle-dual-gpu-production-demo.ipynb`" in intro
assert "historical benchmark experiments" not in intro
assert "các thí nghiệm benchmark trước đây" not in intro
assert "notebook duy nhất" not in intro

assert sum(len(content.splitlines()) for _,content in markdown)>=300
assert sum(len(content) for _,content in markdown)>=22000
for i,content in markdown:
    assert len(content.splitlines())>=14,(i,"Documentation too brief")
    assert len(content)>=950,(i,"Documentation lacks substance")
    assert "Language / Ngôn ngữ" not in content,(i,"Doc-style language switch leaked into notebook")
    assert "🌐" not in content,(i,"Decorative language switch leaked into notebook")
    assert content.count("**English**")==1,(i,"English section label missing/repeated")
    assert content.count("**Tiếng Việt**")==1,(i,"Vietnamese section label missing/repeated")
    assert "\n\n---\n\n" in content,(i,"Missing section divider")
    en,vi=content.split("\n\n---\n\n",1)
    assert len(en)>=450 and len(vi)>=200,(i,"One language is underspecified")
    ratio=len(vi)/len(en)
    assert 0.70<=ratio<=1.45,(i,"Bilingual instructions have unequal detail",ratio)
    assert "**English**" in en and "**Tiếng Việt**" in vi,(i,"Language labels misplaced")

for required in (
    "Tesla T4", "Run All", "SOURCE_SHA", "PIPELINE_READY",
    "NOTEBOOK_OWN_INFERENCE_PROOF", "GENERATED_IN_CURRENT_RUN",
    "SHA256", "p23-runall-acceptance.zip", "PENDING_BROWSER_VERIFICATION",
    "ARCHIVED", "Interrupt Cell", "Studio", "GPU0", "GPU1",
):
    assert any(required in body for _,body in markdown),("Missing user instruction",required)
assert sum(c["cell_type"]=="code" for c in public["cells"])==12

# Execute a minimal real shared-namespace smoke without GPU or network.
with tempfile.TemporaryDirectory(prefix="zimage-public-demo-") as temp:
    root=Path(temp)
    steps=root/"scripts/kaggle_demo_steps"
    steps.mkdir(parents=True)
    (steps/"source.py").write_text(
        "from pathlib import Path\nPROJECT=Path("+repr(str(root))+")\nshared=['source']\n",
        encoding="utf8")
    (steps/"inputs.py").write_text("shared.append('inputs')\n",encoding="utf8")
    demo=ProductionDemo(root)
    demo.source().inputs()
    assert demo.context["shared"]==["source","inputs"]
    assert demo.completed==["source","inputs"]
    try:demo.run("../../danger")
    except ValueError:pass
    else:raise AssertionError("Unknown step accepted")
    try:ProductionDemo(root).inputs()
    except RuntimeError:pass
    else:raise AssertionError("Input step permitted before source")

print("PUBLIC_NOTEBOOK_UI_CPU_PASS detailed_bilingual_markdown=16 concise_28cell_notebook 12_delegated_steps "
      "no_internal_notes shared_kernel_state staged_sha_pin invalid_step_rejected")
