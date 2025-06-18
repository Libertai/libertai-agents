from abc import ABC, abstractmethod
from typing import Literal

from jinja2 import TemplateError

from libertai_agents.interfaces.messages import (
    Message,
    ToolCallFunction,
)
from libertai_agents.interfaces.tools import Tool

ModelId = Literal[
    "NousResearch/Hermes-3-Llama-3.1-8B",
    "unsloth/gemma-3-27b-it",
]


class Model(ABC):
    from transformers import PreTrainedTokenizerFast

    tokenizer: PreTrainedTokenizerFast
    model_id: ModelId
    context_length: int
    ltai_id: str

    def __init__(
        self,
        model_id: ModelId,
        context_length: int,
        ltai_id: str,
    ):
        """
        Creates a new instance of a model

        :param model_id: HuggingFace ID of the model
        :param context_length: Number of tokens allowed
        :param ltai_id: LibertAI ID of the model, used for pricing and other purposes
        """
        from transformers import AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model_id = model_id
        self.context_length = context_length
        self.ltai_id = ltai_id

    def __count_tokens(self, content: str) -> int:
        """
        Count the number of tokens used in a string prompt

        :param content: Prompt to count
        :return: Number of token used
        """
        tokens = self.tokenizer.tokenize(content)
        return len(tokens)

    def generate_prompt(
        self,
        messages: list[Message],
        tools: list[Tool],
        system_prompt: str | None = None,
    ) -> str:
        """
        Generate the whole chat prompt

        :param messages: Messages conversation history
        :param system_prompt: Prompt to include in the beginning
        :param tools: Available tools
        :return: Prompt string
        """
        system_messages = (
            [Message(role="system", content=system_prompt)]
            if system_prompt is not None
            else []
        )
        raw_messages = [x.model_dump() for x in messages]

        # Adding as many messages as we can fit into the context, starting from all of them and remove older ones if needed
        for i in range(len(raw_messages)):
            try:
                prompt = self.tokenizer.apply_chat_template(
                    conversation=system_messages + raw_messages[i:],
                    tools=[x.args_schema for x in tools] if len(tools) > 0 else None,
                    tokenize=False,
                    add_generation_prompt=True,
                )
            except TemplateError:
                # Some models (like mistralai/Mistral-Nemo-Instruct-2407) have strict templating restrictions,
                # removing messages can cause the conversation to start by an assistant message, which is forbidden.
                # If it happens we just continue to try with the next messages
                continue
            if not isinstance(prompt, str):
                raise TypeError("Generated prompt isn't a string")

            if self.__count_tokens(prompt) <= self.context_length:
                return prompt

        raise ValueError(
            f"Can't fit system message and the last message into the available context length ({self.context_length} tokens)"
        )

    def generate_tool_call_id(self) -> str | None:
        """
        Generate a random ID for a tool call

        :return: A string, or None if this model doesn't require a tool call ID
        """
        return None

    @staticmethod
    @abstractmethod
    def extract_tool_calls_from_response(response: str) -> list[ToolCallFunction]:
        """
        Extract tool calls (if any) from a given model response

        :param response: Model response to parse
        :return: List of found tool calls
        """
        pass
