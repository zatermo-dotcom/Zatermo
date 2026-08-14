#!/usr/bin/env python3
"""
LLM Council -- a faithful port of karpathy/llm-council to a single-file CLI.

Instead of asking one LLM, this convenes a "council" of models via OpenRouter
and runs a 3-stage deliberation:

  Stage 1 (First opinions): the query goes to every council model in parallel.
  Stage 2 (Review):         each model ranks the other, anonymized, responses.
  Stage 3 (Final response): a Chairman model synthesizes one final answer.

Only the Python standard library is used, so this runs anywhere `python3` does.

Usage:
  python3 council.py "your question here"
  python3 council.py --stage 1 "just collect first opinions"
  python3 council.py --json "question" > result.json
  python3 council.py --models openai/gpt-5.1,anthropic/claude-sonnet-4.5 \
                     --chairman anthropic/claude-sonnet-4.5 "question"

Environment:
  OPENROUTER_API_KEY   required. Also read from a .env file in CWD or repo root.

Reference: https://github.com/karpathy/llm-council
"""

import argparse
import concurrent.futures
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Defaults mirror karpathy/llm-council backend/config.py
DEFAULT_COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]
DEFAULT_CHAIRMAN_MODEL = "google/gemini-3-pro-preview"


# --------------------------------------------------------------------------- #
# Config / API key
# --------------------------------------------------------------------------- #
def load_env_file():
    """Populate os.environ from a .env file (CWD, then parents) if present."""
    candidates = []
    cwd = os.getcwd()
    path = cwd
    for _ in range(6):  # walk up a few levels toward a repo root
        candidates.append(os.path.join(path, ".env"))
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent

    for env_path in candidates:
        if not os.path.isfile(env_path):
            continue
        try:
            with open(env_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    os.environ.setdefault(key, value)
        except OSError:
            pass


def get_api_key():
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.stderr.write(
            "ERROR: OPENROUTER_API_KEY is not set.\n"
            "  Get a key at https://openrouter.ai/ and either export it:\n"
            "    export OPENROUTER_API_KEY=sk-or-v1-...\n"
            "  or add it to a .env file in the project root.\n"
        )
        sys.exit(2)
    return key


# --------------------------------------------------------------------------- #
# OpenRouter client (stdlib only) -- port of backend/openrouter.py
# --------------------------------------------------------------------------- #
def query_model(model, messages, api_key, timeout=120.0):
    """
    Query a single model via OpenRouter. Returns a dict with 'content' (and
    optional 'reasoning_details'), or None on failure -- graceful degradation.
    """
    payload = json.dumps({"model": model, "messages": messages}).encode("utf-8")
    request = urllib.request.Request(
        OPENROUTER_API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # OpenRouter attribution headers (optional but recommended)
            "HTTP-Referer": "https://github.com/karpathy/llm-council",
            "X-Title": "LLM Council (Claude skill)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        message = data["choices"][0]["message"]
        return {
            "content": message.get("content"),
            "reasoning_details": message.get("reasoning_details"),
        }
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")[:500]
        except Exception:
            pass
        sys.stderr.write(f"Error querying model {model}: HTTP {exc.code} {body}\n")
        return None
    except Exception as exc:  # noqa: BLE001 -- match upstream's broad catch
        sys.stderr.write(f"Error querying model {model}: {exc}\n")
        return None


def query_models_parallel(models, messages, api_key):
    """Query multiple models in parallel. Returns {model: response|None}."""
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(models)) as pool:
        future_to_model = {
            pool.submit(query_model, model, messages, api_key): model
            for model in models
        }
        for future in concurrent.futures.as_completed(future_to_model):
            model = future_to_model[future]
            try:
                results[model] = future.result()
            except Exception as exc:  # noqa: BLE001
                sys.stderr.write(f"Error querying model {model}: {exc}\n")
                results[model] = None
    # Preserve caller's model order for deterministic labelling.
    return {model: results.get(model) for model in models}


# --------------------------------------------------------------------------- #
# Council stages -- port of backend/council.py (prompts kept verbatim)
# --------------------------------------------------------------------------- #
def stage1_collect_responses(user_query, models, api_key):
    messages = [{"role": "user", "content": user_query}]
    responses = query_models_parallel(models, messages, api_key)
    results = []
    for model, response in responses.items():
        if response is not None:
            results.append({"model": model, "response": response.get("content", "")})
    return results


def stage2_collect_rankings(user_query, stage1_results, models, api_key):
    labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...
    label_to_model = {
        f"Response {label}": result["model"]
        for label, result in zip(labels, stage1_results)
    }

    responses_text = "\n\n".join(
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    )

    ranking_prompt = f"""You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

    messages = [{"role": "user", "content": ranking_prompt}]
    responses = query_models_parallel(models, messages, api_key)

    results = []
    for model, response in responses.items():
        if response is not None:
            full_text = response.get("content", "")
            results.append(
                {
                    "model": model,
                    "ranking": full_text,
                    "parsed_ranking": parse_ranking_from_text(full_text),
                }
            )
    return results, label_to_model


def stage3_synthesize_final(user_query, stage1_results, stage2_results,
                            chairman_model, api_key):
    stage1_text = "\n\n".join(
        f"Model: {result['model']}\nResponse: {result['response']}"
        for result in stage1_results
    )
    stage2_text = "\n\n".join(
        f"Model: {result['model']}\nRanking: {result['ranking']}"
        for result in stage2_results
    )

    chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their insights
- The peer rankings and what they reveal about response quality
- Any patterns of agreement or disagreement

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""

    messages = [{"role": "user", "content": chairman_prompt}]
    response = query_model(chairman_model, messages, api_key)
    if response is None:
        return {
            "model": chairman_model,
            "response": "Error: Unable to generate final synthesis.",
        }
    return {"model": chairman_model, "response": response.get("content", "")}


def parse_ranking_from_text(ranking_text):
    """Extract the FINAL RANKING section as an ordered list of response labels."""
    if "FINAL RANKING:" in ranking_text:
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            numbered_matches = re.findall(r"\d+\.\s*Response [A-Z]", ranking_section)
            if numbered_matches:
                return [
                    re.search(r"Response [A-Z]", m).group() for m in numbered_matches
                ]
            return re.findall(r"Response [A-Z]", ranking_section)
    return re.findall(r"Response [A-Z]", ranking_text)


def calculate_aggregate_rankings(stage2_results, label_to_model):
    """Average each model's rank position across all peer evaluations."""
    model_positions = defaultdict(list)
    for ranking in stage2_results:
        parsed_ranking = parse_ranking_from_text(ranking["ranking"])
        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                model_positions[label_to_model[label]].append(position)

    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            aggregate.append(
                {
                    "model": model,
                    "average_rank": round(sum(positions) / len(positions), 2),
                    "rankings_count": len(positions),
                }
            )
    aggregate.sort(key=lambda x: x["average_rank"])
    return aggregate


def run_full_council(user_query, models, chairman_model, api_key, stages=3,
                     progress=None):
    def note(msg):
        if progress:
            progress(msg)

    note(f"Stage 1: querying {len(models)} council members...")
    stage1_results = stage1_collect_responses(user_query, models, api_key)
    if not stage1_results:
        return {
            "stage1": [],
            "stage2": [],
            "stage3": {
                "model": "error",
                "response": "All models failed to respond. Please try again.",
            },
            "metadata": {},
        }
    note(f"Stage 1: {len(stage1_results)}/{len(models)} responded.")

    result = {"stage1": stage1_results, "stage2": [], "stage3": {}, "metadata": {}}
    if stages < 2:
        return result

    responding_models = [r["model"] for r in stage1_results]
    note("Stage 2: council members ranking anonymized responses...")
    stage2_results, label_to_model = stage2_collect_rankings(
        user_query, stage1_results, responding_models, api_key
    )
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
    result["stage2"] = stage2_results
    result["metadata"] = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings,
    }
    if stages < 3:
        return result

    note(f"Stage 3: Chairman ({chairman_model}) synthesizing final answer...")
    result["stage3"] = stage3_synthesize_final(
        user_query, stage1_results, stage2_results, chairman_model, api_key
    )
    return result


