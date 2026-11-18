
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_URL = "http://127.0.0.1:8000/mcp"

async def main():

    async with streamablehttp_client(MCP_URL) as (
        read_stream,
        write_stream,
        _
    ):
        async with ClientSession(
            read_stream,
            write_stream
        ) as session:

            await session.initialize()

            tools = await session.list_tools()

            print("\nAVAILABLE MCP TOOLS")
            print("===================")

            for tool in tools.tools:
                print("-", tool.name)

            tests = [
                ("get_vmware_metrics", {"top_n": 3}),
                ("get_storage_domain_data", {}),
                ("get_backup_metrics", {"top_n": 3}),
                ("get_compute_gpu_metrics", {"top_n": 3}),
                ("get_database_metrics", {"top_n": 3}),
                ("get_licensing_metrics", {"top_n": 3})
            ]

            for tool_name, arguments in tests:

                print(f"\n\nTESTING: {tool_name}")
                print("=" * 60)

                result = await session.call_tool(
                    tool_name,
                    arguments
                )

                for item in result.content:
                    if hasattr(item, "text"):
                        print(item.text[:2500])

                if result.isError:
                    print("TOOL RETURNED AN ERROR")

if __name__ == "__main__":
    asyncio.run(main())
