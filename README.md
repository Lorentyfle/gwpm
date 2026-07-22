# gwpm — GeneralWorkPathManager

Build families of related file paths from a small set of reusable templates,
by substituting placeholder tokens with selected values — instead of
hand-writing `f"{base}/{struct}/{family}/{temp}K/..."` everywhere and
re-deriving the same folder logic in every script.

```python
from gwpm.path_manager import GeneralWorkPathManager

gwpm = GeneralWorkPathManager(
    list_of_variables=[
        ["Li2O", "Li2S"],
        ["300", "600", "900"],
    ],
    path="./simulations/?/!K/",
    replacer=["?", "!"],
)

gwpm.path_conversion({"?": 0, "!": 1})
# './simulations/Li2O/600K/'
```

## Why this exists

Simulation workflows tend to produce deep, structured directory trees —
one folder per structure, per temperature, per method — where the *shape*
of the tree is fixed but the *values* filling it change constantly across
scripts, reruns, and collaborators. Re-deriving that path logic by hand in
every analysis script is where most of the actual bugs come from: a typo
in a folder name, an off-by-one in which temperature a loop is on, a path
that works for one structure but silently breaks for another because its
folder naming was slightly different.

`gwpm` separates the **template** (fixed once you've decided your folder
layout) from the **selection** (what varies per call), and gives you one
consistent way to resolve either into a concrete path.

## Design principles

These four rules are the whole design. If a use case doesn't fit one of
them, that's a sign it needs a new primitive — not a workaround.

**Nothing is hidden.** Resolving a path requires stating a value for
every declared replacer, every time. There's no implicit "keep whatever
was selected last" — a partial selection is rejected rather than silently
reused. This is what makes a resolved path fully reproducible from the
call that produced it.

**Omission is explicit.** If a replacer should sometimes be absent from
the path entirely (rather than take one of its declared values), use the
manual entry point and pass `""` for that token. This removes the token
but does not clean up surrounding separators — a template using omission
should be written to tolerate that (e.g. avoid `"?/x"` if `?` might be
omitted; prefer a layout where omission doesn't leave a stray `/`).

**Depth is handled by nesting, not by branching the API.** A value can
itself contain another replacer token (`refractored=True`), resolved
recursively until none remain. Cyclic dependencies between replacers are
detected and rejected before resolution, rather than looping forever.

**Cross-variable dependency is handled by `ReferenceVariable`.** When one
variable's valid options depend on another variable's selected index
(e.g. which temperatures are valid depends on which structure was
chosen), that dependency is declared once, at construction time — call
sites never need to know about it.

## Selecting a path: positional or named

A selection can be a positional list (one entry per replacer, in
`replacer` order) or a dict keyed by replacer token:

```python
gwpm.path_conversion([0, 1])              # positional
gwpm.path_conversion({"?": 0, "!": 1})    # named — same result
```

Prefer the dict form in new code. It documents itself at the call site
and doesn't rely on remembering replacer order. The positional form
remains supported and isn't going away — it's what most existing
templates and scripts already use.

## Two usage patterns

**Loop cursor** — the common case. Declare the template once, then let a
loop vary the selection, reading the resolved path immediately before the
next iteration overwrites it:

```python
for i, temp in enumerate(temperatures):
    gwpm.path_conversion({"?": struct_idx, "!": i})
    df = read_series(gwpm.specific_path_file)
    ...
```

This works because each iteration is "select → consume → discard" before
moving to the next selection. Don't hold onto `gwpm.specific_path_file`
across iterations — it will have changed.

**Pre-built workspace** — when you want several resolved paths available
out of order, not consumed one at a time in a loop. Use `resolve()`,
which returns an immutable `ResolvedPath` instead of mutating the
manager:

```python
workspace = {
    temp: gwpm.resolve({"?": struct_idx, "!": i})
    for i, temp in enumerate(temperatures)
}
# later, in any order:
workspace[600].path_file
```

## Nested placeholders and dependent variables

A template value can itself contain a replacer token. In that case, one
substitution pass isn't enough — the token inside the substituted value
is left unresolved:

```python
gwpm = GeneralWorkPathManager(
    list_of_variables=[
        ["Li2O", "Li2S"],
        [300, 800, 900],
        ["!_?K_log.txt", "?K.xyz"],   # these entries contain ! and ?
    ],
    path="./data/!/",
    file="$",
    replacer=["!", "?", "$"],
)

gwpm.path_conversion({"!": 0, "?": 1, "$": 0}, refractored=False)
# './data/Li2O/!_?K_log.txt'   <- ! and ? inside the filename are still raw

gwpm.path_conversion({"!": 0, "?": 1, "$": 0}, refractored=True)
# './data/Li2O/Li2O_800K_log.txt'   <- resolved recursively until no token remains
```

`refractored=True` repeats substitution until no replacer token is left
in the result. Cyclic dependencies between replacers (A's value contains
B's token and vice versa) are detected and rejected before resolution
rather than looping forever.

When one variable's options depend on another's selection, declare it
with `ReferenceVariable`:

```python
from gwpm import ReferenceVariable

# Valid temperatures differ per structure (index 0 → Li2O, 1 → Li2S)
temperatures = ReferenceVariable(
    [
        ["300", "600", "900"],   # used when structure index == 0
        ["400", "800"],          # used when structure index == 1
    ],
    reference_position=0,  # "0" = position of the structure variable
)
```

## Omitting a replacer entirely

Use the manual entry point with an empty string:

```python
gwpm.path_manual_conversion({"?": "Li2O", "!": ""})
```

## Installation

```bash
pip install gwpm  # placeholder — update once packaged
```

## API reference

See docstrings on `GeneralWorkPathManager`, `PathResolver`, and
`ReferenceVariable` for full parameter and return documentation. This
README covers *why* and *how to use it*; the docstrings cover *exactly
what each call does*.

## Examples

Runnable examples for both usage patterns live in `examples/`:

- `examples/loop_cursor.py`
- `examples/prebuilt_workspace.py`
- `examples/nested_and_reference_variable.py`
