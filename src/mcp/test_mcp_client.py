
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


MCP_SERVER_URL = "http://127.0.0.1:8000/mcp"


async def main():

    print("Connecting to MCP Server...")

    async with streamablehttp_client(
        MCP_SERVER_URL
    ) as (read_stream, write_stream, _):

        async with ClientSession(
            read_stream,
            write_stream
        ) as session:

            # Initialize MCP connection
            await session.initialize()

            print("\nMCP connection successful!")

            # List available tools
            print("\n========== AVAILABLE MCP TOOLS ==========")

            tools = await session.list_tools()

            for tool in tools.tools:
                print(f"\nTool Name: {tool.name}")
                print(f"Description: {tool.description}")

            # Test storage recommendations
            print("\n========== STORAGE RECOMMENDATIONS ==========")

            result = await session.call_tool(
                "get_storage_recommendations",
                {
                    "workload": "random_read",
                    "top_n": 5
                }
            )

            for content in result.content:
                if hasattr(content, "text"):
                    print(content.text)

            # Test storage metrics
            print("\n========== STORAGE METRICS ==========")

            result = await session.call_tool(
                "get_storage_metrics",
                {}
            )

            for content in result.content:
                if hasattr(content, "text"):
                    print(content.text)

            # Test dataset catalog
            print("\n========== DATASET CATALOG ==========")

            result = await session.call_tool(
                "get_dataset_catalog",
                {}
            )

            for content in result.content:
                if hasattr(content, "text"):
                    print(content.text)


if __name__ == "__main__":
    asyncio.run(main())
