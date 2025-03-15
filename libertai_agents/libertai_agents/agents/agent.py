import asyncio
import inspect
import json
import time
import weakref
from asyncio import Future
from http import HTTPStatus
from typing import Any, AsyncIterable, Awaitable, TypedDict

from aiohttp import ClientSession
from fastapi import APIRouter, FastAPI
from starlette.responses import StreamingResponse
from starlette.types import Lifespan

from libertai_agents.interfaces.llamacpp import (
    CustomizableLlamaCppParams,
    LlamaCppParams,
)
from libertai_agents.interfaces.messages import (
    Message,
    MessageToolCall,
    ToolCallFunction,
    ToolCallMessage,
    ToolResponseMessage,
)
from libertai_agents.interfaces.models import ModelInformation
from libertai_agents.interfaces.tools import Tool
from libertai_agents.models import Model
from libertai_agents.utils import find

MAX_TOOL_CALLS_DEPTH = 3


class AgentFastAPIParams(TypedDict, total=False):
    lifespan: Lifespan | None


class Agent:
    model: Model
    system_prompt: str | None
    tools: list[Tool]
    llamacpp_params: CustomizableLlamaCppParams
    app: FastAPI | None

    __session: ClientSession | None

    def __init__(
        self,
        model: Model,
        system_prompt: str | None = None,
        tools: list[Tool] | None = None,
        llamacpp_params: CustomizableLlamaCppParams = CustomizableLlamaCppParams(),
        expose_api: bool = True,
        fastapi_params: AgentFastAPIParams | None = None,
    ):
        """
        Create a LibertAI chatbot agent that can answer to messages from users

        :param model: The LLM you want to use, selected from the available ones
        :param system_prompt: Customize the behavior of the agent with your own prompt
        :param tools: List of functions that the agent can call. Each function must be asynchronous, have a docstring and return a stringifyable response
        :param llamacpp_params: Override params given to llamacpp when calling the model
        :param expose_api: Set at False to avoid exposing an API (useful if you are using a custom trigger)
        """
        if tools is None:
            tools = []

        if len({x.name for x in tools}) != len(tools):
            raise ValueError("Tool functions must have different names")
        self.model = model
        self.system_prompt = system_prompt
        self.tools = tools
        self.llamacpp_params = llamacpp_params
        self.__session = None

        weakref.finalize(
            self, self.__sync_cleanup
        )  # Ensures cleanup when object is deleted

        if expose_api:
            # Define API routes
            router = APIRouter()
            router.add_api_route(
                "/generate-answer",
                self.__api_generate_answer,
                methods=["POST"],
                summary="Generate Answer",
            )
            router.add_api_route("/model", self.get_model_information, methods=["GET"])

            self.app = FastAPI(title="LibertAI Agent", **(fastapi_params or {}))
            self.app.include_router(router)

    @property
    def session(self) -> ClientSession:
        if self.__session is None:
            self.__session = ClientSession()
        return self.__session

    def __repr__(self):
        return f"{self.__class__.__name__}(model={self.model.model_id})"

    async def __cleanup(self):
        if self.__session is not None and not self.__session.closed:
            await self.__session.close()

    def __sync_cleanup(self):
        """Schedules the async cleanup coroutine properly."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.__cleanup())
        except RuntimeError:
            # No running loop, run cleanup synchronously
            asyncio.run(self.__cleanup())

    def get_model_information(self) -> ModelInformation:
        """
        Get information about the model powering this agent
        """
        return ModelInformation(
            id=self.model.model_id, context_length=self.model.context_length
        )

    async def generate_answer(
        self,
        messages: list[Message],
        only_final_answer: bool = True,
        system_prompt: str | None = None,
    ) -> AsyncIterable[Message]:
        """
        Generate an answer based on a conversation

        :param messages: List of messages previously sent in this conversation
        :param only_final_answer: Only yields the final answer without including the thought process (tool calls and their response)
        :param system_prompt: Optional system prompt to customize the agent's behavior. If one was specified in the agent class instanciation, this will override it.
        :return: The string response of the agent
        """
        if len(messages) == 0:
            raise ValueError("No previous message to respond to")

        for _ in range(MAX_TOOL_CALLS_DEPTH):
            prompt = self.model.generate_prompt(
                messages, self.tools, system_prompt=system_prompt or self.system_prompt
            )

            response = await self.__call_model(prompt)

            if response is None:
                # TODO: handle error correctly
                raise ValueError("Model didn't respond")

            tool_calls = self.model.extract_tool_calls_from_response(response)
            if len(tool_calls) == 0:
                yield Message(role="assistant", content=response)
                return

            # Executing the detected tool calls
            tool_calls_message = self.__create_tool_calls_message(tool_calls)
            messages.append(tool_calls_message)
            if not only_final_answer:
                yield tool_calls_message

            executed_calls = self.__execute_tool_calls(tool_calls_message.tool_calls)
            results = await asyncio.gather(*executed_calls)
            tool_results_messages: list[Message] = [
                ToolResponseMessage(
                    role="tool",
                    name=call.function.name,
                    tool_call_id=call.id,
                    content=str(results[i]),
                )
                for i, call in enumerate(tool_calls_message.tool_calls)
            ]
            if not only_final_answer:
                for tool_result_message in tool_results_messages:
                    yield tool_result_message
            # Doing the next iteration of the loop with the results to make other tool calls or to answer
            messages = messages + tool_results_messages

    async def __api_generate_answer(
        self,
        messages: list[Message],
        stream: bool = False,
        only_final_answer: bool = True,
    ):
        """
        Generate an answer based on an existing conversation.
        The response messages can be streamed or sent in a single block.
        """

        if stream:
            return StreamingResponse(
                self.__dump_api_generate_streamed_answer(
                    messages, only_final_answer=only_final_answer
                ),
                media_type="text/event-stream",
            )

        response_messages: list[Message] = []
        async for message in self.generate_answer(
            messages, only_final_answer=only_final_answer
        ):
            response_messages.append(message)
        return response_messages

    async def __dump_api_generate_streamed_answer(
        self, messages: list[Message], only_final_answer: bool
    ) -> AsyncIterable[str]:
        """
        Dump to JSON the generate_answer iterable

        :param messages: Messages to pass to generate_answer
        :param only_final_answer: Param to pass to generate_answer
        :return: Iterable of each messages from generate_answer dumped to JSON
        """

        async for message in self.generate_answer(
            messages, only_final_answer=only_final_answer
        ):
            yield json.dumps(message.model_dump(), indent=4)

    async def __call_model(self, prompt: str) -> str | None:
        """
        Call the model with a given prompt

        :param prompt: Prompt to give to the model
        :return: String response (if no error)
        """
        params = LlamaCppParams(prompt=prompt, **self.llamacpp_params.model_dump())

        wait_between_retries = 0.1
        max_retries = 150
        # Looping until we get a satisfying response
        for _ in range(max_retries):
            async with self.session.post(
                self.model.vm_url, json=params.model_dump()
            ) as response:
                if response.status == HTTPStatus.OK:
                    response_data = await response.json()
                    return response_data["content"]
                elif response.status == HTTPStatus.SERVICE_UNAVAILABLE:
                    # Can happen sometimes, let's just wait a bit and retry
                    time.sleep(wait_between_retries)
                    continue
            # Other unexpected error
            return None

        # Max number of retries exceeded
        return None

    def __execute_tool_calls(
        self, tool_calls: list[MessageToolCall]
    ) -> list[Awaitable[Any]]:
        """
        Execute the given tool calls (without waiting for completion)

        :param tool_calls: Tool calls to run
        :return: List of tool calls responses to await
        """
        executed_calls: list[Awaitable[Any]] = []
        for call in tool_calls:
            function_name = call.function.name
            tool = find(lambda x: x.name == function_name, self.tools)
            if tool is None:
                future: Future = asyncio.Future()
                future.set_result(None)
                executed_calls.append(future)
                continue

            function_to_call = tool.function
            if inspect.iscoroutinefunction(function_to_call):
                # Call async function directly
                function_response = function_to_call(*call.function.arguments.values())
            else:
                # Wrap sync function in asyncio.to_thread to make it awaitable
                function_response = asyncio.to_thread(
                    function_to_call, **call.function.arguments
                )

            executed_calls.append(function_response)

        return executed_calls

    def __create_tool_calls_message(
        self, tool_calls: list[ToolCallFunction]
    ) -> ToolCallMessage:
        """
        Craft a tool call message

        :param tool_calls: Tool calls to include in the message
        :return: Crafted tool call message
        """
        return ToolCallMessage(
            role="assistant",
            tool_calls=[
                MessageToolCall(
                    type="function",
                    id=self.model.generate_tool_call_id(),
                    function=ToolCallFunction(name=call.name, arguments=call.arguments),
                )
                for call in tool_calls
            ],
        )
