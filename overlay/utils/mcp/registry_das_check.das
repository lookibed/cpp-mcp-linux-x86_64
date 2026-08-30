options gen2
options rtti

module registry_das_check

require protocol_core public
require tools/common public
require daslib/lint
require daslib/perf_lint
require daslib/style_lint
require daslib/lint_config
require daslib/ast_boost
require strings

def do_compile_check_inproc(file : string; project : string = "") : string {
    return compile_and_simulate(file, project) $(_program; issues) {
        var warnings = ""
        if (!empty(issues)) {
            warnings = "Warnings:\n{issues}\n"
        }
        return "{warnings}Compilation OK."
    }
}

def do_lint_inproc(file : string; project : string = "") : string {
    var disabled_codes : table<string>
    let enabled_codes : table<string>
    seed_default_disabled(disabled_codes)
    load_lint_config(disabled_codes)
    return compile_only(file, true, true, project, true) $(program; _issues) {
        var all_issues : array<string>
        var count = paranoid_collect(program, all_issues, disabled_codes, enabled_codes)
        var perf_issues : array<string>
        count += perf_lint_collect(program, perf_issues, disabled_codes, enabled_codes)
        all_issues |> push_from(perf_issues)
        var style_issues : array<string>
        count += style_lint_collect(program, style_issues, disabled_codes, enabled_codes, false)
        all_issues |> push_from(style_issues)
        if (count == 0) {
            return "No lint issues."
        }
        return build_string() $(var w) {
            w |> write("{count} lint issue(s):\n")
            write_deduped(w, all_issues)
        }
    }
}

def build_das_check_tools(var reg : array<ToolDef>) {
    reg |> emplace(ToolDef(
        tool <- make_tool(
            "compile_check",
            "Compile a daslang file in-process and return compiler diagnostics or success.",
            {
                "file" => PropertySchema(_type = "string", description = "Path to a .das file"),
                "project" => PROJECT_PROP
            },
            ["file"]),
        required <- ["file"],
        arg_names <- ["file"],
        handler = @@(arg1, arg2, arg3, arg4, arg5, arg6, project, project_root : string; load_modules : array<string>) => do_compile_check_inproc(arg1, project)))

    reg |> emplace(ToolDef(
        tool <- make_tool(
            "lint",
            "Compile and run daslang lint/performance/style checks in-process.",
            {
                "file" => PropertySchema(_type = "string", description = "Path to a .das file"),
                "project" => PROJECT_PROP
            },
            ["file"]),
        required <- ["file"],
        arg_names <- ["file"],
        handler = @@(arg1, arg2, arg3, arg4, arg5, arg6, project, project_root : string; load_modules : array<string>) => do_lint_inproc(arg1, project)))
}
