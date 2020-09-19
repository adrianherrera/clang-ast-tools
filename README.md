# Clang AST Tools

A collection of Python scripts for working with the JSON format of Clang's
abstract syntax tree (AST).

Requires a [compilation database](https://clang.llvm.org/docs/JSONCompilationDatabase.html)
for generating the AST. I use [bear](https://github.com/rizsotto/Bear) to do
this for non-CMake projects.