# --------------------------------------------------------------------------- #
# Pretty printing
# --------------------------------------------------------------------------- #
def _rule(char="="):
    return char * 72


def print_human(result, stages):
    stage1 = result["stage1"]
    print(_rule())
    print("STAGE 1 — First opinions")
    print(_rule())
    for res in stage1:
        print(f"\n### {res['model']}\n")
        print(res["response"].strip())
    if stages < 2:
        return

    print("\n" + _rule())
    print("STAGE 2 — Peer review (responses were anonymized when ranked)")
    print(_rule())
    label_to_model = result["metadata"].get("label_to_model", {})
    if label_to_model:
        print("\nLabel → model (revealed only after ranking):")
        for label, model in label_to_model.items():
            print(f"  {label} = {model}")
    for res in result["stage2"]:
        print(f"\n### {res['model']} evaluates the council\n")
        print(res["ranking"].strip())
        if res["parsed_ranking"]:
            print(f"\n  Extracted ranking: {' > '.join(res['parsed_ranking'])}")

    aggregate = result["metadata"].get("aggregate_rankings", [])
    if aggregate:
        print("\n" + _rule("-"))
        print("Aggregate ranking (lower average position is better):")
        print(_rule("-"))
        for i, entry in enumerate(aggregate, start=1):
            print(
                f"  {i}. {entry['model']}  "
                f"(avg {entry['average_rank']}, {entry['rankings_count']} votes)"
            )
    if stages < 3:
        return

    print("\n" + _rule())
    print("STAGE 3 — Final response from the Chairman")
    print(_rule())
    stage3 = result["stage3"]
    print(f"\nChairman: {stage3.get('model')}\n")
    print(stage3.get("response", "").strip())


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Convene an LLM Council (karpathy/llm-council) via OpenRouter.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("query", nargs="*", help="The question for the council.")
    parser.add_argument(
        "--models",
        help="Comma-separated OpenRouter model ids for the council "
        "(default: the karpathy defaults).",
    )
    parser.add_argument(
        "--chairman",
        default=DEFAULT_CHAIRMAN_MODEL,
        help=f"Chairman model id (default: {DEFAULT_CHAIRMAN_MODEL}).",
    )
    parser.add_argument(
        "--stage",
        type=int,
        choices=[1, 2, 3],
        default=3,
        help="Stop after stage 1, 2, or 3 (default: 3 = full council).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the full result as JSON instead of formatted text.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress messages on stderr.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])

    query = " ".join(args.query).strip()
    if not query:
        if not sys.stdin.isatty():
            query = sys.stdin.read().strip()
        if not query:
            sys.stderr.write("ERROR: no query provided.\n")
            sys.exit(2)

    load_env_file()
    api_key = get_api_key()

    models = (
        [m.strip() for m in args.models.split(",") if m.strip()]
        if args.models
        else list(DEFAULT_COUNCIL_MODELS)
    )
    if not models:
        sys.stderr.write("ERROR: no council models specified.\n")
        sys.exit(2)

    progress = None if args.quiet else lambda msg: sys.stderr.write(msg + "\n")

    result = run_full_council(
        query,
        models=models,
        chairman_model=args.chairman,
        api_key=api_key,
        stages=args.stage,
        progress=progress,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_human(result, args.stage)

    # Non-zero exit if the whole council failed.
    if not result["stage1"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
