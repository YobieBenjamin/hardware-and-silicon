.PHONY: run demo test sweep blog blog-series figures clean
run:    ; ./run.sh
demo:   ; ./run.sh demo
test:   ; python -m pytest -q tests
sweep:  ; python -m hardware_ref sweep --out results
blog:   ; pandoc blog/01-a-multi-layer-approach-to-ai-safety.md -o blog/01-a-multi-layer-approach-to-ai-safety.docx --from gfm --to docx
figures: ; python3 blog/tools/make_figures.py blog/figures
blog-series: figures ; cd blog/tools && (test -d node_modules || npm install --silent) && node build.js ..
clean:  ; rm -rf .venv .pytest_cache build dist *.egg-info hardware_ref/__pycache__ tests/__pycache__
