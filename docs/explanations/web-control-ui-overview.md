# Web control UI overview

The web control provides a fully interactive environment for designing,
configuring and managing PandA block connections.

## Components

The interface has four core components whose content changes dynamically
depending on the current activity:

```{figure} ../images/webcontrol/ui_schematic.png
:align: center

Web control UI components
```

| Component | Description |
|---|---|
| **Navigation bar** | Breadcrumb trail showing your current position within the Design, starting from the selected {term}`Root Block`.  Use it to move between nested levels. |
| **Left-hand panel** | Information about the {term}`Parent Block` currently in focus. |
| **Central panel** | Details of the selected {term}`Attribute` or the {term}`Layout` view if **Layout** is selected. |
| **Right-hand panel** | Detailed information about the {term}`Block`, {term}`Attribute` or {term}`Link` currently in focus. |

:::{tip}
- A Block is *always* displayed in the left-hand panel (Parent or Child).
- Attribute metadata is always shown in the right-hand panel.
- Link information is always shown in the right-hand panel.
:::

## Views

### Layout view

The Layout view lets you create, modify and manage the overall {term}`Design`.
Open it by clicking **View** or **Edit** next to the *Layout* attribute on any
Parent Block.

```{figure} ../images/webcontrol/PANDA-layout-spread-out.png
:align: center

Example Layout view — PANDA system with CLOCKS block selected
```

In this view:

- Drag blocks to rearrange them; links are re-routed automatically.
- Click **Auto Layout** in the central panel to optimise the arrangement.
- Click a block to load its details in the right-hand panel.

### Attribute view

The interface transitions to Attribute view when you select an attribute from
either panel:

- Selecting from the **left-hand panel** shows more detail about that attribute
  in the right-hand panel.
- Selecting from the **right-hand panel** moves the corresponding block to the
  left-hand panel as the new focus.

The **central panel** shows the attribute's value over time as either:

- **Plot** — an interactive line chart (pan, zoom, export).  See
  [](../how-to/monitor-attribute-values.md) for chart controls.
- **Table** — a time-ordered list of value changes.

```{figure} ../images/webcontrol/attribute_view_chart.png
:align: center

Attribute view — example plot for a continuously updated attribute
```

:::{note}
In Attribute view the left-hand panel shows the selected block (e.g. "Input
Encoder 1"), not the top-level Parent Block.
:::

## Panel popping

In complex designs you may want to monitor several blocks at once.  Click the
pop icon in the top-left corner of any Block Information Panel to open it in
its own independent window.  Multiple panels can be popped simultaneously.

```{figure} ../images/webcontrol/window_popping_output.svg
:align: center

Three Child Blocks (CLOCKS, COUNTER1, BITS) popped into independent windows
alongside the PANDA Layout
```

Each independent window stays live — attribute updates are reflected in real
time, and any edits you make are sent back to the PandA just as they would be
from the integrated panel.
