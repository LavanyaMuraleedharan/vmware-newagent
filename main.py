
from azure.ai.agentserver.responses import (
    CreateResponse,
    ResponseContext,
    ResponsesAgentServerHost,
    TextResponse,
)

from src.agents.supervisor_agent import run_supervisor_agent

app = ResponsesAgentServerHost()


@app.response_handler
async def handler(request, context, cancellation_signal):

    user_input = await context.get_input_text() or ""

    if not user_input.strip():
        result = "Please provide a VMware infrastructure optimization request."

    else:
        try:
            print("Starting VMware multi-agent workflow...")

            workflow_result = await run_supervisor_agent(user_input)

            result = workflow_result.get(
                "markdown_report",
                workflow_result.get("final_response", "Workflow completed.")
            )

        except Exception as error:
            print(f"Workflow failed: {error}")

            result = (
                "The VMware optimization workflow could not complete. "
                f"Error: {type(error).__name__}: {error}. "
                "Please check the hosted agent logs."
            )

    return TextResponse(
        context,
        request,
        text=result,
    )


if __name__ == "__main__":
    app.run()
