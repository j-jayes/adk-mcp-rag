# The difference between evalset.json files and test.json files

Here’s the short version:

* #️⃣ **Scope**

  * **`*.test.json`** = a *single* focused test (one session per file; great for “unit-test” style checks during development). ([Google GitHub][1])
  * **`*.evalset.json`** = a *collection* of tests (multiple, possibly long, multi-turn sessions in one file; better for broader “integration” checks). ([Google GitHub][1])

* 🧱 **Structure (both share the same schema concepts)**

  * Each contains **eval cases** with a **conversation** comprised of turns:

    * `user_content` (the prompt)
    * `final_response` (reference answer)
    * `intermediate_data.tool_uses` / `intermediate_responses` (expected tool-use trajectory)
      Same fields, just packaged differently (single vs many). ([Google GitHub][1])

* 🧪 **When to use which**

  * Use **`*.test.json`** for quick, repeatable checks while iterating (fast feedback, minimal complexity). ([Google GitHub][1])
  * Use **`*.evalset.json`** to simulate realistic workflows with longer, multi-turn sessions (run less frequently, “integration” flavor). ([Google GitHub][1])

* 🏷️ **File naming & runners**

  * Test files must end with **`.test.json`**; you can organize them in folders and add a **`test_config.json`** in that folder to set thresholds/criteria. ([Google GitHub][1])
  * Evalsets are commonly saved as **`.evalset.json`** and run via the ADK web UI or `adk eval` CLI (you can also target specific eval case IDs). ([GitHub][2])

* 📏 **Scoring/criteria**

  * Criteria include (defaults shown in docs):

    * `tool_trajectory_avg_score` (default required: **1.0**)
    * `response_match_score` (ROUGE; default pass: **0.8**)
  * For **test files**, you can override per-folder via **`test_config.json`**. The same metrics apply when running evalsets from the UI/CLI. ([Google GitHub][1])

* ☁️ **Service note**

  * Running **evalsets** through the ADK UI/CLI hooks into **Vertex Gen AI Evaluation Service** (a paid API). Test files are typically used locally (e.g., with `pytest`) for fast dev loops. ([Google GitHub][1])

* 🔄 **Migration**

  * If you have older, non-Pydantic files:

    * For **test files**: use `AgentEvaluator.migrate_eval_data_to_new_schema`. ([Google GitHub][1])
    * For **evalsets**: UI-managed sets are fine; manually maintained older formats are still supported by CLI, with a migration tool “in the works.” ([Google GitHub][1])

If you want, I can draft a minimal example pair (one `foo.test.json` and one `my_suite.evalset.json`) that matches how you’re evaluating your agent today.

[1]: https://google.github.io/adk-docs/evaluate/ "Why Evaluate Agents - Agent Development Kit"
[2]: https://github.com/google/adk-python/issues/1036?utm_source=chatgpt.com "Better option for obtaining Agent Evaluation results in a ..."
