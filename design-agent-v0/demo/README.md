# Men's grooming design-vote demo

This demo uses the documented request in `request.json` and the generated
four-panel board `mens-grooming-board.png`.

Because no `GEMINI_API_KEY` or GCS credentials were available when this demo
was run, `run_demo.py` uses a deterministic `DemoVisionGateway` and local
artifact store. Everything after the model boundary is the production v0 path:
routing, capability gate, plan, tool registry, vote normalization, deterministic
rendering, verification contract, presentation, and trace.

Point `CURIFY_BACKEND_ROOT` at a Curify backend containing the integration patch:

~~~bash
CURIFY_BACKEND_ROOT=/path/to/curify-studio/curify_background \
  python design-agent-v0/demo/run_demo.py
~~~

Outputs are written to `demo/output/`.
