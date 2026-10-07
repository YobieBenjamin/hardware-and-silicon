.PHONY: run demo test sweep clean
run:    ; ./run.sh
demo:   ; ./run.sh demo
test:   ; python -m pytest -q tests
sweep:  ; python -m hardware_ref sweep --out results
clean:  ; rm -rf .venv .pytest_cache build dist *.egg-info hardware_ref/__pycache__ tests/__pycache__
