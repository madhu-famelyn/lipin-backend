"""
Utility functions for parallel LLM calls using AsyncOpenAI.
"""
import asyncio
from typing import Any
from config import async_client


async def parallel_llm_calls(tasks: list[dict]) -> list:
    """
    Execute multiple LLM calls in parallel using asyncio.gather.

    Args:
        tasks: List of dicts with OpenAI API parameters.
               Each dict should contain: model, messages, max_tokens, etc.

    Returns:
        List of OpenAI ChatCompletion responses in the same order as tasks.

    Example:
        tasks = [
            {"model": "gpt-4o-mini", "messages": [...], "max_tokens": 800},
            {"model": "gpt-4o-mini", "messages": [...], "max_tokens": 1500},
        ]
        results = await parallel_llm_calls(tasks)
    """
    async def make_call(task: dict) -> Any:
        return await async_client.chat.completions.create(**task)

    return await asyncio.gather(*[make_call(t) for t in tasks])


async def single_llm_call(
    messages: list[dict],
    model: str = "gpt-4o-mini",
    max_tokens: int = 800,
    temperature: float = 0.7,
    **kwargs
) -> Any:
    """
    Execute a single async LLM call.

    Args:
        messages: List of message dicts with role and content.
        model: OpenAI model to use.
        max_tokens: Maximum tokens in response.
        temperature: Sampling temperature.
        **kwargs: Additional OpenAI API parameters.

    Returns:
        OpenAI ChatCompletion response.
    """
    return await async_client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        **kwargs
    )
