"""Stage 2, factor mining (research only): candidate factors, research signals and the evaluators that test them.

Kept import-free on purpose: the subpackages import each other, and candidates/__init__ registers every
candidate factor once (register() raises on a duplicate). See CLAUDE.md in this folder."""
