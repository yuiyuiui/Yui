"""The source boundary for Lean code supplied to the checked proof pipeline."""
import re


KERNEL_PRIMITIVES = re.compile(
    r"\b(?:skipKernelTC|addDeclCore|addDeclWithoutChecking|lean_(?:elab_)?add_decl_without_checking)\b")
EXECUTABLE_HOOKS = re.compile(
    r"(?:\b(?:run_cmd|run_elab|run_meta|run_tac|elab|elab_rules|macro|macro_rules|initialize|builtin_initialize)\b"
    r"|#eval\b|@\[\s*(?:command_elab|term_elab|tactic|implemented_by|extern)\b)")
UNPROVED = re.compile(r"(?<![\w'.])(?:sorry|admit|axiom)(?![\w'])")


def check(source, *, authored=True):
    from lean_imports import code_tokens
    if not isinstance(source,str) or not source.strip():
        raise ValueError('Empty Lean source')
    code = code_tokens(source,preserve_interpolation=True,preserve_quoted_names=True)
    if match := KERNEL_PRIMITIVES.search(code):
        raise ValueError('Lean kernel checking must remain enabled: '+match[0])
    code=re.sub(r'«[^»]*»',' ',code)
    if authored and (match := EXECUTABLE_HOOKS.search(code)):
        raise ValueError('Executable Lean hook can alter the checked environment: '+match[0])
    return code


def check_proof(source, *, authored=True):
    code = check(source,authored=authored)
    if UNPROVED.search(code):
        raise ValueError('forbidden proof placeholder or unchecked axiom')
    return code
