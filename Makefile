.PHONY: run demo test sweep blog clean
run:    ; ./run.sh
demo:   ; ./run.sh demo
test:   ; python -m pytest -q tests
sweep:  ; python -m hardware_ref sweep --out results
blog:   ; for n in blog/0*.md; do pandoc "$$n" -o "$${n%.md}.docx" --from gfm --to docx; done
clean:  ; rm -rf .venv .pytest_cache build dist *.egg-info hardware_ref/__pycache__ tests/__pycache__
