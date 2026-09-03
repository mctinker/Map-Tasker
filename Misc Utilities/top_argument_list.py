import ast
import os


def count_function_arguments(file_path: str) -> list:
    """Parse a Python file and return function names with their argument counts."""
    try:
        with open(file_path, encoding="utf-8") as file:
            content = file.read()

        tree = ast.parse(content, filename=file_path)
        functions = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                # Count all types of arguments
                args = node.args
                total_args = (
                    len(args.args)  # regular args
                    + len(args.posonlyargs)  # positional-only args
                    + len(args.kwonlyargs)  # keyword-only args
                    + (1 if args.vararg else 0)  # *args
                    + (1 if args.kwarg else 0)  # **kwargs
                )

                functions.append(
                    {
                        "name": node.name,
                        "args": total_args,
                        "file": os.path.relpath(file_path),
                        "line": node.lineno,
                    },
                )

        return functions  # noqa: TRY300
    except Exception as e:  # noqa: BLE001
        print(f"Error parsing {file_path}: {e}")
        return []


def analyze_directory(root_dir: str) -> list:
    """Analyze all Python files in a directory and return function argument counts."""
    all_functions = []

    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                functions = count_function_arguments(file_path)
                all_functions.extend(functions)

    # Sort by argument count (descending) and then by name for consistency
    all_functions.sort(key=lambda x: (-x["args"], x["name"]))

    return all_functions


if __name__ == "__main__":
    # Analyze the src directory
    src_dir = "./maptasker/src"

    if not os.path.exists(src_dir):
        print(f"Directory {src_dir} not found!")
        exit(1)  # noqa: PLR1722

    print("Analyzing Python code in src directory...")
    functions = analyze_directory(src_dir)

    print("\nTop 10 Functions with Most Arguments:")
    print("=" * 60)

    for i, func in enumerate(functions[:20], 1):
        print(
            f"{i:2d}. {func['name']:<30} ({func['args']} args) - {func['file']}:{func['line']}",
        )

    if len(functions) > 10:
        print(f"\nTotal functions analyzed: {len(functions)}")
