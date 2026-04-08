from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Protocol
from urllib import error as url_error
from urllib import request as url_request

from openai import OpenAI


# Required hackathon configuration variables
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4.1-mini")
HF_TOKEN = os.getenv("HF_TOKEN")

# Optional runtime variables for local/OpenEnv execution
ENV_API_BASE_URL = os.getenv("ENV_API_BASE_URL", "http://localhost:8000/api")
TASK_NAME_DEFAULT = os.getenv("TASK_NAME", "task_001")
BENCHMARK_DEFAULT = os.getenv("BENCHMARK", "openenv")
MAX_STEPS_DEFAULT = int(os.getenv("MAX_STEPS", "12"))
EPISODE_SEED_DEFAULT = int(os.getenv("EPISODE_SEED", "42"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
PROMPT_HTML_LIMIT = int(os.getenv("PROMPT_HTML_LIMIT", "5000"))
REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
USE_OPENENV_SDK = os.getenv("USE_OPENENV_SDK", "true").lower() in {"1", "true", "yes", "on"}


@dataclass
class StepOutcome:
    observation: dict[str, Any]
    reward: float
    terminated: bool
    truncated: bool
    info: dict[str, Any]

    @property
    def done(self) -> bool:
        return self.terminated or self.truncated


class EpisodeAdapter(Protocol):
    def reset(self, task_name: str, seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
        ...

    def step(self, action: dict[str, Any]) -> StepOutcome:
        ...

    def close(self) -> None:
        ...


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _reward_text(value: float) -> str:
    return f"{float(value):.2f}"


def _error_text(value: Any) -> str:
    if value is None:
        return "null"
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    return text if text else "null"


def _truncate(value: Any, limit: int = 500) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def _emit_start(task_name: str, benchmark: str, model_name: str) -> None:
    print(f"[START] task={task_name} env={benchmark} model={model_name}", flush=True)


def _emit_step(step_number: int, action: str, reward: float, done: bool, error_value: Any) -> None:
    print(
        f"[STEP] step={step_number} action={action} reward={_reward_text(reward)} "
        f"done={_bool_text(done)} error={_error_text(error_value)}",
        flush=True,
    )


def _emit_end(success: bool, steps: int, rewards: list[float]) -> None:
    rewards_text = ",".join(_reward_text(reward) for reward in rewards)
    print(f"[END] success={_bool_text(success)} steps={steps} rewards={rewards_text}", flush=True)


def _action_to_log_string(action: dict[str, Any]) -> str:
    action_type = str(action.get("action_type", "wait"))
    parameters = action.get("parameters")
    if not isinstance(parameters, dict):
        parameters = {}
    params_json = json.dumps(parameters, ensure_ascii=False, separators=(",", ":"))
    return f"{action_type}({params_json})"


def _strip_code_fences(text: str) -> str:
    content = text.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    return content


def _extract_json_object(text: str) -> dict[str, Any] | None:
    content = _strip_code_fences(text)
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or start > end:
        return None
    payload = content[start : end + 1]

    parsed: Any
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(payload)
        except (ValueError, SyntaxError):
            return None

    if isinstance(parsed, dict):
        return parsed
    return None


def _normalize_action(action: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]:
    action_type = str(action.get("action_type", "")).strip().lower()
    parameters = action.get("parameters")
    if not isinstance(parameters, dict):
        parameters = {}

    available_actions = observation.get("available_actions", [])
    allowed_action_types = {
        str(item.get("action_type")).lower()
        for item in available_actions
        if isinstance(item, dict) and item.get("action_type")
    }

    if not action_type:
        action_type = "wait"
    if allowed_action_types and action_type not in allowed_action_types:
        if "done" in allowed_action_types:
            action_type = "done"
            parameters = {"success": False, "message": "Selected unsupported action type"}
        else:
            action_type = sorted(allowed_action_types)[0]
            parameters = {}

    return {
        "action_type": action_type,
        "parameters": parameters,
        "reasoning": str(action.get("reasoning", "")),
    }


def _fallback_action(observation: dict[str, Any], step_number: int, max_steps: int) -> dict[str, Any]:
    fields_remaining = observation.get("fields_remaining")
    if isinstance(fields_remaining, list) and fields_remaining:
        return {
            "action_type": "extract_field",
            "parameters": {"field_name": str(fields_remaining[0])},
            "reasoning": "Fallback extraction for next required field.",
        }

    if step_number >= max_steps:
        return {
            "action_type": "done",
            "parameters": {"success": False, "message": "Max steps reached"},
            "reasoning": "Forced completion at step limit.",
        }

    return {
        "action_type": "done",
        "parameters": {"success": True, "message": "No fields remaining"},
        "reasoning": "Fallback completion.",
    }


def _build_llm_prompt(
    task_name: str,
    benchmark: str,
    observation: dict[str, Any],
    info: dict[str, Any],
    step_number: int,
    max_steps: int,
) -> str:
    task_context = observation.get("task_context", {})
    if not isinstance(task_context, dict):
        task_context = {}

    current_url = observation.get("current_url") or ""
    page_title = observation.get("page_title") or ""
    extraction_progress = float(observation.get("extraction_progress", 0.0) or 0.0)
    fields_remaining = observation.get("fields_remaining", [])
    if not isinstance(fields_remaining, list):
        fields_remaining = []

    available_actions = observation.get("available_actions", [])
    action_names: list[str] = []
    if isinstance(available_actions, list):
        for item in available_actions:
            if isinstance(item, dict) and item.get("action_type"):
                action_names.append(str(item["action_type"]))

    page_html = observation.get("page_html")
    if not isinstance(page_html, str) or not page_html:
        page_html = observation.get("page_text", "")
    if not isinstance(page_html, str):
        page_html = ""
    page_html = _truncate(page_html, PROMPT_HTML_LIMIT)

    return (
        "You are controlling a web-scraping RL agent.\n"
        "Return ONLY a single JSON object with keys: action_type, parameters, reasoning.\n"
        "Do not include markdown.\n\n"
        f"Benchmark: {benchmark}\n"
        f"Task: {task_name}\n"
        f"Step: {step_number}/{max_steps}\n"
        f"Current URL: {current_url}\n"
        f"Page Title: {page_title}\n"
        f"Extraction Progress: {extraction_progress:.2f}\n"
        f"Fields Remaining: {json.dumps(fields_remaining, ensure_ascii=False)}\n"
        f"Available Actions: {json.dumps(action_names, ensure_ascii=False)}\n"
        f"Task Context: {json.dumps(task_context, ensure_ascii=False)}\n"
        f"Info: {json.dumps(info, ensure_ascii=False)}\n\n"
        "Page Content (truncated):\n"
        f"{page_html}\n\n"
        "If extraction is complete, return action_type=\"done\" with completion parameters."
    )


def _llm_next_action(
    client: OpenAI,
    task_name: str,
    benchmark: str,
    observation: dict[str, Any],
    info: dict[str, Any],
    step_number: int,
    max_steps: int,
) -> dict[str, Any]:
    prompt = _build_llm_prompt(task_name, benchmark, observation, info, step_number, max_steps)

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are a precise action-planning assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=LLM_TEMPERATURE,
    )
    content = response.choices[0].message.content or ""
    parsed = _extract_json_object(content)
    if parsed is None:
        return _fallback_action(observation, step_number, max_steps)
    return _normalize_action(parsed, observation)


def _http_json(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = url_request.Request(url=url, data=data, headers=headers, method=method)

    try:
        with url_request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
    except url_error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {url}: {body}") from exc
    except url_error.URLError as exc:
        raise RuntimeError(f"Network error calling {url}: {exc}") from exc

    if not body:
        return {}
    parsed = json.loads(body)
    if isinstance(parsed, dict):
        return parsed
    raise RuntimeError(f"Expected JSON object from {url}")


class ScrapeRLEpisodeAdapter:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.episode_id: str | None = None

    def reset(self, task_name: str, seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
        payload = {"task_id": task_name, "seed": seed}
        response = _http_json("POST", f"{self.base_url}/episode/reset", payload)
        self.episode_id = str(response.get("episode_id", ""))
        observation = response.get("observation", {})
        info = response.get("info", {})
        if not isinstance(observation, dict):
            observation = {}
        if not isinstance(info, dict):
            info = {}
        return observation, info

    def step(self, action: dict[str, Any]) -> StepOutcome:
        if not self.episode_id:
            raise RuntimeError("Episode has not been reset")

        payload = {
            "episode_id": self.episode_id,
            "action": action,
        }
        response = _http_json("POST", f"{self.base_url}/episode/step", payload)
        observation = response.get("observation", {})
        if not isinstance(observation, dict):
            observation = {}
        info = response.get("info", {})
        if not isinstance(info, dict):
            info = {}

        return StepOutcome(
            observation=observation,
            reward=float(response.get("reward", 0.0) or 0.0),
            terminated=bool(response.get("terminated", False)),
            truncated=bool(response.get("truncated", False)),
            info=info,
        )

    def close(self) -> None:
        if not self.episode_id:
            return
        try:
            _http_json("DELETE", f"{self.base_url}/episode/{self.episode_id}")
        except RuntimeError:
            pass
        self.episode_id = None


class OpenEnvSDKAdapter:
    def __init__(self, benchmark: str) -> None:
        import openenv  # type: ignore

        if not hasattr(openenv, "make"):
            raise RuntimeError("openenv.make is not available")
        self.env = openenv.make(benchmark)

    def reset(self, task_name: str, seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
        reset_attempts = (
            {"task_name": task_name, "seed": seed},
            {"task": task_name, "seed": seed},
            {"task_id": task_name, "seed": seed},
            {},
        )
        last_error: Exception | None = None
        for kwargs in reset_attempts:
            try:
                result = self.env.reset(**kwargs)
                return self._parse_reset(result)
            except TypeError as exc:
                last_error = exc
                continue
        if last_error:
            raise last_error
        raise RuntimeError("Unable to reset OpenEnv environment")

    def step(self, action: dict[str, Any]) -> StepOutcome:
        try:
            result = self.env.step(action)
        except TypeError:
            result = self.env.step(action.get("action_type", "wait"))
        return self._parse_step(result)

    def close(self) -> None:
        if hasattr(self.env, "close"):
            self.env.close()

    @staticmethod
    def _parse_reset(result: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        if isinstance(result, tuple) and len(result) >= 2:
            observation = result[0] if isinstance(result[0], dict) else {}
            info = result[1] if isinstance(result[1], dict) else {}
            return observation, info
        if isinstance(result, dict):
            observation = result.get("observation", result)
            info = result.get("info", {})
            if not isinstance(observation, dict):
                observation = {}
            if not isinstance(info, dict):
                info = {}
            return observation, info
        return {}, {}

    @staticmethod
    def _parse_step(result: Any) -> StepOutcome:
        if isinstance(result, dict):
            observation = result.get("observation", {})
            if not isinstance(observation, dict):
                observation = {}
            info = result.get("info", {})
            if not isinstance(info, dict):
                info = {}
            terminated = bool(result.get("terminated", result.get("done", False)))
            truncated = bool(result.get("truncated", False))
            reward = float(result.get("reward", 0.0) or 0.0)
            return StepOutcome(observation=observation, reward=reward, terminated=terminated, truncated=truncated, info=info)

        if isinstance(result, tuple):
            if len(result) == 6:
                observation, reward, _breakdown, terminated, truncated, info = result
                return StepOutcome(
                    observation=observation if isinstance(observation, dict) else {},
                    reward=float(reward or 0.0),
                    terminated=bool(terminated),
                    truncated=bool(truncated),
                    info=info if isinstance(info, dict) else {},
                )
            if len(result) == 5:
                observation, reward, terminated, truncated, info = result
                return StepOutcome(
                    observation=observation if isinstance(observation, dict) else {},
                    reward=float(reward or 0.0),
                    terminated=bool(terminated),
                    truncated=bool(truncated),
                    info=info if isinstance(info, dict) else {},
                )
            if len(result) == 4:
                observation, reward, done, info = result
                return StepOutcome(
                    observation=observation if isinstance(observation, dict) else {},
                    reward=float(reward or 0.0),
                    terminated=bool(done),
                    truncated=False,
                    info=info if isinstance(info, dict) else {},
                )

        raise RuntimeError("Unsupported step() return format from OpenEnv SDK")


def _build_adapter(benchmark: str, env_api_base_url: str) -> EpisodeAdapter:
    if USE_OPENENV_SDK:
        try:
            return OpenEnvSDKAdapter(benchmark)
        except Exception:
            pass
    return ScrapeRLEpisodeAdapter(env_api_base_url)


def run_inference(task_name: str, benchmark: str, max_steps: int, seed: int, env_api_base_url: str) -> int:
    rewards: list[float] = []
    steps = 0
    success = False

    _emit_start(task_name=task_name, benchmark=benchmark, model_name=MODEL_NAME)

    adapter: EpisodeAdapter | None = None
    try:
        if HF_TOKEN is None:
            raise ValueError("HF_TOKEN environment variable is required")

        client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)
        adapter = _build_adapter(benchmark=benchmark, env_api_base_url=env_api_base_url)
        observation, info = adapter.reset(task_name=task_name, seed=seed)

        for step_number in range(1, max_steps + 1):
            action = _llm_next_action(
                client=client,
                task_name=task_name,
                benchmark=benchmark,
                observation=observation,
                info=info,
                step_number=step_number,
                max_steps=max_steps,
            )
            action_for_log = _action_to_log_string(action)
            outcome = adapter.step(action)

            steps = step_number
            rewards.append(outcome.reward)
            last_error = outcome.observation.get("last_action_error")
            _emit_step(
                step_number=step_number,
                action=action_for_log,
                reward=outcome.reward,
                done=outcome.done,
                error_value=last_error,
            )

            observation = outcome.observation
            info = outcome.info

            if outcome.done:
                success = bool(outcome.terminated and not outcome.truncated)
                break
    except Exception:
        success = False
    finally:
        if adapter is not None:
            try:
                adapter.close()
            except Exception:
                pass
        _emit_end(success=success, steps=steps, rewards=rewards)

    return 0 if success else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenEnv-compliant inference runner.")
    parser.add_argument("--task", default=TASK_NAME_DEFAULT, help="Task name/id")
    parser.add_argument("--benchmark", default=BENCHMARK_DEFAULT, help="Benchmark/environment name")
    parser.add_argument("--max-steps", type=int, default=MAX_STEPS_DEFAULT, help="Maximum step count")
    parser.add_argument("--seed", type=int, default=EPISODE_SEED_DEFAULT, help="Episode reset seed")
    parser.add_argument(
        "--env-api-base-url",
        default=ENV_API_BASE_URL,
        help="Fallback environment API base URL (used when OpenEnv SDK is unavailable)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    exit_code = run_inference(
        task_name=args.task,
        benchmark=args.benchmark,
        max_steps=args.max_steps,
        seed=args.seed,
        env_api_base_url=args.env_api_base_url,
    )
    sys.exit(exit_code)
