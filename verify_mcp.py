
import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


MCP_URL = "http://127.0.0.1:8000/mcp"


def print_section(title):
    print("\n" + "=" * 65)
    print(title)
    print("=" * 65)


def parse_tool_result(result):
    """Extract JSON data returned by an MCP tool."""
    if result.isError:
        print("ERROR: MCP tool returned an error.")

    parsed_data = []

    for content in result.content:
        if hasattr(content, "text"):
            try:
                parsed_data.append(json.loads(content.text))
            except json.JSONDecodeError:
                print("Non-JSON response:")
                print(content.text[:3000])

    return parsed_data


async def main():

    print_section("CONNECTING TO MCP SERVER")
    print(f"MCP URL: {MCP_URL}")

    try:
        async with streamablehttp_client(MCP_URL) as (read, write, _):

            async with ClientSession(read, write) as session:

                await session.initialize()

                print("MCP connection successful.")

                # List available tools
                print_section("AVAILABLE MCP TOOLS")

                tools_response = await session.list_tools()

                for tool in tools_response.tools:
                    print(f"- {tool.name}")

                # Tools to verify
                tools_to_test = [
                    "get_storage_metrics",
                    "get_cost_agent_analysis"
                ]

                for tool_name in tools_to_test:

                    print_section(f"TESTING: {tool_name}")

                    try:
                        result = await session.call_tool(
                            tool_name,
                            {}
                        )

                        if result.isError:
                            print("Tool execution failed.")
                            for content in result.content:
                                if hasattr(content, "text"):
                                    print(content.text[:3000])
                            continue

                        parsed_results = parse_tool_result(result)

                        if not parsed_results:
                            print("No data returned by the tool.")
                            continue

                        for data in parsed_results:

                            if not isinstance(data, dict):
                                print(json.dumps(
                                    data,
                                    indent=2,
                                    ensure_ascii=False
                                )[:3000])
                                continue

                            print("Tool execution successful.")
                            print("Top-level keys:")
                            print(list(data.keys()))

                            # STORAGE METRICS
                            if tool_name == "get_storage_metrics":

                                print_section("STORAGE PERFORMANCE SUMMARY")

                                print(
                                    "Performance groups:",
                                    data.get("performance_group_count", "Not found")
                                )

                                print_section("STORAGE CAPACITY ANALYSIS")

                                capacity = data.get(
                                    "capacity_analysis",
                                    None
                                )

                                if capacity is None:
                                    print(
                                        "capacity_analysis NOT FOUND "
                                        "in the MCP response."
                                    )
                                else:
                                    print(json.dumps(
                                        capacity,
                                        indent=2,
                                        ensure_ascii=False
                                    )[:5000])

                                print_section("OTHER STORAGE DATA")

                                other_storage_keys = {
                                    key: value
                                    for key, value in data.items()
                                    if key != "capacity_analysis"
                                }

                                print(json.dumps(
                                    other_storage_keys,
                                    indent=2,
                                    ensure_ascii=False
                                )[:3000])

                            # CONSOLIDATED COST AGENT ANALYSIS
                            elif tool_name == "get_cost_agent_analysis":

                                print_section("CONSOLIDATED ANALYSIS")

                                print(
                                    "Report name:",
                                    data.get("report_name", "Not found")
                                )

                                print(
                                    "Report type:",
                                    data.get("report_type", "Not found")
                                )

                                print(
                                    "Total domains:",
                                    data.get("domain_count", 0)
                                )

                                print(
                                    "Successfully analyzed:",
                                    data.get(
                                        "successfully_analyzed_domains",
                                        0
                                    )
                                )

                                print_section("DOMAIN-WISE SUMMARY")

                                domains = data.get("domains", {})

                                if not domains:
                                    print("No domain data found.")
                                else:
                                    for domain_name, domain_data in domains.items():

                                        print(f"\nDOMAIN: {domain_name.upper()}")

                                        if isinstance(domain_data, dict):

                                            print(
                                                "Status:",
                                                domain_data.get(
                                                    "status",
                                                    "Not available"
                                                )
                                            )

                                            # Print useful summary fields
                                            for key, value in domain_data.items():

                                                if key in [
                                                    "status",
                                                    "candidate_sample",
                                                    "recommendation_sample",
                                                    "performance_summary"
                                                ]:
                                                    continue

                                                if isinstance(value, (str, int, float, bool)):
                                                    print(f"{key}: {value}")

                                            if "financial_policy" in data:
                                                print(
                                                    "\nFinancial policy:",
                                                    data["financial_policy"]
                                                )

                                print_section("END OF CONSOLIDATED ANALYSIS")

                    except Exception as tool_error:
                        print(f"Error testing {tool_name}: {tool_error}")

    except Exception as connection_error:
        print_section("MCP CONNECTION ERROR")
        print(connection_error)

        print("\nCheck that the MCP server is running:")
        print("python src/mcp/mcp_server.py")


if __name__ == "__main__":
    asyncio.run(main())
