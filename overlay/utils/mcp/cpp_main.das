options gen2
options persistent_heap
options gc
options multiple_contexts
options rtti

require protocol_core public
require registry_das_check public
require registry_cpp public

[export]
def main() {
    logger_init("mcp_das_check_server")
    logger_info("mcp", "Starting minimal daslang check MCP server (stdio transport)")

    let sg_check = detect_ast_grep()
    if (!empty(sg_check)) {
        ast_grep_available = true
    }

    var reg : array<ToolDef>
    build_das_check_tools(reg)
    build_cpp_tools(reg)
    register_shutdown(reg)
    serve_stdio(reg)
}
